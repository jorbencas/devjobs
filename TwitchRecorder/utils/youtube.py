import yt_dlp

from utils.logger import log


def is_live(channel: str) -> bool:
    """¿Está el canal en directo en YouTube? (yt-dlp contra la URL /live)."""
    try:
        url = f"https://www.youtube.com/@{channel}/live"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info and info.get("is_live", False)
    except Exception:
        return False


def get_quality(channel: str) -> str:
    """Calidad de grabación en YouTube (siempre 'best')."""
    return "best"


def get_stream_url(channel: str) -> str:
    """URL del directo de YouTube del canal."""
    return f"https://www.youtube.com/@{channel}/live"
