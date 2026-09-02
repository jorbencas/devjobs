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
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeVideo,
)

try:
    from pipeline_bridge import update_status, remove_status, append_log
except ImportError:
    update_status = remove_status = append_log = None

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
CONFIG_FILE = Path(os.environ.get("UPLOADER_CONFIG", REPO_DIR / "config" / "config.bin"))
KEY_FILE = Path(os.environ.get("UPLOADER_KEY", REPO_DIR / "config" / "secret.key"))
SESION_UPLOADER = os.environ.get("UPLOADER_SESION", str(REPO_DIR / "sessions" / "uploader.session"))
GRUPOS_FILE = Path(os.environ.get("UPLOADER_GRUPOS", REPO_DIR / "config" / "grupos.json"))
ENVIADOS_FILE = Path(os.environ.get("UPLOADER_ENVIADOS", REPO_DIR / "config" / "enviados.json"))
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
            "default": <id_grupo_fallback>,        # opcional, red de seguridad
            "grupos": [ {"nombre": "prueba", "id": <id>}, ... ],  # chats sueltos
            "foros": [                              # grupos/foros con temas
                {
                    "id": <id_chat_con_foro>,
                    "nombre": "sendo",
                    "general": <id_tema_general>,   # tema al que van los no matcheados
                    "temas": [ {"nombre": "serie", "id": <topic>}, ... ]
                },
                ...
            ]
        }

    Backward-compatible: si se definen 'grupo_series' + 'temas' (formato antiguo)
    se envuelven como un único foro (catch-all).

    Devuelve (default, grupos, foros) donde:
        - default: id del grupo al que se sube si ninguna keyword coincide
        - grupos: [{nombre, id}] (chats sueltos)
        - foros: [{id, nombre, general, temas}] o [] si no hay
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
    foros_raw = data.get("foros")

    if not isinstance(grupos, list):
        raise SystemExit(
            f"\n[x] {GRUPOS_FILE} está mal configurado.\n"
            "  → 'grupos' debe ser una lista [{nombre, id}]."
        )

    validos = []
    for g in grupos:
        if isinstance(g, dict) and g.get("nombre") and g.get("id"):
            validos.append({"nombre": str(g["nombre"]).lower(), "id": g["id"]})

    foros = []
    if foros_raw:
        for f in foros_raw:
            if not isinstance(f, dict) or not f.get("id"):
                continue
            temas_f = []
            for t in (f.get("temas") or []):
                if isinstance(t, dict) and t.get("nombre") and t.get("id"):
                    temas_f.append({"nombre": str(t["nombre"]).lower(), "id": t["id"]})
            foros.append({
                "id": f["id"],
                "nombre": str(f.get("nombre") or f["id"]),
                "general": f.get("general"),
                "temas": temas_f,
            })
    else:
        # Backward-compatible: formato antiguo grupo_series + temas
        grupo_series = data.get("grupo_series")
        temas = data.get("temas", [])
        temas_validos = []
        if isinstance(temas, list):
            for t in temas:
                if isinstance(t, dict) and t.get("nombre") and t.get("id"):
                    temas_validos.append({"nombre": str(t["nombre"]).lower(), "id": t["id"]})
        if temas_validos and not grupo_series:
            raise SystemExit(
                f"\n[x] {GRUPOS_FILE}: definiste 'temas' pero falta 'grupo_series'.\n"
                "  → Indica el id del grupo donde están los temas: "
                "'grupo_series': <id>."
            )
        if grupo_series:
            foros.append({
                "id": grupo_series,
                "nombre": str(grupo_series),
                "general": None,
                "temas": temas_validos,
            })

    if not validos and not foros:
        raise SystemExit(
            f"\n[x] {GRUPOS_FILE} no tiene grupos ni foros/temas válidos.\n"
            "  → Cada entrada debe ser {'nombre': '...', 'id': <id>} y/o "
            "'foros' con sus temas."
        )

    return default, validos, foros


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


def match_tema_foro(foro, *textos):
    """Primer tema del foro que coincide con cualquiera de los textos (canal,
    keyword...). Devuelve el topic ID o None si ninguno coincide."""
    for texto in textos:
        if not texto:
            continue
        m = temas_para_keyword(texto, foro.get("temas") or [])
        if m:
            return m[0]
    return None


