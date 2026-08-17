import time
import threading
from datetime import datetime

from utils.config import load_config, parse_duration, get_channels_with_platform
from utils.logger import log
from utils.recorder import Recorder


def _parse_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def is_after_time(t: str) -> bool:
    now = datetime.now()
    return now.hour * 60 + now.minute >= _parse_minutes(t)


def _seconds_until_time(t: str) -> int:
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute
    diff = _parse_minutes(t) - now_minutes
    if diff <= 0:
        return 0
    return diff * 60


ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _dias_para(extra: dict, config: dict) -> list:
    dias = extra.get("days") or config.get("days")
    if isinstance(dias, str):
        dias = [dias]
    # Si no se indica nada, se entiende que emite todos los días.
    return list(dias) if dias else ALL_DAYS


def _hora_inicio_para(extra: dict, config: dict, day: str) -> str:
    st = extra.get("start_time") or config.get("start_time", "19:55")
    if isinstance(st, dict):
        return st.get(day) or st.get("*") or config.get("start_time", "19:55")
    return st


def _programados_hoy(config: dict, channels: list) -> dict:
    """Devuelve {canal: {start_time, extra}} de los canales con emisión hoy."""
    today = datetime.now().strftime("%A")
    out = {}
    for channel, platform_name, url, extra in channels:
        if today not in _dias_para(extra, config):
            continue
        out[channel] = {
            "start_time": _hora_inicio_para(extra, config, today),
            "extra": extra,
        }
    return out


def _get_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def run_scheduler(dry_run: bool = False):
    config = load_config()
    channels_with_platform = get_channels_with_platform(config)
    check_interval = config.get("check_every", 30)
    record_path = config.get("record_path", "")
    max_duration_str = config.get("max_duration", "24:00:00")
    max_duration = parse_duration(max_duration_str)
    retry_interval = config.get("retry_interval", 60)
    copy_to_test = config.get("copy_to_test", False)
    test_path = config.get("test_path", "")

    log.info("=== TwitchRecorder iniciado ===")
    log.info(f"Canales: {[ch for ch, _, _, _ in channels_with_platform]}")
    log.info(f"Comprobando cada {check_interval}s")
    if dry_run:
        log.info("Modo DRY-RUN activo")

    recorders = {}
    for channel, platform_name, url, extra in channels_with_platform:
        recorders[channel] = Recorder(channel, platform_name, url, record_path, max_duration, max_duration_str, retry_interval, copy_to_test, test_path)

    # Esperar a la hora de inicio más temprana de los canales de hoy
    progs = _programados_hoy(config, channels_with_platform)
    if not progs:
        log.info("Hoy no hay canales programados. Saliendo.")
        return
    earliest = min(p["start_time"] for p in progs.values())
    if not is_after_time(earliest):
        remaining = _seconds_until_time(earliest)
        mins, secs = divmod(remaining, 60)
        log.info(f"Hoy: {progs}")
        log.info(f"Aún no es hora de inicio (primera emisión a las {earliest}). Esperando {mins}m {secs:02d}s...")
        while not is_after_time(earliest):
            time.sleep(10)
            remaining = _seconds_until_time(earliest)
            if remaining > 0 and remaining % 60 < 10:
                mins, secs = divmod(remaining, 60)
                log.info(f"Esperando {mins}m {secs:02d}s...")
        log.info("Hora de inicio alcanzada")

    current_day = _get_today()

    while True:
        today = _get_today()
        if today != current_day:
            log.info("Nuevo día detectado, reiniciando grabadores...")
            for recorder in recorders.values():
                if not recorder.is_recording:
                    recorder.finished = False
            current_day = today

        config = load_config()
        new_channels_with_platform = get_channels_with_platform(config)
        for channel, platform_name, url, extra in new_channels_with_platform:
            if channel not in recorders:
                log.info(f"[{channel}] Nuevo canal detectado ({platform_name}), añadiendo...")
                recorders[channel] = Recorder(channel, platform_name, url, record_path, max_duration, max_duration_str, retry_interval, copy_to_test, test_path, extra.get("dias_plataforma"))
        channels_with_platform = new_channels_with_platform

        progs = _programados_hoy(config, channels_with_platform)
        if not progs:
            log.info("Ningún canal programado para hoy. Esperando al próximo día...")
            time.sleep(check_interval)
            continue

        all_offline = True

        for channel, recorder in recorders.items():
            if recorder.is_recording or recorder.finished:
                all_offline = False
                continue

            prog = progs.get(channel)
            if not prog:
                continue  # no programado hoy

            if not is_after_time(prog["start_time"]):
                continue  # aún no es su hora de inicio

            if recorder.is_live():
                all_offline = False
                log.info(f"[{channel}] ¡Directo detectado! ({recorder.platform_name})")
                if dry_run:
                    log.info(f"[{channel}] DRY-RUN: grabaría aquí")
                else:
                    keyword = recorder.get_live_keyword()
                    if keyword:
                        log.info(f"[{channel}] Keyword del directo: {keyword}")
                    if recorder.start(keyword):
                        monitor_thread = threading.Thread(
                            target=recorder.monitor,
                            daemon=True
                        )
                        monitor_thread.start()

        if all_offline and not any(r.is_recording for r in recorders.values()):
            log.info("Todos los canales offline. Esperando...")

        time.sleep(check_interval)

    for recorder in recorders.values():
        if recorder.is_recording:
            recorder.stop()

    log.info("=== TwitchRecorder finalizado ===")
