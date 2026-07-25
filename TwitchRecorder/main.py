import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.config import load_config
from utils.files import ensure_directories
from utils.scheduler import run_scheduler


def main():
    config = load_config()
    ensure_directories(config.get("record_path", ""))

    print("TwitchRecorder arrancando...")

    try:
        run_scheduler()
    except KeyboardInterrupt:
        print("Interrumpido por el usuario")
    except Exception as e:
        print(f"Error fatal: {e}")
        raise


if __name__ == "__main__":
    main()
