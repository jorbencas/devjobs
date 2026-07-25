import yt_dlp

from utils.logger import log


def is_live(channel: str) -> bool:
    try:
        url = f"https://kick.com/{channel}"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get("is_live"):
                return True
            return False
    except Exception:
        return False


def get_quality(channel: str) -> str:
    return "best"


def get_stream_url(channel: str) -> str:
    return f"https://kick.com/{channel}"
