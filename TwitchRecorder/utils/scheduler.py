import time
import threading
from datetime import datetime

from utils.config import load_config, parse_duration, get_channels_with_platform
from utils.logger import log
from utils.recorder import Recorder


def is_scheduled_day(config: dict) -> bool:
    today = datetime.now().strftime("%A")
    return today in config.get("days", [])


def is_after_start_time(config: dict) -> bool:
    now = datetime.now()
    start = config.get("start_time", "19:55")
    h, m = map(int, start.split(":"))
    return now.hour * 60 + now.minute >= h * 60 + m


def _seconds_until_start(config: dict) -> int:
    now = datetime.now()
    start = config.get("start_time", "19:55")
    h, m = map(int, start.split(":"))
    start_minutes = h * 60 + m
    now_minutes = now.hour * 60 + now.minute
    diff = start_minutes - now_minutes
    if diff <= 0:
        return 0
    return diff * 60


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
    log.info(f"Canales: {[ch for ch, _ in channels_with_platform]}")
    log.info(f"Comprobando cada {check_interval}s")
    if dry_run:
        log.info("Modo DRY-RUN activo")

    if not is_scheduled_day(config):
        log.info("Hoy no es día programado. Saliendo.")
        return

    if not is_after_start_time(config):
        remaining = _seconds_until_start(config)
        mins, secs = divmod(remaining, 60)
        log.info(f"Aún no es hora de inicio. Esperando {mins}m {secs:02d}s para start_time...")
        while not is_after_start_time(config):
            time.sleep(10)
            remaining = _seconds_until_start(config)
            if remaining > 0 and remaining % 60 < 10:
                mins, secs = divmod(remaining, 60)
                log.info(f"Esperando {mins}m {secs:02d}s...")
        log.info("Hora de inicio alcanzada")

    recorders = {}
    for channel, platform_name in channels_with_platform:
        recorders[channel] = Recorder(channel, platform_name, record_path, max_duration, max_duration_str, retry_interval, copy_to_test, test_path)

    current_day = _get_today()

    while is_scheduled_day(config):
        today = _get_today()
        if today != current_day:
            log.info("Nuevo día detectado, reiniciando grabadores...")
            for recorder in recorders.values():
                if not recorder.is_recording:
                    recorder.finished = False
            current_day = today

        config = load_config()
        new_channels_with_platform = get_channels_with_platform(config)
        for channel, platform_name in new_channels_with_platform:
            if channel not in recorders:
                log.info(f"[{channel}] Nuevo canal detectado ({platform_name}), añadiendo...")
                recorders[channel] = Recorder(channel, platform_name, record_path, max_duration, max_duration_str, retry_interval, copy_to_test, test_path)

        all_offline = True

        for channel, recorder in recorders.items():
            if recorder.is_recording or recorder.finished:
                all_offline = False
                continue

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

        if not is_scheduled_day(config):
            break

    for recorder in recorders.values():
        if recorder.is_recording:
            recorder.stop()

    log.info("=== TwitchRecorder finalizado ===")
