import requests
import yt_dlp

from datetime import datetime
from pathlib import Path

from utils.logger import log


def _get_hls_domain(url: str) -> str:
    """Obtiene el dominio del servidor HLS desde la API interna de watch.sendosama.net.

    La web es un React SPA que no tiene m3u8 embebido. La API /api/playback-domain
    devuelve el dominio del edge server que sirve el stream HLS.
    """
    try:
        base = url.rstrip("/")
        resp = requests.get(f"{base}/api/playback-domain", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        domain = data.get("domain", "")
        if domain:
            return domain
    except Exception as e:
        log.warning(f"[web] _get_hls_domain falló para {url}: {e}")
    return ""


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

    Usa la API /api/playback-domain para obtener el dominio HLS y comprueba
    si el stream m3u8 está activo.
    """
    if not url or not _server_up(url):
        return False
    try:
        domain = _get_hls_domain(url)
        if not domain:
            return False
        hls_url = f"https://{domain}/hls/public/ts:abr.m3u8"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 6,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(hls_url, download=False)
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
    """Devuelve la URL directa del m3u8 HLS en vez de la página web.

    yt-dlp no puede extraer streams de React SPAs porque el HTML está vacío.
    Esta función llama a la API /api/playback-domain para obtener el dominio
    del edge server y construir la URL del m3u8 directamente.
    """
    if not url:
        return url
    domain = _get_hls_domain(url)
    if domain:
        hls_url = f"https://{domain}/hls/public/ts:abr.m3u8"
        log.info(f"[web] HLS URL: {hls_url}")
        return hls_url
    log.warning(f"[web] No se pudo obtener dominio HLS para {url}")
    return url


def get_title(url: str) -> str:
    """Obtiene el título del directo desde la web.

    La web es un React SPA, pero el título puede estar en:
    1. La etiqueta <title> del HTML
    2. Un meta tag og:title
    3. El nombre del canal en la URL
    """
    if not url:
        return ""
    try:
        resp = requests.get(url, timeout=5, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        html = resp.text
        # Buscar <title>
        import re
        m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            if title and title.lower() != "sendosama":
                return title
        # Buscar og:title
        m = re.search(r'og:title\s+content="([^"]+)"', html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


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
        domain = _get_hls_domain(url)
        hls_url = f"https://{domain}/hls/public/ts:abr.m3u8" if domain else url
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 6,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(hls_url, download=False)
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
        report.append(f"  Dominio HLS: {domain}")
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
