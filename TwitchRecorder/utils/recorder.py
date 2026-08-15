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


def _is_generic_live_title(title: str, channel: str, uploader: str = "") -> bool:
    """True si `title` es el título genérico de Twitch ("<nombre> (live)") y no el
    real. El título real de muchos directos de Twitch va en la descripción."""
    t = (title or "").strip().lower()
    if not t:
        return True
    # Quitar marcas de fecha que a veces yt-dlp añade: "<name> (live) 2026-08-13 21:48"
    t = re.sub(r"\b20\d{2}-?\d{0,2}-?\d{0,2}.*$", "", t).strip()
    names = {n.strip().lower() for n in (channel, uploader) if n}
    for name in names:
        if name and re.match(rf"^{re.escape(name)}(\s*\(?\s*live?\s*\)?)?$", t):
            return True
    return False


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def parse_sources(platform, url: str = "") -> list:
    """Normaliza la config de fuentes de un canal a una lista ordenada por prioridad.

    - `platform` puede ser un str ("twitch") o una lista donde cada elemento es
      un str (plataforma) o un dict {"platform": ..., "url": ...} (para la
      fuente "web" con su URL).
    - Mantiene compatibilidad con la config antigua (platform como str).
    Devuelve una lista de dicts {'platform', 'url'}.
    """
    if isinstance(platform, (list, tuple)):
        sources = []
        for s in platform:
            if isinstance(s, str):
                sources.append({"platform": s, "url": url or ""})
            elif isinstance(s, dict):
                sources.append({
                    "platform": s.get("platform", "web"),
                    "url": s.get("url", "") or (url or ""),
                })
        return sources or [{"platform": "twitch", "url": ""}]
    return [{"platform": platform, "url": url or ""}]


class Recorder:
    def __init__(self, channel: str, platform_name: str, url: str = "", record_path: str = "", max_duration_hours: int = 12, max_duration_str: str = "24:00:00", retry_interval: int = 60, copy_to_test: bool = False, test_path: str = ""):
        self.channel = channel
        self.sources = parse_sources(platform_name, url)
        self.platform_name = self.sources[0]["platform"]
        self._active = None
        self._probed_sources = set()
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

    def _is_source_live(self, src: dict) -> bool:
        platform = src["platform"]
        s_url = src.get("url", "")
        if platform == "twitch":
            from utils.twitch import is_live
            return is_live(self.channel)
        elif platform == "youtube":
            from utils.youtube import is_live
            return is_live(self.channel)
        elif platform == "kick":
            from utils.kick import is_live
            return is_live(self.channel)
        elif platform == "web":
            from utils.web import is_live
            return is_live(s_url or self.channel)
        return False

    def _autoprobar_web(self, src: dict) -> None:
        """Cuando la fuente activa es la web del streamer, ejecuta UNA vez la
        prueba de captura (yt-dlp -F) y guarda el informe en record_path/web_probe.log.
        Se re-activa si la web se detecta caída (para volver a probar en la
        siguiente vez que esté activa)."""
        platform = src["platform"]
        s_url = src.get("url", "")
        if platform != "web":
            return
        key = s_url or self.channel
        if key in self._probed_sources:
            return
        self._probed_sources.add(key)
        try:
            from utils.web import probe
            probe(key, out_dir=str(self.record_path))
        except Exception as e:
            log.warning(f"[{self.channel}] web.probe falló: {e}")

    def is_live(self) -> bool:
        # Prioridad: la primera fuente que esté en directo gana (ej. la web del
        # streamer antes que kick/twitch).
        for src in self.sources:
            if not self._is_source_live(src):
                # Si la web está caída, permitir re-probar cuando vuelva a estar activa
                if src["platform"] == "web":
                    self._probed_sources.discard(src.get("url", "") or self.channel)
                continue
            self._active = src
            self.platform_name = src["platform"]
            if src["platform"] == "web":
                self._autoprobar_web(src)
            else:
                self._probed_sources.discard(src.get("url", "") or self.channel)
            return True
        return False

    def get_stream_url(self) -> str:
        src = self._active or self.sources[0]
        platform = src["platform"]
        s_url = src.get("url", "")
        if platform == "twitch":
            return f"https://www.twitch.tv/{self.channel}"
        elif platform == "youtube":
            return f"https://www.youtube.com/@{self.channel}/live"
        elif platform == "kick":
            return f"https://kick.com/{self.channel}"
        elif platform == "web":
            return s_url or self.channel
        return ""

    def get_live_title(self) -> str:
        """Obtiene el título del directo usando yt-dlp (sin guardar nada).
        Algunos canales de Twitch dejan el título genérico ("<canal> (live)") en
        el campo title, pero ponen el título real en la descripción. Si detectamos
        un título genérico, usamos la descripción como fuente del título."""
        url = self.get_stream_url()
        if not url:
            return ""
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            return ""

        title = info.get("title", "") or ""
        desc = info.get("description", "") or ""

        generic = _is_generic_live_title(title, self.channel, info.get("uploader", ""))
        if generic and desc:
            return desc
        return title

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
            src = self._active or self.sources[0]
            if src["platform"] == "twitch":
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
