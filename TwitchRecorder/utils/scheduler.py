import time
import threading
from datetime import datetime

from utils.config import load_config, parse_duration
from utils.twitch import is_live
from utils.recorder import Recorder


def is_scheduled_day(config: dict) -> bool:
    today = datetime.now().strftime("%A")
    return today in config.get("days", [])


def is_after_start_time(config: dict) -> bool:
    now = datetime.now()
    start = config.get("start_time", "19:55")
    h, m = map(int, start.split(":"))
    return now.hour * 60 + now.minute >= h * 60 + m


def _get_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def run_scheduler():
    config = load_config()
    channels = config.get("channels", [])
    check_interval = config.get("check_every", 30)
    record_path = config.get("record_path", "")
    max_duration_str = config.get("max_duration", "24:00:00")
    max_duration = parse_duration(max_duration_str)
    retry_interval = config.get("retry_interval", 60)
    copy_to_test = config.get("copy_to_test", True)

    print("=== TwitchRecorder iniciado ===")
    print(f"Canales: {channels}")
    print(f"Comprobando cada {check_interval}s")

    if not is_scheduled_day(config):
        print("Hoy no es día programado. Saliendo.")
        return

    if not is_after_start_time(config):
        print("Aún no es hora de inicio. Esperando...")
        while not is_after_start_time(config):
            time.sleep(10)
        print("Hora de inicio alcanzada")

    recorders = {}
    for channel in channels:
        recorders[channel] = Recorder(channel, record_path, max_duration, max_duration_str, retry_interval, copy_to_test)

    current_day = _get_today()

    while is_scheduled_day(config):
        today = _get_today()
        if today != current_day:
            print("Nuevo día detectado, reiniciando grabadores...")
            for recorder in recorders.values():
                recorder.finished = False
            current_day = today

        config = load_config()
        new_channels = config.get("channels", [])
        for channel in new_channels:
            if channel not in recorders:
                print(f"[{channel}] Nuevo canal detectado, añadiendo...")
                recorders[channel] = Recorder(channel, record_path, max_duration, max_duration_str, retry_interval, copy_to_test)

        all_offline = True

        for channel, recorder in recorders.items():
            if recorder.is_recording or recorder.finished:
                all_offline = False
                continue

            if is_live(channel):
                all_offline = False
                print(f"[{channel}] ¡Directo detectado!")
                if recorder.start():
                    monitor_thread = threading.Thread(
                        target=recorder.monitor,
                        daemon=True
                    )
                    monitor_thread.start()

        if all_offline and not any(r.is_recording for r in recorders.values()):
            print("Todos los canales offline. Esperando...")

        time.sleep(check_interval)

        if not is_scheduled_day(config):
            break

    for recorder in recorders.values():
        if recorder.is_recording:
            recorder.stop()

    print("=== TwitchRecorder finalizado ===")