def foro_objetivo(foros, canal):
    """Elige el foro por defecto (catch-all) para un vídeo cuyo canal no
    ha coincidido con ningún tema. Usa el primer foro de la lista (o None)."""
    if not foros:
        return None
    return foros[0]


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
    # Poda automática: mantener solo las N últimas subidas (default 15) para que
    # enviados.json no crezca indefinidamente. El límite es configurable con
    # UPLOADER_MAX_ENVIADOS (0 = sin límite).
    max_enviados = int(os.environ.get("UPLOADER_MAX_ENVIADOS", "15"))
    if max_enviados > 0 and len(lista) > max_enviados:
        podados = lista[:len(lista) - max_enviados]
        lista = lista[len(lista) - max_enviados:]
        log("LIMP", f"enviados.json podado: {len(podados)} entrada(s) antigua(s) eliminadas")
    guardar_enviados(lista)
    if archivo.exists():
        try:
            os.remove(archivo)
        except OSError as e:
            log("WARN", f"No se pudo eliminar el archivo ya subido: {e}")
    limpiar_restos(archivo)


def limpiar_restos(archivo):
    """Tras subir un archivo, elimina TODOS sus restos de /comprimidos:
    1) el sidecar '<nombre>_episodios.json' generado por el monitor,
    2) el original de .processed (ya subido a Telegram),
    3) los logs completos (log_*.txt): residuos de procesamiento,
    4) las partes divididas en PARTES_DIR (si el vídeo >2GB).
    Objetivo: al terminar la subida no debe quedar nada residual.
    """
    base = archivo.stem.replace("_compressed", "")

    sidecar = archivo.with_name(base + "_episodios.json")
    for resto, nombre in ((sidecar, "sidecar"),):
        try:
            if resto.exists():
                resto.unlink()
                log("LIMP", f"Eliminado {nombre}: {resto.name}")
        except OSError as e:
            log("WARN", f"No se pudo eliminar {nombre} {resto.name}: {e}")

    # 3) Borrar el original de .processed (ya subido)
    proc_dir = archivo.parent / ".processed"
    try:
        if proc_dir.exists():
            candidatos = [p for p in proc_dir.glob("*")
                          if p.is_file() and p.name.startswith(base)]
            for p in candidatos:
                try:
                    p.unlink()
                    log("LIMP", f"Eliminado .processed: {p.name}")
                except OSError as e:
                    log("WARN", f"No se pudo eliminar .processed {p.name}: {e}")
    except OSError as e:
        log("WARN", f"No se pudo acceder a {proc_dir}: {e}")

    # 3) Borrar los logs completos (residuos del procesamiento)
    for log_file in archivo.parent.glob("log_*.txt"):
        try:
            log_file.unlink()
            log("LIMP", f"Eliminado log: {log_file.name}")
        except OSError as e:
            log("WARN", f"No se pudo eliminar log {log_file.name}: {e}")

    # 4) Borrar las partes divididas del vídeo (si >2GB)
    try:
        if PARTES_DIR.exists():
            for p in PARTES_DIR.glob(f"{base}_part*"):
                try:
                    p.unlink()
                    log("LIMP", f"Eliminada parte: {p.name}")
                except OSError as e:
                    log("WARN", f"No se pudo eliminar parte {p.name}: {e}")
    except OSError as e:
        log("WARN", f"No se pudo acceder a {PARTES_DIR}: {e}")



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
        return data.get("titulo", "") or data.get("descripcion", "") or data.get("rango", "") or ""
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


def es_rango_episodios(texto):
    """True si el texto describre un rango de episodios/temporada (p. ej.
    'Episodio 1-4', 'Temporada 2 · Episodio 1-4'). False para descripciones
    libres (p. ej. la propia del canal de YouTube). Se usa para decidir si la
    metadata sirve como caption o cae al nombre del canal."""
    if not texto:
        return False
    import re
    return bool(re.match(r"(?i)^\s*(temporada\s*\d+\s*[·\-\|]\s*)?episodio(s)?\s*\d", texto))


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


