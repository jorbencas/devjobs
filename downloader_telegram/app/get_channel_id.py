#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obtener el channel_id de un canal/grupo de Telegram por nombre.

Usa la infraestructura existente de tg_toolbox (credenciales cifradas, sesión propia).
Útil para encontrar el ID del canal 'reportes proyectos' y guardarlo como secret de GitHub.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from tg_toolbox.cli_base import cargar_credenciales
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

SESSION_FILE = REPO_DIR / "data" / "sessions" / "get_channel_id.session"
SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)


async def find_channel_by_name(target_name: str):
    api_id, api_hash = cargar_credenciales()
    client = TelegramClient(str(SESSION_FILE), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("[x] Sesión no autorizada. Ejecuta primero el setup interactivo (test_download_protected_content_telegram.py)")
        await client.disconnect()
        return

    print(f"\n[*] Buscando canal/grupo que contenga: '{target_name}'\n")
    found = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        title = getattr(entity, "title", getattr(entity, "first_name", ""))
        username = getattr(entity, "username", None)
        chat_id = dialog.id

        if target_name.lower() in title.lower():
            entity_type = "Canal" if isinstance(entity, Channel) and entity.broadcast else \
                          "Grupo/Foro" if isinstance(entity, Channel) and entity.megagroup else \
                          "Chat" if isinstance(entity, Chat) else "Desconocido"
            found.append({
                "id": chat_id,
                "title": title,
                "username": f"@{username}" if username else "sin username",
                "type": entity_type,
                "is_forum": getattr(entity, "forum", False) if isinstance(entity, Channel) else False,
            })

    await client.disconnect()

    if not found:
        print(f"[!] No se encontró ningún chat con '{target_name}' en el nombre.")
        print("    Asegúrate de que el bot/usuario esté unido al canal/grupo.")
        return

    print(f"[✓] Encontrados {len(found)} resultado(s):\n")
    for i, ch in enumerate(found, 1):
        print(f"  {i}. ID: {ch['id']}")
        print(f"     Título: {ch['title']}")
        print(f"     Username: {ch['username']}")
        print(f"     Tipo: {ch['type']}")
        if ch['is_forum']:
            print(f"     ⚠ Es un FORO (tiene temas)")
        print()

    if len(found) == 1:
        ch = found[0]
        print("=" * 60)
        print(f"CHANNEL_ID para GitHub Secret: {ch['id']}")
        print("=" * 60)
        print("\nAñade este valor como secret en GitHub:")
        print(f"  Name: TELEGRAM_REPORTES_PROYECTOS_CHANNEL_ID")
        print(f"  Value: {ch['id']}")
    else:
        print("Hay múltiples resultados. Usa el ID del correcto.")


def main():
    if len(sys.argv) < 2:
        print("Uso: python get_channel_id.py \"nombre del canal\"")
        print("Ejemplo: python get_channel_id.py \"reportes proyectos\"")
        sys.exit(1)

    target_name = sys.argv[1]
    asyncio.run(find_channel_by_name(target_name))


if __name__ == "__main__":
    main()