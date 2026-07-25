import platform
import shutil
import subprocess
import sys
import time
import threading
from pathlib import Path

from utils.twitch import is_live, get_best_quality
from utils.files import get_recording_path


IS_WINDOWS = platform.system() == "Windows"


def _find_streamlink() -> str:
    if IS_WINDOWS:
        return sys.executable, ["-m", "streamlink"]
    exe = shutil.which("streamlink")
    if exe:
        return exe, []
    return sys.executable, ["-m", "streamlink"]


class Recorder:
    def __init__(self, channel: str, record_path: str, max_duration_hours: int = 12, max_duration_str: str = "24:00:00", retry_interval: int = 60, copy_to_test: bool = True):
        self.channel = channel
        self.record_path = Path(record_path)
        self.max_duration_hours = max_duration_hours
        self.max_duration_str = max_duration_str
        self.retry_interval = retry_interval
        self.copy_to_test = copy_to_test
        self.process = None
        self.is_recording = False
        self.finished = False
        self._current_file = None
        self._stop_event = threading.Event()

    def start(self) -> bool:
        if not is_live(self.channel):
            print(f"[{self.channel}] No está en directo")
            return False

        quality = get_best_quality(self.channel)
        if not quality:
            print(f"[{self.channel}] No se pudo obtener calidad")
            return False

        output_path = get_recording_path(self.channel, self.record_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"[{self.channel}] Calidad: {quality}")
        print(f"[{self.channel}] Grabación iniciada -> {output_path}")

        sl_exe, sl_prefix = _find_streamlink()
        cmd = sl_prefix + [
            f"https://www.twitch.tv/{self.channel}",
            quality,
            "-o", str(output_path),
            "--force"
        ]

        popen_kwargs = dict(
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            self.process = subprocess.Popen([sl_exe] + cmd, **popen_kwargs)
            self.is_recording = True
            self._current_file = output_path
            self._stop_event.clear()
            return True
        except Exception as e:
            print(f"[{self.channel}] Error al iniciar grabación: {e}")
            return False

    def stop(self) -> None:
        self._stop_event.set()
        self.finished = True
        if self.process and self.process.poll() is None:
            print(f"[{self.channel}] Deteniendo grabación...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.is_recording = False
        if self.copy_to_test:
            self._copy_to_test()
        print(f"[{self.channel}] Grabación finalizada")

    def _copy_to_test(self) -> None:
        if not self._current_file or not self._current_file.exists():
            return

        test_dir = self.record_path / "test"
        test_dir.mkdir(parents=True, exist_ok=True)

        dest = test_dir / self._current_file.name
        if self._current_file.resolve() != dest.resolve():
            shutil.copy2(self._current_file, dest)
            print(f"[{self.channel}] Copiado a {dest}")

    def monitor(self) -> None:
        max_seconds = self.max_duration_hours * 3600
        start_time = time.time()

        while not self._stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= max_seconds:
                print(f"[{self.channel}] Límite de duración alcanzado ({self.max_duration_str})")
                self.stop()
                return

            if self.process and self.process.poll() is not None:
                if not is_live(self.channel):
                    print(f"[{self.channel}] Directo finalizado")
                    self.stop()
                    return

                print(f"[{self.channel}] Conexión perdida, reconectando en {self.retry_interval}s...")
                time.sleep(self.retry_interval)

                if not self._stop_event.is_set() and is_live(self.channel):
                    print(f"[{self.channel}] Reconectado, reanudando grabación")
                    self.start()

            time.sleep(5)
