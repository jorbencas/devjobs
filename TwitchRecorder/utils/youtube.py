import yt_dlp

from utils.logger import log


def is_live(channel: str) -> bool:
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
    return "best"


def get_stream_url(channel: str) -> str:
    return f"https://www.youtube.com/@{channel}/live"
