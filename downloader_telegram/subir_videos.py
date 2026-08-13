#!/usr/bin/env python3
"""Subir videos comprimidos a grupos de Telegram (Telethon).

Reutiliza las credenciales cifradas en config.bin + secret.key del proyecto
downloader_telegram, pero usa su PROPIA sesion (uploader.session) para no
entrar en conflicto con la sesion del menu interactivo (ultimate_session).

Modos:
  --setup       Iniciar sesion una vez (genera uploader.session).
  --list-chats  Mostrar tus chats/grupos para configurar grupos.json.
  --autoupload  Vigilar CARPETAS/ y subir cada *_compressed.mp4 a los
                grupos de grupos.json. (modo por defecto)
  --once        Procesar una sola pasada y salir (sin bucle).
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from telethon import TelegramClient, events

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = Path(os.environ.get("UPLOADER_CONFIG", SCRIPT_DIR / "config.bin"))
KEY_FILE = Path(os.environ.get("UPLOADER_KEY", SCRIPT_DIR / "secret.key"))
SESION_UPLOADER = os.environ.get("UPLOADER_SESION", str(SCRIPT_DIR / "uploader.session"))
GRUPOS_FILE = Path(os.environ.get("UPLOADER_GRUPOS", SCRIPT_DIR / "grupos.json"))
ENVIADOS_FILE = Path(os.environ.get("UPLOADER_ENVIADOS", SCRIPT_DIR / "enviados.json"))
MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
PARTES_DIR = Path(os.environ.get("UPLOADER_PARTES", SCRIPT_DIR / "partes"))


def cargar_o_generar_llave():
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


def cargar_credenciales():
    """Devuelve (api_id, api_hash). Lee de config.bin cifrado.
    Fallback a variables de entorno UPLOADER_API_ID / UPLOADER_API_HASH
    por si se quieren cambiar credenciales sin tocar config.bin."""
    env_id = os.environ.get("UPLOADER_API_ID")
    env_hash = os.environ.get("UPLOADER_API_HASH")
    if env_id and env_hash:
        return int(env_id), env_hash
    if not CONFIG_FILE.exists():
        raise SystemExit(
            "\n[x] No existe config.bin.\n"
            "  → Configura credenciales con el menú interactivo "
            "(test_download_protected_content_telegram.py)\n"
            "  → o en el contenedor con las envs UPLOADER_API_ID / UPLOADER_API_HASH."
        )
    try:
        cipher = Fernet(cargar_o_generar_llave())
        datos = cipher.decrypt(CONFIG_FILE.read_bytes()).decode("utf-8")
        conf = json.loads(datos)
        return int(conf["api_id"]), conf["api_hash"]
    except Exception as e:
        raise SystemExit(
            f"\n[x] Error leyendo config.bin: {e}\n"
            "  → Las credenciales están corruptas o mal guardadas.\n"
            "  → Reconfigúralas en el menú interactivo o usa las envs "
            "UPLOADER_API_ID / UPLOADER_API_HASH."
        )


def log(tipo, mensaje):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icono = {"INFO": "[i]", "OK": "[v]", "WARN": "[!]", "ERR": "[x]",
             "SUBIR": "[^]", "PART": "[>]"}.get(tipo, "[i]")
    print(f"{ts} {icono} {mensaje}", flush=True)


def cargar_grupos():
    if not GRUPOS_FILE.exists():
        raise SystemExit(
            f"\n[x] No existe {GRUPOS_FILE}.\n"
            "  → Rellena con los chat_id/@usuario de tus grupos.\n"
            "  → Usa --list-chats para descubrirlos."
        )
    try:
        with open(GRUPOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        grupos = data.get("grupos", [])
    except Exception as e:
        raise SystemExit(
            f"\n[x] Error leyendo {GRUPOS_FILE}: {e}\n"
            "  → El JSON está mal formado. Revísalo."
        )
    if not isinstance(grupos, list) or not grupos:
        raise SystemExit(
            f"\n[x] {GRUPOS_FILE} está vacío o mal configurado.\n"
            "  → Debe contener una lista 'grupos' con los chat_id/@usuario."
        )
    return grupos


def cargar_enviados():
    if not ENVIADOS_FILE.exists():
        return []
    try:
        with open(ENVIADOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def guardar_enviados(lista):
    try:
        with open(ENVIADOS_FILE, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
    except OSError as e:
        log("ERR", f"No se pudo guardar enviados.json: {e}")


def enviado(archivo):
    return str(archivo) in cargar_enviados()


def marcar_enviado(archivo):
    lista = cargar_enviados()
    if str(archivo) not in lista:
        lista.append(str(archivo))
    guardar_enviados(lista)
    if archivo.exists():
        try:
            os.remove(archivo)
        except OSError as e:
            log("WARN", f"No se pudo eliminar el archivo ya subido: {e}")


def dividir_video(archivo):
    """Divide un video >2GB en partes numeradas (ffmpeg -c copy, sin recompresión)."""
    log("PART", f"Dividiendo {archivo.name} (>2GB) para Telegram...")
    PARTES_DIR.mkdir(exist_ok=True)
    base = archivo.stem
    ext = archivo.suffix[1:]
    out_pattern = str(PARTES_DIR / f"{base}_part%02d.{ext}")
    cmd = ["ffmpeg", "-y", "-i", str(archivo),
           "-c", "copy", "-map", "0",
           "-f", "segment", "-segment_time", "5400",
           "-reset_timestamps", "1", out_pattern]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log("ERR", f"Error dividiendo: {r.stderr[-400:]}")
        return []
    partes = sorted(PARTES_DIR.glob(f"{base}_part*.{ext}"))
    partes = [p for p in partes if p.stat().st_size > 1024 * 1024]
    return partes


def fotograma(archivo):
    """Genera un thumbnail jpg (necesario para send_file de video)."""
    thumb = archivo.with_suffix(".jpg")
    cmd = ["ffmpeg", "-y", "-ss", "2", "-i", str(archivo),
           "-frames:v", "1", "-vf", "scale=320:-1", str(thumb)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return str(thumb) if r.returncode == 0 and thumb.exists() else None


async def subir_archivo(client, archivo, grupos, caption_base):
    nombre = archivo.name
    try:
        if enviado(archivo):
            log("INFO", f"Ya enviado, saltando: {nombre}")
            return
    except Exception as e:
        log("WARN", f"Error al comprobar enviados: {e}")

    try:
        tamano_mb = archivo.stat().st_size / 1024**2
    except OSError as e:
        log("ERR", f"No se puede acceder a {nombre}: {e}")
        return

    log("SUBIR", f"Subiendo: {nombre} ({tamano_mb:.0f} MB)")
    thumb = None
    try:
        thumb = fotograma(archivo)
    except Exception:
        thumb = None

    # Si supera 2GB, dividir en partes y subir cada parte
    partes = []
    try:
        if archivo.stat().st_size > MAX_BYTES:
            partes = dividir_video(archivo)
            if not partes:
                log("ERR", f"No se pudo dividir {nombre}. Se sube sin dividir (puede fallar por tamaño).")
                partes = [archivo]
        else:
            partes = [archivo]
    except Exception as e:
        log("ERR", f"Error preparando {nombre}: {e}")
        return

    subidos = 0
    for parte in partes:
        for idx, grupo in enumerate(grupos, start=1):
            try:
                await client.send_file(
                    grupo, str(parte),
                    caption=f"{caption_base} {parte.name}",
                    video_note=False,
                    thumb=thumb,
                    progress_callback=lambda c, t: None,
                )
                log("OK", f"  → {grupo} ({idx}/{len(grupos)}) : {parte.name}")
                subidos += 1
            except Exception as e:
                err = str(e)
                if "auth" in err.lower() or "not authorized" in err.lower():
                    log("ERR", f"  → {grupo}: sesión no autorizada — comprueba credenciales/sesión: {e}")
                else:
                    log("ERR", f"  → {grupo} ({parte.name}) falló: {e}")

    if thumb:
        try:
            os.remove(thumb)
        except OSError:
            pass

    if subidos >= len(grupos) * max(1, len(partes)) or subidos >= len(grupos):
        # Se marcó como enviado si al menos llegó a todos los grupos de la 1ª parte
        marcar_enviado(archivo)
    else:
        log("WARN", f"{nombre}: no se completó la subida a todos los grupos. Se reintentará.")


async def run_setup(api_id, api_hash):
    log("INFO", "Modo setup: creará uploader.session (inicio de sesión único).")
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await client.start()
    me = await client.get_me()
    log("OK", f"Sesión uploader creada. Cuenta: {me.first_name} ({me.username})")
    await client.disconnect()


async def run_list_chats(api_id, api_hash):
    log("INFO", "Modo list-chats: mostrando tus chats/grupos.")
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await client.start()
    print("\nID\tTipo\tNombre")
    print("-" * 60)
    async for d in client.iter_dialogs():
        tipo = "grupo" if d.is_group else ("canal" if d.is_channel else "usuario")
        print(f"{d.id}\t{tipo}\t{d.name}")
    print("\nCopia los IDs (negativos para grupos) o @usernames a grupos.json.")
    await client.disconnect()


async def run_autoupload(api_id, api_hash, carpetas, intervalo, una_pasada):
    grupos = cargar_grupos()
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    try:
        await client.start()
    except Exception as e:
        await client.disconnect()
        raise SystemExit(
            f"\n[x] No se pudo conectar con la sesión uploader: {e}\n"
            "  → Si la sesión expiró o es inválida, regenérala:\n"
            "    docker compose run --rm uploader python /app/subir_videos.py --setup"
        )

    log("INFO", f"Vigilando {len(carpetas)} carpeta(s). Grupos: {grupos}")

    def a_carpeta(p):
        pp = Path(p)
        pp.mkdir(parents=True, exist_ok=True)
        return pp

    carpetas = [a_carpeta(c) for c in carpetas]

    while True:
        try:
            for carpeta in carpetas:
                for archivo in sorted(carpeta.glob("*_compressed.mp4")):
                    caption_base = "🎬 Directo sendo sama"
                    await subir_archivo(client, archivo, grupos, caption_base)
        except Exception as e:
            log("ERR", f"Error en la pasada: {e}")
        if una_pasada:
            break
        await asyncio.sleep(intervalo)

    await client.disconnect()
    log("OK", "Pase finalizada.")


def main():
    parser = argparse.ArgumentParser(description="Subir videos comprimidos a grupos de Telegram")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--setup", action="store_true", help="Iniciar sesión una vez (crea uploader.session)")
    grupo.add_argument("--list-chats", action="store_true", help="Listar chats/grupos")
    parser.add_argument("--once", action="store_true", help="Una sola pasada y salir")
    parser.add_argument("--intervalo", type=int, default=int(os.environ.get("UPLOADER_INTERVALO", "60")), help="Segundos entre pasadas (default: 60)")
    parser.add_argument("carpetas", nargs="*", default=os.environ.get("UPLOADER_CARPETAS", "").split(":"), help="Carpetas a vigilar (default: UPLOADER_CARPETAS o /comprimidos)")
    args = parser.parse_args()

    try:
        api_id, api_hash = cargar_credenciales()
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n[x] Error de configuración: {e}")
        return

    try:
        if args.setup:
            asyncio.run(run_setup(api_id, api_hash))
            return
        if args.list_chats:
            asyncio.run(run_list_chats(api_id, api_hash))
            return
        carpetas = [c for c in args.carpetas if c] or ["/comprimidos"]
        asyncio.run(run_autoupload(api_id, api_hash, carpetas, args.intervalo, args.once))
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    except Exception as e:
        print(f"\n[x] Error inesperado: {e}")


if __name__ == "__main__":
    main()