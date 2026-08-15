import requests
import yt_dlp

from datetime import datetime
from pathlib import Path

from utils.logger import log


def _server_up(url: str) -> bool:
    """Comprobación rápida: ¿responde el servidor del streamer?

    La web suele estar CAÍDA (Sendo normalmente emite en Twitch y la enciende
    solo para mostrar los capítulos). Con este chequeo evitamos esperar los
    reintentos de yt-dlp (que tardarían ~20s) antes de pasar a la siguiente
    fuente. Basta con que responda HTTP para pasar al extractor de yt-dlp.
    """
    try:
        r = requests.get(url, timeout=4, stream=True)
        r.close()
        return True
    except Exception:
        return False


def is_live(url: str) -> bool:
    """¿Está emitiendo la web del streamer?

    Cuando está arriba, la página contiene el m3u8 del directo y el extractor
    genérico de yt-dlp lo encuentra. Cuando está caída, el pre-check HTTP
    devuelve False en ~4s.
    """
    if not url or not _server_up(url):
        return False
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 6,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return False
            if info.get("is_live"):
                return True
            formats = info.get("formats") or info.get("entries") or []
            return bool(formats)
    except Exception:
        return False


def get_quality(url: str) -> str:
    return "best"


def get_stream_url(url: str) -> str:
    return url


def probe(url: str, out_dir: str = "") -> dict:
    """Autotest de la web del streamer.

    Se ejecuta SOLO cuando el recorder detecta la web en directo: lista los
    formatos que encuentra yt-dlp (equivalente a 'yt-dlp -F'), deja un informe
    en 'web_probe.log' (dentro de out_dir, si se indica) y devuelve
    {'ok': bool, 'formats': [...]} para saber si el m3u8 es capturable.
    """
    report = []
    ok = False
    formats = []
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 6,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        info = info or {}
        is_live = bool(info.get("is_live"))
        for f in info.get("formats", []) or []:
            formats.append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution") or f.get("height") or "",
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
            })
        ok = bool(formats)
        report.append(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] WEB ACTIVA DETECTADA: {url}")
        report.append(f"  is_live: {is_live} | formatos encontrados: {len(formats)}")
        for f in formats[:25]:
            report.append(
                f"  - {f['format_id'] or '?':>6} {f['ext'] or '?':>4} "
                f"{(f['resolution'] or ''):>12} {(f['vcodec'] or '?'):>8} {(f['acodec'] or '?'):>6}"
            )
        if len(formats) > 25:
            report.append(f"  ... y {len(formats) - 25} más")
        report.append(f"  VEREDICTO: {'CAPTURABLE (m3u8 encontrado)' if ok else 'NO CAPTURABLE: sin formatos'}")
    except Exception as e:
        report.append(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] WEB ACTIVA PERO LA PRUEBA FALLÓ: {url}")
        report.append(f"  {type(e).__name__}: {e}")
        ok = False

    if out_dir:
        try:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            with open(Path(out_dir) / "web_probe.log", "a", encoding="utf-8") as f:
                f.write("\n".join(report) + "\n")
        except OSError as e:
            log.warning(f"web.probe: no se pudo escribir web_probe.log: {e}")

    log.info("\n".join(report))
    return {"ok": ok, "formats": formats}
