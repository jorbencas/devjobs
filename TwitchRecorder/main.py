import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.config import load_config
from utils.files import ensure_directories
from utils.logger import log
from utils.scheduler import run_scheduler


def main():
    parser = argparse.ArgumentParser(description="TwitchRecorder - Grabador automático de Twitch")
    parser.add_argument("--dry-run", action="store_true", help="Simula sin grabar")
    args = parser.parse_args()

    config = load_config()
    ensure_directories(config.get("record_path", ""))

    if args.dry_run:
        log.info("=== MODO DRY-RUN (sin grabar) ===")

    log.info("TwitchRecorder arrancando...")

    try:
        run_scheduler(dry_run=args.dry_run)
    except KeyboardInterrupt:
        log.info("Interrumpido por el usuario")
    except Exception as e:
        log.error(f"Error fatal: {e}")
        raise


if __name__ == "__main__":
    main()
