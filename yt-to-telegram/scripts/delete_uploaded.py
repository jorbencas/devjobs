#!/usr/bin/env python3
"""
delete_uploaded.py — Borra mensajes de Telegram usando message_ids guardados.
Útil para limpiar el grupo antes de empezar de 0.
"""
import json
import os
import subprocess
import logging
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("delete")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data/yt-pipeline"))
MESSAGE_IDS_FILE = DATA_DIR / "message_ids.json"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "")

# Canales intocables (no borrar)
PROTECTED_CHANNELS = {"Midudev", "MoureDev"}


def load_message_ids():
    """Carga los message_ids guardados."""
    if MESSAGE_IDS_FILE.exists():
        with open(MESSAGE_IDS_FILE) as f:
            return json.load(f)
    return {}


def save_message_ids(ids):
    """Guarda los message_ids actualizados."""
    with open(MESSAGE_IDS_FILE, "w") as f:
        json.dump(ids, f, indent=2, ensure_ascii=False)


def delete_message(message_id):
    """Borra un mensaje del grupo."""
    cmd = [
        "curl", "-s",
        "-X", "POST",
        f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
        "-d", f"chat_id={GROUP_ID}",
        "-d", f"message_id={message_id}"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)
        return response.get("ok", False)
    except Exception as e:
        logger.error(f"  Error borrando mensaje {message_id}: {e}")
        return False


def main():
    """Borra todos los mensajes de los canales no protegidos."""
    if not BOT_TOKEN or not GROUP_ID:
        logger.error("❌ BOT_TOKEN y TELEGRAM_GROUP_ID son requeridos")
        return

    ids = load_message_ids()
    if not ids:
        logger.info("ℹ️  No hay message_ids guardados")
        return

    total_deleted = 0
    total_failed = 0
    channels_cleaned = []

    for channel, messages in ids.items():
        if channel in PROTECTED_CHANNELS:
            logger.info(f"⏭️  Saltando (protegido): {channel}")
            continue

        if not messages:
            continue

        logger.info(f"\n🗑️  Borrando {len(messages)} mensajes de: {channel}")
        deleted = 0
        failed = 0

        for msg in messages:
            msg_id = msg["message_id"]
            if delete_message(msg_id):
                deleted += 1
            else:
                failed += 1
            time.sleep(0.1)  # Rate limit

        total_deleted += deleted
        total_failed += failed
        channels_cleaned.append(channel)
        logger.info(f"  ✅ {deleted} borrados, {failed} fallidos")

        # Limpiar IDs de este canal
        ids[channel] = []

    # Guardar IDs restantes (protegidos)
    remaining = {k: v for k, v in ids.items() if v}
    save_message_ids(remaining)

    logger.info(f"\n{'='*50}")
    logger.info(f"✅ Limpieza completada")
    logger.info(f"   Canales limpiados: {len(channels_cleaned)}")
    logger.info(f"   Mensajes borrados: {total_deleted}")
    logger.info(f"   Fallidos: {total_failed}")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
