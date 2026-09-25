import time
import threading
import signal
import sys
from datetime import datetime

from utils.config import get_channels_with_platform, load_config, parse_duration
from utils.logger import log
from utils.recorder import Recorder

running = True


def signal_handler(sig, frame):
    """Handler de SIGTERM/SIGINT: pone `running=False` para que el bucle
    principal detenga todos los grabadores y salga limpio."""
    global running
    log.info("=== Señal SIGTERM recibida, apagando scheduler ===")
    running = False


def _parse_minutes(t: str) -> int:
    """Convierte 'HH:MM' a minutos totales."""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def is_after_time(t: str) -> bool:
    """¿Ya pasó la hora 'HH:MM' de hoy? (comparando minutos desde medianoche)."""
    now = datetime.now()
    return now.hour * 60 + now.minute >= _parse_minutes(t)


def _seconds_until_time(t: str) -> int:
    """Segundos que faltan hasta la hora 'HH:MM' de hoy (0 si ya pasó)."""
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute
    diff = _parse_minutes(t) - now_minutes
    if diff <= 0:
        return 0
    return diff * 60


ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _build_schedule_from_legacy(extra: dict, config: dict) -> list:
    """Convierte config legacy (days, start_time, dias_plataforma) a schedule unificado.
    
    Formato legacy:
      - days: ["Monday", ...] o "Monday" o global config.days
      - start_time: "HH:MM" o {"Monday": "19:00", "*": "21:30"} o global
      - dias_plataforma: {"*": ["web"], "Sunday": ["youtube", "web"]} o global
    
    Devuelve lista de reglas: [{"days": [...], "time": "HH:MM", "platforms": [...]}]
    """
    schedule = []
    
    # Helper para obtener dias_plataforma de forma segura
    def _get_dias_plataforma():
        dp = extra.get("dias_plataforma")
        if dp is None:
            dp = config.get("dias_plataforma")
        return dp if isinstance(dp, dict) else {}
    
    dias_plataforma = _get_dias_plataforma()
    
    # 1. Obtener días (canal > global > todos)
    dias = extra.get("days") or config.get("days") or ALL_DAYS
    if isinstance(dias, str):
        dias = [dias]
    dias = [d.capitalize() for d in dias]
    
    # 2. Obtener start_time (canal > global)
    st = extra.get("start_time") or config.get("start_time", "19:55")
    if isinstance(st, dict):
        # start_time por día: convertir cada entrada a regla
        for day, time_str in st.items():
            if day == "*":
                continue  # lo manejamos al final como fallback
            if day.capitalize() in ALL_DAYS:
                schedule.append({
                    "days": [day.capitalize()],
                    "time": time_str,
                    "platforms": dias_plataforma.get(day.capitalize(), dias_plataforma.get("*", ["web"]))
                })
        # Fallback "*"
        if "*" in st:
            schedule.append({
                "days": ALL_DAYS,
                "time": st["*"],
                "platforms": dias_plataforma.get("*", ["web"])
            })
    else:
        # start_time único para todos los días
        schedule.append({
            "days": dias,
            "time": st,
            "platforms": dias_plataforma.get("*", ["web"])
        })
    
    # Si no hay schedule (sin start_time), crear uno por defecto
    if not schedule:
        schedule.append({
            "days": dias,
            "time": "19:55",
            "platforms": dias_plataforma.get("*", ["web"])
        })
    
    return schedule


def _get_channel_schedule(extra: dict, config: dict) -> list:
    """Obtiene el schedule del canal.
    
    Prioridad:
    1. Si hay 'schedule' a nivel canal (legacy) -> usa ese
    2. Si hay 'schedule' en cada platform -> construye schedule combinado
    3. Si hay legacy (days/start_time/dias_plataforma) -> construye desde legacy
    4. Default
    """
    # 1. Schedule legacy a nivel canal
    if "schedule" in extra:
        return extra["schedule"]
    
    # 2. Schedule por platform (nuevo formato)
    platforms = extra.get("platform", [])
    if isinstance(platforms, list):
        combined = []
        for p in platforms:
            if isinstance(p, dict) and "schedule" in p:
                for rule in p.get("schedule", []):
                    # Añadir platform a la regla si no está
                    rule_with_platform = dict(rule)
                    rule_with_platform["platforms"] = [p.get("platform", "web")]
                    combined.append(rule_with_platform)
        if combined:
            return combined
    
    # 3. Legacy (days/start_time/dias_plataforma)
    return _build_schedule_from_legacy(extra, config)


def _get_platforms_for_now(extra: dict, config: dict, now: datetime = None) -> list:
    """Devuelve lista de plataformas a probar ahora mismo, en orden de prioridad.
    
    Para cada platform, verifica su schedule. Si coincide (día + hora),
    se añade a la lista. Orden = orden en config.platform.
    """
    if now is None:
        now = datetime.now()
    today = now.strftime("%A")
    current_minutes = now.hour * 60 + now.minute
    
    # Primero intentar schedule por platform
    platforms = extra.get("platform", [])
    if isinstance(platforms, list):
        matched = []
        for p in platforms:
            if not isinstance(p, dict):
                continue
            platform_name = p.get("platform")
            if not platform_name:
                continue
            for rule in p.get("schedule", []):
                rule_days = rule.get("days", [])
                rule_time = rule.get("time", "00:00")
                
                if today in rule_days:
                    try:
                        rule_h, rule_m = map(int, rule["time"].split(":"))
                        rule_minutes = rule_h * 60 + rule_m
                    except Exception:
                        continue
                    if current_minutes >= rule_minutes:
                        matched.append(platform_name)
                        break  # una regla que coincida por platform es suficiente
        if matched:
            return matched
    
    # Fallback: schedule legacy a nivel canal
    schedule = _get_channel_schedule(extra, {})
    current_minutes = now.hour * 60 + now.minute
    today = now.strftime("%A")
    
    for rule in schedule:
        rule_days = rule.get("days", [])
        rule_time = rule.get("time", "00:00")
        rule_platforms = rule.get("platforms", ["web"])
        
        if today in rule_days:
            try:
                rule_h, rule_m = map(int, rule["time"].split(":"))
                rule_minutes = rule_h * 60 + rule_m
            except Exception:
                continue
            if current_minutes >= rule_minutes:
                return rule_platforms
    return []


