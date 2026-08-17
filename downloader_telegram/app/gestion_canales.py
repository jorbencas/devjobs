#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestión de canales/foros de Telegram para el pipeline de subida.

Operaciones:
  --crear-canal "TITULO" [--about "descr"] [--foro]   crea un canal privado
                                                       (con foro/temas si --foro)
  --archivar <ID>[,ID...]                              mueve a la carpeta Archivo
  --crear-temas <FORO_ID>:T1,T2,...                    crea temas en el foro
  --listar-temas <FORO_ID>                             lista los temas del foro
  --migrar FORO_ID:TEMA_ID:ORIGEN_ID                   re-subida (sin borrar)
                                                       (repetible)
  --borrar-canal <ID>[,ID...]                          BORRA canales (irreversible)

Reutiliza las credenciales/sesión del uploader (uploader.session).
"""
import argparse
import asyncio
import sys

from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, DeleteChannelRequest
from telethon.tl.functions.messages import (
    CreateForumTopicRequest,
    GetForumTopicsRequest,
)
from telethon.tl.functions.folders import EditPeerFoldersRequest
from telethon.tl.types import InputFolderPeer

sys.path.insert(0, __file__ and __file__.rsplit("/", 1)[0] or ".")

from subir_videos import (  # noqa: E402
    SESION_UPLOADER,
    cargar_credenciales,
    _conectar,
    log,
)


async def _resolver(client, ref):
    try:
        return await client.get_entity(int(ref))
    except (ValueError, TypeError):
        try:
            return await client.get_entity(ref)
        except Exception:
            raise SystemExit(f"[x] No se resolvió la entidad {ref}")


async def run_crear_canal(api_id, api_hash, titulo, about, foro):
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    res = await client(CreateChannelRequest(
        title=titulo,
        about=about or "",
        broadcast=True,
        megagroup=False,
        forum=bool(foro),
    ))
    chat = res.chats[0]
    log("OK", f"Canal creado: '{chat.title}' id={chat.id} foro={bool(foro)}")
    await client.disconnect()


async def run_archivar(api_id, api_hash, refs):
    from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    for ref in refs:
        ent = await _resolver(client, ref)
        inp = await client.get_input_entity(ent)
        await client(EditPeerFoldersRequest(folder_peers=[InputFolderPeer(peer=inp, folder_id=1)]))
        log("OK", f"'{getattr(ent, 'title', getattr(ent, 'name', ref))}' archivado (id={ent.id})")
    await client.disconnect()


async def run_crear_temas(api_id, api_hash, foro, titulos):
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    ent = await _resolver(client, foro)
    for i, titulo in enumerate(titulos):
        try:
            res = await client(CreateForumTopicRequest(
                peer=ent, title=titulo,
                random_id=int(asyncio.get_event_loop().time() * 1000) + i,
            ))
            tid = getattr(getattr(res.updates[0], "message", None), "id", None)
            log("OK", f"Tema creado: '{titulo}' id={tid}")
        except Exception as e:
            log("ERR", f"Fallo al crear '{titulo}': {e}")
    await client.disconnect()


async def run_listar_temas(api_id, api_hash, foro):
    from datetime import datetime as dt
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    ent = await _resolver(client, foro)
    res = await client(GetForumTopicsRequest(
        peer=ent, offset_date=dt(1970, 1, 1), offset_id=0,
        offset_topic=0, limit=100,
    ))
    print("\nID\tTítulo")
    print("-" * 50)
    for t in res.topics:
        print(f"{t.id}\t{t.title}")
    print(f"\n{len(res.topics)} de {res.count} temas.")
    await client.disconnect()


async def run_migrar(api_id, api_hash, tripletas):
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    for spec in tripletas:
        foro_s, tema_s, origen_s = spec.split(":", 2)
        foro = int(foro_s)
        tema_id = int(tema_s)
        origen = int(origen_s)
        foro_ent = await _resolver(client, foro_s)
        try:
            source_ent = await _resolver(client, origen_s)
        except SystemExit:
            source_ent = origen
        n = 0
        async for _ in client.iter_messages(source_ent):
            n += 1
        log("..", f"origen {origen_s}: {n} msgs -> foro {foro} tema {tema_id}")
        nenv = ntxt = 0
        async for msg in client.iter_messages(source_ent, reverse=True):
            try:
                if msg.message and getattr(msg, "media", None) and getattr(msg, "document", None):
                    await client.send_file(foro_ent, msg.media, caption=msg.message, reply_to=tema_id)
                    nenv += 1
                elif msg.message and not getattr(msg, "media", None):
                    await client.send_message(foro_ent, msg.message, reply_to=tema_id)
                    ntxt += 1
                elif getattr(msg, "media", None) and getattr(msg, "document", None):
                    await client.send_file(foro_ent, msg.media, reply_to=tema_id)
                    nenv += 1
                else:
                    continue
            except Exception as e:
                log("x", f"  fallo msg {msg.id}: {e}")
            await asyncio.sleep(0.3)
        log("ok", f"origen {origen_s}: {nenv} vídeos + {ntxt} textos al tema {tema_id}.")
        await asyncio.sleep(1)
    await client.disconnect()


async def run_borrar(api_id, api_hash, refs):
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    for ref in refs:
        ent = await _resolver(client, ref)
        nom = getattr(ent, "title", getattr(ent, "name", ref))
        print(f"\n⚠ Borrando canal '{nom}' (id={ent.id})...")
        ans = input("    ¿Confirmas? [y/N]: ").strip().lower()
        if ans != "y":
            print("    cancelado.")
            continue
        escribir = input(f"    Escribe el título exacto '{nom}' para confirmar: ").strip()
        if escribir != nom:
            print("    El texto no coincide. cancelado.")
            continue
        await client(DeleteChannelRequest(channel=ent))
        log("OK", f"Canal '{nom}' borrado.")
    await client.disconnect()


def main():
    p = argparse.ArgumentParser(description="Gestión de canales/foros para el pipeline")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--crear-canal", metavar="TITULO", help="Crea un canal privado")
    g.add_argument("--archivar", metavar="ID[,ID...]", help="Mueve chats a la carpeta Archivo")
    g.add_argument("--crear-temas", metavar="FORO:T1,T2,...", help="Crea temas en el foro")
    g.add_argument("--listar-temas", metavar="FORO", help="Lista temas de un foro")
    g.add_argument("--migrar", action="append", metavar="FORO:TEMA:ORIGEN", help="Re-subida (repetible)")
    g.add_argument("--borrar-canal", metavar="ID[,ID...]", help="Borra canales (pide confirmación)")
    p.add_argument("--about", default="", help="Descripción del canal")
    p.add_argument("--foro", action="store_true", help="Crea el canal con foro/temas")
    args = p.parse_args()
    try:
        api_id, api_hash = cargar_credenciales()
    except Exception as e:
        print(f"[x] {e}")
        return
    if args.crear_canal:
        asyncio.run(run_crear_canal(api_id, api_hash, args.crear_canal, args.about, args.foro))
    elif args.archivar:
        asyncio.run(run_archivar(api_id, api_hash, [r.strip() for r in args.archivar.split(",") if r.strip()]))
    elif args.crear_temas:
        foro, _, titulos = args.crear_temas.partition(":")
        lista = [t.strip() for t in titulos.split(",") if t.strip()]
        asyncio.run(run_crear_temas(api_id, api_hash, foro, lista))
    elif args.listar_temas:
        asyncio.run(run_listar_temas(api_id, api_hash, args.listar_temas))
    elif args.migrar:
        asyncio.run(run_migrar(api_id, api_hash, args.migrar))
    elif args.borrar_canal:
        asyncio.run(run_borrar(api_id, api_hash, [r.strip() for r in args.borrar_canal.split(",") if r.strip()]))


if __name__ == "__main__":
    main()