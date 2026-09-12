from streamlink import Streamlink


def get_streamlink() -> Streamlink:
    """Devuelve una sesión de streamlink lista para usar."""
    return Streamlink()


def is_live(channel: str) -> bool:
    """¿Está en directo el canal en Twitch? (streamlink obtiene los streams,
    si hay alguno → True)."""
    try:
        session = get_streamlink()
        streams = session.streams(f"https://www.twitch.tv/{channel}")
        return len(streams) > 0
    except Exception:
        return False


def get_streams(channel: str) -> dict:
    """Devuelve el dict de calidades disponibles del canal ({} si no emite)."""
    try:
        session = get_streamlink()
        return session.streams(f"https://www.twitch.tv/{channel}")
    except Exception:
        return {}


def get_best_quality(channel: str) -> str:
    """Elige la mejor calidad disponible: 'best'→1080p60→...→la que quede."""
    streams = get_streams(channel)
    if not streams:
        return ""

    if "best" in streams:
        return "best"

    quality_order = ["1080p60", "1080p", "720p60", "720p", "480p", "360p", "160p"]
    for quality in quality_order:
        if quality in streams:
            return quality

    return list(streams.keys())[-1] if streams else ""
