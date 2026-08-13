import platform
import re
import shutil
import subprocess
import sys
import time
import threading
from pathlib import Path

from utils.files import get_recording_path
from utils.logger import log


IS_WINDOWS = platform.system() == "Windows"


def _normalize_keyword(text: str, max_len: int = 40) -> str:
    """Reduce el título del directo a una keyword segura para el nombre del archivo."""
    if not text:
        return ""
    text = re.sub(r"[\W_]+", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    words = [w for w in text.split(" ") if w]
    # Intentar quedarse con las primeras palabras que sean 'informativas'
    stop = {"de", "la", "el", "los", "las", "del", "en", "con", "y", "a", "para", "por", "es", "un", "una"}
    selected = [w for w in words if w not in stop][:2] or words[:2]
    return "_".join(selected)[:max_len]


def _find_streamlink() -> str:
    if IS_WINDOWS:
        return sys.executable, ["-m", "streamlink"]
    exe = shutil.which("streamlink")
    if exe:
        return exe, []
    return sys.executable, ["-m", "streamlink"]


def _find_ytdlp() -> str:
    if IS_WINDOWS:
        return sys.executable, ["-m", "yt_dlp"]
    exe = shutil.which("yt-dlp")
    if exe:
        return exe, []
    return sys.executable, ["-m", "yt_dlp"]


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


class Recorder:
    def __init__(self, channel: str, platform_name: str, record_path: str, max_duration_hours: int = 12, max_duration_str: str = "24:00:00", retry_interval: int = 60, copy_to_test: bool = False, test_path: str = ""):
        self.channel = channel
        self.platform_name = platform_name
        self.record_path = Path(record_path)
        self.max_duration_hours = max_duration_hours
        self.max_duration_str = max_duration_str
        self.retry_interval = retry_interval
        self.copy_to_test = copy_to_test
        self.test_path = Path(test_path) if test_path else None
        self.process = None
        self.is_recording = False
        self.finished = False
        self._current_file = None
        self._stop_event = threading.Event()

    def is_live(self) -> bool:
        if self.platform_name == "twitch":
            from utils.twitch import is_live
            return is_live(self.channel)
        elif self.platform_name == "youtube":
            from utils.youtube import is_live
            return is_live(self.channel)
        elif self.platform_name == "kick":
            from utils.kick import is_live
            return is_live(self.channel)
        return False

    def get_stream_url(self) -> str:
        if self.platform_name == "twitch":
            return f"https://www.twitch.tv/{self.channel}"
        elif self.platform_name == "youtube":
            return f"https://www.youtube.com/@{self.channel}/live"
        elif self.platform_name == "kick":
            return f"https://kick.com/{self.channel}"
        return ""

    def get_live_title(self) -> str:
        """Obtiene el título del directo usando yt-dlp (sin guardar nada)."""
        url = self.get_stream_url()
        if not url:
            return ""
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("title", "")
        except Exception:
            return ""

    def get_live_keyword(self) -> str:
        return _normalize_keyword(self.get_live_title())

    def start(self, keyword: str = "") -> bool:
        if not self.is_live():
            log.info(f"[{self.channel}] No está en directo")
            return False

        # RECONEXIÓN: si ya hay una grabación con archivo, seguir escribiendo
        # en el mismo archivo, NO crear uno nuevo (evita doble vídeo al cruzar
        # la medianoche o tras un corte de conexión).
        if self.is_recording and self._current_file and self._current_file.exists():
            output_path = self._current_file
        else:
            output_path = get_recording_path(self.channel, self.record_path, keyword)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        log.info(f"[{self.channel}] Grabación iniciada -> {output_path}")

        popen_kwargs = dict(
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        try:
            if self.platform_name == "twitch":
                self._start_streamlink(output_path, popen_kwargs)
            else:
                self._start_ytdlp(output_path, popen_kwargs)

            self.is_recording = True
            self._current_file = output_path
            self._stop_event.clear()
            return True
        except Exception as e:
            log.error(f"[{self.channel}] Error al iniciar grabación: {e}")
            return False

    def _start_streamlink(self, output_path: Path, popen_kwargs: dict) -> None:
        from utils.twitch import get_best_quality
        quality = get_best_quality(self.channel)
        if not quality:
            log.warning(f"[{self.channel}] No se pudo obtener calidad")
            raise Exception("No quality available")

        log.info(f"[{self.channel}] Calidad: {quality}")

        sl_exe, sl_prefix = _find_streamlink()
        cmd = sl_prefix + [
            f"https://www.twitch.tv/{self.channel}",
            quality,
            "-o", str(output_path),
            "--force"
        ]

        self.process = subprocess.Popen([sl_exe] + cmd, **popen_kwargs)

    def _start_ytdlp(self, output_path: Path, popen_kwargs: dict) -> None:
        url = self.get_stream_url()
        ytdlp_exe, ytdlp_prefix = _find_ytdlp()

        output_template = str(output_path)

        cmd = ytdlp_prefix + [
            url,
            "-f", "best",
            "-o", output_template,
            "--no-part",
            "--no-overwrites",
            "--write-thumbnail",
            "--convert-thumbnails", "jpg",
            "--no-warnings",
        ]

        self.process = subprocess.Popen([ytdlp_exe] + cmd, **popen_kwargs)

    def stop(self) -> None:
        self._stop_event.set()
        self.finished = True
        if self.process and self.process.poll() is None:
            log.info(f"[{self.channel}] Deteniendo grabación...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.is_recording = False
        if self._current_file and self._current_file.exists():
            size = _format_size(self._current_file.stat().st_size)
            log.info(f"[{self.channel}] Grabación finalizada ({size})")
            self._move_to_completed()
        else:
            log.info(f"[{self.channel}] Grabación finalizada")

    def _move_to_completed(self) -> None:
        if not self.copy_to_test or not self.test_path or not self._current_file:
            return
        try:
            self.test_path.mkdir(parents=True, exist_ok=True)
            dest = self.test_path / f"{self._current_file.stem}_completed.mp4"
            shutil.move(str(self._current_file), str(dest))
            log.info(f"[{self.channel}] Movida a test/ como {dest.name}")
            self._current_file = dest
        except Exception as e:
            log.error(f"[{self.channel}] Error moviendo a test/: {e}")

    def monitor(self) -> None:
        max_seconds = self.max_duration_hours * 3600
        start_time = time.time()

        while not self._stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= max_seconds:
                log.info(f"[{self.channel}] Límite de duración alcanzado ({self.max_duration_str})")
                self.stop()
                return

            if self.process and self.process.poll() is not None:
                if not self.is_live():
                    log.info(f"[{self.channel}] Directo finalizado")
                    self.stop()
                    return

                log.warning(f"[{self.channel}] Conexión perdida, reconectando en {self.retry_interval}s...")
                time.sleep(self.retry_interval)

                if not self._stop_event.is_set() and self.is_live():
                    log.info(f"[{self.channel}] Reconectado, reanudando grabación")
                    self.start()

            time.sleep(5)
