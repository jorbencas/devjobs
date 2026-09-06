#!/usr/bin/env python3
"""
delete_telegram_messages.py — Borra mensajes de Telegram usando Telethon (userbot).
Requiere api_id y api_hash de https://my.telegram.org

Uso:
  python3 delete_telegram_messages.py --api-id 12345 --api-hash abc123

Primera vez: pedirá código de verificación por Telegram.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data/yt-pipeline"))
TOPICS_FILE = Path(__file__).parent.parent / "config" / "topics.json"
SESSION_FILE = DATA_DIR / "telethon_session"

# Grupo "stream tecnologia"
GROUP_ID = -1004332325883

# Canales intocables (no borrar)
PROTECTED_CHANNELS = {"Midudev", "MoureDev"}


def load_topics():
    """Carga el mapping de canales a topic_ids."""
    if TOPICS_FILE.exists():
        with open(TOPICS_FILE) as f:
            return json.load(f)
    return {}


async def delete_messages(client, topic_id, channel_name):
    """Borra todos los mensajes de un topic específico."""
    print(f"\n🗑️  Borrando mensajes de: {channel_name} (topic {topic_id})")
    
    deleted = 0
    failed = 0
    
    async for message in client.iter_messages(
        GROUP_ID,
        reverse=True,
        reply_to=topic_id
    ):
        try:
            await message.delete()
            deleted += 1
            if deleted % 10 == 0:
                print(f"  ... {deleted} borrados")
            await asyncio.sleep(0.2)  # Rate limit
        except Exception as e:
            failed += 1
            print(f"  ⚠️  Error borrando {message.id}: {e}")
    
    print(f"  ✅ {deleted} borrados, {failed} fallidos")
    return deleted, failed


async def main():
    parser = argparse.ArgumentParser(description="Borrar mensajes de Telegram")
    parser.add_argument("--api-id", type=int, required=True, help="API ID de my.telegram.org")
    parser.add_argument("--api-hash", type=str, required=True, help="API Hash de my.telegram.org")
    parser.add_argument("--phone", type=str, help="Número de teléfono (solo primera vez)")
    parser.add_argument("--canal", type=str, help="Borrar solo un canal específico")
    args = parser.parse_args()
    
    from telethon import TelegramClient
    
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    session_path = str(SESSION_FILE)
    
    client = TelegramClient(session_path, args.api_id, args.api_hash)
    
    print("🔌 Conectando a Telegram...")
    if args.phone:
        await client.start(phone=args.phone)
    else:
        await client.start()
    
    me = await client.get_me()
    print(f"✅ Conectado como: {me.first_name} (@{me.username})")
    
    topics = load_topics()
    if not topics:
        print("❌ No se encontró topics.json")
        return
    
    total_deleted = 0
    total_failed = 0
    
    # Obtener los topics del grupo
    print(f"\n📋 Obteniendo topics del grupo...")
    
    # Iterar por los topics conocidos
    for channel_name, topic_id in topics.items():
        if isinstance(topic_id, dict):
            topic_id = topic_id.get("id")
        
        if not topic_id:
            continue
        
        # Saltar canales protegidos
        if channel_name in PROTECTED_CHANNELS:
            print(f"\n⏭️  Saltando (protegido): {channel_name}")
            continue
        
        # Si se especifica un canal, solo procesar ese
        if args.canal and args.canal.lower() not in channel_name.lower():
            continue
        
        try:
            deleted, failed = await delete_messages(client, topic_id, channel_name)
            total_deleted += deleted
            total_failed += failed
        except Exception as e:
            print(f"  ❌ Error procesando {channel_name}: {e}")
    
    await client.disconnect()
    
    print(f"\n{'='*50}")
    print(f"✅ Limpieza completada")
    print(f"   Mensajes borrados: {total_deleted}")
    print(f"   Fallidos: {total_failed}")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
