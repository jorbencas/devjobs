import json
import platform
from pathlib import Path

from utils.logger import log


CONFIG_PATH = Path(__file__).parent.parent / "config.json"

_PROJECT_DIR = Path(__file__).parent.parent


def _default_record_path() -> str:
    if platform.system() == "Windows":
        return "D:\\Grabaciones"
    return str(_PROJECT_DIR / "recordings")


def parse_duration(duration_str: str) -> float:
    parts = duration_str.split(":")
    if len(parts) == 3:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h + m / 60 + s / 3600
    elif len(parts) == 2:
        m, s = int(parts[0]), int(parts[1])
        return m / 60 + s / 3600
    else:
        try:
            return float(duration_str)
        except ValueError:
            log.warning(f"Formato de duración inválido: '{duration_str}'. Usando 24:00:00 por defecto.")
            return 24.0


DEFAULT_CONFIG = {
    "channels": [],
    "record_path": _default_record_path(),
    "days": [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ],
    "start_time": "19:55",
    "check_every": 30,
    "max_duration": "24:00:00",
    "copy_to_test": False,
    "test_path": ""
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        save_config(DEFAULT_CONFIG, path)
        return DEFAULT_CONFIG.copy()

    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value

    return config


def get_channels_with_platform(config: dict) -> list:
    channels = config.get("channels", [])

    if isinstance(channels, dict):
        result = []
        for name, info in channels.items():
            if isinstance(info, dict):
                platform_name = info.get("platform", "twitch")
            else:
                platform_name = "twitch"
            result.append((name, platform_name))
        return result

    return [(ch, "twitch") for ch in channels]


def save_config(config: dict, path: Path = CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
