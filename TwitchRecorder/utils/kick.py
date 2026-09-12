import requests

from utils.logger import log


def is_live(channel: str) -> bool:
    """Detecta si un canal está en directo en Kick usando la API de canales."""
    try:
        resp = requests.get(f"https://kick.com/api/v2/channels/{channel}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        livestream = data.get("livestream")
        if livestream and livestream.get("is_live"):
            return True
        return False
    except Exception as e:
        log.warning(f"[kick] is_live falló para {channel}: {e}")
        return False


def get_quality(channel: str) -> str:
    """Calidad de grabación en Kick (yt-dlp la elige: siempre 'best')."""
    return "best"


def get_stream_url(channel: str) -> str:
    """URL del canal en Kick."""
    return f"https://kick.com/{channel}"
