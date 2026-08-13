from datetime import datetime
from pathlib import Path


def get_recording_path(channel: str, base_path: str | Path, keyword: str = "") -> Path:
    base = Path(base_path)
    now = datetime.now()

    year_dir = base / str(now.year)
    month_dir = year_dir / now.strftime("%m")

    base_name = f"{channel}_{now.strftime('%Y-%m-%d_%H-%M-%S')}"
    if keyword:
        base_name += f"_KW_{keyword}"
    filename = f"{base_name}.mp4"

    return month_dir / filename


def ensure_directories(base_path: str | Path) -> None:
    base = Path(base_path)
    base.mkdir(parents=True, exist_ok=True)