def atributos_video(archivo):
    """Genera los attributes de vídeo correctos para send_file usando ffprobe.

    Sin 'hachoir' instalado, Telethon no analiza el archivo y envía
    w=1/h=1/duration=0 con supports_streaming=False → Telegram lo muestra
    como documento ilegible. Con estos attributes explícitos (duración y
    dimensiones reales + supports_streaming=True) se reproduce en línea.
    """
    r = subprocess.run(
        ["ffprobe", "-v", "error",
         "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration:format=duration",
         "-of", "json", str(archivo)],
        capture_output=True, text=True)
    w = h = 1
    duracion = 0.0
    try:
        data = json.loads(r.stdout)
        stream = data.get("streams", [{}])[0]
        w = int(stream.get("width") or 1)
        h = int(stream.get("height") or 1)
        dur = stream.get("duration") or data.get("format", {}).get("duration")
        duracion = float(dur) if dur else 0.0
    except (ValueError, TypeError, IndexError):
        pass
    return [
        DocumentAttributeVideo(
            duration=int(round(duracion)),
            w=w, h=h,
            round_message=False,
            supports_streaming=True,
        ),
        DocumentAttributeFilename(archivo.name),
    ]


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
    forward_kw = _normalizar_texto(FORWARD_KEYWORD)
    reenviar = bool(FORWARD_CHANNEL) and bool(forward_kw) and forward_kw in kw_norm
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
                    attributes=atributos_video(parte),
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

    from telethon.tl.functions.messages import GetForumTopicsRequest

    log("INFO", f"Modo list-topics: mostrando temas de {grupo}.")
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    try:
        await _conectar(client)
    except SystemExit:
        await client.disconnect()
        raise
    try:
        target = int(grupo)
    except (TypeError, ValueError):
        target = None

    chat = None
    async for d in client.iter_dialogs():
        ent = getattr(d, "entity", None)
        if ent is None:
            continue
        if target is not None:
            if getattr(d, "id", None) == target:
                chat = ent
                break
        elif (d.name or "").strip().lower() == str(grupo).strip().lower():
            chat = ent
            break
    if chat is None:
        log("ERR", f"No se encontró el grupo '{grupo}' en los diálogos de la sesión.")
        await client.disconnect()
        return
    try:
        res = await client(GetForumTopicsRequest(
            peer=chat,
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


async def run_create_topics(api_id, api_hash, grupo, titulos):
    """Crea temas (series) nuevos en un grupo con foro."""
    from telethon.tl.functions.messages import CreateForumTopicRequest
    log("INFO", f"Creando {len(titulos)} temas en {grupo}.")
    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    await _conectar(client)
    try:
        target = int(grupo)
    except (TypeError, ValueError):
        target = None
    chat = None
    async for d in client.iter_dialogs():
        if target is not None and getattr(d, "id", None) == target:
            chat = getattr(d, "entity", None)
            break
    if chat is None:
        log("ERR", f"No se encontró el grupo '{grupo}' en los diálogos.")
        await client.disconnect()
        return
    for i, titulo in enumerate(titulos):
        try:
            res = await client(CreateForumTopicRequest(
                peer=chat,
                title=titulo,
                random_id=int(asyncio.get_event_loop().time() * 1000) + i,
            ))
            tid = getattr(res.updates[0], "message", None)
            tid = getattr(tid, "id", None)
            log("OK", f"Tema creado: {titulo} (id={tid})")
        except Exception as e:
            log("ERR", f"Fallo al crear '{titulo}': {e}")
    await client.disconnect()


async def run_delete_videos(api_id, api_hash, grupo, topic_ids=None, dry_run=False, channel_filter=None, force=False):
    """Elimina todos los mensajes de vídeo de un grupo (o de topics específicos).

    Flujo de seguridad:
      1. Primer escaneo: lista todos los videos sin eliminar nada
      2. Pide confirmación numérica al usuario (cantidad exacta)
      3. Segunda confirmación: "ESCRIBE EL NÚMERO para confirmar"
      4. Solo entonces procede a borrar

    Args:
        grupo: ID del grupo de Telegram
        topic_ids: Lista de topic IDs a limpiar (None = todos los topics)
        dry_run: Si es True, solo muestra los mensajes sin eliminar
        channel_filter: Lista de nombres de canal a filtrar (None = todos)
        force: Si es True, salta las confirmaciones interactivas
    """
    from telethon.tl.types import DocumentAttributeFilename

    log("INFO", f"Modo delete-videos: escaneando grupo {grupo}"
        + (f" (topics: {topic_ids})" if topic_ids else " (todos los topics)")
        + (f" (canales: {channel_filter})" if channel_filter else ""))

    client = TelegramClient(SESION_UPLOADER, api_id, api_hash)
    try:
        await _conectar(client)
    except SystemExit:
        await client.disconnect()
        raise

    try:
        target = int(grupo)
    except (TypeError, ValueError):
        log("ERR", f"ID de grupo inválido: {grupo}")
        await client.disconnect()
        return

    # Buscar la entidad del chat
    chat = None
    async for d in client.iter_dialogs():
        if getattr(d, "id", None) == target:
            chat = getattr(d, "entity", None)
            break

    if chat is None:
        log("ERR", f"No se encontró el grupo '{grupo}' en los diálogos.")
        await client.disconnect()
        return

    chat_title = getattr(chat, "title", str(grupo))
    log("OK", f"Grupo encontrado: {chat_title}")

    # ── PASO 1: Escaneo completo (sin borrar nada) ──
    video_msgs = []
    async for msg in client.iter_messages(chat, limit=None):
        if msg.video is None:
            continue
        if topic_ids:
            msg_topic = getattr(msg, "message_thread_id", None)
            if msg_topic not in topic_ids:
                continue

        # Obtener filename del video para filtrar por canal
        filename = ""
        if msg.video and msg.video.attributes:
            for attr in msg.video.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name or ""
                    break

        caption = msg.message or ""

        # Filtrar por canal si se especifica
        if channel_filter:
            match = False
            for ch in channel_filter:
                ch_lower = ch.lower()
                if ch_lower in filename.lower() or ch_lower in caption.lower():
                    match = True
                    break
            if not match:
                continue

        video_msgs.append((msg, filename, caption))

    total = len(video_msgs)
    if total == 0:
        log("OK", "No se encontraron videos. Nada que eliminar.")
        await client.disconnect()
        return

    # Mostrar resumen del escaneo
    log("WARN", f"═══════════════════════════════════════════════════")
    log("WARN", f"  VIDEOS ENCONTRADOS: {total}")
    log("WARN", f"  Grupo: {chat_title} ({grupo})")
    if topic_ids:
        log("WARN", f"  Topics: {topic_ids}")
    if channel_filter:
        log("WARN", f"  Filtro de canal: {channel_filter}")
    log("WARN", f"═══════════════════════════════════════════════════")

    for i, (msg, filename, caption) in enumerate(video_msgs[:30], 1):
        topic_id = getattr(msg, "message_thread_id", None)
        topic_info = f"topic={topic_id}" if topic_id else "general"
        date_str = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "?"
        name_display = filename[:60] if filename else (caption[:60] if caption else "(sin nombre)")
        log("WARN", f"  {i:3d}. msg={msg.id} | {topic_info} | {date_str} | {name_display}")
    if total > 30:
        log("WARN", f"  ... y {total - 30} más")

    if dry_run:
        log("OK", f"[DRY-RUN] Se eliminarían {total} videos. No se borró nada.")
        await client.disconnect()
        return

    # ── PASO 2: Confirmación (saltada con --force) ──
    if not force:
        log("WARN", "")
        log("WARN", f"⚠  Vas a ELIMINAR {total} videos de '{chat_title}'")
        log("WARN", "   Esta acción es IRREVERSIBLE.")
        log("WARN", "")
        try:
            confirm1 = input(f"   Escribe S para continuar o N para cancelar: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            log("INFO", "Cancelado por el usuario.")
            await client.disconnect()
            return

        if confirm1 != "S":
            log("INFO", "Cancelado. No se eliminó nada.")
            await client.disconnect()
            return

        # ── PASO 3: Segunda confirmación (escribir el número exacto) ──
        log("WARN", "")
        log("WARN", f"   Para confirmar, escribe el número EXACTO de videos: {total}")
        log("WARN", "")
        try:
            confirm2 = input(f"   Escribe {total} para confirmar: ").strip()
        except (EOFError, KeyboardInterrupt):
            log("INFO", "Cancelado por el usuario.")
            await client.disconnect()
            return

        if confirm2 != str(total):
            log("ERR", f"Cancelado. Se esperaba '{total}', se recibió '{confirm2}'. No se eliminó nada.")
            await client.disconnect()
            return
    else:
        log("WARN", f"[FORCE] Eliminando {total} videos (confirmación omitida con --force)")

    # ── PASO 4: Eliminación ──
    log("WARN", "")
    log("WARN", "   Confirmed. Eliminando videos...")
    log("WARN", "")

    deleted = 0
    errors = 0
    for i, (msg, filename, caption) in enumerate(video_msgs, 1):
        topic_id = getattr(msg, "message_thread_id", None)
        topic_info = f"topic={topic_id}" if topic_id else "general"
        try:
            await client.delete_messages(chat, [msg.id])
            deleted += 1
            log("OK", f"  [{i}/{total}] Eliminado msg {msg.id}: {topic_info}")
        except Exception as e:
            errors += 1
            log("ERR", f"  [{i}/{total}] Error msg {msg.id}: {e}")

    log("WARN", "")
    log("WARN", f"═══════════════════════════════════════════════════")
    log("OK",   f"  ELIMINADOS: {deleted}/{total}")
    if errors:
        log("ERR", f"  ERRORES: {errors}")
    log("WARN", f"═══════════════════════════════════════════════════")

    await client.disconnect()


async def run_autoupload(api_id, api_hash, carpetas, intervalo, una_pasada):
    default, grupos, foros = cargar_grupos()
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

    info_foros = f", foros: {[f['nombre'] for f in foros]}" if foros else ""
    log("INFO", f"Vigilando {len(carpetas)} carpeta(s). Grupos: {len(grupos)}, default: {default}{info_foros}")

    def a_carpeta(p):
        pp = Path(p)
        pp.mkdir(parents=True, exist_ok=True)
        return pp

    carpetas = [a_carpeta(c) for c in carpetas]

    while True:
        try:
            for carpeta in carpetas:
                for archivo in sorted(carpeta.glob("*_compressed.*")):
                    if archivo.suffix.lower() not in (".mp4", ".mkv", ".webm", ".mov", ".avi"):
                        continue
                    keyword = keyword_from_filename(archivo.name)
                    canal = canal_from_filename(archivo.name)
                    destinos = [(g, None) for g in grupos_para_keyword(keyword, default, grupos)]
                    episodios = episodios_desde_json(archivo)

                    if foros:
                        if not episodios:
                            episodios = detectar_episodios(archivo)
                            log("INFO", f"{archivo.name}: OCR de episodios realizado")
                        # El tema del foro actúa como clave (sin lista canales):
                        #  1) Si el canal del archivo coincide con un tema → ese
                        #     foro/tema (p.ej. 'midudev' → tema 'midu').
                        #  2) Si no, al foro por defecto (catch-all) matcheando la
                        #     keyword o episodios; si tampoco, al tema 'general'.
                        foro = tid = None
                        for fo in foros:
                            m = match_tema_foro(fo, canal)
                            if m:
                                foro, tid = fo, m
                                break
                        if foro is None:
                            foro = foro_objetivo(foros, canal)
                            tid = match_tema_foro(foro, keyword) or \
                                (match_tema_foro(foro, str(episodios)) if episodios else None)
                        destinos.append((foro["id"], tid if tid else foro.get("general")))
                        destinos = list(dict.fromkeys(destinos))
                        log("INFO", f"{archivo.name}: canal='{canal}' → foro '{foro['nombre']}' tema {tid or foro.get('general')}")
                    if not destinos:
                        log("WARN", f"{archivo.name}: sin keyword, sin grupo default ni foro. Se omite.")
                        continue
                    log("INFO", f"{archivo.name}: keyword='{keyword}' → {destinos}")
                    if episodios and es_rango_episodios(str(episodios)):
                        # Routing con el texto completo; el caption se muestra
                        # sin la palabra 'Episodio' (p. ej. '1-4').
                        caption_base = caption_sin_episodio(str(episodios))
                        log("INFO", f"{archivo.name}: episodio(s): {episodios} → caption '{caption_base}'")
                    else:
                        # Descripción libre (p. ej. la de YouTube) o sin metadata:
                        # se usa el NOMBRE del canal, no la descripción propia.
                        canal = canal or canal_from_filename(archivo.name)
                        caption_base = f"🎬 Directo de {canal}" if canal else "🎬 Directo"
                        log("WARN", f"{archivo.name}: caption por defecto (descripción no usada)")
                    if update_status:
                        update_status("uploader",
                                      status="uploading",
                                      file=archivo.name,
                                      destination=str(destinos),
                                      started_at=datetime.now().isoformat())
                    if append_log:
                        append_log("uploader", f"Subiendo {archivo.name} → {destinos}")
                    await subir_archivo(client, archivo, destinos, caption_base, keyword)
                    if remove_status:
                        remove_status("uploader")
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
    grupo.add_argument("--create-topics", metavar="GRUPO:TÍT1,TÍT2,...", help="Crear temas en un grupo con foro")
    grupo.add_argument("--delete-videos", metavar="GRUPO", help="Eliminar todos los videos de un grupo")
    parser.add_argument("--topics", help="Topic IDs separados por coma (para --delete-videos)")
    parser.add_argument("--channel", help="Filtrar por nombre de canal (para --delete-videos,ej: 'Programa Con Arnau')")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar sin eliminar (--delete-videos)")
    parser.add_argument("--force", action="store_true", help="Saltar confirmaciones (--delete-videos,requiere --dry-run previo)")
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
        if args.create_topics:
            grupo, _, titulos = args.create_topics.partition(":")
            lista = [t.strip() for t in titulos.split(",") if t.strip()]
            asyncio.run(run_create_topics(api_id, api_hash, grupo, lista))
            return
        if args.delete_videos:
            topic_ids = None
            if args.topics:
                topic_ids = [int(t.strip()) for t in args.topics.split(",") if t.strip()]
            channel_filter = None
            if args.channel:
                channel_filter = [c.strip() for c in args.channel.split(",") if c.strip()]
            asyncio.run(run_delete_videos(api_id, api_hash, args.delete_videos, topic_ids, args.dry_run, channel_filter, args.force))
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