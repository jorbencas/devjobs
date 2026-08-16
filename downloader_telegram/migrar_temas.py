#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migra (re-subida, sin borrar) el contenido de canales origen concretos hacia
su tema en el foro 'Sendo resubidos'.

Usa un MAPEO EXPLÍCITO tema_id:origen (no inferencia por nombre).
  --migrar TEMA_ID:ORIGEN   (repetible)
  --ejecutar                hacer la re-subida real; sin él, solo informa.
NO borra el original.
"""
import argparse
import asyncio
import os
import sys

from telethon import TelegramClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subir_videos import (  # noqa: E402
    SESION_UPLOADER,
    cargar_credenciales,
    cargar_grupos,
    _conectar,
    log,
)


async def run(api_id, api_hash, pares, ejecutar):
    default, grupos, grupo_series, temas = cargar_grupos()
    if not grupo_series:
        raise SystemExit("[x] No hay grupo_series en grupos.json.")
    tmap = {t["id"]: t["nombre"] for t in temas}

    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)

    foro_ent = None
    async for d in client.iter_dialogs():
        if getattr(d, "id", None) == grupo_series:
            foro_ent = getattr(d, "entity", None)
            break
    if foro_ent is None:
        raise SystemExit(f"[x] No se encontró el foro {grupo_series}.")

    for spec in pares:
        tema_id_s, origen_s = spec.split(":", 1)
        tema_id = int(tema_id_s)
        origen = int(origen_s)
        nombre = tmap.get(tema_id, f"tema {tema_id}")
        try:
            source_ent = await client.get_entity(origen)
        except Exception:
            source_ent = origen

        n = 0
        async for _ in client.iter_messages(source_ent):
            n += 1
        log("..", f"Tema '{nombre}' (id={tema_id}) <- origen {origen}: {n} msgs")
        if not ejecutar:
            continue

        nenv = 0
        async for msg in client.iter_messages(source_ent):
            if not (msg.media and getattr(msg, "document", None)):
                continue
            try:
                caption = msg.message or ""
                await client.send_file(foro_ent, msg.media, caption=caption, reply_to=tema_id)
                nenv += 1
                if nenv % 5 == 0:
                    log("ok", f"  {nombre}: re-subidos {nenv}")
                await asyncio.sleep(0.5)
            except Exception as e:
                log("x", f"  fallo msg {msg.id}: {e}")
        log("ok", f"{nombre}: {nenv} vídeos re-subidos al tema.")
        await asyncio.sleep(1)

    await client.disconnect()


async def run_deshacer(api_id, api_hash, pares, ventana_min):
    """Borra de los temas las re-subidas hechas por la propia cuenta dentro de la
    ventana, en cada tema objetivo (pares = origen recuperado en el formato TEMA_ID:ORIGEN)."""
    from datetime import datetime, timedelta
    default, grupos, grupo_series, temas = cargar_grupos()
    if not grupo_series:
        raise SystemExit("[x] No hay grupo_series en grupos.json.")
    tmap = {t["id"]: t["nombre"] for t in temas}
    topic_ids = sorted({int(p.split(":", 1)[0]) for p in pares})

    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    me = await client.get_me()
    myid = getattr(me, "id", None)
    foro_ent = None
    async for d in client.iter_dialogs():
        if getattr(d, "id", None) == grupo_series:
            foro_ent = getattr(d, "entity", None)
            break
    if foro_ent is None:
        raise SystemExit(f"[x] No se encontró el foro {grupo_series}.")
    since = datetime.now().astimezone() - timedelta(minutes=ventana_min)
    log("..", f"Buscando en el foro mensajes propios (id {myid}) en temas {topic_ids} desde {since:%H:%M}...")

    borrados = 0
    total_borrables = 0
    async for msg in client.iter_messages(foro_ent, from_user=myid, wait_time=2):
        if msg.date < since:
            continue
        topic = None
        rt = getattr(msg, "reply_to", None)
        if rt is not None:
            topic = getattr(rt, "reply_to_msg_id", None) or getattr(rt, "reply_to_top_id", None)
        if topic not in topic_ids:
            continue
        total_borrables += 1
        try:
            await msg.delete()
            borrados += 1
            log("ok", f"  borrado msg {msg.id} (tema {tmap.get(topic, topic)})")
        except Exception as e:
            log("x", f"  no pude borrar msg {msg.id}: {e}")
    log("==", f"Borrados {borrados}/{total_borrables} re-subidas.")
    await client.disconnect()


def main():
    p = argparse.ArgumentParser(description="Migrar canales concretos a temas del foro")
    p.add_argument("--migrar", action="append", required=True, metavar="TEMA_ID:ORIGEN",
                   help="Par tema->origen, repetible")
    p.add_argument("--ejecutar", action="store_true", help="Re-subida real (sin borrar); por defecto informa")
    p.add_argument("--deshacer", action="store_true",
                   help="Borra en esos temas las re-subidas de tu propia cuenta en la ventana")
    p.add_argument("--ventana", type=int, default=60, help="Minutos hacia atrás a revisar (deshacer)")
    args = p.parse_args()
    try:
        api_id, api_hash = cargar_credenciales()
    except Exception as e:
        print(f"[x] {e}")
        return
    if args.deshacer:
        asyncio.run(run_deshacer(api_id, api_hash, args.migrar, args.ventana))
    else:
        asyncio.run(run(api_id, api_hash, args.migrar, args.ejecutar))


if __name__ == "__main__":
    main()