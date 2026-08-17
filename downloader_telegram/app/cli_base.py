#!/usr/bin/env python3
"""CLI_BASE — utilidades AUTÓNOMAS del Telegram Toolbox CLI.

Este módulo es independiente del daemon uploader (subir_videos.py). NO importa
nada de él ni modifica sus archivos. Solo LEE la configuración compartida
(config.bin, secret.key, grupos.json) y mantiene su PROPIO seguimiento de
subidas (sync_cli.json) y su propio log de auditoría (tg_toolbox.log).
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeVideo,
)

REPO_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = Path(os.environ.get("TG_TOOLBOX_CONFIG", REPO_DIR / "config" / "config.bin"))
KEY_FILE = Path(os.environ.get("TG_TOOLBOX_KEY", REPO_DIR / "config" / "secret.key"))
GRUPOS_FILE = Path(os.environ.get("UPLOADER_GRUPOS", REPO_DIR / "config" / "grupos.json"))
# Seguimiento y auditoría PROPIOS del CLI (no tocan enviados.json del daemon)
LOGS_DIR = REPO_DIR / "data" / "logs"
SYNC_FILE = LOGS_DIR / "sync_cli.json"
AUDIT_FILE = LOGS_DIR / "tg_toolbox.log"
MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


def _log_auditoria(accion, detalle=""):
    """Registro local de auditoría del CLI (independiente de los daemons)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {accion}{' — ' + detalle if detalle else ''}\n")
    except OSError:
        pass


def cargar_o_generar_llave():
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


def cargar_credenciales():
    """Devuelve (api_id, api_hash). Lee config.bin cifrado (solo lectura)."""
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


def cargar_grupos():
    """Carga grupos.json (solo lectura). Devuelve (default, grupos, foros)."""
    if not GRUPOS_FILE.exists():
        raise SystemExit(
            f"\n[x] No existe {GRUPOS_FILE}.\n"
            "  → Rellena con 'default', 'grupos' y opcionalmente 'foros'."
        )
    try:
        with open(GRUPOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise SystemExit(f"\n[x] Error leyendo {GRUPOS_FILE}: {e}\n")

    grupos = data.get("grupos", [])
    default = data.get("default")
    foros_raw = data.get("foros")

    validos = []
    if isinstance(grupos, list):
        for g in grupos:
            if isinstance(g, dict) and g.get("nombre") and g.get("id"):
                validos.append({"nombre": str(g["nombre"]).lower(), "id": g["id"]})

    foros = []
    if isinstance(foros_raw, list):
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
        if grupo_series:
            foros.append({
                "id": grupo_series,
                "nombre": str(grupo_series),
                "general": None,
                "temas": temas_validos,
            })

    return default, validos, foros


# ---- parseo de nombres (idéntico al daemon, pero autónomo) ----
def keyword_from_filename(filename: str) -> str:
    base = Path(filename).stem
    if "_KW_" in base:
        kw = base.split("_KW_", 1)[1]
        for suffix in ("_compressed", "_completed"):
            if kw.endswith(suffix):
                kw = kw[: -len(suffix)]
        return kw.lower()
    return ""


def canal_from_filename(filename: str) -> str:
    base = Path(filename).stem
    canal = base.split("_", 1)[0]
    return canal or ""


def _normalizar_texto(s: str) -> str:
    import re
    s = s.lower()
    s = s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    s = s.replace("ñ", "n")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"y+$", "y", s)
    return s


def _entrada_coincide(nombre, kw):
    nombre = _normalizar_texto(nombre)
    if not nombre:
        return False
    if nombre in kw:
        return True
    palabras = [p for p in nombre.split() if len(p) >= 4]
    if any(p in kw for p in palabras):
        return True
    for p in palabras:
        for kw_word in kw.split():
            if len(kw_word) >= 4 and (kw_word.startswith(p) or p.startswith(kw_word)):
                return True
    return False


def grupos_para_keyword(keyword, default, grupos):
    kw = _normalizar_texto(keyword)
    if kw:
        coincidencias = [g["id"] for g in grupos if _entrada_coincide(g["nombre"], kw)]
        if coincidencias:
            return list(dict.fromkeys(coincidencias))
    if default:
        return [default]
    return []