def _dias_para(extra: dict, config: dict) -> list:
    """Días de emisión de un canal: unión de todos los días de todos los schedules."""
    # Primero platform-level
    platforms = extra.get("platform", [])
    if isinstance(platforms, list):
        days_set = set()
        for p in platforms:
            if isinstance(p, dict):
                for rule in p.get("schedule", []):
                    days_set.update(rule.get("days", []))
        if days_set:
            return list(days_set)
    
    # Fallback legacy
    schedule = _get_channel_schedule(extra, {})
    days_set = set()
    for rule in schedule:
        days_set.update(rule.get("days", []))
    if days_set:
        return list(days_set)
    
    # Fallback legacy
    dias = extra.get("days") or config.get("days")
    if isinstance(dias, str):
        dias = [dias]
    if not dias:
        return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return [d.capitalize() for d in dias]


def _hora_inicio_para(extra: dict, config: dict, day: str) -> str:
    """Hora de inicio del canal ese día: la primera regla que coincida con ese día."""
    schedule = _get_channel_schedule(extra, config)
    for rule in schedule:
        if day in rule.get("days", []):
            return rule.get("time", "19:55")
    # Fallback legacy
    st = extra.get("start_time") or config.get("start_time", "19:55")
    if isinstance(st, dict):
        return st.get(day) or st.get("*") or "19:55"
    return st


def _programados_hoy(config: dict, channels: list) -> dict:
    """Devuelve {canal: {start_time, extra}} de los canales con emisión hoy."""
    now = datetime.now()
    today = now.strftime("%A")
    out = {}
    for channel, platform_name, url, extra in channels:
        # Verificar si el canal tiene emisión hoy usando schedule unificado
        platforms = _get_platforms_for_now(extra, config, now)
        if not platforms:
            continue
        # Obtener la hora de inicio más temprana hoy
        schedule = _get_channel_schedule(extra, config)
        earliest = None
        for rule in schedule:
            if today in rule.get("days", []):
                t = rule.get("time")
                if t and (earliest is None or t < earliest):
                    earliest = t
        if earliest:
            out[channel] = {
                "start_time": earliest,
                "extra": extra,
            }
    return out


def _get_today() -> str:
    """Fecha de hoy en formato AAAA-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def _canales_colisionan(config: dict, channels: list) -> list:
    """Devuelve [(canal_a, canal_b, dia, hora)] de canales distintos que emiten a la vez.

    La grabación en paralelo es posible, pero avisar ayuda a decidir si conviene
    ajustar schedule si no es deseado."""
    programados = {}
    for channel, platform_name, url, extra in channels:
        schedule = _get_channel_schedule(extra, config)
        for rule in schedule:
            for day in rule.get("days", []):
                hora = rule.get("time", "19:55")
                programados.setdefault((day, hora), []).append(channel)
    return [
        (lista[0], ch, day, hora)
        for (day, hora), lista in programados.items()
        for ch in lista[1:]
    ]


def run_scheduler(dry_run: bool = False):
    """Bucle principal del grabador:
    1. Carga config y crea un Recorder por canal.
    2. Espera a la primera hora de inicio del día.
    3. Cada `check_every` segundos, por canal programado: si está en directo,
       lo inicia y lanza su `monitor` en un hilo daemon.
    4. Detecta canales nuevos/día nuevo (reinicia 'finished') y paradas limpias."""
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
    for a, b, day, hora in _canales_colisionan(config, channels_with_platform):
        log.warning(f"COLISIÓN: {a} y {b} coinciden {day} a las {hora} → se grabarán en paralelo (doble carga CPU/disco). Ajusta 'days'/'start_time' si no es deseado.")
    if dry_run:
        log.info("Modo DRY-RUN activo")

    recorders = {}
    for channel, platform_name, url, extra in channels_with_platform:
        schedule = _get_channel_schedule(extra, config)
        platform_configs = extra.get("platform", []) if isinstance(extra.get("platform"), list) else []
        recorders[channel] = Recorder(channel, platform_name, url, record_path, max_duration, max_duration_str, retry_interval, copy_to_test, test_path, extra.get("dias_plataforma"), schedule, platform_configs)

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

    while running:
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
                schedule = _get_channel_schedule(extra, config)
                platform_configs = extra.get("platform", []) if isinstance(extra.get("platform"), list) else []
                recorders[channel] = Recorder(channel, platform_name, url, record_path, max_duration, max_duration_str, retry_interval, copy_to_test, test_path, extra.get("dias_plataforma"), schedule, platform_configs)
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