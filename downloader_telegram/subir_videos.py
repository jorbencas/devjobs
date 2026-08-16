#!/usr/bin/env python3
"""Subir videos comprimidos a grupos de Telegram (Telethon).

Reutiliza las credenciales cifradas en config.bin + secret.key del proyecto
downloader_telegram, pero usa su PROPIA sesion (uploader.session) para no
entrar en conflicto con la sesion del menu interactivo (ultimate_session).

Modos:
  --setup       Iniciar sesion una vez (genera uploader.session).
  --list-chats  Mostrar tus chats/grupos para configurar grupos.json.
  --list-topics Listar los temas (series) de un grupo con foro.
  --autoupload  Vigilar CARPETAS/ y subir cada *_compressed.mp4 a los
                grupos de grupos.json (y a los temas de grupo_series).
                (modo por defecto)
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
# Reenvío automático: cuando se sube un vídeo de la keyword indicada, además de
# enviarlo a su(s) grupo(s), se REENVÍA (forward, no re-subida) al canal de solo
# reenvío. Vacío ("") desactiva la función.
FORWARD_CHANNEL = int(os.environ.get("UPLOADER_FORWARD_CHANNEL", "-1004359591062"))
FORWARD_KEYWORD = os.environ.get("UPLOADER_FORWARD_KEYWORD", "diarios_boticaria")


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
    """Carga la config de grupos con ruteo por keyword.

    Formato:
        {
            "default": <id_grupo_fallback>,
            "grupo_series": <id_grupo_con_temas>,                  # opcional
            "temas": [ {"nombre": "serie", "id": <topic>}, ... ],  # opcional
            "grupos": [ {"nombre": "prueba", "id": <id>}, ... ]
        }

    Devuelve (default, grupos, grupo_series, temas) donde:
        - default: id del grupo al que se sube si ninguna keyword coincide
        - grupos: [{nombre, id}]
        - grupo_series: id del grupo donde están los temas (series) o None
        - temas: [{nombre, id}] con los IDs de tema (mensaje raíz del tema)
    """
    if not GRUPOS_FILE.exists():
        raise SystemExit(
            f"\n[x] No existe {GRUPOS_FILE}.\n"
            "  → Rellena con 'default', 'grupos' y opcionalmente "
            "'grupo_series' + 'temas'.\n"
            "  → Usa --list-chats / --list-topics para descubrir los IDs."
        )
    try:
        with open(GRUPOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise SystemExit(
            f"\n[x] Error leyendo {GRUPOS_FILE}: {e}\n"
            "  → El JSON está mal formado. Revísalo."
        )

    grupos = data.get("grupos", [])
    default = data.get("default")
    grupo_series = data.get("grupo_series")
    temas = data.get("temas", [])

    if not isinstance(grupos, list):
        raise SystemExit(
            f"\n[x] {GRUPOS_FILE} está mal configurado.\n"
            "  → 'grupos' debe ser una lista [{nombre, id}]."
        )

    validos = []
    for g in grupos:
        if isinstance(g, dict) and g.get("nombre") and g.get("id"):
            validos.append({"nombre": str(g["nombre"]).lower(), "id": g["id"]})

    temas_validos = []
    if isinstance(temas, list):
        for t in temas:
            if isinstance(t, dict) and t.get("nombre") and t.get("id"):
                temas_validos.append({"nombre": str(t["nombre"]).lower(), "id": t["id"]})

    if not validos and not temas_validos:
        raise SystemExit(
            f"\n[x] {GRUPOS_FILE} no tiene grupos ni temas válidos.\n"
            "  → Cada entrada de 'grupos'/'temas' debe ser "
            "{'nombre': '...', 'id': <id>}."
        )

    if temas_validos and not grupo_series:
        raise SystemExit(
            f"\n[x] {GRUPOS_FILE}: definiste 'temas' pero falta 'grupo_series'.\n"
            "  → Indica el id del grupo donde están los temas: "
            "'grupo_series': <id>."
        )

    return default, validos, grupo_series, temas_validos


def keyword_from_filename(filename: str) -> str:
    """Extrae la keyword del nombre del archivo (*_KW_<keyword>_compressed.mp4)."""
    base = Path(filename).stem
    if "_KW_" in base:
        # ..._KW_<keyword>_compressed -> quitar prefijo y sufijo _compressed
        kw = base.split("_KW_", 1)[1]
        for suffix in ("_compressed", "_completed"):
            if kw.endswith(suffix):
                kw = kw[: -len(suffix)]
        return kw.lower()
    return ""


def canal_from_filename(filename: str) -> str:
    """Extrae el canal del nombre del archivo (primer token, ej.
    'midudev_2026-08-16_18-00-00_..._compressed.mp4' → 'midudev')."""
    base = Path(filename).stem
    canal = base.split("_", 1)[0]
    return canal or ""


def _normalizar_texto(s: str) -> str:
    """Normaliza para comparar: minúsculas, sin tildes, sin signos,
    espacios colapsados y quita una 'y' extra al final (ej. 'cry' vs 'cryy')."""
    import re
    s = s.lower()
    s = s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    s = s.replace("ñ", "n")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"y+$", "y", s)  # 'cryyy' -> 'cry'
    return s


def _entrada_coincide(nombre, kw):
    """¿La keyword del directo coincide con el nombre de un grupo/tema?
    Coincidencia flexible: el 'nombre' (o una palabra significativa del nombre)
    debe aparecer en la keyword, aunque el directo repita letras (ej. 'cryyy').
    También tolera singular/plural y prefijos ('peliculas' ↔ 'pelicula')."""
    nombre = _normalizar_texto(nombre)
    if not nombre:
        return False
    # coincidencia por substring del nombre completo
    if nombre in kw:
        return True
    # coincidencia por palabra significativa del nombre (>= 4 letras)
    palabras = [p for p in nombre.split() if len(p) >= 4]
    if any(p in kw for p in palabras):
        return True
    # coincidencia por prefijo (singular/plural): 'pelicula' ↔ 'peliculas'
    for p in palabras:
        for kw_word in kw.split():
            if len(kw_word) >= 4 and (kw_word.startswith(p) or p.startswith(kw_word)):
                return True
    return False


def grupos_para_keyword(keyword, default, grupos):
    """Elige el(los) grupo(s) según la keyword del directo.
    - Coincidencia flexible con _entrada_coincide.
    - Si no coincide → el grupo 'default' (si existe)."""
    kw = _normalizar_texto(keyword)
    if kw:
        coincidencias = [g["id"] for g in grupos if _entrada_coincide(g["nombre"], kw)]
        if coincidencias:
            return list(dict.fromkeys(coincidencias))

    # Fallback al grupo por defecto
    if default:
        return [default]
    return []


def temas_para_keyword(keyword, temas):
    """Elige el(los) tema(s) (series del grupo con foro) según la keyword.
    Misma coincidencia flexible que los grupos. Devuelve lista de topic IDs."""
    kw = _normalizar_texto(keyword)
    if not kw:
        return []
    coincidencias = [t["id"] for t in temas if _entrada_coincide(t["nombre"], kw)]
    return list(dict.fromkeys(coincidencias))


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
    """Divide un video >2GB en partes numeradas (ffmpeg -c copy, sin recompresión).

    Cada parte se genera con -movflags +faststart (moov al inicio) para que
    Telegram pueda reproducirla en línea sin obligar a descargarla. NO se usa
    -f segment: el muxer de segmentos ignora +faststart y deja el moov al final.
    """
    log("PART", f"Dividiendo {archivo.name} (>2GB) para Telegram...")
    PARTES_DIR.mkdir(exist_ok=True)
    base = archivo.stem
    ext = archivo.suffix[1:] or "mp4"
    dur_out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(archivo)],
        capture_output=True, text=True)
    try:
        duracion = float(dur_out.stdout.strip())
    except (ValueError, AttributeError):
        duracion = 0.0
    if not duracion or duracion <= 0:
        log("ERR", f"No se pudo obtener duración de {archivo.name}; no se divide.")
        return []
    paso = 5400  # 90 minutos por parte
    partes = []
    idx = 1
    inicio = 0.0
    while inicio < duracion:
        parte = PARTES_DIR / f"{base}_part{idx:02d}.{ext}"
        cmd = ["ffmpeg", "-y", "-ss", str(int(inicio)), "-i", str(archivo),
               "-t", str(paso), "-c", "copy", "-map", "0",
               "-movflags", "+faststart", str(parte)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            log("ERR", f"Error dividiendo: {r.stderr[-400:]}")
            break
        if not parte.exists() or parte.stat().st_size <= 1024 * 1024:
            parte.unlink(missing_ok=True)
            break
        partes.append(parte)
        idx += 1
        inicio += paso
    return partes


def episodios_desde_json(archivo):
    """Lee la descripción de episodios/temporada de la metadata que genera
    el monitor ('<name>_episodios.json' junto al comprimido). Evita repetir
    el OCR. Devuelve la cadena 'descripcion' (p. ej. 'Episodio 1-4' o
    'Temporada 2 · Episodio 1-4') o '' si no hay metadata."""
    meta = archivo.with_name(archivo.stem.replace("_compressed", "_episodios") + ".json")
    if not meta.exists():
        return ""
    try:
        with open(meta, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("descripcion", "") or data.get("rango", "") or ""
    except (OSError, json.JSONDecodeError):
        return ""


def caption_sin_episodio(texto):
    """Caption de Telegram sin la palabra 'Episodio(s)' cuando el texto ES un
    rango de episodios (p. ej. 'Episodio 1-4' → '1-4', 'Temporada 2 · Episodio 1-4'
    → 'Temporada 2 · 1-4'). No toca descripciones libres (p. ej. las de YouTube),
    que podrían contener 'episodio' como palabra normal."""
    if not texto:
        return texto
    import re
    if not re.match(r"(?i)^\s*(temporada\s*\d+\s*[·\-\|]\s*)?episodio(s)?\s*\d", texto):
        return texto
    return re.sub(r"\s+", " ", re.sub(r"(?i)\bepisodio(s)?\b", "", texto)).strip()


def detectar_episodios(archivo):
    """Detecta el contenido de la franja superior (episodios/temporada o
    película) mediante OCR de varios frames.

    Escanea el vídeo con un paso (3 min por defecto, configurable con
    UPLOADER_OCR_STEP), recorta la franja superior, hace OCR y:
      - Si aparecen 'EPISODIO/CAPÍTULO N' (opcionalmente con 'TEMPORADA N'),
        devuelve 'Episodio 1-4' o 'Temporada 2 · Episodio 1-4'.
      - Si aparece 'película', devuelve 'Película · TÍTULO' (por frecuencia
        de palabras de la franja).
      - Si no detecta nada, ''.
    Necesita ffmpeg y tesseract-ocr (con tesseract-ocr-data-eng) disponibles."""
    import re
    from collections import Counter
    paso = int(os.environ.get("UPLOADER_OCR_STEP", "180"))
    try:
        dur_out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(archivo)],
            capture_output=True, text=True)
        dur = float(dur_out.stdout.strip()) if dur_out.stdout.strip() else 0
    except Exception:
        return ""
    if not dur or dur <= 0:
        return ""

    STOP = {
        "episodio", "episodios", "capitulo", "capitulos", "capítulo", "capítulos",
        "temporada", "temp", "pelicula", "peliculas", "película", "películas",
        "la", "el", "los", "las", "de", "en", "y", "a", "que",
    }
    episodios = set()
    temporadas = set()
    pelicula_times = 0
    palabras = Counter()
    muestras = 0
    tmp = Path("/tmp") / (archivo.stem + "_ep")
    n = 0
    t = 0
    while t < dur:
        img = str(tmp) + f"_{n}.png"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(t), "-i", str(archivo),
                 "-frames:v", "1", "-vf", "crop=iw:ih*0.2:0:0,scale=iw*2:-1",
                 "-q:v", "2", img],
                capture_output=True, text=True, check=True)
            ocr = subprocess.run(
                ["tesseract", img, "stdout", "-l", "eng"],
                capture_output=True, text=True)
            texto = ocr.stdout
            texto_bajo = texto.lower()
            for m in re.finditer(r"(?:episodio|cap[ií]tulo)\s*(\d+)", texto, re.IGNORECASE):
                episodios.add(int(m.group(1)))
            for m in re.finditer(r"(?:temporada|temp)[a-z]*\s*(\d+)", texto, re.IGNORECASE):
                temporadas.add(int(m.group(1)))
            if re.search(r"pel[ií]cula", texto_bajo):
                pelicula_times += 1
            for m in re.finditer(r"[a-záéíóúñü]{3,}", texto_bajo):
                w = m.group(0)
                if w not in STOP:
                    palabras[w] += 1
            muestras += 1
        except Exception:
            pass
        finally:
            try:
                Path(img).unlink(missing_ok=True)
            except OSError:
                pass
        n += 1
        t = n * paso

    if pelicula_times >= 2:
        umbral = max(3, int(muestras * 0.25))
        orden = [w for w, c in palabras.most_common() if c >= umbral]
        titulo = " ".join(orden).upper()
        return f"Película · {titulo}" if titulo else "Película"

    if not episodios:
        return ""
    episodios = sorted(episodios)
    grupos = []
    inicio = prev = episodios[0]
    for e in episodios[1:]:
        if e == prev + 1:
            prev = e
        else:
            grupos.append(str(inicio) if inicio == prev else f"{inicio}-{prev}")
            inicio = prev = e
    grupos.append(str(inicio) if inicio == prev else f"{inicio}-{prev}")
    rango = ", ".join(grupos)
    if temporadas:
        rango = f"Temporada {min(temporadas)} · Episodio {rango}"
    return rango


def fotograma(archivo):
    """Genera un thumbnail jpg (necesario para send_file de video)."""
    thumb = archivo.with_suffix(".jpg")
    cmd = ["ffmpeg", "-y", "-ss", "2", "-i", str(archivo),
           "-frames:v", "1", "-vf", "scale=320:-1", str(thumb)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return str(thumb) if r.returncode == 0 and thumb.exists() else None


async def subir_archivo(client, archivo, destinos, caption_base, keyword=""):
    """Sube 'archivo' a cada destino de 'destinos'.

    Cada destino es una tupla (grupo, topico) donde:
        - grupo: id del chat (o username)
        - topico: id del tema (mensaje raíz) si es un grupo con foro, o None.
    """
    nombre = archivo.name
    try:
        if enviado(archivo):
            log("INFO", f"Ya enviado, saltando: {nombre}")
            return
    except Exception as e:
        log("WARN", f"Error al comprobar enviados: {e}")

    # ¿Reenviar este vídeo al canal de solo-reenvío?
    kw_norm = _normalizar_texto(keyword)
    reenviar = bool(FORWARD_CHANNEL) and bool(FORWARD_KEYWORD) and FORWARD_KEYWORD in kw_norm
    if reenviar:
        log("INFO", f"{nombre}: keyword '{keyword}' → se reenviará a {FORWARD_CHANNEL}")

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
    total_partes = len(partes)
    for i, parte in enumerate(partes, start=1):
        # Si el vídeo se parte (por superar 2 GB), cada parte indica cuál es:
        # p. ej. '1-4 (1/2)' y '1-4 (2/2)'.
        cap = caption_base
        if total_partes > 1:
            cap = f"{caption_base} ({i}/{total_partes})"
        enviado_msg = None
        for idx, (grupo, topico) in enumerate(destinos, start=1):
            ref = f" → tema {topico}" if topico else ""
            try:
                msg = await client.send_file(
                    grupo, str(parte),
                    caption=cap,
                    video_note=False,
                    thumb=thumb,
                    reply_to=topico,
                    progress_callback=lambda c, t: None,
                )
                if enviado_msg is None:
                    enviado_msg = msg
                log("OK", f"  → {grupo}{ref} ({idx}/{len(destinos)}) : {parte.name}")
                subidos += 1
            except Exception as e:
                err = str(e)
                if "auth" in err.lower() or "not authorized" in err.lower():
                    log("ERR", f"  → {grupo}{ref}: sesión no autorizada — comprueba credenciales/sesión: {e}")
                else:
                    log("ERR", f"  → {grupo}{ref} ({parte.name}) falló: {e}")
        if reenviar and enviado_msg is not None:
            try:
                # Reenvío nativo: instantáneo (copia en servidor, no re-subir)
                await client.forward_messages(FORWARD_CHANNEL, messages=enviado_msg)
                log("OK", f"  ↪ reenviado al canal {FORWARD_CHANNEL}: {parte.name}")
            except Exception as e:
                log("ERR", f"  ↪ falló el reenvío a {FORWARD_CHANNEL} ({parte.name}): {e}")

    if thumb:
        try:
            os.remove(thumb)
        except OSError:
            pass

    if subidos >= len(destinos) * max(1, len(partes)) or subidos >= len(destinos):
        # Se marcó como enviado si al menos llegó a todos los destinos de la 1ª parte
        marcar_enviado(archivo)
    else:
        log("WARN", f"{nombre}: no se completó la subida a todos los destinos. Se reintentará.")


async def _conectar(client, pedir_login=False):
    """Conecta y comprueba si la sesión está autenticada.
    - Si ya hay sesión logueada: reutiliza (nunca vuelve a pedir credenciales).
    - Si NO hay sesión válida y pedir_login=False: avisa y sale (modo no interactivo).
    - Si pedir_login=True (--setup): hace el login interactivo (teléfono + código)."""
    await client.connect()
    if await client.is_user_authorized():
        return True
    if not pedir_login:
        raise SystemExit(
            "\n[x] No hay sesión de Telegram autenticada (o está vencida).\n"
            f"  → Archivo de sesión: {SESION_UPLOADER}\n"
            "  → Inicia sesión una vez con: python subir_videos.py --setup"
        )
    return False


async def run_setup(api_id, api_hash):
    log("INFO", "Modo setup: creará uploader.session (inicio de sesión único).")
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    if await _conectar(client):
        me = await client.get_me()
        log("OK", f"Sesión ya autenticada. Cuenta: {me.first_name} ({me.username}) → no hace falta loguear de nuevo.")
        await client.disconnect()
        return
    await client.start()
    me = await client.get_me()
    log("OK", f"Sesión uploader creada. Cuenta: {me.first_name} ({me.username})")
    await client.disconnect()


async def run_list_chats(api_id, api_hash, folder=None, creados=False):
    log("INFO", "Modo list-chats: mostrando tus chats/grupos.")
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    print("\nID\tTipo\tNombre\tCarpeta\t¿Creado por ti?\t¿Foro?")
    print("-" * 90)
    count = 0
    async for d in client.iter_dialogs():
        fid = getattr(d, "folder_id", None)
        f_title = "Archivado" if fid == 1 else ("Principal" if fid in (None, 0) else f"#{fid}")
        ent = getattr(d, "entity", None)
        creado = bool(getattr(ent, "creator", False)) if ent is not None else False
        if folder:
            f = folder.strip().lower()
            if f != f_title.lower() and f not in (d.name or "").lower():
                continue
        if creados and not creado:
            continue
        tipo = "grupo" if getattr(d, "is_group", False) else ("canal" if getattr(d, "is_channel", False) else "usuario")
        forum = "sí" if (ent is not None and getattr(ent, "forum", False)) else ""
        print(f"{d.id}\t{tipo}\t{d.name}\t{f_title}\t{'sí' if creado else 'no'}\t{forum}")
        count += 1
    print(f"\n{count} chats mostrados.")
    print("Copia los IDs (negativos para grupos/canales) o @usernames a grupos.json.")
    print("Los grupos con '¿Foro? = sí' admiten temas: usa --list-topics <id> para verlos.")
    await client.disconnect()


async def run_list_topics(api_id, api_hash, grupo):
    """Lista los temas (series) de un grupo con foro activado."""
    from datetime import datetime as dt

    from telethon.tl.functions.channels import GetForumTopicsRequest

    log("INFO", f"Modo list-topics: mostrando temas de {grupo}.")
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    try:
        await _conectar(client)
    except SystemExit:
        await client.disconnect()
        raise
    try:
        chat = await client.get_entity(grupo)
    except Exception as e:
        log("ERR", f"No se pudo resolver el grupo '{grupo}': {e}")
        await client.disconnect()
        return
    try:
        res = await client(GetForumTopicsRequest(
            channel=chat,
            offset_date=dt(1970, 1, 1),
            offset_id=0,
            offset_topic=0,
            limit=100,
        ))
    except Exception as e:
        log("ERR", f"'{grupo}' no es un grupo con temas (foro): {e}")
        await client.disconnect()
        return
    print(f"\nTemas de {grupo}:")
    print("ID\tTítulo")
    print("-" * 60)
    for t in res.topics:
        print(f"{t.id}\t{t.title}")
    print(f"\n{len(res.topics)} de {res.count} temas mostrados.")
    print("Usa esos IDs en 'temas' de grupos.json (junto a 'grupo_series': id del grupo).")
    await client.disconnect()


async def run_autoupload(api_id, api_hash, carpetas, intervalo, una_pasada):
    default, grupos, grupo_series, temas = cargar_grupos()
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    try:
        await _conectar(client)
    except SystemExit:
        await client.disconnect()
        raise
    except Exception as e:
        await client.disconnect()
        raise SystemExit(
            f"\n[x] No se pudo conectar con la sesión uploader: {e}\n"
            "  → Si la sesión expiró o es inválida, regenérala:\n"
            "    docker compose run --rm uploader python /app/subir_videos.py --setup"
        )

    info_series = f", temas en {grupo_series}: {len(temas)}" if grupo_series else ""
    log("INFO", f"Vigilando {len(carpetas)} carpeta(s). Grupos: {len(grupos)}, default: {default}{info_series}")

    def a_carpeta(p):
        pp = Path(p)
        pp.mkdir(parents=True, exist_ok=True)
        return pp

    carpetas = [a_carpeta(c) for c in carpetas]

    while True:
        try:
            for carpeta in carpetas:
                for archivo in sorted(carpeta.glob("*_compressed.mp4")):
                    keyword = keyword_from_filename(archivo.name)
                    destinos = [(g, None) for g in grupos_para_keyword(keyword, default, grupos)]
                    if grupo_series and temas:
                        destinos += [(grupo_series, t) for t in temas_para_keyword(keyword, temas)]
                        episodios = episodios_desde_json(archivo)
                        if not episodios:
                            episodios = detectar_episodios(archivo)
                            log("INFO", f"{archivo.name}: OCR de episodios realizado")
                        # Si el contenido detectado es una película, enrutar también
                        # al tema que coincida (p. ej. 'peliculas'), aunque la keyword
                        # del título no la mencione.
                        if episodios:
                            destinos += [(grupo_series, t) for t in temas_para_keyword(str(episodios), temas)]
                        destinos = list(dict.fromkeys(destinos))
                    if not destinos:
                        log("WARN", f"{archivo.name}: sin keyword, sin grupo default ni tema. Se omite.")
                        continue
                    log("INFO", f"{archivo.name}: keyword='{keyword}' → {destinos}")
                    if episodios:
                        # Routing con el texto completo; el caption se muestra
                        # sin la palabra 'Episodio' (p. ej. '1-4').
                        caption_base = caption_sin_episodio(str(episodios))
                        log("INFO", f"{archivo.name}: episodio(s): {episodios} → caption '{caption_base}'")
                    else:
                        canal = canal_from_filename(archivo.name)
                        caption_base = f"🎬 Directo de {canal}" if canal else "🎬 Directo"
                        log("WARN", f"{archivo.name}: sin episodios ni descripción, caption por defecto")
                    await subir_archivo(client, archivo, destinos, caption_base, keyword)
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
    grupo.add_argument("--list-topics", metavar="GRUPO", help="Listar los temas (series) de un grupo con foro")
    parser.add_argument("--folder", help="Filtrar por nombre del chat o carpeta (archivado/principal) (--list-chats)")
    parser.add_argument("--creados", action="store_true", help="Solo chats que creaste tú (--list-chats)")
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
            asyncio.run(run_list_chats(api_id, api_hash, args.folder, args.creados))
            return
        if args.list_topics:
            asyncio.run(run_list_topics(api_id, api_hash, args.list_topics))
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