def temas_para_keyword(keyword, temas):
    kw = _normalizar_texto(keyword)
    if not kw:
        return []
    coincidencias = [t["id"] for t in temas if _entrada_coincide(t["nombre"], kw)]
    return list(dict.fromkeys(coincidencias))


def match_tema_foro(foro, *textos):
    for texto in textos:
        if not texto:
            continue
        m = temas_para_keyword(texto, foro.get("temas") or [])
        if m:
            return m[0]
    return None


def foro_objetivo(foros, canal):
    if not foros:
        return None
    return foros[0]


def episodios_desde_json(archivo):
    """Lee la metadata '<name>_episodios.json' (solo lectura)."""
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
    if not texto:
        return texto
    import re
    if not re.match(r"(?i)^\s*(temporada\s*\d+\s*[·\-\|]\s*)?episodio(s)?\s*\d", texto):
        return texto
    return re.sub(r"\s+", " ", re.sub(r"(?i)\bepisodio(s)?\b", "", texto)).strip()


def detectar_episodios(archivo):
    """Detecta episodios/temporada/película por OCR de la franja superior.
    Replica la lógica del daemon de forma autónoma (ffmpeg + tesseract)."""
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


# ---- subida autónoma del CLI (propio tracking, no toca el daemon) ----
def _sync_cargar():
    if not SYNC_FILE.exists():
        return []
    try:
        with open(SYNC_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _sync_guardar(lista):
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SYNC_FILE, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def sync_ya_subido(archivo):
    return str(archivo) in _sync_cargar()


def sync_marcar(archivo):
    lista = _sync_cargar()
    if str(archivo) not in lista:
        lista.append(str(archivo))
    _sync_guardar(lista)


def atributos_video(archivo):
    """Attributes de vídeo correctos (ffprobe) para que Telegram lo
    reproduzca en línea (sin depender de hachoir)."""
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


def fotograma(archivo):
    """Thumbnail jpg para send_file de vídeo (o None si falla)."""
    thumb = archivo.with_suffix(".jpg")
    cmd = ["ffmpeg", "-y", "-ss", "2", "-i", str(archivo),
           "-frames:v", "1", "-vf", "scale=320:-1", str(thumb)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return str(thumb) if r.returncode == 0 and thumb.exists() else None


async def subir_archivo_cli(client, archivo, destinos, caption_base, keyword="",
                            usar_sync=True, borrar_origen=False):
    """Sube 'archivo' a cada destino (grupo, topico) usando el propio tracking
    del CLI (sync_cli.json) y los attributes de vídeo correctos.

    - usar_sync: si True, salta archivos ya registrados (dedup persistente).
    - borrar_origen: si True, borra el archivo local tras subir a todos.
    NO toca enviados.json ni archivos del daemon.
    """
    nombre = archivo.name
    if usar_sync and sync_ya_subido(archivo):
        return {"nombre": nombre, "estado": "omitido", "destinos": 0}
    try:
        tamano_mb = archivo.stat().st_size / 1024**2
    except OSError:
        return {"nombre": nombre, "estado": "error", "destinos": 0}

    thumb = None
    try:
        thumb = fotograma(archivo)
    except Exception:
        thumb = None

    subidos = 0
    total = len(destinos)
    for idx, (grupo, topico) in enumerate(destinos, start=1):
        ref = f" → tema {topico}" if topico else ""
        try:
            msg = await client.send_file(
                grupo, str(archivo),
                caption=caption_base,
                video_note=False,
                thumb=thumb,
                attributes=atributos_video(archivo),
                reply_to=topico,
                progress_callback=lambda c, t: None,
            )
            subidos += 1
            _log_auditoria("SUBIR", f"{nombre} → {grupo}{ref}")
        except Exception as e:
            _log_auditoria("ERR_SUBIR", f"{nombre} → {grupo}{ref}: {e}")
            return {"nombre": nombre, "estado": "error", "destinos": subidos}

    if thumb:
        try:
            Path(thumb).unlink(missing_ok=True)
        except OSError:
            pass

    if subidos >= total:
        if usar_sync:
            sync_marcar(archivo)
        if borrar_origen:
            try:
                archivo.unlink()
                _log_auditoria("BORRADO", nombre)
            except OSError:
                pass
        return {"nombre": nombre, "estado": "ok", "destinos": subidos}
    return {"nombre": nombre, "estado": "error", "destinos": subidos}
