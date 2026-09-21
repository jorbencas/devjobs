from streamlink import Streamlink


def get_streams(channel: str) -> dict:
    """Devuelve el dict de calidades disponibles del canal ({} si no emite)."""
    try:
        return Streamlink().streams(f"https://www.twitch.tv/{channel}")
    except Exception:
        return {}


def is_live(channel: str) -> bool:
    """¿Está en directo el canal en Twitch?"""
    return bool(get_streams(channel))


def get_best_quality(channel: str) -> str:
    """Elige la mejor calidad disponible: 'best'→1080p60→...→la que quede."""
    streams = get_streams(channel)
    if not streams:
        return ""
    if "best" in streams:
        return "best"
    for q in ("1080p60", "1080p", "720p60", "720p", "480p", "360p", "160p"):
        if q in streams:
            return q
    return list(streams)[-1]
