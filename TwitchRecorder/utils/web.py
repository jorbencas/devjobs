import re
import time
import urllib.parse
import requests
import yt_dlp

from datetime import datetime
from pathlib import Path

from utils.logger import log


_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Umbrales para detectar la web "congelada" (playlist servida pero sin avance):
#   _PDT_FUERA  → el último segmento lleva más de 90s de antigüedad → fuera.
#   _COLA_FUERA → sin PROGRAM-DATE-TIME: la cola de segmentos no avanza en 60s → fuera.
_PDT_FUERA = 90
_COLA_FUERA = 60

# Estado por URL de variante media: {"url": {"sig": str, "desde": float}}
_MEDIA_STATE = {}


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


def _fetch_m3u8(url: str):
    """Devuelve el cuerpo del m3u8; "" si no existe (404/410) o None si es dudoso
    (5xx/429/timeout), para no tomar decisiones con respuestas transitorias."""
    try:
        resp = requests.get(url, timeout=6, headers={"User-Agent": _USER_AGENT})
        if resp.status_code in (404, 410):
            return ""
        if resp.status_code != 200:
            return None
        return resp.text
    except Exception:
        return None


def _lineas_m3u8(body: str):
    """Líneas del m3u8 normalizando CRLF, sin vacías."""
    return [ln.strip() for ln in body.replace("\r\n", "\n").split("\n") if ln.strip()]


def _primer_variante(master_body: str, master_url: str) -> str:
    """Devuelve la URL del primer variante del master (o "" si no la encuentra)."""
    seguir = False
    for linea in _lineas_m3u8(master_body):
        if seguir and not linea.startswith("#"):
            return urllib.parse.urljoin(master_url, linea)
        seguir = linea.startswith("#EXT-X-STREAM-INF")
    return ""


def _ultimo_pdt(body: str):
    """Época (segundos UTC) del último #EXT-X-PROGRAM-DATE-TIME, o None."""
    valor = None
    for linea in _lineas_m3u8(body):
        if linea.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
            valor = linea.split(":", 1)[1].strip()
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _sig_media(body: str):
    """Firma de la posición de la cola de segmentos de una playlist media."""
    seq = ""
    m = re.search(r"#EXT-X-MEDIA-SEQUENCE:\s*(\d+)", body)
    if m:
        seq = m.group(1)
    lineas = [ln for ln in _lineas_m3u8(body) if not ln.startswith("#")]
    if not lineas:
        return None
    return f"{seq}|{len(lineas)}|{lineas[-1]}"


def _media_estado(media_url: str) -> str:
    """Estado de una playlist media: 'f' fuera, 'v' en directo, 'i' indeterminado."""
    body = _fetch_m3u8(media_url)
    if body is None:
        return "i"
    if body == "":
        return "f"
    if "#EXT-X-ENDLIST" in body:
        return "f"
    if "#EXTINF" not in body:
        # Sin segmentos no hay evidencia de directo → que decida yt-dlp.
        return "i"
    pdt = _ultimo_pdt(body)
    if pdt is not None:
        return "f" if (time.time() - pdt) > _PDT_FUERA else "v"
    sig = _sig_media(body)
    if sig is None:
        return "i"
    ahora = time.time()
    estado = _MEDIA_STATE.setdefault(media_url, {"sig": sig, "desde": ahora})
    if estado["sig"] != sig:
        # La cola avanza → sigue en directo.
        estado["sig"] = sig
        estado["desde"] = ahora
        return "v"
    return "f" if (ahora - estado["desde"]) > _COLA_FUERA else "v"


def _hls_estado(hls_url: str) -> str:
    """Estado global del HLS de la web: 'f' fuera, 'v' en directo, 'i' indeterminado.

    Detecta tanto finales limpios (#EXT-X-ENDLIST / 404) como playlists
    CONGELADAS (m3u8 servido pero sin avance: último segmento antiguo o cola
    estática), que yt-dlp seguiría dando por "en directo" para siempre."""
    body = _fetch_m3u8(hls_url)
    if body is None:
        return "i"
    if body == "":
        return "f"
    if "#EXT-X-ENDLIST" in body:
        return "f"
    if "#EXT-X-STREAM-INF" in body:
        url = _primer_variante(body, hls_url)
        if not url:
            return "i"
        return _media_estado(url)
    return _media_estado(hls_url)


def is_live(url: str) -> bool:
    """¿Está emitiendo la web del streamer?

    Comprueba el m3u8 HLS directamente (más barato y fiable que yt-dlp para
    detectar colas congeladas o terminadas); solo si el estado es indeterminado
    cae al extractor de yt-dlp como seguridad.
    """
    if not url or not _server_up(url):
        return False
    domain = ""
    try:
        domain = _get_hls_domain(url)
        if not domain:
            return False
        hls_url = f"https://{domain}/hls/public/ts:abr.m3u8"
        estado = _hls_estado(hls_url)
        if estado == "f":
            return False
        if estado == "v":
            return True
    except Exception:
        return False

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 6,
        }
        hls_url = f"https://{domain}/hls/public/ts:abr.m3u8"
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
    """Calidad de grabación de la web (yt-dlp la elige: siempre 'best')."""
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
