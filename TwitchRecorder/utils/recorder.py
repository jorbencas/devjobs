import json
import platform
from datetime import datetime
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
    stop = {"de", "la", "el", "los", "las", "del", "en", "con", "y", "a", "para", "por", "es", "un", "una",
            "lo", "que", "se", "su", "al", "no", "mi", "me", "te", "le"}
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
    - Conserva campos extra del dict (ej. "channel" para un handle distinto al
      del canal, o "descripcion": true para captions propios).
    Devuelve una lista de dicts {'platform', 'url', ...}."""
    if isinstance(platform, (list, tuple)):
        sources = []
        for s in platform:
            if isinstance(s, str):
                sources.append({"platform": s, "url": url or ""})
            elif isinstance(s, dict):
                source = dict(s)
                source.setdefault("platform", "web")
                if not source.get("url"):
                    source["url"] = url or ""
                sources.append(source)
        return sources or [{"platform": "twitch", "url": ""}]
    return [{"platform": platform, "url": url or ""}]


class Recorder:
    def __init__(self, channel: str, platform_name: str, url: str = "", record_path: str = "", max_duration_hours: int = 12, max_duration_str: str = "24:00:00", retry_interval: int = 60, copy_to_test: bool = False, test_path: str = "", dias_plataforma: dict = None):
        self.channel = channel
        self.sources = parse_sources(platform_name, url)
        self.platform_name = self.sources[0]["platform"]
        self.dias_plataforma = dias_plataforma or {}
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
        self._partes = []
        self._stop_event = threading.Event()

    def _is_source_live(self, src: dict) -> bool:
        platform = src["platform"]
        s_url = src.get("url", "")
        canal = src.get("channel") or self.channel
        if platform == "twitch":
            from utils.twitch import is_live
            return is_live(canal)
        elif platform == "youtube":
            from utils.youtube import is_live
            return is_live(canal)
        elif platform == "kick":
            from utils.kick import is_live
            return is_live(canal)
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

    def _reordenar_por_dia(self) -> None:
        """Fija las plataformas a usar según el día (p.ej. siendo: domingo YT/Twitch,
        resto de días sin YouTube). El mapa REPLACE la lista de fuentes: solo se
        usan las plataformas indicadas, en ese orden."""
        if not self.dias_plataforma:
            return
        day = datetime.now().strftime("%A")
        order = self.dias_plataforma.get(day) or self.dias_plataforma.get("*")
        if not order:
            return
        by_platform = {}
        for src in self.sources:
            by_platform.setdefault(src["platform"], []).append(src)
        ordered = []
        for plat in order:
            ordered.extend(by_platform.pop(plat, []))
        # Las plataformas NO listadas se descartan (no se usan ese día).
        if ordered:
            self.sources = ordered

    def is_live(self) -> bool:
        # Prioridad: la primera fuente que esté en directo gana (ej. la web del
        # streamer antes que kick/twitch). Según el día se puede priorizar otra
        # plataforma (ej. siendo → youtube el domingo).
        self._reordenar_por_dia()
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
        canal = src.get("channel") or self.channel
        if platform == "twitch":
            return f"https://www.twitch.tv/{canal}"
        elif platform == "youtube":
            return f"https://www.youtube.com/@{canal}/live"
        elif platform == "kick":
            return f"https://kick.com/{canal}"
        elif platform == "web":
            return s_url or self.channel
        return ""

    def get_live_title(self) -> str:
        """Obtiene el título del directo usando yt-dlp (sin guardar nada).
        Algunos canales de Twitch dejan el título genérico ("<canal> (live)") en
        el campo title, pero ponen el título real en la descripción. Si detectamos
        un título genérico, usamos la descripción como fuente del título."""
        info = self._fetch_live_info()
        if not info:
            return ""

        title = info.get("title", "") or ""
        desc = info.get("description", "") or ""

        generic = _is_generic_live_title(title, self.channel, info.get("uploader", ""))
        if generic and desc:
            return desc
        return title

    def _fetch_live_info(self) -> dict:
        """Extrae la metadata del directo con yt-dlp (info dict). Devuelve {}
        si falla o no hay URL."""
        url = self.get_stream_url()
        if not url:
            return {}
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
                return ydl.extract_info(url, download=False) or {}
        except Exception:
            return {}

    def get_live_description(self) -> str:
        """Descripción completa del directo (p. ej. la de YouTube). Se usa como
        caption de Telegram para canales que no detectan episodios."""
        return (self._fetch_live_info().get("description") or "").strip()

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
            # Cambio de plataforma a mitad del directo (p. ej. Twitch → Kick):
            # se graba en una parte nueva con el MISMO nombre base + "__parteN".
            if self._partes:
                base = self._partes[0]
                output_path = base.with_name(base.stem + f"__parte{len(self._partes) + 1}.mp4")

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

            # Sidecar de configuración del directo para el monitor: solo cuando
            # la fuente NO usa los valores por defecto (descripción propia,
            # sin detección de episodios y/o sin corte de extremos).
            if src.get("descripcion") or src.get("detectar") is False or src.get("corte") is False:
                self._guardar_sidecar(output_path, src)

            return True
        except Exception as e:
            log.error(f"[{self.channel}] Error al iniciar grabación: {e}")
            return False

    def _guardar_sidecar(self, output_path: Path, src: dict) -> None:
        """Guarda '<output>_descripcion.json' con la configuración del directo:
        - "descripcion": descripción del directo (recortada al máximo de caption
          de Telegram, 1024 chars). El monitor la usa como caption y omite la
          detección de episodios/corte.
        - "detectar": false cuando la fuente está configurada sin detección de
          episodios (el monitor no hace OCR).
        - "corte": false cuando la fuente está configurada sin corte de extremos
          (el monitor no recorta, aunque el OCR siga disponible).
        Detección y corte son independientes: se puede detectar sin cortar.
        """
        data = {}
        if src.get("descripcion"):
            titulo = self.get_live_title()
            if titulo:
                data["titulo"] = titulo[:1024]
            desc = self.get_live_description()
            if not desc:
                log.warning(f"[{self.channel}] Sin descripción que guardar")
            else:
                data["descripcion"] = desc[:1024]
        if src.get("detectar") is False:
            data["detectar"] = False
        if src.get("corte") is False:
            data["corte"] = False
        if not data:
            return
        try:
            sidecar = output_path.with_name(output_path.stem + "_descripcion.json")
            sidecar.write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info(f"[{self.channel}] Sidecar guardado para el monitor: {data}")
        except Exception as e:
            log.warning(f"[{self.channel}] No se pudo guardar el sidecar: {e}")

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
            self._concatenar_partes()
            self._move_to_completed()
        else:
            log.info(f"[{self.channel}] Grabación finalizada")

    def _add_parte_actual(self) -> None:
        """Cierra la parte actual de un directo (cambio de plataforma a mitad de
        emisión) y la guarda en self._partes para concatenarla al final."""
        if self._current_file and self._current_file.exists():
            self._partes.append(self._current_file)
            log.info(f"[{self.channel}] Parte {len(self._partes)} cerrada: {self._current_file.name}")
        self._current_file = None
        self.process = None
        self.is_recording = False

    def _concatenar_partes(self) -> None:
        """Une todas las partes de un directo que cambió de plataforma a mitad de
        emisión en un único archivo (nombre base sin sufijo __parteN). Si algo
        falla, se mantienen las partes por separado."""
        partes = [p for p in (self._partes + [self._current_file]) if p and p.exists()]
        if not self._partes or len(partes) < 2 or not self._current_file:
            return
        final = self._partes[0].with_name(self._partes[0].stem + ".mp4")
        tmp = final.with_name(final.stem + "_tmp.mp4")
        log.info(f"[{self.channel}] Concatenando {len(partes)} partes del directo...")
        if not self._concatenar(partes, tmp):
            log.warning(f"[{self.channel}] No se pudo concatenar; se mantienen las partes por separado")
            return
        # Primero colocar el concat en su nombre final y SOLO entonces borrar
        # las partes (si algo falla antes, las partes siguen intactas).
        try:
            shutil.move(str(tmp), str(final))
        except Exception as e:
            log.error(f"[{self.channel}] Error moviendo concat a su nombre final: {e}")
            return
        # Sidecar de descripción de la primera parte (si existe) → archivo final
        for p in partes:
            sc = p.with_name(p.stem + "_descripcion.json")
            if sc.exists():
                try:
                    shutil.copy(sc, final.with_name(final.stem + "_descripcion.json"))
                except Exception:
                    pass
                break
        for p in partes:
            sc = p.with_name(p.stem + "_descripcion.json")
            for f in (p, sc):
                try:
                    if f.exists():
                        f.unlink()
                except Exception:
                    pass
        self._partes = []
        self._current_file = final
        log.info(f"[{self.channel}] Partes del directo unidas en {final.name}")

    def _concatenar(self, partes: list, output: Path) -> bool:
        """Concatena las partes con ffmpeg (concat filter + re-encode), escalando
        cada entrada a la altura común más baja para que el filtro no falle."""
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            log.warning(f"[{self.channel}] ffmpeg/ffprobe no disponibles, sin concatenar")
            return False
        try:
            heights = []
            for p in partes:
                out = subprocess.check_output(
                    [ffprobe, "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=height", "-of", "csv=p=0", str(p)],
                    stderr=subprocess.DEVNULL,
                )
                out = out.decode().strip()
                if out:
                    heights.append(int(out))
            if not heights:
                return False
            h = min(heights)
            n = len(partes)
            filters = [f"[{i}:v]scale=-2:{h}[v{i}]" for i in range(n)]
            vlabels = "".join(f"[v{i}]" for i in range(n))
            alabels = "".join(f"[{i}:a]" for i in range(n))
            filters.append(f"{vlabels}{alabels}concat=n={n}:v=1:a=1[vout][aout]")
            cmd = [ffmpeg, "-y"]
            for p in partes:
                cmd += ["-i", str(p)]
            cmd += [
                "-filter_complex", ";".join(filters),
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-crf", "23", "-preset", "medium",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart", "-f", "mp4",
                str(output),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            log.warning(f"[{self.channel}] Error al concatenar: {e}")
            return False

    def _move_to_completed(self) -> None:
        if not self.copy_to_test or not self.test_path or not self._current_file:
            return
        try:
            self.test_path.mkdir(parents=True, exist_ok=True)
            orig = self._current_file
            dest = self.test_path / f"{orig.stem}_completed.mp4"
            sidecar = orig.with_name(orig.stem + "_descripcion.json")
            shutil.move(str(orig), str(dest))
            self._current_file = dest
            if sidecar.exists():
                shutil.move(str(sidecar), dest.with_name(dest.stem + "_descripcion.json"))
                log.info(f"[{self.channel}] Sidecar de descripción movido junto al completado")
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
                prev_platform = self._active["platform"] if self._active else self.sources[0]["platform"]
                if not self.is_live():
                    log.info(f"[{self.channel}] Directo finalizado")
                    self.stop()
                    return

                new_platform = self._active["platform"] if self._active else prev_platform
                if new_platform != prev_platform:
                    # Cambio de plataforma a mitad del directo (p. ej. le cortan
                    # en Twitch y se va a Kick): se cierra la parte actual y se
                    # abre una nueva (mismo nombre base + "__parteN") desde la
                    # nueva plataforma. Al terminar el directo se concatenan.
                    log.warning(
                        f"[{self.channel}] Cambio de plataforma {prev_platform} → {new_platform}: "
                        f"cerrando parte actual y empezando nueva desde {new_platform}"
                    )
                    self._add_parte_actual()
                    if not self._stop_event.is_set() and self.is_live():
                        self.start()
                else:
                    log.warning(f"[{self.channel}] Conexión perdida, reconectando en {self.retry_interval}s...")
                    time.sleep(self.retry_interval)

                    if not self._stop_event.is_set() and self.is_live():
                        log.info(f"[{self.channel}] Reconectado, reanudando grabación")
                        self.start()

            time.sleep(5)
