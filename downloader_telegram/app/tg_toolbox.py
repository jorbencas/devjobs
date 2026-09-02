#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TELEGRAM TOOLBOX — CLI unificada para gestionar Telegram.

Reúne en un solo menú: descargas, clonación, gestión de chats/carpetas,
canales/foros/temas, migración, subida (pipeline) y vigilante.

Reutiliza credenciales cifradas (config.bin + secret.key) y, por defecto, usa su
PROPIA sesión (tg_toolbox.session) para no pisar la del daemon uploader.

Requiere: telethon, cryptography, rich, inquirerpy, mtranslate.
"""
import asyncio
import importlib
import json
import os
import re
import types
import shutil
import subprocess
import sys
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

# ---- auto-instalación de dependencias (igual que el menú original) ----
def _sistema_auto_setup():
    libs = ["telethon", "mtranslate", "cryptography", "cryptg", "rich", "InquirerPy"]
    if platform.system().lower() == "linux":
        try:
            subprocess.check_call(["python3", "-m", "pip", "--version"], stdout=subprocess.DEVNULL)
        except Exception:
            subprocess.check_call(["sudo", "apt", "update", "-y"])
            subprocess.check_call(["sudo", "apt", "install", "-y", "python3-pip"])
    for lib in libs:
        try:
            __import__(lib if lib != "cryptography" else "cryptography.fernet")
        except ImportError:
            pip_name = "inquirerpy" if lib == "InquirerPy" else lib
            print(f"[+] Instalando: {pip_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

_sistema_auto_setup()

from telethon import TelegramClient, errors, events  # noqa: E402
from telethon.tl.types import (  # noqa: E402
    User,
    MessageMediaDocument, MessageMediaPhoto, MessageMediaWebPage,
    MessageMediaPoll, MessageMediaContact, MessageMediaGeo,
    MessageMediaGeoLive, MessageMediaVenue, MessageMediaDice,
    DocumentAttributeSticker, DocumentAttributeAnimated, DocumentAttributeAudio,
    DocumentAttributeVideo,
    InputMessagesFilterPhotos,
    DialogFilter, InputFolderPeer, InputNotifyPeer, InputPeerNotifySettings,
)
from telethon.tl.functions.messages import (  # noqa: E402
    GetForumTopicsRequest, UpdateDialogFilterRequest, ToggleDialogPinRequest,
    CreateForumTopicRequest, EditForumTopicRequest, DeleteTopicHistoryRequest,
    DeleteHistoryRequest, GetHistoryRequest, UpdatePinnedMessageRequest,
    UnpinAllMessagesRequest, GetMessageEditDataRequest,
)
from telethon.tl.functions.folders import EditPeerFoldersRequest  # noqa: E402
from telethon.tl.functions.account import UpdateNotifySettingsRequest  # noqa: E402
from telethon.tl.functions.channels import (  # noqa: E402
    CreateChannelRequest, DeleteChannelRequest,
)
from telethon.tl.functions.stories import GetPeerStoriesRequest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from InquirerPy import inquirer  # noqa: E402
from InquirerPy.separator import Separator  # noqa: E402
from mtranslate import translate  # noqa: E402

# ---------------------------------------------------------------------------
# Monkey-patch: ejecutar .execute() de InquirerPy en un thread separado cuando
# ya hay un event loop asyncio activo (evita "asyncio.run() cannot be called
# from a running event loop").
# ---------------------------------------------------------------------------
import concurrent.futures as _futures
from InquirerPy.base.simple import BaseSimplePrompt as _SP
from InquirerPy.base.complex import BaseComplexPrompt as _CP

_orig_sp_execute = _SP.execute
_orig_cp_execute = _CP.execute

def _threaded_execute(self):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with _futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_orig_sp_execute, self).result()
    return _orig_sp_execute(self)

_SP.execute = _threaded_execute
_CP.execute = _threaded_execute

try:
    import whisper as _whisper
    _WHISPER_OK = True
except ImportError:
    _whisper = None
    _WHISPER_OK = False

from cli_base import (  # noqa: E402
    cargar_credenciales,
    cargar_grupos,
    canal_from_filename,
    keyword_from_filename,
    episodios_desde_json,
    detectar_episodios,
    caption_sin_episodio,
    foro_objetivo,
    match_tema_foro,
    grupos_para_keyword,
    subir_archivo_cli,
    sync_ya_subido,
    _log_auditoria,
    _sync_cargar,
    _sync_guardar,
    AUDIT_FILE,
)

console = Console()
BG = "blue"
FG = "green"

# Config de archivos
CONFIG_FILE = Path(os.environ.get("TG_TOOLBOX_CONFIG", REPO_DIR / "config" / "config.bin"))
KEY_FILE = Path(os.environ.get("TG_TOOLBOX_KEY", REPO_DIR / "config" / "secret.key"))
CARPETA_BASE = Path(os.environ.get("TG_TOOLBOX_DESCARGAS", REPO_DIR / "Descargas_Telegram"))
SESION = os.environ.get("TG_TOOLBOX_SESION", str(REPO_DIR / "sessions" / "tg_toolbox.session"))
GRUPOS_FILE = os.environ.get("UPLOADER_GRUPOS", str(REPO_DIR / "config" / "grupos.json"))
VIGCONFIG_FILE = os.environ.get("TG_TOOLBOX_VIGCONFIG", str(REPO_DIR / "config" / "vigilante.json"))

SPAM_LIST = ["crypto", "ganar dinero", "casino", "poker", "estafa", "bet", "sex", "porn", "gore", "nude"]

TIPOS_MEDIA = ["vídeo", "foto", "audio", "voice", "documento", "sticker", "gif",
               "encuesta", "contacto", "ubicación"]


def styled_panel(content, title="", style="blue"):
    return Panel(content, title=title, border_style=style, expand=True)


def styled_print(msg, style=f"bold {FG}"):
    console.print(msg, style=style)


def styled_error(msg):
    console.print(f"  [bold red]✗[/bold red] {msg}")


def styled_success(msg):
    console.print(f"  [bold green]✓[/bold green] {msg}")


def styled_info(msg):
    console.print(f"  [bold blue]ℹ[/bold blue] {msg}")


def styled_warn(msg):
    console.print(f"  [bold yellow]⚠[/bold yellow] {msg}")


def log(tipo, mensaje):
    icons = {"INFO": "ℹ", "OK": "✓", "WARN": "⚠", "ERR": "✗", "DB": "↓", "SPAM": "🚫", "TRAD": "📝"}
    styles = {"INFO": f"bold {BG}", "OK": f"bold {FG}", "WARN": "bold yellow",
              "ERR": "bold red", "DB": f"bold {BG}", "SPAM": "bold red", "TRAD": "bold cyan"}
    ts = datetime.now().strftime("%H:%M:%S")
    console.print(f"  [dim]{ts}[/dim] [{styles.get(tipo, 'white')}]{icons.get(tipo, '·')}[/{styles.get(tipo, 'white')}] {mensaje}")


def cargar_o_generar_llave():
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


# ---- cliente compartido ----
async def conectar():
    api_id, api_hash = cargar_credenciales()
    client = TelegramClient(SESION, api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        styled_warn("Sesión no autenticada. Haz login con código (2FA si aplica).")
        await client.start()
    styled_success("Conexión establecida.")
    return client


async def resolver(client, ref):
    try:
        return await client.get_entity(int(ref))
    except (ValueError, TypeError):
        return await client.get_entity(ref)


def _tipo(ent):
    if isinstance(ent, User):
        return "user" if not getattr(ent, "bot", False) else "bot"
    if getattr(ent, "forum", False):
        return "foro"
    if getattr(ent, "broadcast", False):
        return "canal"
    return "grupo"


# ----------------------------------------------------------------------------
# Selectores interactivos reutilizables (chats y temas) con filtros
# ----------------------------------------------------------------------------
async def _carpeta_dialogo(d):
    """Nombre legible de la carpeta de un diálogo."""
    fid = getattr(d, "folder_id", None)
    if fid == 1:
        return "Archivado"
    if fid in (None, 0):
        return "Principal"
    return f"#{fid}"


async def _listar_chats_filtrado(client, tipos=None, filtro="todos", folder=None, creados=None):
    """Devuelve lista de dicts {ent, id, nombre, tipo, carpeta, creado} según filtros:
    - tipos: subset de ('grupo','canal','foro')
    - filtro: 'todos' | 'mios' | 'ajenos' | 'carpeta'
    - folder: nombre de carpeta/chat para el filtro 'carpeta'
    - creados: si es True/False fuerza el filtro de "creados por mí" directamente.
    """
    if filtro == "mios":
        creados = True
    elif filtro == "ajenos":
        creados = False
    resultados = []
    if tipos and "me" in tipos:
        resultados.append({
            "ent": "me", "id": "me", "nombre": "💾 Mensajes guardados",
            "tipo": "me", "carpeta": "Principal", "creado": True,
        })
    async for d in client.iter_dialogs():
        ent = getattr(d, "entity", None)
        if ent is None:
            continue
        tipo = _tipo(ent)
        if tipos and tipo not in tipos:
            continue
        carpeta = await _carpeta_dialogo(d)
        creado = bool(getattr(ent, "creator", False))
        if creados is not None and creado != creados:
            continue
        if folder and folder.lower() not in (carpeta.lower(), (d.name or "").lower()):
            continue
        resultados.append({
            "ent": ent, "id": d.id, "nombre": d.name or "(sin nombre)",
            "tipo": tipo, "carpeta": carpeta, "creado": creado,
        })
    return sorted(resultados, key=lambda r: (r["nombre"] or "").lower())


def _filtro_interactivo():
    """Pregunta al usuario qué filtro aplicar a la lista de chats."""
    opcion = inquirer.select(
        "Filtrar por:",
        choices=[
            {"name": "🌐  Todos", "value": "todos"},
            {"name": "🙋  Los míos (creados por mí)", "value": "mios"},
            {"name": "👥  Los que NO son míos", "value": "ajenos"},
            {"name": "🗂️  De una carpeta específica", "value": "carpeta"},
        ],
        pointer="▸",
    ).execute()
    folder = None
    if opcion == "carpeta":
        folder = inquirer.text("Nombre de carpeta o chat:").execute().strip()
        return "todos", folder
    return opcion, folder


async def _seleccionar_chat(client, titulo="Selecciona un chat:", tipos=None,
                            filtro="todos", folder=None, creados=None, permitir_volver=True):
    """Lista los chats según filtros y devuelve el dict seleccionado (o None si vuelve)."""
    opcion_filtro = filtro
    carpeta_filtro = folder
    if filtro is None:
        opcion_filtro, carpeta_filtro = _filtro_interactivo()
    while True:
        items = await _listar_chats_filtrado(client, tipos=tipos, filtro=opcion_filtro,
                                             folder=carpeta_filtro, creados=creados)
        if not items:
            styled_warn("Sin resultados con ese filtro.")
            return None
        icons = {"grupo": "💬", "canal": "📢", "foro": "🧭"}
        choices = [{
            "name": f"{icons.get(i['tipo'], '•')} {i['nombre']} "
                    f"[{i['tipo']}] · {i['carpeta']}"
                    f"{' · mío' if i['creado'] else ''}",
            "value": i,
        } for i in items]
        if permitir_volver:
            choices.append({"name": "🔙  Cambiar filtro / Volver", "value": None})
        seleccion = inquirer.select(titulo, choices=choices, pointer="▸").execute()
        if seleccion is None:
            if filtro is not None:
                return None
            opcion_filtro, carpeta_filtro = _filtro_interactivo()
            continue
        if not inquirer.confirm(
                f"¿Confirmas '{seleccion['nombre']}' [{seleccion['tipo']}]?",
                default=True).execute():
            continue
        return seleccion


async def _seleccionar_tema(client, foro_ent, titulo="Selecciona un tema:", permitir_general=True):
    """Lista los temas de un foro y devuelve el topic_id elegido (o None si vuelve)."""
    res = await client(GetForumTopicsRequest(peer=foro_ent, offset_date=datetime(1970, 1, 1),
                                             offset_id=0, offset_topic=0, limit=100))
    temas = {t.id: t.title for t in res.topics}
    if not temas:
        styled_warn("Sin temas.")
        return None
    while True:
        choices = [{"name": f"• {tit}", "value": tid} for tid, tit in temas.items()]
        if permitir_general and 1 not in temas:
            choices.insert(0, {"name": "• General", "value": 1})
        choices.append({"name": "🔙  Volver", "value": None})
        pick = inquirer.select(titulo, choices=choices, pointer="▸").execute()
        if pick is None:
            return None
        nombre = temas.get(pick) or ("General" if pick == 1 else str(pick))
        if inquirer.confirm(f"¿Confirmas el tema '{nombre}'?", default=True).execute():
            return pick


# ----------------------------------------------------------------------------
# Utilidades de robustez (Fase A): números seguros, rutas seguras, reintentos
# ----------------------------------------------------------------------------
def _pedir_numero(mensaje, minimo=None, maximo=None, por_defecto=None, es_id=False):
    """Pide un número con reintentos. Devuelve int o None si se cancela.
    - es_id: acepta negativos (ids de Telegram), no exige mínimo."""
    while True:
        try:
            resp = inquirer.text(message=mensaje,
                                 default=str(por_defecto) if por_defecto is not None else "",
                                 validate=lambda r: r.strip() != "" or r.strip() == "").execute()
        except KeyboardInterrupt:
            return None
        resp = (resp or "").strip()
        if not resp and por_defecto is not None:
            return int(por_defecto)
        if not resp:
            styled_warn("No puede estar vacío.")
            continue
        try:
            valor = int(resp)
        except ValueError:
            styled_warn(f"'{resp}' no es un número válido.")
            continue
        if es_id:
            return valor
        if minimo is not None and valor < minimo:
            styled_warn(f"Debe ser >= {minimo}.")
            continue
        if maximo is not None and valor > maximo:
            styled_warn(f"Debe ser <= {maximo}.")
            continue
        return valor


def _saneado(nombre):
    """Quita caracteres inválidos para rutas de archivo."""
    nombre = re.sub(r'[\\/*?:"<>|]', "_", nombre)
    return nombre.strip().strip(".") or "sin_nombre"


def _ruta_segura(destino):
    """Convierte una ruta de usuario en una Path segura y crea los padres."""
    p = Path(str(destino)).expanduser()
    p = p.resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _mensaje_limite(e):
    """Devuelve un mensaje legible si el error RPC es un límite de cuenta Telegram.
    Retorna None si no es un límite reconocible."""
    nombre = type(e).__name__
    limites = {
        "PinnedDialogsTooMuchError": "límite de chats fijados alcanzado (Telegram permite fijar un máximo)",
        "PinnedDialogsTooMuch": "límite de chats fijados alcanzado (Telegram permite fijar un máximo)",
        "FolderLimitReachedError": "límite de carpetas alcanzado (máximo de folders de tu cuenta)",
        "FolderLimitReached": "límite de carpetas alcanzado (máximo de folders de tu cuenta)",
        "FolderIdInvalidError": "ID de carpeta inválido (revisa que el folder exista)",
        "FolderIdInvalid": "ID de carpeta inválido (revisa que el folder exista)",
        "FolderIdEmptyError": "carpeta vacía no soportada",
        "ChannelsTooMuchError": "límite de canales alcanzado (máximo de canales/grupos por cuenta)",
        "ChannelsTooMuch": "límite de canales alcanzado (máximo de canales/grupos por cuenta)",
        "UsersTooMuchError": "el chat ha alcanzado el máximo de miembros",
        "UsersTooMuch": "el chat ha alcanzado el máximo de miembros",
        "BotCommandsTooMuchError": "límite de comandos del bot alcanzado",
        "AdminsTooMuchError": "límite de administradores del chat alcanzado",
        "ChatAdminRequiredError": "se necesitan permisos de administrador para esta acción",
        "ChatAdminRequired": "se necesitan permisos de administrador para esta acción",
    }
    return limites.get(nombre)


async def _reintentar(coro_factory, veces=3, espera=2.0, etiqueta="operación"):
    """Ejecuta un coroutine (fábrica sin args) con reintentos y backoff.
    Devuelve el resultado o None si falla tras todos los intentos."""
    for i in range(veces):
        try:
            return await coro_factory()
        except errors.FloodWaitError as e:
            styled_warn(f"{etiqueta}: FloodWait {e.seconds}s → esperando...")
            await asyncio.sleep(e.seconds)
        except (ConnectionError, OSError, TimeoutError) as e:
            if i < veces - 1:
                styled_warn(f"{etiqueta}: error ({e}) → reintento {i + 1}/{veces - 1}")
                await asyncio.sleep(espera * (2 ** i))
            else:
                styled_error(f"{etiqueta}: falló tras {veces} intentos: {e}")
        except Exception as e:
            limite = _mensaje_limite(e)
            if limite:
                styled_error(f"{etiqueta}: no se pudo completar — {limite}.")
                return None
            styled_error(f"{etiqueta}: error inesperado: {e}")
            return None
    return None


async def _comprobar_conexion(client):
    """Reconecta el cliente si la conexión se perdió."""
    try:
        if not client.is_connected():
            styled_warn("Reconectando a Telegram...")
            await client.connect()
        return True
    except Exception as e:
        styled_error(f"No se pudo reconectar: {e}")
        return False


def _tabla_resumen(columnas, filas, titulo="Resumen"):
    """Tabla de resumen/confirmación antes de ejecutar una acción."""
    t = Table(title=titulo, title_style=f"bold {BG}")
    for col in columnas:
        t.add_column(col, style="white", overflow="fold")
    for fila in filas:
        t.add_row(*[str(c) for c in fila])
    console.print(t)


async def _stats_chat(client, ent):
    """(~n_mensajes, fecha_ultimo) vía GetHistoryRequest (rápido, 1 petición)."""
    try:
        r = await client(GetHistoryRequest(
            peer=ent, limit=1, offset_date=None, offset_id=0,
            max_id=0, min_id=0, add_offset=0, hash=0))
        fecha = r.messages[0].date if r.messages else None
        return getattr(r, "count", 0), fecha
    except Exception:
        return None, None


async def _confirmar_destruccion(nombre, detalle="", client=None, ent=None):
    """Patrón unificado para acciones irreversibles:
    1. Muestra stats del chat (nº mensajes y última actividad) si hay ent.
    2. Exige escribir el nombre exacto (fail-safe si no coincide).
    3. Confirmación final con default=False."""
    extra = ""
    if client is not None and ent is not None:
        n, fecha = await _stats_chat(client, ent)
        f = fecha.strftime("%d/%m/%Y") if fecha else "¿?"
        total = f"~{n}" if n is not None else "¿?"
        extra = f" ({total} mensajes, último el {f})"
    styled_warn(f"{detalle} '{nombre}'{extra}. ¡IRREVERSIBLE!")
    escribir = inquirer.text(
        f"Escribe el nombre exacto '{nombre}' para confirmar:").execute().strip()
    if escribir != nombre:
        styled_warn("El texto no coincide. Cancelado.")
        return False
    if not inquirer.confirm("¿Seguro? Esta acción NO se puede deshacer.",
                            default=False).execute():
        styled_info("Cancelado.")
        return False
    return True


# ============================================================================
# MÓDULO 1: Descargas
# ============================================================================
def procesar_texto_inteligente(texto, activar_traduccion=False):
    if not texto:
        return None
    if any(w in texto.lower() for w in SPAM_LIST):
        return "FILTERED_CONTENT"
    if activar_traduccion:
        try:
            return translate(texto, "es")
        except Exception:
            return texto
    return texto


async def download_media_robust(client, message, folder):
    if not message or not getattr(message, "media", None):
        return False
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    tipo = _tipo_medio(message)
    if tipo in ("encuesta", "contacto", "ubicación", "dado"):
        return await _guardar_medio_texto(message, folder, tipo)

    file_name = message.file.name if message.file and message.file.name else _nombre_por_defecto(message, tipo)
    full = os.path.join(str(folder), file_name)
    temp = full + ".part"
    if os.path.exists(full):
        log("INFO", f"Ya existe: {file_name}")
        return True
    try:
        log("DB", f"Bajando: {file_name}")
        with open(temp, "wb") as f:
            await client.download_media(message, file=f, progress_callback=lambda c, t: None)
        os.rename(temp, full)
        log("OK", f"Completado: {file_name}")
        return True
    except Exception as e:
        log("ERR", f"Fallo en descarga {file_name}: {e}")
        return False


def _nombre_por_defecto(message, tipo):
    ext = getattr(getattr(message, "file", None), "ext", None)
    if not ext:
        ext = {"voice": ".ogg", "gif": ".mp4", "sticker": ".webp"}.get(tipo, ".bin")
    return f"msg_{message.id}{ext}"


async def _guardar_medio_texto(message, folder, tipo):
    """Guarda encuestas/contactos/ubicaciones/dados como .txt legible (no son archivos)."""
    m = getattr(message, "media", None)
    lineas = [f"[{tipo.upper()}] msg {message.id}", str(getattr(message, "date", "") or "")]
    if message.text:
        lineas.append(message.text)
    if isinstance(m, MessageMediaPoll):
        poll = m.poll
        lineas.append(f"Pregunta: {poll.question}")
        for i, r in enumerate(poll.answers, 1):
            lineas.append(f"  {i}. {r.text}")
    elif isinstance(m, MessageMediaContact):
        lineas.append(f"Contacto: {m.first_name or ''} {m.last_name or ''} ({m.phone or ''})")
        if m.user_id:
            lineas.append(f"user_id={m.user_id}")
    elif isinstance(m, (MessageMediaGeo, MessageMediaVenue)):
        if isinstance(m, MessageMediaVenue):
            lineas.append(f"Lugar: {m.title} — {m.address or ''}")
        lat = getattr(m, "lat", None) or getattr(getattr(m, "geo", None), "lat", None)
        lon = getattr(m, "long", None) or getattr(getattr(m, "geo", None), "long", None)
        if lat is not None and lon is not None:
            lineas.append(f"Coordenadas: {lat},{lon}")
            lineas.append(f"Mapa: https://www.google.com/maps?q={lat},{lon}")
    contenido = "\n".join(x for x in lineas if x).strip() + "\n"
    full = folder / f"{tipo}_{message.id}.txt"
    if not full.exists():
        full.write_text(contenido, encoding="utf-8")
        log("OK", f"Guardado: {full.name}")
    else:
        log("INFO", f"Ya existe: {full.name}")
    return True


# ============================================================================
# Transcripción de voice messages con whisper (instala openai-whisper si falta)
# ============================================================================
def _whisper_instalado():
    return _WHISPER_OK


def _instalar_whisper():
    global _whisper, _WHISPER_OK
    if _WHISPER_OK:
        return True
    styled_info("whisper no está instalado. Intento instalarlo (openai-whisper)...")
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "openai-whisper"],
                           capture_output=True, text=True, timeout=60 * 10)
        if r.returncode != 0:
            styled_error(f"No se pudo instalar whisper: {r.stderr[-300:]}")
            return False
        _whisper = importlib.import_module("whisper")
        _WHISPER_OK = True
        return True
    except Exception as e:
        styled_error(f"No se pudo instalar whisper: {e}")
        return False


async def _transcribir_voice(client, message, folder):
    """Descarga el voice message y lo transcribe a un .txt con whisper."""
    if not _instalar_whisper():
        return False
    m = getattr(message, "media", None)
    if not isinstance(m, MessageMediaDocument):
        return False
    if not any(isinstance(a, DocumentAttributeAudio) and getattr(a, "voice", False)
               for a in (getattr(getattr(m, "document", None), "attributes", None) or [])):
        return False
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    txt_path = folder / f"transcripcion_{message.id}.txt"
    if txt_path.exists():
        styled_info(f"Transcripción ya existe: {txt_path.name}")
        return True
    ogg = folder / f"voice_{message.id}.ogg"
    if not ogg.exists():
        try:
            await client.download_media(message, file=str(ogg))
        except Exception as e:
            log("ERR", f"No se pudo bajar voice {message.id}: {e}")
            return False
    try:
        styled_info(f"Transcribiendo voice {message.id}... (puede tardar)")
        model = _whisper.load_model("base")
        result = model.transcribe(str(ogg), language="es")
        texto = result.get("text", "").strip()
        (folder / f"transcripcion_{message.id}.txt").write_text(
            texto or "(sin texto reconocido)", encoding="utf-8")
        if ogg.exists() and not inquirer.confirm(
                f"¿Eliminar el .ogg temporal de {message.id}?", default=True).execute():
            pass
        else:
            try:
                ogg.unlink(missing_ok=True)
            except OSError:
                pass
        styled_success(f"Transcrito → transcripcion_{message.id}.txt")
        return True
    except Exception as e:
        log("ERR", f"Fallo transcribiendo voice {message.id}: {e}")
        return False


# ============================================================================
# FASE EXTRA · Descarga de YouTube (yt-dlp)
# ============================================================================
def _yt_instalado():
    return bool(shutil.which("yt-dlp") or shutil.which("yt-dlp3"))


async def _descargar_youtube(client, trad):
    """Descarga un vídeo/playlist de YouTube con yt-dlp a una carpeta local."""
    if not (shutil.which("yt-dlp") or shutil.which("yt-dlp3")):
        styled_warn("yt-dlp no está instalado en el contenedor. Intento instalarlo...")
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yt-dlp"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                styled_error(f"No se pudo instalar yt-dlp: {r.stderr[-200:]}")
                return
        except Exception as e:
            styled_error(f"No se pudo instalar yt-dlp: {e}")
            return
    url = inquirer.text("URL de YouTube:").execute().strip()
    if not url:
        return
    destino = inquirer.text("Carpeta (vacío = Descargas_Telegram/YouTube):").execute().strip()
    carpeta = _ruta_segura(destino or str(CARPETA_BASE / "YouTube"))
    formato = inquirer.select("Formato:", choices=[
        {"name": "🎬  Mejor calidad (mp4)", "value": "best"},
        {"name": "🔊  Solo audio (mp3)", "value": "audio"},
        {"name": "📦  Mejor vídeo+audio (mkv)", "value": "bestvideo"},
    ], pointer="▸").execute()
    cmd = [shutil.which("yt-dlp") or shutil.which("yt-dlp3"), "-o", str(carpeta / "%(title)s.%(ext)s")]
    if formato == "audio":
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    elif formato == "bestvideo":
        cmd += ["-f", "bv*+ba/b", "--merge-output-format", "mkv"]
    else:
        cmd += ["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b"]
    cmd += [url]
    styled_info("Descargando con yt-dlp... (puede tardar)")
    _log_auditoria("YOUTUBE", f"{url} → {carpeta} [{formato}]")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 60)
        if r.returncode != 0:
            styled_error(f"yt-dlp falló: {r.stderr[-300:]}")
            return
    except subprocess.TimeoutExpired:
        styled_error("La descarga excedió 60 min. Cancelada.")
        return
    styled_success(f"Descarga completada en {carpeta}")
    if inquirer.confirm("¿Subir lo descargado a un canal/tema propio?", default=False).execute():
        sel = await _seleccionar_chat(client, "Destino (los míos):", tipos=["canal", "grupo", "foro"],
                                      filtro="mios", creados=True)
        if sel:
            destino_ent = sel["ent"]
            topico = None
            if sel["tipo"] == "foro":
                topico = await _seleccionar_tema(client, destino_ent, "Tema destino:")
            for a in sorted([f for f in carpeta.iterdir() if f.is_file()]):
                async def _sf(aa=a, d=destino_ent, td=topico):
                    return await client.send_file(d, str(aa), caption=aa.name, reply_to=td)
                if await _reintentar(_sf, etiqueta=f"subida {a.name}"):
                    styled_success(f"  → {a.name}")
            _log_auditoria("YOUTUBE_RESUBIR", f"{url} → {sel['nombre']}")


# ============================================================================
# FASE EXTRA · Progreso de conversión en vivo (solo lectura del daemon)
# ============================================================================
async def _progreso_conversion(client):
    """Muestra el estado de la conversión leyendo la carpeta de salida del
    monitor directamente (sin depender del contenedor ffmpeg_monitor)."""
    styled_info("Leyendo estado de la conversión...")
    comp_dir = Path("/comprimidos")
    if not comp_dir.is_dir():
        styled_warn("Carpeta /comprimidos no montada. Monta data/comprimidos en el servicio.")
        return
    try:
        lineas = []
        # En curso: temporales del monitor(*.tmp / .staging)
        en_curso = sorted([p for p in comp_dir.glob("*.tmp")]) + sorted(
            [p for p in (comp_dir / ".staging").glob("*.mp4")] if (comp_dir / ".staging").is_dir() else [])
        if en_curso:
            lineas.append(f"⏳ En conversión: {', '.join(p.name for p in en_curso)}")
        listos = sorted([p for p in comp_dir.glob("*_compressed.mp4")])[-3:]
        if listos:
            lineas.append("✅ Listos para subir (últimos):")
            lineas += [f"   · {p.name}" for p in listos]
        if not lineas:
            styled_success("Sin conversión activa ni vídeos listos.")
            return
        console.print("\n".join(f"[bold {BG}]{l}[/]" if i == 0 else l for i, l in enumerate(lineas)))
    except Exception as e:
        styled_warn(f"No se pudo consultar el estado: {e}")


async def modulo_descargas(client):
    console.print(styled_panel("[bold white]MÓDULO DESCARGAS[/bold white]", title="📥", style=BG))
    sub = inquirer.select(
        "Tipo de descarga:",
        choices=[
            {"name": "🎯  Descarga interactiva (origen → destino)", "value": "i"},
            {"name": "🔗  Enlace único", "value": "a"},
            {"name": "📊  Rango de IDs", "value": "b"},
            {"name": "📄  Procesar enlaces.txt", "value": "c"},
            {"name": "📺  Canal completo", "value": "d"},
            {"name": "📈  Estadísticas de un canal/tema", "value": "stats"},
            {"name": "🔎  Búsqueda por texto y descarga", "value": "busca"},
            {"name": "🌟  Descargar storys activas de un canal", "value": "storia"},
            {"name": "🎙️  Transcribir voice messages (whisper)", "value": "voice"},
            {"name": "▶️  Descarga de YouTube (yt-dlp)", "value": "yt"},
        ],
        pointer="▸",
    ).execute()
    trad = inquirer.confirm("¿Traducir textos detectados?", default=False).execute()

    folder = CARPETA_BASE / "Masivo"
    if sub == "d":
        folder = CARPETA_BASE / "Canales"

    if sub == "i":
        await _descarga_interactiva(client, trad)
        return

    if sub == "yt":
        await _descargar_youtube(client, trad)
        return

    if sub == "stats":
        await _estadisticas_canal(client)
        return

    if sub == "busca":
        await _buscar_y_descargar(client, trad)
        return

    if sub == "storia":
        await _descargar_storys(client)
        return

    if sub == "voice":
        await _transcribir_voice_canal(client)
        return

    if sub == "a":
        link = inquirer.text(message="Pega el enlace:").execute().strip()
        if not link:
            return
        await _descargar_enlace(client, link, folder, trad)
        return

    if sub == "d":
        await _canal_completo(client)
        return

    if sub == "b":
        sel = await _seleccionar_chat(client, "Canal/foro para rango de IDs:", filtro=None)
        if not sel:
            return
        peer = sel["ent"]
        ini = _pedir_numero("Desde ID (mensaje):", minimo=1, por_defecto=1)
        if ini is None:
            return
        fin = _pedir_numero("Hasta ID (mensaje):", minimo=ini, por_defecto=100)
        if fin is None:
            return
        if not inquirer.confirm(f"¿Descargar mensajes {ini}-{fin} de '{sel['nombre']}'?", default=True).execute():
            styled_info("Cancelado.")
            return
        cant = 0
        try:
            for mid in range(ini, fin + 1):
                if not await _comprobar_conexion(client):
                    break
                msg = await client.get_messages(peer, ids=mid)
                if not msg:
                    continue
                txt = procesar_texto_inteligente(msg.text, trad)
                if txt == "FILTERED_CONTENT":
                    continue
                if msg.media:
                    await _reintentar(lambda m=msg: download_media_robust(client, m, folder),
                                      etiqueta=f"descarga ID {mid}")
                cant += 1
                await asyncio.sleep(0.1)
        except Exception as e:
            log("ERR", f"Error: {e}")
        _log_auditoria("DESCARGAR_RANGO", f"{sel['nombre']}: {ini}-{fin} → {cant} procesados")
        styled_info(f"Procesados {cant} mensajes.")
        return

    if sub == "c":
        enlaces = [l.strip() for l in (SCRIPT_DIR / "enlaces.txt").read_text().splitlines() if l.strip()] if (SCRIPT_DIR / "enlaces.txt").exists() else []
        if not enlaces:
            styled_error("No se encontró enlaces.txt")
            return
        for link in enlaces:
            await _descargar_enlace(client, link, folder, trad)
        return


def _tipo_medio(msg):
    """Clasifica el tipo de medio de un mensaje (para el filtro B3)."""
    m = getattr(msg, "media", None)
    if m is None:
        return None
    if isinstance(m, MessageMediaPhoto):
        return "foto"
    if isinstance(m, MessageMediaPoll):
        return "encuesta"
    if isinstance(m, (MessageMediaContact,)):
        return "contacto"
    if isinstance(m, (MessageMediaGeo, MessageMediaGeoLive, MessageMediaVenue)):
        return "ubicación"
    if isinstance(m, MessageMediaDice):
        return "dado"
    if isinstance(m, (MessageMediaWebPage,)):
        return None
    if isinstance(m, MessageMediaDocument):
        d = getattr(m, "document", None)
        attrs = getattr(d, "attributes", None) or []
        if any(isinstance(a, DocumentAttributeSticker) for a in attrs):
            return "sticker"
        if any(isinstance(a, DocumentAttributeAnimated) for a in attrs):
            return "gif"
        audio_attr = next((a for a in attrs if isinstance(a, DocumentAttributeAudio)), None)
        if audio_attr is not None and getattr(audio_attr, "voice", False):
            return "voice"
        if any(isinstance(a, DocumentAttributeVideo) for a in attrs):
            return "vídeo"
        nm = [getattr(a, "file_name", "") or "" for a in attrs]
        ext = next((n for n in nm if n), "")
        if re.search(r"\.(mp[34]|mkv|avi|mov|webm|ts)$", ext.lower()):
            return "vídeo"
        if re.search(r"\.(mp3|flac|aac|ogg|opus|wav|m4a)$", ext.lower()):
            return "audio"
        return "documento"
    return "documento"


async def _descarga_interactiva(client, trad):
    """Descarga interactiva: elige origen (canal/foro + tema), selecciona los
    mensajes a bajar (todos o 1), elige carpeta destino y, opcionalmente,
    re-subida a un canal/tema PROPIO (de los que tú has creado)."""
    styled_info("PASO 1 · Elige el ORIGEN (puedes filtrar).")
    sel = await _seleccionar_chat(client, "Canal/foro ORIGEN:",
                                  tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    origen = sel["ent"]
    topico = None
    if sel["tipo"] == "foro":
        styled_info("PASO 1b · Elige un tema (o 'Volver' = descargar TODO el foro).")
        topico = await _seleccionar_tema(client, origen, "Tema a descargar:",
                                         permitir_general=False)
        # permitir_general=True y opción volver → None

    # B2 · Filtros por fecha
    desde_f = hasta_f = None
    if inquirer.confirm("¿Filtrar por rango de fechas?", default=False).execute():
        desde_str = inquirer.text("Desde (YYYY-MM-DD, vacío = sin límite):").execute().strip()
        hasta_str = inquirer.text("Hasta (YYYY-MM-DD, vacío = sin límite):").execute().strip()
        try:
            if desde_str:
                desde_f = datetime.strptime(desde_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if hasta_str:
                hasta_f = datetime.strptime(hasta_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59,
                                                                           tzinfo=timezone.utc)
        except ValueError:
            styled_warn("Fecha inválida; se ignora el filtro de fecha.")

    # B3 · Tipos de media
    tipos_ok = {t: True for t in TIPOS_MEDIA}
    if inquirer.confirm("¿Filtrar por tipo de medio?", default=False).execute():
        for t in TIPOS_MEDIA:
            tipos_ok[t] = inquirer.confirm(f"¿Descargar {t}s?", default=True).execute()
    if not any(tipos_ok.values()):
        styled_warn("Ningún tipo seleccionado; se descargará todo.")
        tipos_ok = {t: True for t in TIPOS_MEDIA}

    styled_info("PASO 2 · Leyendo mensajes del origen...")
    mensajes = []
    async for msg in client.iter_messages(origen, reply_to=topico):
        if not getattr(msg, "media", None):
            continue
        if desde_f is not None and msg.date and msg.date < desde_f:
            continue
        if hasta_f is not None and msg.date and msg.date > hasta_f:
            continue
        tipo = _tipo_medio(msg)
        if tipo and not tipos_ok.get(tipo, True):
            continue
        if not getattr(getattr(msg, "file", None), "name", None) and not msg.media:
            continue
        nombre = msg.file.name if getattr(getattr(msg, "file", None), "name", None) else f"msg_{msg.id}"
        mensajes.append((msg.id, nombre, msg))
        if len(mensajes) >= 200:
            break
    if not mensajes:
        styled_warn("Sin archivos en ese origen/tema.")
        return
    styled_info(f"Encontrados {len(mensajes)} archivos.")

    # Selección: todo el contenido o 1 a 1
    opc = inquirer.select(
        "¿Qué descargo?",
        choices=[
            {"name": f"📥  Todo el contenido ({len(mensajes)} archivos)", "value": "todos"},
            {"name": "🎯  1 a 1 (elegir y confirmar cada uno)", "value": "uno"},
        ],
        pointer="▸",
    ).execute()
    elegidos = []
    if opc == "todos":
        elegidos = mensajes
    else:
        while True:
            cho = [{"name": f"{nombre}", "value": (mid, msg)}
                   for mid, nombre, msg in mensajes]
            cho.append({"name": "✅  Terminar", "value": None})
            pick = inquirer.select("Elige el archivo:", choices=cho, pointer="▸").execute()
            if pick is None:
                break
            mid, msg = pick
            nombre = msg.file.name or f"msg_{mid}"
            if not inquirer.confirm(f"¿Descargar '{nombre}'?", default=True).execute():
                continue
            elegidos.append((mid, nombre, msg))
            styled_success(f"Seleccionado: {nombre}")
            if not inquirer.confirm("¿Elegir otro?", default=True).execute():
                break
    if not elegidos:
        styled_info("Nada seleccionado.")
        return

    # Carpeta destino
    destino_archivo = inquirer.text(
        "Carpeta donde guardar (vacío = Descargas_Telegram/Origen):").execute().strip()
    if not destino_archivo:
        destino_archivo = str(CARPETA_BASE / "Origen" / _saneado(sel["nombre"] or "sin_nombre"))
    carpeta = _ruta_segura(destino_archivo)

    _tabla_resumen(
        ["Origen", "Tema", "Archivos", "Carpeta"],
        [(sel["nombre"], topico if topico else "todo", str(len(elegidos)), str(carpeta))],
        titulo="Resumen de descarga",
    )
    if not inquirer.confirm("¿Descargar ahora?", default=True).execute():
        styled_info("Cancelado.")
        return

    styled_info(f"PASO 3 · Descargando {len(elegidos)} archivo(s) a {carpeta}...")
    ok = 0
    for mid, nombre, msg in elegidos:
        if not await _comprobar_conexion(client):
            break
        r = await _reintentar(lambda m=msg: download_media_robust(client, m, carpeta),
                              etiqueta=f"descarga {nombre}")
        if r:
            ok += 1
        await asyncio.sleep(0.2)
    _log_auditoria("DESCARGAR_INTERACTIVO", f"{sel['nombre']}: {ok}/{len(elegidos)} → {carpeta}")
    styled_success(f"Descargados {ok}/{len(elegidos)} archivos a {carpeta}.")

    # Re-subida opcional a canal/tema propio
    if not inquirer.confirm("¿Subir los descargados a un canal/tema PROPIO?", default=False).execute():
        styled_info("Listo, sin re-subida.")
        return

    styled_info("PASO 4 · Elige el DESTINO (solo canales/foros creados por ti).")
    sel_dest = await _seleccionar_chat(client, "Canal/foro DESTINO (los míos):",
                                       tipos=["canal", "grupo", "foro"],
                                       filtro="mios", creados=True)
    if not sel_dest:
        return
    destino = sel_dest["ent"]
    topico_dest = None
    if sel_dest["tipo"] == "foro":
        topico_dest = await _seleccionar_tema(client, destino, "Tema destino:")
    ref_t = f" → tema {topico_dest}" if topico_dest else ""
    _tabla_resumen(
        ["Destino", "Tema", "Archivos", "Origen carpeta"],
        [(sel_dest["nombre"], topico_dest if topico_dest else "-", str(len(elegidos)), str(carpeta))],
        titulo="Resumen de re-subida",
    )
    if not inquirer.confirm(f"¿Subir a {sel_dest['nombre']}{ref_t}?", default=True).execute():
        styled_info("Cancelado.")
        return
    styled_info(f"Subiendo a {sel_dest['nombre']}{ref_t}...")
    n_subidos = 0
    for _, nombre, msg in elegidos:
        if not await _comprobar_conexion(client):
            break
        ruta = carpeta / _saneado(nombre)
        try:
            if not ruta.exists():
                styled_warn(f"No existe localmente: {nombre}")
                continue
            async def _sf(r=ruta, n=nombre, td=topico_dest, d=destino):
                return await client.send_file(d, str(r), caption=n, reply_to=td)
            r = await _reintentar(_sf, etiqueta=f"subida {nombre}")
            if r:
                n_subidos += 1
        except Exception as e:
            log("ERR", f"Fallo subida {nombre}: {e}")
        await asyncio.sleep(0.3)
    _log_auditoria("RE_SUBIR", f"{sel_dest['nombre']}{ref_t}: {n_subidos}/{len(elegidos)}")
    styled_success(f"Subidos {n_subidos}/{len(elegidos)} a {sel_dest['nombre']}.")


async def _descargar_enlace(client, link, folder, trad):
    try:
        partes = link.split("/")
        msg_id = int(partes[-1].split("?")[0])
        peer = int("-100" + partes[-2]) if "/c/" in link else partes[-2]
        msg = await client.get_messages(peer, ids=msg_id)
        if not msg:
            return
        txt = procesar_texto_inteligente(msg.text, trad)
        if txt == "FILTERED_CONTENT":
            log("SPAM", "Mensaje bloqueado por filtro.")
            return
        if msg.media:
            await download_media_robust(client, msg, folder)
    except Exception as e:
        log("ERR", f"Error en enlace {link}: {e}")


async def _canal_completo(client):
    sel = await _seleccionar_chat(client, "Canal ORIGEN (con filtro):", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    peer = sel["ent"]
    trad = inquirer.confirm("¿Traducir textos?", default=False).execute()
    descargar = inquirer.confirm("¿Descargar multimedia?", default=True).execute()
    limite = _pedir_numero("¿Cuántos mensajes? (vacío = todos):", minimo=1, por_defecto=100)
    if limite is None:
        return
    folder = CARPETA_BASE / "Canales" / (str(sel["id"]).replace("-100", "c").replace("-", "_"))
    folder.mkdir(parents=True, exist_ok=True)
    _tabla_resumen(
        ["Origen", "Traducir", "Multimedia", "Mensajes", "Carpeta"],
        [(sel["nombre"], "sí" if trad else "no", "sí" if descargar else "no",
          str(limite), str(folder))],
        titulo="Resumen de descarga de canal",
    )
    if not inquirer.confirm("¿Ejecutar la descarga?", default=True).execute():
        styled_info("Cancelado.")
        return
    n = 0
    try:
        async for msg in client.iter_messages(peer, limit=limite):
            if not await _comprobar_conexion(client):
                break
            txt = procesar_texto_inteligente(msg.text, trad)
            if txt == "FILTERED_CONTENT":
                continue
            if descargar and msg.media:
                await _reintentar(lambda m=msg: download_media_robust(client, m, folder),
                                  etiqueta=f"descarga msg {msg.id}")
            elif msg.text:
                styled_info(msg.text[:80])
            n += 1
    except Exception as e:
        log("ERR", f"Error: {e}")
    _log_auditoria("DESCARGAR_CANAL", f"{sel['nombre']}: {n} mensajes → {folder}")
    styled_info(f"Procesados {n} mensajes.")


# ============================================================================
# FASE B4 · Estadísticas de un canal / tema
# ============================================================================
async def _estadisticas_canal(client):
    styled_info("Elige el canal (con filtro).")
    sel = await _seleccionar_chat(client, "Canal/foro:", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    peer = sel["ent"]
    topico = None
    if sel["tipo"] == "foro":
        topico = await _seleccionar_tema(client, peer, "Tema (o Volver = todo):", permitir_general=False)
    styled_info("Contando mensajes...")
    total = videos = fotos = audios = docs = 0
    async for msg in client.iter_messages(peer, reply_to=topico):
        total += 1
        t = _tipo_medio(msg)
        if t == "vídeo":
            videos += 1
        elif t == "foto":
            fotos += 1
        elif t == "audio":
            audios += 1
        elif t == "documento":
            docs += 1
    _tabla_resumen(
        ["Total", "Vídeos", "Fotos", "Audios", "Documentos"],
        [(str(total), str(videos), str(fotos), str(audios), str(docs))],
        titulo=f"Estadísticas de {sel['nombre']}" + (f" (tema {topico})" if topico else ""),
    )
    styled_info("Últimos títulos (hasta 10):")
    async for msg in client.iter_messages(peer, reply_to=topico, limit=10):
        if msg.message:
            styled_info(f"  • {msg.message[:60]}")
    _log_auditoria("ESTADISTICAS", f"{sel['nombre']}: {total} msgs ({videos}V/{fotos}F/{audios}A/{docs}D)")


# ============================================================================
# FASE B5 · Búsqueda por texto y descarga de resultados
# ============================================================================
async def _buscar_y_descargar(client, trad):
    styled_info("Elige el canal donde buscar (con filtro).")
    sel = await _seleccionar_chat(client, "Canal/foro:", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    peer = sel["ent"]
    topico = None
    if sel["tipo"] == "foro":
        topico = await _seleccionar_tema(client, peer, "Tema (o Volver = todo):", permitir_general=False)
    termino = inquirer.text("Texto a buscar:").execute().strip()
    if not termino:
        styled_warn("Término vacío.")
        return
    styled_info(f"Buscando '{termino}'...")
    coincidencias = []
    async for msg in client.iter_messages(peer, reply_to=topico, search=termino):
        nombre = getattr(getattr(msg, "file", None), "name", None) or f"msg_{msg.id}"
        coincidencias.append((msg.id, nombre, msg))
        if len(coincidencias) >= 50:
            break
    if not coincidencias:
        styled_warn("Sin coincidencias.")
        return
    _tabla_resumen(["ID", "Archivo/Texto", "Tipo"],
                   [(_str_id(i), n, _tipo_medio(m) or "texto")
                    for i, n, m in coincidencias],
                   titulo=f"{len(coincidencias)} coincidencias para '{termino}'")

    folder = CARPETA_BASE / "Busqueda"
    if not inquirer.confirm("¿Descargar el contenido de estas coincidencias?", default=True).execute():
        styled_info("Solo visualización.")
        return
    folder = _ruta_segura(folder)
    ok = 0
    for mid, nombre, msg in coincidencias:
        if not await _comprobar_conexion(client):
            break
        if msg.media:
            if await _reintentar(lambda m=msg: download_media_robust(client, m, folder),
                                 etiqueta=f"descarga búsqueda {mid}"):
                ok += 1
    _log_auditoria("BUSQUEDA", f"{sel['nombre']}: '{termino}' → {ok}")
    styled_success(f"Descargados {ok}/{len(coincidencias)} a {folder}.")


# ============================================================================
# Descarga de storys activas de un canal/grupo
# ============================================================================
async def _descargar_storys(client):
    """Descarga las storys activas (no expiradas) de un canal/grupo."""
    sel = await _seleccionar_chat(client, "Canal/grupo del que saco las storys:",
                                  tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    peer = sel["ent"]
    styled_info("Leyendo storys activas...")
    try:
        res = await client(GetPeerStoriesRequest(peer=peer))
    except Exception as e:
        limite = _mensaje_limite(e)
        styled_error(f"No se pudieron leer las storys: {limite or e}")
        return
    items = [s for s in getattr(res.stories, "stories", []) if not getattr(s, "min", False)]
    if not items:
        styled_info("Sin storys activas de ese chat.")
        return
    _tabla_resumen(["Story", "Fecha", "Vistas", "Caption"],
                   [(f"#{s.id}", str(getattr(s, "date", "") or ""), str(getattr(s, "views", 0) or 0),
                     (getattr(s, "caption", "") or "")[:40]) for s in items],
                   titulo=f"{len(items)} storys activas de {sel['nombre']}")

    folder = _ruta_segura(CARPETA_BASE / "Storys" / _saneado(sel["nombre"] or "sin_nombre"))
    if not inquirer.confirm(f"¿Descargar las {len(items)} storys a {folder}?", default=True).execute():
        styled_info("Cancelado.")
        return
    folder.mkdir(parents=True, exist_ok=True)
    ok = 0
    for s in items:
        media = getattr(s, "media", None)
        if not media or isinstance(media, MessageMediaWebPage):
            continue
        mime = getattr(getattr(media, "document", None), "mime_type", None) if getattr(media, "document", None) else None
        es_foto = getattr(media, "photo", None) is not None
        ext = {m: e for m, e in {"video/mp4": ".mp4", "image/jpeg": ".jpg", "image/png": ".png",
                                  "audio/ogg": ".ogg", "application/x-tgsticker": ".tgs",
                                  "image/webp": ".webp"}.items()}.get(mime) if mime else None
        if es_foto and not ext:
            ext = ".jpg"
        full = folder / f"story_{s.id}{ext or '.bin'}"
        temp = str(full) + ".part"
        if full.exists():
            styled_info(f"Ya existe: {full.name}")
            ok += 1
            continue
        fake = types.SimpleNamespace(id=s.id, media=media, date=getattr(s, "date", None))
        try:
            with open(temp, "wb") as f:
                await client.download_media(fake, file=f, progress_callback=lambda c, t: None)
            os.rename(temp, full)
            styled_success(f"  → {full.name}")
            ok += 1
        except Exception as e:
            log("ERR", f"No se pudo bajar story {s.id}: {e}")
    _log_auditoria("STORY", f"{sel['nombre']}: {ok}/{len(items)} storys → {folder}")
    styled_success(f"Descargadas {ok}/{len(items)} storys a {folder}.")


async def _transcribir_voice_canal(client):
    """Busca voice messages en un canal/tema y los transcribe con whisper."""
    sel = await _seleccionar_chat(client, "Canal/foro con voice messages:",
                                  tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    peer = sel["ent"]
    topico = None
    if sel["tipo"] == "foro":
        topico = await _seleccionar_tema(client, peer, "Tema (o Volver = todo):",
                                         permitir_general=False)
    limite = _pedir_numero("¿Cuántos mensajes revisar? (vacío = todos):",
                           minimo=1, por_defecto=200)
    if limite is None:
        return
    styled_info("Buscando voice messages...")
    voices = []
    async for msg in client.iter_messages(peer, reply_to=topico, limit=limite):
        m = getattr(msg, "media", None)
        if isinstance(m, MessageMediaDocument) and any(
                isinstance(a, DocumentAttributeAudio) and getattr(a, "voice", False)
                for a in (getattr(getattr(m, "document", None), "attributes", None) or [])):
            voices.append(msg)
        if len(voices) >= 50:
            break
    if not voices:
        styled_info("Sin voice messages en ese rango.")
        return
    folder = _ruta_segura(CARPETA_BASE / "Transcripciones" / _saneado(sel["nombre"] or "sin_nombre"))
    folder.mkdir(parents=True, exist_ok=True)
    if not inquirer.confirm(
            f"Transcribir {len(voices)} voice messages → {folder}? "
            "(descarga openai-whisper si falta; puede tardar)", default=True).execute():
        styled_info("Cancelado.")
        return
    ok = 0
    for msg in voices:
        if not await _comprobar_conexion(client):
            break
        if await _reintentar(lambda m=msg: _transcribir_voice(client, m, folder),
                             veces=2, etiqueta=f"transcripción voice {msg.id}"):
            ok += 1
        await asyncio.sleep(0.2)
    _log_auditoria("TRANSCRIBIR_VOICE", f"{sel['nombre']}: {ok}/{len(voices)}")
    styled_success(f"Transcritos {ok}/{len(voices)} → {folder}.")


def _str_id(x):
    return str(x)


# ============================================================================
# MÓDULO 2: Clonar & Backup
# ============================================================================
async def _clonar_canal_a_canal(client):
    styled_info("Elige el canal ORIGEN (puedes filtrar).")
    sel_origen = await _seleccionar_chat(client, "Canal ORIGEN:", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel_origen:
        return
    origen = sel_origen["ent"]
    styled_info("Elige el canal DESTINO (puedes filtrar).")
    sel_destino = await _seleccionar_chat(client, "Canal DESTINO:", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel_destino:
        return
    destino = sel_destino["ent"]
    limite = _pedir_numero("¿Cuántos mensajes clonar? (vacío = todos):", minimo=1, por_defecto=100)
    if limite is None:
        return
    descargar = inquirer.confirm("¿Descargar multimedia también?", default=False).execute()
    trad = inquirer.confirm("¿Traducir contenido al clonar?", default=False).execute()
    quitar_rem = inquirer.confirm("¿Quitar remitente? (reenviar como copia, sin 'Forwarded from')",
                                  default=False).execute()
    quitar_cap = inquirer.confirm("¿Quitar descripción/caption?", default=False).execute()
    _tabla_resumen(
        ["Origen", "Destino", "Límite", "Multimedia", "Traducir", "Sin remitente", "Sin caption"],
        [(sel_origen["nombre"], sel_destino["nombre"], str(limite),
          "sí" if descargar else "no", "sí" if trad else "no",
          "sí" if quitar_rem else "no", "sí" if quitar_cap else "no")],
        titulo="Resumen de clonación",
    )
    if not inquirer.confirm("¿Ejecutar la clonación?", default=True).execute():
        styled_info("Cancelado.")
        return
    cola = []
    try:
        async for message in client.iter_messages(origen, limit=limite, reverse=True):
            if not await _comprobar_conexion(client):
                break
            try:
                texto = procesar_texto_inteligente(message.text, trad)
                if texto == "FILTERED_CONTENT":
                    log("SPAM", f"Saltando ID {message.id}")
                    continue

                def _caption_emitir(m, txt):
                    """Devuelve el caption según las opciones de quitar descripción."""
                    if quitar_cap:
                        return None
                    return txt if (trad and txt) else m.message

                async def _enviar(m=message, txt=texto):
                    cap = _caption_emitir(m, txt)
                    # Si descargar=True, la media va al disco: no adjuntar, solo texto.
                    if descargar:
                        return await client.send_message(destino, cap if cap else "")
                    # Modo copia: sin "Forwarded from" (quitar remitente).
                    if quitar_rem or quitar_cap:
                        if m.media:
                            return await client.send_file(destino, m.media, caption=cap)
                        return await client.send_message(destino, cap if cap else "")
                    # Modo reenvío normal (con remitente y caption original).
                    return await client.send_message(destino, m)

                await _reintentar(_enviar, etiqueta=f"clonado ID {message.id}")
                if descargar and message.media:
                    cola.append(message)
                log("OK", f"Clonado ID: {message.id}")
                await asyncio.sleep(0.6)
            except Exception as e:
                log("ERR", f"Error en ID {message.id}: {e}")
    except Exception as e:
        log("ERR", f"Error: {e}")
    _log_auditoria("CLONAR", f"{sel_origen['nombre']} → {sel_destino['nombre']} ({limite} msgs)")
    if descargar and cola:
        styled_info(f"{len(cola)} archivos en cola.")
        if inquirer.confirm("¿Procesar descarga ahora?", default=False).execute():
            folder = _ruta_segura(CARPETA_BASE / "Clonados")
            for msg in cola:
                await _reintentar(lambda m=msg: download_media_robust(client, m, folder),
                                  etiqueta=f"descarga clonado {msg.id}")


def _ruta_backup():
    carpeta = _ruta_segura(CARPETA_BASE / "Backups")
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


async def _backup_a_archivo(client):
    """Guarda mensajes + media de un chat/tema en un JSON local (backup)."""
    sel = await _seleccionar_chat(client, "Chat a respaldar:", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    ent = sel["ent"]
    tema_id = None
    if _tipo(ent) == "foro":
        tema_id = await _seleccionar_tema(client, ent, "Elige el tema:")
        if tema_id is None:
            return
    limite = _pedir_numero("¿Cuántos mensajes respaldar? (vacío = todos):", minimo=1, por_defecto=200)
    if limite is None:
        return
    descargar = inquirer.confirm("¿Descargar media también al respaldo?", default=False).execute()
    if not inquirer.confirm("¿Ejecutar el backup?", default=True).execute():
        return
    nombre_base = _saneado(sel["nombre"])
    backup_dir = _ruta_backup() / f"{nombre_base}_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    media_dir = backup_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    data = []
    try:
        async for message in client.iter_messages(ent, limit=limite, reverse=True):
            if not await _comprobar_conexion(client):
                break
            registro = {"id": message.id, "text": message.text or "", "date": str(message.date)}
            if descargar and message.media:
                try:
                    ruta = await client.download_media(message, file=media_dir)
                    registro["media"] = str(ruta)
                except Exception as e:
                    log("ERR", f"id {message.id} media: {e}")
            data.append(registro)
            if len(data) % 100 == 0:
                styled_info(f"{len(data)} mensajes...")
            await asyncio.sleep(0.3)
        out = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps({"fuente": sel["nombre"], "tema": tema_id, "mensajes": data},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        _log_auditoria("BACKUP", f"{sel['nombre']} → {out} ({len(data)} msgs)")
        styled_success(f"Backup guardado: {out} ({len(data)} mensajes)")
    except Exception as e:
        styled_error(f"Error en backup: {e}")


async def _restaurar_backup(client):
    """Carga un backup JSON local y lo reenvía a un chat elegido."""
    backup_dir = _ruta_backup()
    archivos = sorted([f for f in backup_dir.glob("**/*.json") if f.is_file()])
    if not archivos:
        styled_warn("No hay backups guardados.")
        return
    op = inquirer.select("Elige el backup a restaurar:",
                         choices=[{"name": f"• {f.relative_to(backup_dir)}", "value": f}
                                  for f in archivos], pointer="▸").execute()
    if op is None:
        return
    try:
        data = json.loads(op.read_text(encoding="utf-8"))
        msgs = data.get("mensajes", [])
    except Exception as e:
        styled_error(f"No se pudo leer: {e}")
        return
    sel = await _seleccionar_chat(client, "Chat DESTINO de la restauración:",
                                  tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel:
        return
    destino = sel["ent"]
    trad = inquirer.confirm("¿Traducir al restaurar?", default=False).execute()
    quitar_cap = inquirer.confirm("¿Quitar descripción/caption al restaurar?", default=False).execute()
    if not inquirer.confirm(f"¿Restaurar {len(msgs)} mensajes a '{sel['nombre']}'?",
                            default=True).execute():
        return
    ok = 0
    for m in msgs:
        texto = procesar_texto_inteligente(m.get("text"), trad)
        if texto == "FILTERED_CONTENT":
            continue
        if quitar_cap:
            texto = ""
        ruta_media = m.get("media")
        try:
            if ruta_media and Path(ruta_media).exists():
                await client.send_message(destino, texto or None, file=ruta_media)
            elif texto:
                await client.send_message(destino, texto)
            else:
                continue
            ok += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            log("ERR", f"id {m.get('id')}: {e}")
    _log_auditoria("RESTAURAR", f"{data.get('fuente', '?')} → {sel['nombre']} ({ok} msgs)")
    styled_success(f"Restaurados {ok}/{len(msgs)} mensajes.")


async def modulo_clonar(client):
    while True:
        console.print(styled_panel("[bold white]MÓDULO CLONACIÓN / BACKUP[/bold white]", title="🔄", style=BG))
        op = inquirer.select(
            "Opciones:",
            choices=[
                {"name": "🔀  Clonar canal → canal", "value": "c"},
                {"name": "💾  Backup a archivo local", "value": "b"},
                {"name": "♻️  Restaurar backup", "value": "r"},
                {"name": "🔙  Volver", "value": "x"},
            ],
            pointer="▸",
        ).execute()
        if op in ("x", None):
            return
        if op == "c":
            await _clonar_canal_a_canal(client)
        elif op == "b":
            await _backup_a_archivo(client)
        elif op == "r":
            await _restaurar_backup(client)
        styled_info("Pulsa Enter para continuar...")
        input()


# ============================================================================
# MÓDULO 3: Chats y carpetas
# ============================================================================
async def _lista_chats(client, solo_creados=False, folder_filtro=None):
    rows = []
    async for d in client.iter_dialogs():
        ent = getattr(d, "entity", None)
        fid = getattr(d, "folder_id", None)
        carpeta = "Archivado" if fid == 1 else ("Principal" if fid in (None, 0) else f"#{fid}")
        creado = bool(getattr(ent, "creator", False)) if ent is not None else False
        if folder_filtro and folder_filtro.lower() not in (carpeta.lower(), (d.name or "").lower()):
            continue
        if solo_creados and not creado:
            continue
        rows.append((d.id, d.name or "(sin nombre)", _tipo(ent) if ent else "?", carpeta, "sí" if creado else "no"))
    return rows


def _tabla_chats(rows):
    t = Table(title="Chats", title_style=f"bold {BG}")
    for col in ("ID", "Nombre", "Tipo", "Carpeta", "Creado"):
        t.add_column(col, style=col in ("ID", "Nombre") and f"bold {FG}" or "white")
    for r in rows:
        t.add_row(*[str(r[0]), r[1], r[2], r[3], r[4]])
    console.print(t)


async def _crear_carpeta(client):
    """Crea una carpeta de chats con un título."""
    nombre = inquirer.text("Nombre de la carpeta:").execute().strip()
    if not nombre:
        return
    if not inquirer.confirm(f"¿Crear carpeta '{nombre}' (vacía)?", default=True).execute():
        return
    try:
        filtro = DialogFilter(
            id=0, title=nombre, pinned_peers=[], include_peers=[], exclude_peers=[],
            contacts=False, non_contacts=False, groups=False, broadcasts=False,
            bots=False, exclude_muted=False, exclude_read=False,
            exclude_archived=False, emoticon=None,
        )
        await client(UpdateDialogFilterRequest(id=0, filter=filtro))
        _log_auditoria("CREAR_CARPETA", nombre)
        styled_success(f"Carpeta '{nombre}' creada.")
    except Exception as e:
        limite = _mensaje_limite(e)
        styled_error(f"Error: {limite or e}")


async def _mover_chat_carpeta(client):
    """Mueve un chat dentro de una carpeta (folder)."""
    sel = await _seleccionar_chat(client, "Chat a mover:", filtro=None)
    if not sel:
        return
    folder_id = _pedir_numero("ID de carpeta destino (0 = Principal, 1 = Archivado):",
                              minimo=0, por_defecto=0)
    if folder_id is None:
        return
    if not inquirer.confirm(f"¿Mover '{sel['nombre']}' a la carpeta {folder_id}? (se aplica en Telegram)",
                            default=True).execute():
        styled_info("Cancelado.")
        return
    inp = await client.get_input_entity(sel["ent"])
    try:
        await client(EditPeerFoldersRequest(folder_peers=[InputFolderPeer(peer=inp, folder_id=folder_id)]))
    except Exception as e:
        limite = _mensaje_limite(e)
        styled_error(f"No se pudo mover: {limite or e}")
        return
    _log_auditoria("MOVERCARPETA", f"{sel['nombre']} → carpeta {folder_id}")
    styled_success(f"{sel['nombre']} movido a carpeta {folder_id}.")


async def _silenciar_chat(client):
    """Silencia / desilencia un chat o canal."""
    sel = await _seleccionar_chat(client, "Chat a silenciar/desilenciar:", filtro=None)
    if not sel:
        return
    silenciar = inquirer.confirm(f"Acción sobre '{sel['nombre']}': ¿silenciarlo? (No = desilenciarlo)",
                                 default=True).execute()
    muted_until = 2**31 - 1 if silenciar else 0
    peer = await client.get_input_entity(sel["ent"])
    try:
        await client(UpdateNotifySettingsRequest(
            peer=InputNotifyPeer(peer=peer),
            settings=InputPeerNotifySettings(show_previews=True, silent=False,
                                             mute_until=muted_until, sound="Default")))
    except Exception as e:
        limite = _mensaje_limite(e)
        styled_error(f"No se pudo cambiar notificaciones: {limite or e}")
        return
    _log_auditoria("SILENCIAR" if silenciar else "DESILENCIAR", sel["nombre"])
    styled_success(f"{sel['nombre']} {'silenciado' if silenciar else 'desilenciado'}.")


async def _pinar_chat(client):
    """Fija / desfija un chat arriba de la lista de chats."""
    sel = await _seleccionar_chat(client, "Chat a fijar/desfijar:", filtro=None)
    if not sel:
        return
    pin = inquirer.confirm(f"Acción sobre '{sel['nombre']}': ¿fijarlo arriba? (No = desfijarlo)",
                           default=True).execute()
    peer = await client.get_input_entity(sel["ent"])
    try:
        await client(ToggleDialogPinRequest(peer=peer, pinned=pin))
    except Exception as e:
        limite = _mensaje_limite(e)
        styled_error(f"No se pudo fijar: {limite or e}")
        return
    _log_auditoria("PINCHAT" if pin else "UNPINCHAT", sel["nombre"])
    styled_success(f"{sel['nombre']} {'fijado' if pin else 'desfijado'}.")


async def modulo_chats(client):
    console.print(styled_panel("[bold white]MÓDULO CHATS Y CARPETAS[/bold white]", title="🗂️", style=BG))
    while True:
        op = inquirer.select(
            "Opciones:",
            choices=[
                {"name": "📋  Listar chats (con filtros)", "value": "l"},
                {"name": "🗄️  Archivar / Desarchivar chat", "value": "a"},
                {"name": "🏷️  Listar por carpeta", "value": "f"},
                {"name": "📁  Crear carpeta", "value": "cf"},
                {"name": "📦  Mover chat a carpeta", "value": "m"},
                {"name": "🔇  Silenciar / Desilenciar chat", "value": "s"},
                {"name": "📌  Fijar / Desfijar chat", "value": "p"},
                {"name": "✏️  Renombrar / Mover archivos", "value": "r"},
                {"name": "🔙  Volver", "value": "b"},
            ],
            pointer="▸",
        ).execute()
        if op in ("b", None):
            break
        if op == "l":
            opcion_filtro, carpeta_filtro = _filtro_interactivo()
            items = await _listar_chats_filtrado(client, filtro=opcion_filtro, folder=carpeta_filtro)
            if not items:
                styled_warn("Sin resultados con ese filtro.")
                continue
            _tabla_chats([(i["id"], i["nombre"], i["tipo"], i["carpeta"],
                           "sí" if i["creado"] else "no") for i in items])
        elif op == "f":
            carpeta_filtro = inquirer.text("Nombre de carpeta / chat:").execute().strip()
            items = await _listar_chats_filtrado(client, filtro="todos", folder=carpeta_filtro)
            if not items:
                styled_warn("Sin resultados con ese filtro.")
                continue
            _tabla_chats([(i["id"], i["nombre"], i["tipo"], i["carpeta"],
                           "sí" if i["creado"] else "no") for i in items])
        elif op == "a":
            await _archivar(client)
        elif op == "cf":
            await _crear_carpeta(client)
        elif op == "m":
            await _mover_chat_carpeta(client)
        elif op == "s":
            await _silenciar_chat(client)
        elif op == "p":
            await _pinar_chat(client)
        elif op == "r":
            await _renombrar_mover(client)


# ============================================================================
# FASE B8 · Renombrar / Mover archivos descargados
# ============================================================================
async def _renombrar_mover(client):
    styled_info("Elige la carpeta local donde están los archivos.")
    carpeta_str = inquirer.text("Ruta de la carpeta (vacío = Descargas_Telegram):").execute().strip()
    carpeta = _ruta_segura(carpeta_str or str(CARPETA_BASE))
    archivos = sorted([f for f in carpeta.iterdir() if f.is_file()])
    if not archivos:
        styled_warn("Carpeta vacía.")
        return
    while True:
        op = inquirer.select(
            "Archivos:",
            choices=[{"name": f"✏️  {f.name}", "value": ("renombrar", f)} for f in archivos]
                    + [{"name": "📂  Mover a otra carpeta", "value": ("mover", None)}]
                    + [{"name": "🔙  Volver", "value": None}],
            pointer="▸",
        ).execute()
        if op is None:
            return
        accion, f = op
        if accion == "renombrar":
            nuevo = inquirer.text("Nuevo nombre:").execute().strip()
            if nuevo:
                destino = _saneado(Path(nuevo).name)
                nuevo_path = carpeta / destino
                if nuevo_path.exists():
                    styled_warn("Ya existe un archivo con ese nombre.")
                    continue
                if inquirer.confirm(f"¿Renombrar '{f.name}' → '{destino}'?", default=True).execute():
                    f.rename(nuevo_path)
                    _log_auditoria("RENOMBRAR", f"{f.name} → {destino}")
                    styled_success(f"Renombrado a {destino}")
        else:
            d_str = inquirer.text("Carpeta destino:").execute().strip()
            if not d_str:
                continue
            d = _ruta_segura(d_str)
            choice = inquirer.select("¿Qué muevo?",
                                     choices=[{"name": f"📄  {f.name}", "value": f} for f in archivos]
                                             + [{"name": "🔙  Volver", "value": None}],
                                     pointer="▸").execute()
            if choice is None:
                continue
            if inquirer.confirm(f"¿Mover '{choice.name}' a {d}?", default=True).execute():
                choice.rename(d / choice.name)
                _log_auditoria("MOVER", f"{choice.name} → {d}")
                styled_success(f"Movido a {d}")


async def _archivar(client, ref=None, folder_id=None):
    if ref is None:
        sel = await _seleccionar_chat(client, "Chat a archivar/desarchivar (con filtro):", filtro=None)
        if not sel:
            return
        ent = sel["ent"]
    else:
        ent = await resolver(client, ref)
    if folder_id is None:
        folder_id = 1 if inquirer.confirm("¿Archivar? (No = desarchivar)", default=True).execute() else 0
    inp = await client.get_input_entity(ent)
    await client(EditPeerFoldersRequest(folder_peers=[InputFolderPeer(peer=inp, folder_id=folder_id)]))
    _log_auditoria("ARCHIVAR" if folder_id == 1 else "DESARCHIVAR",
                   f"{getattr(ent, 'title', ref)} → {'Archivado' if folder_id == 1 else 'Principal'}")
    styled_success(f"{getattr(ent, 'title', ref)} → carpeta {'Archivado' if folder_id == 1 else 'Principal'}.")


# ============================================================================
# MÓDULO 4: Canales / Foros / Temas
# ============================================================================
async def modulo_foros(client):
    console.print(styled_panel("[bold white]MÓDULO CANALES / FOROS / TEMAS[/bold white]", title="🧭", style=BG))
    while True:
        op = inquirer.select(
            "Opciones:",
            choices=[
                {"name": "📋  Ver mis canales/foros", "value": "l"},
                {"name": "✨  Crear canal (con foro)", "value": "cc"},
                {"name": "📂  Archivar / Desarchivar", "value": "ar"},
                {"name": "🗂️  Gestionar temas de un foro", "value": "temas"},
                {"name": "📤  Migrar canal → tema de foro", "value": "mig"},
                {"name": "🗑️  Borrar canal", "value": "del"},
                {"name": "🔙  Volver", "value": "b"},
            ],
            pointer="▸",
        ).execute()
        if op in ("b", None):
            break
        if op == "l":
            opcion_filtro, carpeta_filtro = _filtro_interactivo()
            items = await _listar_chats_filtrado(client, tipos=["foro", "canal"],
                                                 filtro=opcion_filtro, folder=carpeta_filtro)
            if not items:
                styled_warn("Sin resultados con ese filtro.")
                break
            _tabla_chats([(i["id"], i["nombre"], i["tipo"], i["carpeta"],
                           "sí" if i["creado"] else "no") for i in items])
        elif op == "cc":
            await _crear_canal(client)
        elif op == "ar":
            await _archivar(client)
        elif op == "temas":
            await _gestionar_temas(client)
        elif op == "mig":
            await _migrar_canal_a_tema(client)
        elif op == "del":
            await _borrar_canal(client)


async def _crear_canal(client):
    titulo = inquirer.text("Título del canal:").execute().strip()
    about = inquirer.text("Descripción (vacío = nada):").execute().strip()
    foro = inquirer.confirm("¿Activar foro (temas)?", default=True).execute()
    tipo = "canal" if not foro else "canal-foro"
    if not inquirer.confirm(f"¿Crear {tipo} '{titulo}'? (se aplica en Telegram)", default=True).execute():
        styled_info("Cancelado.")
        return
    res = await client(CreateChannelRequest(title=titulo, about=about, broadcast=True, megagroup=False, forum=bool(foro)))
    chat = res.chats[0]
    _log_auditoria("CREAR_CANAL", f"{chat.title} (id={chat.id}) foro={bool(foro)}")
    styled_success(f"Canal '{chat.title}' id={chat.id} foro={bool(foro)}")


async def _gestionar_temas(client):
    sel = await _seleccionar_chat(client, "Selecciona el foro:", tipos=["foro"], filtro=None)
    if not sel:
        return
    foro_ent = sel["ent"]
    res = await client(GetForumTopicsRequest(peer=foro_ent, offset_date=datetime(1970, 1, 1), offset_id=0, offset_topic=0, limit=100))
    temas = {t.id: t.title for t in res.topics}
    if not temas:
        styled_warn("Sin temas.")
        return
    t = Table(title=f"Temas de {sel['nombre']}", title_style=f"bold {BG}")
    t.add_column("ID", style=f"bold {FG}")
    t.add_column("Título")
    for tid, tit in temas.items():
        t.add_row(str(tid), tit)
    console.print(t)
    op = inquirer.select(
        "Acción:",
        choices=[
            {"name": "➕  Crear tema", "value": "c"},
            {"name": "✏️  Renombrar tema", "value": "r"},
            {"name": "🗑️  Vaciar tema (borrar mensajes)", "value": "d"},
            {"name": "🔙  Volver", "value": "b"},
        ],
        pointer="▸",
    ).execute()
    if op == "c":
        titulos = inquirer.text("Títulos (separados por coma):").execute().strip()
        lista = [x.strip() for x in titulos.split(",") if x.strip()]
        if not lista:
            return
        if not inquirer.confirm(f"¿Crear {len(lista)} tema(s) en '{sel['nombre']}'?",
                                default=True).execute():
            styled_info("Cancelado.")
            return
        for i, titulo in enumerate(lista):
            r = await client(CreateForumTopicRequest(peer=foro_ent, title=titulo, random_id=int(asyncio.get_event_loop().time() * 1000) + i))
            _log_auditoria("CREAR_TEMA", f"{sel['nombre']}: {titulo}")
            styled_success(f"Tema '{titulo}' creado (id={getattr(r.updates[0], 'message', None).id if r.updates else '?'})")
    elif op == "r":
        tid = await _seleccionar_tema(client, foro_ent, "Elegir tema a renombrar:")
        if tid is None:
            return
        nuevo = inquirer.text("Nuevo título:").execute().strip()
        if nuevo:
            if not inquirer.confirm(f"¿Renombrar tema a '{nuevo}'? (se aplica en Telegram)",
                                    default=True).execute():
                styled_info("Cancelado.")
                return
            await client(EditForumTopicRequest(peer=foro_ent, topic_id=tid, title=nuevo))
            _log_auditoria("RENOMBRAR_TEMA", f"{sel['nombre']}/tema{tid} → {nuevo}")
            styled_success("Tema renombrado.")
    elif op == "d":
        tid = await _seleccionar_tema(client, foro_ent, "Elegir tema a vaciar:")
        if tid is None:
            return
        titulo = temas.get(tid, str(tid))
        if not await _confirmar_destruccion(
                titulo,
                detalle=f"Vaciar TODO el contenido del tema en '{sel['nombre']}'"):
            return
        await client(DeleteTopicHistoryRequest(peer=foro_ent, top_msg_id=tid))
        _log_auditoria("VACIAR_TEMA", f"{sel['nombre']}: {titulo}")
        styled_success("Tema vaciado (borrado de mensajes).")


async def _migrar_canal_a_tema(client):
    styled_info("Destino: elige el foro (con filtro).")
    sel_foro = await _seleccionar_chat(client, "Foro DESTINO:", tipos=["foro"], filtro=None)
    if not sel_foro:
        return
    foro_ent = sel_foro["ent"]
    styled_info("Destino: elige el tema.")
    tema_id = await _seleccionar_tema(client, foro_ent, "Tema destino:")
    if tema_id is None:
        return
    styled_info("Origen: elige el canal/grupo a mover (puedes filtrar).")
    sel_origen = await _seleccionar_chat(client, "Canal ORIGEN:", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel_origen:
        return
    source_ent = sel_origen["ent"]
    n = 0
    styled_info("Contando mensajes...")
    async for _ in client.iter_messages(source_ent):
        n += 1
    _tabla_resumen(
        ["Origen", "Destino", "Tema", "Mensajes"],
        [(sel_origen["nombre"], sel_foro["nombre"], tema_id, str(n))],
        titulo="Resumen de migración (re-subida)",
    )
    if not inquirer.confirm("¿Ejecutar la migración (sin borrar origen)?", default=True).execute():
        styled_info("Cancelado.")
        return
    quitar_cap = inquirer.confirm("¿Quitar descripción/caption?", default=False).execute()
    borrar_origen = False
    if inquirer.confirm("¿BORRAR el origen tras migrar correctamente? (irreversible)",
                        default=False).execute():
        if not await _confirmar_destruccion(
                sel_origen["nombre"],
                detalle=f"BORRAR el canal ORIGEN tras migrar sus {n} mensajes"):
            styled_warn("Se migrará sin borrar el origen.")
        else:
            borrar_origen = True

    nenv = ntxt = 0
    styled_info(f"Migrando {n} mensajes...")
    async for msg in client.iter_messages(source_ent, reverse=True):
        if not await _comprobar_conexion(client):
            break
        try:
            cap = None if quitar_cap else msg.message
            if msg.message and getattr(msg, "media", None) and getattr(msg, "document", None):
                async def _f(m=msg, c=cap):
                    return await client.send_file(foro_ent, m.media, caption=c, reply_to=tema_id)
                if await _reintentar(_f, etiqueta=f"migrar msg {msg.id}"):
                    nenv += 1
            elif msg.message and not getattr(msg, "media", None):
                async def _t(m=msg, c=cap):
                    return await client.send_message(foro_ent, c or "", reply_to=tema_id)
                if await _reintentar(_t, etiqueta=f"migrar msg {msg.id}"):
                    ntxt += 1
            elif getattr(msg, "media", None) and getattr(msg, "document", None):
                async def _d(m=msg):
                    return await client.send_file(foro_ent, m.media, reply_to=tema_id)
                if await _reintentar(_d, etiqueta=f"migrar msg {msg.id}"):
                    nenv += 1
            else:
                continue
        except Exception as e:
            log("x", f" fallo msg {msg.id}: {e}")
        await asyncio.sleep(0.3)
    styled_success(f"Migrados {nenv} vídeos + {ntxt} textos al tema {tema_id}.")
    if borrar_origen:
        styled_warn("La migración se hace por re-subida; el borrado del origen hay que hacerlo manualmente para no perder datos.")
        await _vaciar_canal(client, sel_origen["ent"], sel_origen["nombre"])
    _log_auditoria("MIGRAR", f"{sel_origen['nombre']} → {sel_foro['nombre']}/tema{tema_id}: {nenv}V+{ntxt}T")


async def _vaciar_canal(client, ent, nombre):
    """Borra TODOS los mensajes de un canal/grupo (con doble confirmación)."""
    if not await _confirmar_destruccion(
            nombre, detalle="BORRADO DE CANAL: SE BORRARÁ TODO EL HISTORIAL.",
            client=client, ent=ent):
        return
    await client(DeleteHistoryRequest(peer=ent, max_id=0))
    _log_auditoria("VACIAR_CANAL", nombre)
    styled_success("Historial del canal borrado.")


async def _borrar_canal(client):
    sel = await _seleccionar_chat(client, "Canal a BORRAR (con filtro):",
                                  tipos=["canal", "foro"], filtro=None)
    if not sel:
        return
    ent = sel["ent"]
    titulo = getattr(ent, "title", sel["nombre"])
    if not await _confirmar_destruccion(
            titulo, detalle=f"Vas a borrar el canal (id={ent.id})",
            client=client, ent=ent):
        return
    await client(DeleteChannelRequest(channel=ent))
    _log_auditoria("BORRAR_CANAL", titulo)
    styled_success("Canal borrado.")


# ============================================================================
# MÓDULO 5: Subida (pipeline)
# ============================================================================
async def modulo_subida(client):
    console.print(styled_panel("[bold white]MÓDULO SUBIDA / SYNC (autónomo)[/bold white]", title="🚚", style=BG))
    while True:
        op = inquirer.select(
            "Opciones:",
            choices=[
                {"name": "🔄  Sync carpeta → Telegram (lo nuevo)", "value": "sync"},
                {"name": "📄  Ver grupos.json (foros/grupos)", "value": "ver"},
                {"name": "🚀  Subir pasada (ruteo por grupos.json)", "value": "subir"},
                {"name": "🎬  Subir un archivo concreto", "value": "archivo"},
                {"name": "⏰  Subida diferida (programar)", "value": "diferida"},
                {"name": "🏷️  Plantillas de caption", "value": "plantillas"},
                {"name": "💾  Exportar / Importar config", "value": "config"},
                {"name": "🔙  Volver", "value": "b"},
            ],
            pointer="▸",
        ).execute()
        if op in ("b", None):
            break
        if op == "sync":
            await _sync_carpeta(client)
        elif op == "ver":
            _ver_grupos()
        elif op == "subir":
            await _subir_pasada(client)
        elif op == "archivo":
            await _subir_archivo_manual(client)
        elif op == "diferida":
            await _subida_diferida(client)
        elif op == "plantillas":
            _gestionar_plantillas()
        elif op == "config":
            _export_import_config()


# ============================================================================
# FASE B1 · Sync carpeta → Telegram (lo nuevo, con dedup y elegir destino)
# ============================================================================
async def _sync_carpeta(client):
    styled_info("1) Elige la carpeta local con los archivos.")
    carpeta_str = inquirer.text("Ruta de la carpeta (vacío = Descargas_Telegram):").execute().strip()
    if not carpeta_str:
        carpeta_str = str(CARPETA_BASE)
    carpeta = _ruta_segura(carpeta_str)

    archivos = sorted([a for a in carpeta.iterdir() if a.is_file()])
    if not archivos:
        styled_warn("Carpeta vacía.")
        return
    _tabla_resumen(["Archivo", "MB", "¿Nuevo?"],
                   [(a.name, f"{a.stat().st_size / 1024**2:.0f}",
                     "no" if sync_ya_subido(a) else "sí") for a in archivos],
                   titulo=f"Archivos en {carpeta}")
    nuevo = [a for a in archivos if not sync_ya_subido(a)]
    styled_info(f"{len(nuevo)} archivo(s) nuevo(s) por subir.")
    if not nuevo:
        styled_success("Todo ya subido (sync_cli.json).")
        return

    styled_info("2) Elige el canal DESTINO (los míos).")
    sel_dest = await _seleccionar_chat(client, "Canal/foro DESTINO:",
                                       tipos=["canal", "grupo", "foro"],
                                       filtro="mios", creados=True)
    if not sel_dest:
        return
    destino = sel_dest["ent"]
    topico_dest = None
    if sel_dest["tipo"] == "foro":
        topico_dest = await _seleccionar_tema(client, destino, "Tema destino:")

    # Elegir archivos: todos o 1 a 1
    todos = inquirer.confirm(f"¿Subir los {len(nuevo)} nuevos? (No = elegir 1 a 1)",
                             default=True).execute()
    elegidos = nuevo if todos else []
    if not todos:
        while True:
            cho = [{"name": a.name, "value": a} for a in nuevo]
            cho.append({"name": "✅  Terminar", "value": None})
            pick = inquirer.select("Elige archivo a subir:", choices=cho, pointer="▸").execute()
            if pick is None:
                break
            if inquirer.confirm(f"¿Subir '{pick.name}'?", default=True).execute():
                elegidos.append(pick)
            if not inquirer.confirm("¿Elegir otro?", default=True).execute():
                break
    if not elegidos:
        styled_info("Nada seleccionado.")
        return

    _tabla_resumen(["Destino", "Tema", "Archivos a subir"],
                   [(sel_dest["nombre"], topico_dest if topico_dest else "-", str(len(elegidos)))],
                   titulo="Resumen de sync")
    if not inquirer.confirm("¿Ejecutar la subida?", default=True).execute():
        styled_info("Cancelado.")
        return

    ok = 0
    for a in elegidos:
        if not await _comprobar_conexion(client):
            break
        cap = _caption_archivo(a)
        result = await subir_archivo_cli(client, a, [(destino, topico_dest)], cap,
                                         keyword_from_filename(a.name), usar_sync=True)
        if result["estado"] == "ok":
            ok += 1
        await asyncio.sleep(0.3)
    _log_auditoria("SYNC", f"{carpeta} → {sel_dest['nombre']}: {ok}/{len(elegidos)}")
    styled_success(f"Sync completado: {ok}/{len(elegidos)} subidos.")


# ============================================================================
# FASE B10 · Subida diferida
# ============================================================================
async def _subida_diferida(client):
    styled_info("Subida programada. Elige el canal destino (los míos).")
    sel = await _seleccionar_chat(client, "Canal/foro destino:", tipos=["canal", "grupo", "foro"],
                                  filtro="mios", creados=True)
    if not sel:
        return
    destino = sel["ent"]
    topico = None
    if sel["tipo"] == "foro":
        topico = await _seleccionar_tema(client, destino, "Tema destino:")
    ruta = inquirer.text("Ruta del archivo a subir:").execute().strip()
    if not ruta or not Path(ruta).exists():
        styled_error("Archivo no válido.")
        return
    archivo = Path(ruta)
    hora = inquirer.text("Hora de subida (HH:MM):").execute().strip()
    try:
        hh, mm = hora.split(":")
        momento = datetime.now().replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    except (ValueError, AttributeError):
        styled_error("Formato de hora inválido (usa HH:MM).")
        return
    styled_info(f"Esperando hasta {momento.strftime('%H:%M')}... (Ctrl+C para cancelar)")
    _log_auditoria("SUBIDA_DIFERIDA", f"{archivo.name} → {sel['nombre']} a las {momento.strftime('%H:%M')}")
    while datetime.now() < momento:
        await asyncio.sleep(10)
    styled_success("Hora alcanzada, subiendo...")
    cap = _caption_archivo(archivo)
    result = await subir_archivo_cli(client, archivo, [(destino, topico)], cap,
                                     keyword_from_filename(archivo.name), usar_sync=True)
    styled_success(f"Subida: {result['estado']} ({result['destinos']} destinos).")


# ============================================================================
# FASE B11 · Plantillas de caption
# ============================================================================
PLANTILLAS_FILE = REPO_DIR / "config" / "plantillas_cli.json"


def _cargar_plantillas():
    default = {"{canal}": "🎬 Directo de {canal}", "{titulo}": "{titulo} | {canal}"}
    if not PLANTILLAS_FILE.exists():
        return default
    try:
        with open(PLANTILLAS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data else default
    except (OSError, json.JSONDecodeError):
        return default


def _guardar_plantillas(data):
    PLANTILLAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLANTILLAS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _gestionar_plantillas():
    while True:
        data = _cargar_plantillas()
        op = inquirer.select(
            "Plantillas de caption:",
            choices=[
                {"name": "📋  Ver", "value": "ver"},
                {"name": "➕  Añadir", "value": "add"},
                {"name": "🗑️  Eliminar", "value": "del"},
                {"name": "🔙  Volver", "value": "b"},
            ],
            pointer="▸",
        ).execute()
        if op in ("b", None):
            break
        if op == "ver":
            _tabla_resumen(["Clave", "Caption"], [(k, v) for k, v in data.items()],
                           titulo="Plantillas de caption")
        elif op == "add":
            clave = inquirer.text("Clave (ej: {canal}):").execute().strip()
            valor = inquirer.text("Caption (ej: 🎬 Directo de {canal}):").execute().strip()
            if clave and valor:
                data[clave] = valor
                _guardar_plantillas(data)
                styled_success(f"Plantilla '{clave}' guardada.")
        elif op == "del":
            if not data:
                styled_warn("Sin plantillas.")
                continue
            clave = inquirer.select("Eliminar:", choices=[{"name": k, "value": k} for k in data]
                                    + [{"name": "🔙  Volver", "value": None}], pointer="▸").execute()
            if clave and clave in data:
                data.pop(clave)
                _guardar_plantillas(data)
                styled_success(f"'{clave}' eliminado.")


def _caption_archivo(archivo):
    """Caption: si hay episodios detectados los usa; si no, la plantilla."""
    episodios = episodios_desde_json(archivo)
    if episodios:
        return caption_sin_episodio(str(episodios))
    plantillas = _cargar_plantillas()
    canal = canal_from_filename(archivo.name) or "desconocido"
    recambio = plantillas.get("{canal}", "🎬 Directo de {canal}")
    return recambio.format(canal=canal, titulo=archivo.stem)


# ============================================================================
# FASE B12 · Exportar / Importar config
# ============================================================================
def _export_import_config():
    op = inquirer.select(
        "Config:",
        choices=[
            {"name": "💾  Exportar (backup)", "value": "exp"},
            {"name": "📂  Importar (restaurar)", "value": "imp"},
            {"name": "🔙  Volver", "value": "b"},
        ],
        pointer="▸",
    ).execute()
    if op in ("b", None):
        return
    if op == "exp":
        dest = inquirer.text("Destino del backup (carpeta):").execute().strip() or str(REPO_DIR / "data" / "backups")
        d = _ruta_segura(dest)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        for src, nombre in [(GRUPOS_FILE, f"grupos_{ts}.json"),
                            (PLANTILLAS_FILE, f"plantillas_{ts}.json")]:
            if src.exists():
                shutil.copy2(src, d / nombre)
        styled_success(f"Backup de config en {d}")
        _log_auditoria("EXPORT_CONFIG", str(d))
    else:
        src = inquirer.text("Ruta del backup (carpeta):").execute().strip() or str(REPO_DIR / "data" / "backups")
        d = Path(src)
        if not d.exists():
            styled_error("No existe esa carpeta.")
            return
        dest_config = PLANTILLAS_FILE.parent
        dest_config.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in sorted(d.glob("grupos_*.json")):
            shutil.copy2(f, dest_config / "grupos.json")
            styled_info(f"Restaurado grupos.json desde {f.name}")
            count += 1
        for f in sorted(d.glob("plantillas_*.json")):
            shutil.copy2(f, dest_config / "plantillas_cli.json")
            styled_info(f"Restaurado plantillas desde {f.name}")
            count += 1
        if not count:
            styled_warn("Sin backups en esa carpeta.")
            return
        styled_success(f"Importadas {count} copias.")
        _log_auditoria("IMPORT_CONFIG", str(d))


def _ver_grupos():
    try:
        default, grupos, foros = cargar_grupos()
    except SystemExit as e:
        styled_error(str(e))
        return
    t = Table(title=f"Config de enrutado ({GRUPOS_FILE})", title_style=f"bold {BG}")
    t.add_column("Tipo", style=f"bold {FG}")
    t.add_column("id / clave")
    t.add_column("general")
    t.add_column("temas")
    for f in foros:
        nombres = ", ".join(tt["nombre"] for tt in f["temas"][:6]) + ("..." if len(f["temas"]) > 6 else "")
        t.add_row("foro", f"{f['nombre']} ({f['id']})", str(f.get("general")), nombres)
    for g in grupos:
        t.add_row("grupo", f"{g['nombre']} ({g['id']})", "-", "-")
    if not foros and not grupos:
        t.add_row("-", "sin foros ni grupos", "-", "-")
    console.print(t)


async def _subir_pasada(client):
    carpeta = inquirer.text("Carpeta con *_compressed.mp4:").execute().strip() or "/comprimidos"
    p = Path(carpeta)
    if not p.exists():
        styled_error(f"No existe {p}")
        return
    default, grupos, foros = cargar_grupos()
    plan = []
    for archivo in sorted(p.glob("*_compressed.mp4")):
        if sync_ya_subido(archivo):
            continue
        destinos = await _calcular_destinos(archivo, default, grupos, foros)
        keyword = keyword_from_filename(archivo.name)
        if not destinos:
            styled_warn(f"{archivo.name}: sin destino → omitido.")
            continue
        plan.append((archivo, destinos, keyword))
    if not plan:
        styled_success("Nada pendiente por subir.")
        return
    _tabla_resumen(["Archivo", "Keyword", "Destinos"],
                   [(a.name, k or "-", str(d)) for a, d, k in plan],
                   titulo=f"Plan de pasada ({len(plan)} archivo(s))")
    if not inquirer.confirm("¿Ejecutar la pasada?", default=True).execute():
        styled_info("Cancelado.")
        return
    total = 0
    for archivo, destinos, keyword in plan:
        if not await _comprobar_conexion(client):
            break
        styled_info(f"{archivo.name}: keyword='{keyword}' → {destinos}")
        await subir_archivo_cli(client, archivo, destinos, _caption_archivo(archivo), keyword)
        total += 1
    _log_auditoria("PASADA", f"{p}: {total} archivos")
    styled_success(f"Pasada completada: {total} archivos.")


async def _subir_archivo_manual(client):
    ruta = inquirer.text("Ruta del archivo a subir:").execute().strip()
    archivo = Path(ruta)
    if not archivo.exists():
        styled_error(f"No existe {archivo}")
        return
    default, grupos, foros = cargar_grupos()
    destinos = await _calcular_destinos(archivo, default, grupos, foros)
    keyword = keyword_from_filename(archivo.name)
    styled_info(f"{archivo.name}: → {destinos}")
    if not inquirer.confirm("¿Ejecutar la subida?", default=True).execute():
        styled_info("Cancelado.")
        return
    await subir_archivo_cli(client, archivo, destinos, _caption_archivo(archivo), keyword)


async def _calcular_destinos(archivo, default, grupos, foros):
    canal = canal_from_filename(archivo.name)
    keyword = keyword_from_filename(archivo.name)
    destinos = [(g, None) for g in grupos_para_keyword(keyword, default, grupos)]
    if foros:
        episodios = episodios_desde_json(archivo)
        if not episodios:
            episodios = detectar_episodios(archivo)
        foro = tid = None
        for fo in foros:
            m = match_tema_foro(fo, canal)
            if m:
                foro, tid = fo, m
                break
        if foro is None:
            foro = foro_objetivo(foros, canal)
            tid = match_tema_foro(foro, keyword) or (match_tema_foro(foro, str(episodios)) if episodios else None)
        destinos.append((foro["id"], tid if tid else foro.get("general")))
    return list(dict.fromkeys(destinos))


# ============================================================================
# MÓDULO 6: Vigilante (ampliado)
# ============================================================================
def _vig_cargar():
    """Carga la config persistente del vigilante (o devuelve dict vacío)."""
    try:
        with open(VIGCONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _vig_guardar(cfg):
    Path(VIGCONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(VIGCONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    styled_success(f"Config guardada en {VIGCONFIG_FILE}")


def _vig_nombre_chat(cfg, chat_id, destinos):
    """Devuelve el nombre guardado del chat (o el id)."""
    for d in cfg.get("nombres", []):
        if d["id"] == chat_id:
            return d["nombre"]
    return str(chat_id)


def _tema_mensaje(msg):
    """Devuelve el topic_id del mensaje (foro) o None si no es de un tema."""
    rt = getattr(msg, "reply_to", None)
    if rt is not None:
        return getattr(rt, "reply_to_top_id", None)
    return None


def _cooldown_activo(ultimo, ahora, seg):
    return ultimo is not None and (ahora - ultimo).total_seconds() < seg


async def modulo_vigilante(client):
    """Vigilante mejorado: filtros por tipo/emisor, inclusión/exclusión de chats y
    temas, varios destinos con razones, cooldown, config persistente y resumen."""
    previa = _vig_cargar()
    if previa and inquirer.confirm(
            "¿Reusar la config del vigilante guardada?", default=True).execute():
        cfg = previa
    else:
        cfg = {}
    usar = inquirer.select("Configuración:",
                           choices=[
                               {"name": "✨  Configurar vigilante desde cero", "value": "nuevo"},
                               {"name": "🔄  Cambiar configuración actual", "value": "editar"},
                               {"name": "🧹  Borrar config guardada y empezar", "value": "borrar"},
                               {"name": "❌  Cancelar", "value": "salir"},
                           ], pointer="▸").execute()
    if usar == "salir":
        return
    if usar == "borrar":
        try:
            Path(VIGCONFIG_FILE).unlink(missing_ok=True)
        except OSError:
            pass
        cfg = {}
        styled_info("Config borrada.")
    elif usar == "nuevo":
        cfg = {}
    # --- 1. Chats: incluir / excluir / temas ---
    styled_info("PASO 1 · CHATS A VIGILAR")
    todos = inquirer.confirm("¿Vigilar TODOS los chats? (No = elegir una lista)",
                             default=cfg.get("todos", True)).execute()
    incluir = []
    if not todos:
        styled_info("Elige los chats a vigilar (varias selecciones).")
        while True:
            sel = await _seleccionar_chat(client, "Añadir chat a vigilar (Volver = terminar):",
                                          tipos=["canal", "grupo", "foro"], filtro=None)
            if not sel:
                break
            incluir.append({"id": getattr(sel["ent"], "id", None), "nombre": sel["nombre"],
                            "tipo": sel["tipo"]})
            if not inquirer.confirm("¿Añadir otro chat?", default=True).execute():
                break
        cfg["incluir"] = incluir
    else:
        cfg["incluir"] = []
    cfg["todos"] = todos

    excluir = cfg.get("excluir", [])
    if inquirer.confirm("¿Excluir algunos chats concretos?", default=bool(excluir)).execute():
        excluir = []
        styled_info("Elige los chats a EXCLUIR (no se vigilarán).")
        while True:
            sel = await _seleccionar_chat(client, "Añadir chat a EXCLUIR (Volver = terminar):",
                                          tipos=["canal", "grupo", "foro"], filtro=None)
            if not sel:
                break
            excluir.append({"id": getattr(sel["ent"], "id", None), "nombre": sel["nombre"]})
            if not inquirer.confirm("¿Añadir otro chat a excluir?", default=True).execute():
                break
    cfg["excluir"] = excluir

    # Temas de foro restringidos
    solo_temas = cfg.get("solo_temas", {})
    if inquirer.confirm("¿Vigilar SOLO ciertos temas de foros?", default=bool(solo_temas)).execute():
        solo_temas = {}
        styled_info("Elige foro y, dentro, los temas que sí se vigilan.")
        while True:
            sel = await _seleccionar_chat(client, "Foro (Volver = terminar):",
                                          tipos=["foro"], filtro=None)
            if not sel:
                break
            foro_ent = sel["ent"]
            styled_info("Elige los temas (1 a 1).")
            temas_elegidos = []
            while True:
                tid = await _seleccionar_tema(client, foro_ent,
                                              "Tema a incluir (Volver = terminar):")
                if tid is None:
                    break
                temas_elegidos.append(tid)
                if not inquirer.confirm("¿Añadir otro tema?", default=True).execute():
                    break
            solo_temas[str(getattr(foro_ent, "id", None))] = temas_elegidos
            if not inquirer.confirm("¿Configurar otro foro?", default=False).execute():
                break
    cfg["solo_temas"] = solo_temas

    # --- 2. Tipos de medio ---
    styled_info("PASO 2 · FILTRO POR TIPO DE MEDIO")
    cfg["tipos"] = cfg.get("tipos", TIPOS_MEDIA[:])
    if inquirer.confirm("¿Filtrar solo por ciertos tipos de medio?", default=False).execute():
        tipos_ok = {t: True for t in TIPOS_MEDIA}
        for t in TIPOS_MEDIA:
            tipos_ok[t] = inquirer.confirm(f"¿Detectar {t}s?", default=(t in cfg.get("tipos", TIPOS_MEDIA))).execute()
        cfg["tipos"] = [t for t, ok in tipos_ok.items() if ok]
    styled_info(f"Tipos activos: {', '.join(cfg['tipos']) if cfg['tipos'] else 'TODOS (sin filtro de tipo)'}")

    # --- 3. Emisores ---
    styled_info("PASO 3 · FILTRO POR EMISOR")
    cfg["emisores"] = cfg.get("emisores", [])
    if inquirer.confirm("¿Solo reaccionar a ciertos remitentes?", default=bool(cfg["emisores"])).execute():
        emisores = []
        styled_info("Elige los remitentes (canales/users) que sí interesan.")
        while True:
            sel = await _seleccionar_chat(client, "Remitente (Volver = terminar):",
                                          tipos=["canal", "grupo", "foro", "user"], filtro=None)
            if not sel:
                break
            emisores.append({"id": getattr(sel["ent"], "id", None), "nombre": sel["nombre"]})
            if not inquirer.confirm("¿Añadir otro remitente?", default=True).execute():
                break
        cfg["emisores"] = emisores
    styled_info("Emisores: " + (", ".join(e["nombre"] for e in cfg["emisores"]) or "TODOS"))

    # --- 4. Palabras clave ---
    styled_info("PASO 4 · PALABRAS CLAVE")
    extra_str = inquirer.text("Palabras clave extra (separadas por coma):",
                              default=", ".join(cfg.get("keywords", []))).execute()
    cfg["keywords"] = [p.lower() for p in extra_str.split(",") if p.strip()]

    # --- 5. Destinos + modo de reenvío ---
    styled_info("PASO 5 · REENVÍO")
    destinos = cfg.get("destinos", [])
    reenviar = inquirer.confirm("¿REENVIAR alertas a otro(s) chat(s)?",
                                default=bool(destinos)).execute()
    if reenviar:
        destinos = []
        styled_info("Elige los destinos (varias selecciones; 'Mensajes guardados' = tu propio chat).")
        while True:
            sel = await _seleccionar_chat(client, "Destino del reenvío (Volver = terminar):",
                                          tipos=["canal", "grupo", "foro", "me"], filtro=None)
            if not sel:
                break
            destinos.append({"id": getattr(sel["ent"], "id", None) or "me",
                             "nombre": sel["nombre"]})
            if not inquirer.confirm("¿Añadir otro destino?", default=True).execute():
                break
        if not destinos:
            reenviar = False
    cfg["destinos"] = destinos

    cfg["reenviar_original"] = reenviar and inquirer.confirm(
        "¿Reenviar el mensaje ORIGINAL (media incluida) en vez de solo el texto?",
        default=cfg.get("reenviar_original", False)).execute()
    cfg["quitar_rem"] = cfg.get("reenviar_original") and inquirer.confirm(
        "¿Quitar remitente al reenviar? (copia sin 'Forwarded from')",
        default=cfg.get("quitar_rem", False)).execute()
    cfg["quitar_cap"] = cfg.get("reenviar_original") and inquirer.confirm(
        "¿Quitar descripción/caption al reenviar?", default=cfg.get("quitar_cap", False)).execute()
    cfg["marcar_razon"] = reenviar and inquirer.confirm(
        "¿Marcar en la alerta QUÉ keyword/tipo disparó?", default=cfg.get("marcar_razon", True)).execute()

    # --- 6. Descarga de media ---
    styled_info("PASO 6 · DESCARGA DE MEDIA")
    cfg["descargar_media"] = inquirer.confirm(
        "¿Descargar archivos adjuntos de las alertas?", default=cfg.get("descargar_media", False)).execute()
    if cfg["descargar_media"]:
        cfg["carpeta_media"] = _ruta_segura(cfg.get("carpeta_media") or
                                            CARPETA_BASE / "Vigilante_Media").as_posix()

    # --- 7. Cooldown ---
    styled_info("PASO 7 · COOLDOWN (anti-ráfagas)")
    cfg["cooldown"] = _pedir_numero(
        "Segundos de espera entre alertas del mismo chat (0 = sin límite):",
        minimo=0, por_defecto=cfg.get("cooldown", 30)) or 0

    _vig_guardar(cfg)

    # --- Resumen de confirmación ---
    _tabla_resumen(
        ["Chats", "Tipos", "Emisores", "Keywords", "Destinos", "Media", "Cooldown"],
        [("TODOS" if cfg["todos"] else f"{len(cfg['incluir'])} chat(s)",
          ", ".join(cfg["tipos"]) if cfg["tipos"] else "todo",
          "todos" if not cfg["emisores"] else f"{len(cfg['emisores'])}",
          ", ".join(cfg["keywords"]) or "-",
          ", ".join(d["nombre"] for d in cfg["destinos"]) or "Mensajes guardados",
          "sí" if cfg.get("descargar_media") else "no",
          f"{cfg['cooldown']}s")],
        titulo="Resumen del vigilante",
    )
    if not inquirer.confirm("¿Iniciar el vigilante?", default=True).execute():
        styled_info("Cancelado.")
        return

    ids_incluir = {c["id"] for c in cfg["incluir"]}
    ids_excluir = {c["id"] for c in cfg["excluir"]}
    ids_emisores = {e["id"] for e in cfg["emisores"]}
    ids_destinos = [d["id"] for d in cfg["destinos"]]
    solo_temas = {int(k): set(v) for k, v in cfg.get("solo_temas", {}).items()}
    keywords = cfg.get("keywords", [])
    tipos_ok = set(cfg.get("tipos", [])) or None
    cooldown = cfg.get("cooldown", 0)
    al_guardado = "me"
    contador = {"alertas": 0, "reenviadas": 0, "descargadas": 0}
    ultimo_por_chat = {}

    @client.on(events.NewMessage)
    async def handler(event):
        chat_id = getattr(event, "chat_id", None)
        if chat_id is None:
            return
        if ids_incluir and chat_id not in ids_incluir:
            return
        if chat_id in ids_excluir:
            return
        msg = event.message
        if solo_temas and chat_id in solo_temas:
            t = _tema_mensaje(msg)
            if t not in solo_temas[chat_id]:
                return
        if cooldown and chat_id in ultimo_por_chat and \
                _cooldown_activo(ultimo_por_chat[chat_id], datetime.now(timezone.utc), cooldown):
            return

        razones = []
        texto = msg.message or ""
        if procesar_texto_inteligente(texto) == "FILTERED_CONTENT":
            razones.append("🚫 contenido filtrado")
        if keywords and any(p in texto.lower() for p in keywords):
            razones.append("🔑 keyword")
        tipo = _tipo_medio(msg)
        if tipos_ok and tipo and tipo in tipos_ok:
            razones.append(f"🎯 {tipo}")
        if ids_emisores:
            sender = getattr(msg, "sender_id", None) or getattr(msg, "from_id", None)
            if sender is not None and getattr(sender, "user_id", sender) in ids_emisores:
                razones.append("👤 emisor")
        if not razones:
            return
        ultimo_por_chat[chat_id] = datetime.now(timezone.utc)
        contador["alertas"] += 1
        log("SPAM", f"Vigilante: {', '.join(razones)} → {texto[:60]}")

        cabecera = " | ".join(razones)
        alerta = f"🔔 Alerta ({cabecera})\n{texto[:1500]}" if texto else \
            f"🔔 Alerta ({cabecera}): media detectada"
        origen = f"\n· Origen: {_vig_nombre_chat(cfg, chat_id, ids_destinos)}"
        if _tema_mensaje(msg):
            origen += f" (tema {_tema_mensaje(msg)})"
        try:
            for dest in ids_destinos:
                if cfg.get("reenviar_original"):
                    if cfg.get("quitar_rem") or cfg.get("quitar_cap"):
                        cap = None if cfg.get("quitar_cap") else (msg.message or None)
                        if msg.media:
                            await client.send_file(dest, msg.media, caption=cap)
                        elif cap:
                            await client.send_message(dest, cap)
                        else:
                            await client.send_message(dest, alerta + origen)
                    else:
                        await client.send_message(dest, msg)
                    contador["reenviadas"] += 1
                else:
                    if cfg.get("marcar_razon"):
                        await client.send_message(dest, alerta + origen)
                    else:
                        await client.send_message(dest, alerta)
                    contador["reenviadas"] += 1
            if not ids_destinos:
                await client.send_message(al_guardado,
                                          (alerta + origen) if cfg.get("marcar_razon") else alerta)
                contador["reenviadas"] += 1
        except Exception as e:
            log("ERR", f"Vigilante reenvío: {e}")
        if cfg.get("descargar_media") and msg.media:
            try:
                folder = _ruta_segura(cfg.get("carpeta_media") or CARPETA_BASE / "Vigilante_Media")
                if await _reintentar(lambda: download_media_robust(client, msg, folder),
                                     veces=2, etiqueta="vigilante media"):
                    contador["descargadas"] += 1
            except Exception:
                pass

    styled_success("Vigilante activo. Ctrl+C para detener (y ver resumen).")
    styled_info(f"  Chats: {'TODOS' if cfg['todos'] else f'{len(ids_incluir)}'} · "
                f"Tipos: {', '.join(cfg['tipos']) if cfg['tipos'] else 'todo'} · "
                f"Destinos: {len(ids_destinos) or 'guardados'}")
    try:
        while client.is_connected():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        styled_warn(f"Conexión perdida: {e}")
    styled_info("Deteniendo vigilante...")
    try:
        client.remove_event_handler(handler, events.NewMessage)
    except Exception:
        pass
    _log_auditoria("VIGILANTE_FIN",
                   f"{contador['alertas']} alertas, {contador['reenviadas']} reenviadas, "
                   f"{contador['descargadas']} media")
    styled_success(f"Resumen: {contador['alertas']} alertas · "
                   f"{contador['reenviadas']} reenviadas · "
                   f"{contador['descargadas']} media descargada.")


# ============================================================================
# MÓDULO 7: Modo guiado (flujo completo)
# ============================================================================
async def _modo_guiado(client):
    """Flujo guiado paso a paso: origen → tema → qué → carpeta → destino → ejecutar."""
    console.print(styled_panel("[bold white]MODO GUIADO[/bold white]", title="🧭", style=BG))

    styled_info("PASO 1 · ORIGEN (de dónde saco el contenido).")
    sel_o = await _seleccionar_chat(client, "Origen:", tipos=["canal", "grupo", "foro"], filtro=None)
    if not sel_o:
        return
    origen = sel_o["ent"]
    topico_o = None
    if sel_o["tipo"] == "foro":
        styled_info("PASO 1b · Tema del origen (Volver = todo).")
        topico_o = await _seleccionar_tema(client, origen, "Tema origen:", permitir_general=False)

    styled_info("PASO 2 · QUÉ descargo.")
    desde_f = hasta_f = None
    if inquirer.confirm("¿Filtrar por fecha?", default=False).execute():
        d = inquirer.text("Desde (YYYY-MM-DD):").execute().strip()
        h = inquirer.text("Hasta (YYYY-MM-DD):").execute().strip()
        try:
            desde_f = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc) if d else None
            hasta_f = datetime.strptime(h, "%Y-%m-%d").replace(hour=23, minute=59, second=59,
                                                                tzinfo=timezone.utc) if h else None
        except ValueError:
            styled_warn("Fecha inválida; se ignora.")
    tipos_ok = {t: True for t in TIPOS_MEDIA}
    if inquirer.confirm("¿Filtrar por tipo de medio?", default=False).execute():
        for t in TIPOS_MEDIA:
            tipos_ok[t] = inquirer.confirm(f"¿{t.capitalize()}s?", default=True).execute()

    styled_info("PASO 3 · Buscando archivos...")
    mensajes = []
    async for msg in client.iter_messages(origen, reply_to=topico_o):
        if not getattr(msg, "media", None):
            continue
        if desde_f is not None and msg.date and msg.date < desde_f:
            continue
        if hasta_f is not None and msg.date and msg.date > hasta_f:
            continue
        t = _tipo_medio(msg)
        if t and not tipos_ok.get(t, True):
            continue
        nombre = msg.file.name if getattr(getattr(msg, "file", None), "name", None) else f"msg_{msg.id}"
        mensajes.append((msg.id, nombre, msg))
        if len(mensajes) >= 200:
            break
    if not mensajes:
        styled_warn("Sin archivos que cumplan los filtros.")
        return
    styled_info(f"Encontrados {len(mensajes)} archivos.")

    todos = inquirer.confirm(f"¿Descargar los {len(mensajes)} (No = elegir 1×1)?", default=True).execute()
    elegidos = mensajes if todos else []
    if not todos:
        while True:
            cho = [{"name": n, "value": (mid, msg)} for mid, n, msg in mensajes]
            cho.append({"name": "✅  Terminar", "value": None})
            pick = inquirer.select("Elige archivo:", choices=cho, pointer="▸").execute()
            if pick is None:
                break
            mid, msg = pick
            nombre = msg.file.name or f"msg_{mid}"
            if inquirer.confirm(f"¿Descargar '{nombre}'?", default=True).execute():
                elegidos.append((mid, nombre, msg))
            if not inquirer.confirm("¿Otro?", default=True).execute():
                break
    if not elegidos:
        styled_info("Nada seleccionado.")
        return

    styled_info("PASO 4 · Carpeta local.")
    carpeta = _ruta_segura(inquirer.text(
        "Carpeta (vacío = Descargas_Telegram/Origen):").execute().strip()
        or str(CARPETA_BASE / "Origen" / _saneado(sel_o["nombre"])))

    styled_info("PASO 5 · ¿RE-SUBIR al terminar?")
    resubir = inquirer.confirm("¿Subir a un canal/tema propio tras descargar?", default=False).execute()
    destino = topico_d = None
    if resubir:
        sel_d = await _seleccionar_chat(client, "Destino (los míos):",
                                        tipos=["canal", "grupo", "foro"],
                                        filtro="mios", creados=True)
        if not sel_d:
            resubir = False
        else:
            destino = sel_d["ent"]
            if sel_d["tipo"] == "foro":
                topico_d = await _seleccionar_tema(client, destino, "Tema destino:")

    _tabla_resumen(
        ["Origen", "Tema", "Archivos", "Carpeta", "Re-subir", "Destino"],
        [(sel_o["nombre"], topico_o or "-", str(len(elegidos)), str(carpeta),
          "sí" if resubir else "no", (sel_d["nombre"] if resubir else "-"))],
        titulo="Resumen final del modo guiado",
    )
    if not inquirer.confirm("¿Ejecutar todo el flujo?", default=True).execute():
        styled_info("Cancelado.")
        return

    ok = 0
    for mid, nombre, msg in elegidos:
        if not await _comprobar_conexion(client):
            break
        r = await _reintentar(lambda m=msg: download_media_robust(client, m, carpeta),
                              etiqueta=f"descarga {nombre}")
        if r:
            ok += 1
        await asyncio.sleep(0.2)
    styled_success(f"Descargados {ok}/{len(elegidos)} a {carpeta}.")

    if resubir and ok:
        styled_info("Re-subiendo...")
        n_sub = 0
        for _, nombre, msg in elegidos:
            ruta = carpeta / _saneado(nombre)
            if not ruta.exists():
                continue
            async def _sf(r=ruta, n=nombre, td=topico_d, d=destino):
                return await client.send_file(d, str(r), caption=n, reply_to=td)
            if await _reintentar(_sf, etiqueta=f"subida {nombre}"):
                n_sub += 1
            await asyncio.sleep(0.3)
        styled_success(f"Re-subidos {n_sub} archivos.")
        _log_auditoria("MODO_GUIADO", f"{sel_o['nombre']} → {sel_d['nombre']}: {ok} descargados, {n_sub} re-subidos")
    else:
        _log_auditoria("MODO_GUIADO", f"{sel_o['nombre']} → carpeta {carpeta}: {ok} descargados")


# ============================================================================
# BÚSQUEDA DE FOTOS EN GUARDADOS (por descripción y por OCR del contenido)
# ============================================================================
def _tesseract_ok():
    return shutil.which("tesseract") is not None


async def _buscar_caption_fotos(client, termino, limite=200):
    """Recorre los mensajes guardados ('me') y devuelve los que son FOTOS cuyo
    caption contiene el término. Devuelve lista de (msg, motivo)."""
    res = []
    try:
        async for msg in client.iter_messages("me", search=termino, filter=InputMessagesFilterPhotos,
                                        limit=limite, wait_time=2):
            if getattr(msg, "media", None) and isinstance(getattr(msg, "media", None), MessageMediaPhoto):
                res.append((msg, "caption"))
    except Exception:
        pass
    return res


def _ocr_de_imagen(ruta):
    """Corre tesseract sobre una imagen y devuelve el texto (o "")."""
    try:
        r = subprocess.run(["tesseract", str(ruta), "stdout", "-l", "spa+eng", "--psm", "6"],
                           capture_output=True, text=True, timeout=60)
        return r.stdout
    except Exception:
        return ""


async def _buscar_fotos_en_guardados(client):
    termino = inquirer.text("Texto a buscar (p. ej. 'apaches'):").execute().strip()
    if not termino:
        styled_warn("Sin texto de búsqueda.")
        return

    en_caption = inquirer.confirm(
        "¿Buscar en la DESCRIPCIÓN de las fotos?", default=True).execute()
    por_ocr = inquirer.confirm(
        "¿Buscar TAMBIÉN dentro de la imagen (OCR, más lento)?", default=True).execute()
    limite = _pedir_numero("Máximo de fotos a revisar (vacío = 200):",
                           minimo=1, por_defecto=200)
    if limite is None:
        limite = 200

    tmp_dir = Path(tempfile.mkdtemp(prefix="tg_buscar_"))
    resultados = []  # (msg, motivo)

    styled_info(f"Buscando '{termino}' en 'Mensajes guardados'...")

    try:
        if en_caption:
            for msg, motivo in await _buscar_caption_fotos(client, termino, limite):
                resultados.append((msg, motivo))

        if por_ocr:
            if not _tesseract_ok():
                styled_warn("tesseract no está instalado; se omite la búsqueda por OCR.")
            else:
                n = 0
                skipped = 0
                try:
                    async for msg in client.iter_messages("me", filter=InputMessagesFilterPhotos,
                                                              limit=limite, wait_time=2):
                        n += 1
                        styled_info(f"  OCR: {n}/{limite}...")
                        if any(msg.id == m.id for m, _ in resultados):
                            continue
                        try:
                            ruta = await client.download_media(msg, file=tmp_dir)
                        except Exception:
                            skipped += 1
                            if skipped > 5:
                                styled_warn(f"Demasiados errores de descarga tras {n} fotos, parando OCR.")
                                break
                            continue
                        if ruta and Path(ruta).is_file():
                            cli_txt = _ocr_de_imagen(Path(ruta)).lower()
                            if termino.lower() in cli_txt:
                                resultados.append((msg, "OCR"))
                except Exception as e:
                    styled_warn(f"Conexión perdida tras {n} fotos (skipped={skipped}): {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if not resultados:
        styled_warn(f"No se encontró ninguna foto con '{termino}' (descripción u OCR).")
        return

    styled_success(f"Encontradas {len(resultados)} foto(s) con '{termino}'.")
    filas = []
    for msg, motivo in resultados:
        fecha = str(getattr(msg, "date", ""))[:16]
        cap = (getattr(msg, "text", "") or "").replace("\n", " ")[:40]
        filas.append((msg.id, motivo, fecha, cap))
    _tabla_resumen(["ID", "Dónde", "Fecha", "Descripción"], filas, titulo="Fotos encontradas")

    descargar = inquirer.confirm("¿Descargar las fotos encontradas?", default=True).execute()
    if not descargar:
        return
    carpeta = _ruta_segura(inquirer.text(
        "Carpeta destino (vacío = Descargas_Telegram/Busqueda_Guardados):").execute().strip()
        or str(CARPETA_BASE / "Busqueda_Guardados"))
    carpeta.mkdir(parents=True, exist_ok=True)
    carpeta = Path(carpeta)
    ok = 0
    for msg, _ in resultados:
        if await download_media_robust(client, msg, carpeta):
            ok += 1
        await asyncio.sleep(0.2)
    _log_auditoria("BUSCAR_FOTOS", f"'{termino}': {ok} descargadas de {len(resultados)}")
    styled_success(f"Descargadas {ok}/{len(resultados)} fotos a {carpeta}")


async def modulo_buscar_fotos(client):
    console.print(styled_panel("[bold white]BUSCAR FOTOS EN GUARDADOS[/bold white]", title="🔎", style=BG))
    await _buscar_fotos_en_guardados(client)


# ============================================================================
# MÓDULO 12: Editar descripciones en Guardados (sin descargar archivos)
# ============================================================================
def _tipo_edicion_msg(msg):
    if msg.photo:
        return "FOTO"
    if msg.video:
        return "VIDEO"
    if msg.voice:
        return "VOICE"
    if getattr(msg, "document", None):
        return "DOC"
    if msg.sticker:
        return "STICKER"
    if msg.text:
        return "TEXTO"
    return "OTRO"


async def _confirmar_editable(client, msg_id):
    d = await client(GetMessageEditDataRequest(peer="me", id=msg_id))
    return getattr(d, "caption", False)


async def _editar_caption_guardados(client):
    styled_info("""
Este módulo AÑADE texto a la descripción de un mensaje de 'Mensajes guardados',
sin sustituir lo que ya tiene y sin descargar el archivo.

Recordatorio: no todo se puede editar. Telegram lo decide por mensaje (no por
antigüedad); se consulta antes de guardar y solo se edita si es posible.
""")

    busqueda = inquirer.text(
        "Texto para localizar el mensaje (p. ej. 'apaches', 'mononoke'):"
    ).execute().strip()
    tipo_filtro = inquirer.select(
        "¿Qué tipo de mensaje?",
        choices=[
            {"name": "Fotos", "value": "foto"},
            {"name": "Videos", "value": "video"},
            {"name": "Cualquiera", "value": "any"},
        ],
        pointer="▸", default="foto",
    ).execute()
    limite = _pedir_numero("Máximo de mensajes a revisar (vacío = 300):",
                           minimo=1, por_defecto=300)
    if limite is None:
        limite = 300

    filtro = None
    if tipo_filtro == "foto":
        filtro = InputMessagesFilterPhotos
    elif tipo_filtro == "video":
        from telethon.tl.types import InputMessagesFilterVideo
        filtro = InputMessagesFilterVideo

    styled_info(f"Buscando '{busqueda}' en 'Mensajes guardados'...")
    candidatos = []
    iterator = client.iter_messages("me", filter=filtro, limit=limite)
    async for msg in iterator:
        texto = msg.text or ""
        if busqueda.lower() in texto.lower():
            candidatos.append(msg)
            if len(candidatos) >= 25:
                break

    if not candidatos:
        styled_warn(f"No se encontró ningún mensaje con '{busqueda}'.")
        return

    styled_success(f"{len(candidatos)} mensaje(s) coinciden. Revisa la lista:")
    filas = []
    for msg in candidatos:
        fecha = str(getattr(msg, "date", ""))[:16]
        cap = (msg.text or "").replace("\n", " ")[:38] or "(sin descripción)"
        filas.append((msg.id, _tipo_edicion_msg(msg), fecha, cap))
    _tabla_resumen(["ID", "Tipo", "Fecha", "Descripción"], filas,
                   titulo="Candidatos (confirma antes de guardar)")

    elegir = inquirer.select(
        "¿Quieres editar TODOS, elegir por ID, o cancelar?",
        choices=[
            {"name": "Todos los listados", "value": "all"},
            {"name": "Elegir por ID", "value": "pick"},
            {"name": "Cancelar", "value": "cancel"},
        ],
        pointer="▸", default="pick",
    ).execute()
    if elegir == "cancel":
        styled_warn("Cancelado.")
        return

    seleccion = []
    if elegir == "pick":
        raw = inquirer.text("IDs separados por comas (p. ej. 122490,122489):").execute().strip()
        ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        seleccion = [m for m in candidatos if m.id in ids]
    else:
        seleccion = candidatos

    if not seleccion:
        styled_warn("No se seleccionó ningún mensaje.")
        return

    texto_a_anadir = inquirer.text("Texto que quieres AÑADIR a la descripción:").execute()
    if not texto_a_anadir.strip():
        styled_warn("Sin texto, nada que añadir.")
        return

    confirm = inquirer.confirm(
        f"¿Añadir a {len(seleccion)} mensaje(s)? Se hace en su sitio, no se borra lo actual.",
        default=True).execute()
    if not confirm:
        styled_warn("Cancelado.")
        return

    no_editables = []
    editados = 0
    for msg in seleccion:
        try:
            ok = await _confirmar_editable(client, msg.id)
        except Exception as e:
            styled_warn(f"ID {msg.id}: no se pudo comprobar ({e})")
            no_editables.append(msg.id)
            continue
        if not ok:
            styled_warn(
                f"ID {msg.id}: Telegram no permite editar la descripción de este mensaje.")
            no_editables.append(msg.id)
            continue
        anterior = (msg.text or "").rstrip() or ""
        nuevo = f"{anterior}\n{texto_a_anadir}".strip() if anterior else texto_a_anadir.strip()
        try:
            await client.edit_message("me", msg.id, text=nuevo)
            editados += 1
            styled_success(f"ID {msg.id}: descripción actualizada.")
        except Exception as e:
            styled_warn(f"ID {msg.id}: error al guardar ({e})")
            no_editables.append(msg.id)

    styled_success(f"Editados {editados} de {len(seleccion)}.")
    if no_editables:
        styled_warn(f"No editables / con error: {', '.join(map(str, no_editables))}")
    _log_auditoria("EDITAR_CAPTION",
                   f"'{busqueda}': {editados} editados de {len(seleccion)}, "
                   f"no editables {len(no_editables)}")


async def modulo_editar_caption(client):
    console.print(styled_panel("[bold white]EDITAR DESCRIPCIONES EN GUARDADOS[/bold white]",
                               title="✏️", style=BG))
    await _editar_caption_guardados(client)


# ============================================================================
# MÓDULO 8: Limpieza / Programación
# ============================================================================
async def _modo_limpieza(client):
    console.print(styled_panel("[bold white]LIMPIEZA / PROGRAMACIÓN / ESTADO[/bold white]", title="🧹", style=BG))
    while True:
        op = inquirer.select(
            "Opciones:",
            choices=[
                {"name": "📊  Estado de la conversión (monitor)", "value": "prog"},
                {"name": "🧹  Limpiar archivos temporales (.part, .jpg, .staging)", "value": "limp"},
                {"name": "🗑️  Limpiar descargas ya subidas (sync_cli)", "value": "sync"},
                {"name": "⏰  Programar sync automático (cada N min)", "value": "auto"},
                {"name": "🔙  Volver", "value": "b"},
            ],
            pointer="▸",
        ).execute()
        if op in ("b", None):
            return
        if op == "prog":
            await _progreso_conversion(client)
        elif op == "limp":
            await _limpiar_temporales()
        elif op == "sync":
            _limpiar_sync()
        elif op == "auto":
            await _programar_sync(client)


async def _limpiar_temporales():
    carpetas = [CARPETA_BASE, CARPETA_BASE / "Masivo", CARPETA_BASE / "Canales"]
    carpetas += [p for p in CARPETA_BASE.rglob("*") if p.is_dir()]
    encontrados = []
    for c in carpetas:
        for f in c.glob("*"):
            if f.is_file() and (f.suffix in (".part", ".jpg") or ".staging" in str(f) or f.name.endswith(".part")):
                encontrados.append(f)
    # .jpg de thumbs (nombres que acompañan a un mp4)
    thumbs = [f for f in encontrados if f.suffix == ".jpg" and f.with_suffix(".mp4").exists()]
    for t in thumbs:
        if t in encontrados:
            encontrados.remove(t)
    if not encontrados:
        styled_success("Sin temporales que limpiar.")
        return
    _tabla_resumen(["Archivo", "KB"], [(f.name, f"{f.stat().st_size / 1024:.0f}") for f in encontrados],
                   titulo="Temporales encontrados")
    if not inquirer.confirm(f"¿Eliminar {len(encontrados)} archivos?", default=False).execute():
        styled_info("Cancelado.")
        return
    n = 0
    for f in encontrados:
        try:
            f.unlink(missing_ok=True)
            n += 1
        except OSError as e:
            log("ERR", f"No se pudo borrar {f.name}: {e}")
    _log_auditoria("LIMPIEZA", f"{n} temporales eliminados")
    styled_success(f"{n} temporales eliminados.")


def _limpiar_sync():
    lista = _sync_cargar()
    if not lista:
        styled_success("sync_cli.json vacío.")
        return
    _tabla_resumen(["#", "Archivo"], [(str(i + 1), p) for i, p in enumerate(lista)],
                   titulo=f"Registrados en sync_cli.json ({len(lista)})")
    if not inquirer.confirm(f"¿Vaciar el registro de sync ({len(lista)} entradas)? "
                            "(No borra archivos, solo el seguimiento)", default=False).execute():
        styled_info("Cancelado.")
        return
    _sync_guardar([])
    _log_auditoria("LIMPIEZA_SYNC", f"{len(lista)} entradas vaciadas")
    styled_success("Registro de sync vaciado.")


async def _programar_sync(client):
    styled_info("Programación de sync automático (solo lo nuevo).")
    carpeta = _ruta_segura(inquirer.text("Carpeta (vacío = Descargas_Telegram):").execute().strip() or str(CARPETA_BASE))
    sel = await _seleccionar_chat(client, "Canal/foro destino (los míos):", tipos=["canal", "grupo", "foro"],
                                  filtro="mios", creados=True)
    if not sel:
        return
    destino = sel["ent"]
    topico = None
    if sel["tipo"] == "foro":
        topico = await _seleccionar_tema(client, destino, "Tema destino:")
    minutos = _pedir_numero("Cada cuántos minutos revisar?", minimo=1, por_defecto=30)
    if minutos is None:
        return
    styled_warn(f"Sync automático cada {minutos} min en {carpeta} → {sel['nombre']}. Ctrl+C para detener.")
    _log_auditoria("PROGRAMAR_SYNC", f"cada {minutos} min: {carpeta} → {sel['nombre']}")
    while True:
        try:
            nuevos = [a for a in carpeta.iterdir() if a.is_file() and not sync_ya_subido(a)]
            if nuevos:
                styled_info(f"{len(nuevos)} nuevos → subiendo...")
                for a in nuevos:
                    cap = _caption_archivo(a)
                    await subir_archivo_cli(client, a, [(destino, topico)], cap,
                                            keyword_from_filename(a.name), usar_sync=True)
                    await asyncio.sleep(0.3)
                styled_success("Tanda completada.")
            else:
                styled_info("Sin novedades.")
        except KeyboardInterrupt:
            styled_warn("Sync automático detenido.")
            return
        except Exception as e:
            styled_warn(f"Error en ciclo: {e}")
        await asyncio.sleep(minutos * 60)


# ============================================================================
# PIN / UNPIN (fijar y desfijar mensajes)
# ============================================================================
async def _ultimo_mensaje_id(client, ent, tema_id=None):
    """Devuelve el id del último mensaje de un chat (o tema de foro)."""
    kwargs = dict(peer=ent, limit=1)
    res = await client(GetHistoryRequest(**kwargs))
    msgs = res.messages
    if not msgs:
        return None
    return msgs[0].id


async def modulo_pin(client):
    """Fijar / desfijar mensajes en un chat o tema."""
    sel = await _seleccionar_chat(client, "Selecciona el chat donde fijar/desfijar:",
                                  tipos=["grupo", "canal", "foro"], filtro=None)
    if not sel:
        return
    ent = sel["ent"]
    ent_ref = ent

    tema_id = None
    if _tipo(ent) == "foro":
        tema_id = await _seleccionar_tema(client, ent, "Elige el tema:")
        if tema_id is None:
            return

    while True:
        console.clear()
        console.print(styled_panel(
            f"[bold white]{sel['nombre']}[/bold white] · {sel['tipo']}"
            f"{' · tema ' + str(tema_id) if tema_id else ''}",
            title="📌 PIN / UNPIN", style=f"bold {FG}"
        ))
        op = inquirer.select(
            "Acción:",
            choices=[
                {"name": "📌  Fijar mensaje (por ID o último)", "value": "pin"},
                {"name": "📌  Fijar con silencio (sin notificación)", "value": "pin_silent"},
                {"name": "🔓  Desfijar un mensaje concreto", "value": "unpin"},
                {"name": "🗑️  Desfijar TODOS los fijados", "value": "unpin_all"},
                {"name": "🔙  Volver", "value": "b"},
            ],
            pointer="▸",
        ).execute()
        if op in ("b", None):
            return
        try:
            if op in ("pin", "pin_silent"):
                ultimo = await _ultimo_mensaje_id(client, ent_ref, tema_id)
                mid_str = inquirer.text(
                    f"ID del mensaje a fijar (vacío = último, ahora {ultimo}):"
                ).execute().strip()
                mid = int(mid_str) if mid_str.isdigit() else (ultimo or 1)
                if not inquirer.confirm(
                        f"¿Fijar el mensaje {mid} en '{sel['nombre']}'?",
                        default=True).execute():
                    continue
                await client(UpdatePinnedMessageRequest(
                    peer=ent_ref, id=mid,
                    silent=(op == "pin_silent"), unpin=False))
                _log_auditoria("PIN", f"{sel['nombre']} msg {mid}")
                styled_success(f"Mensaje {mid} fijado.")
            elif op == "unpin":
                ultimo = await _ultimo_mensaje_id(client, ent_ref, tema_id)
                mid_str = inquirer.text(
                    f"ID del mensaje a desfijar (vacío = último, ahora {ultimo}):"
                ).execute().strip()
                mid = int(mid_str) if mid_str.isdigit() else (ultimo or 1)
                if not inquirer.confirm(
                        f"¿Desfijar el mensaje {mid}?", default=True).execute():
                    continue
                await client(UpdatePinnedMessageRequest(peer=ent_ref, id=mid, unpin=True))
                _log_auditoria("UNPIN", f"{sel['nombre']} msg {mid}")
                styled_success(f"Mensaje {mid} desfijado.")
            elif op == "unpin_all":
                if not inquirer.confirm(
                        f"¿Desfijar TODOS los mensajes fijados de '{sel['nombre']}'?",
                        default=False).execute():
                    continue
                kwargs = {"peer": ent_ref}
                if tema_id:
                    kwargs["top_msg_id"] = tema_id
                await client(UnpinAllMessagesRequest(**kwargs))
                _log_auditoria("UNPIN_ALL", sel["nombre"])
                styled_success("Mensajes desfijados.")
        except Exception as e:
            limite = _mensaje_limite(e)
            styled_error(f"Error: {limite or e}")
        styled_info("Pulsa Enter para continuar...")
        input()


# ============================================================================
# CONFIG / main
# ============================================================================
def _ver_auditoria():
    if not AUDIT_FILE.exists() or AUDIT_FILE.stat().st_size == 0:
        styled_warn("Sin registros de auditoría aún.")
        return
    lineas = AUDIT_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    n = _pedir_numero("¿Cuántas últimas líneas ver? (vacío = todas):",
                      minimo=1, por_defecto=50)
    if n is None:
        return
    ultimas = lineas[-n:]
    styled_info(f"Últimos {len(ultimas)} eventos de {AUDIT_FILE}")
    for l in ultimas:
        console.print(f"  [dim]{l}[/dim]")


def modulo_config(client):
    while True:
        console.clear()
        console.print(styled_panel(
            f"[bold white]Credenciales: config.bin ok[/bold white]\n"
            f"[dim]Sesión: {SESION}[/dim]\n[dim]Registros: {GRUPOS_FILE}[/dim]",
            title="⚙️ CONFIG", style=BG
        ))
        op = inquirer.select(
            "Opciones:",
            choices=[
                {"name": "📋  Ver log de auditoría", "value": "audit"},
                {"name": "🚪  Cerrar sesión y salir", "value": "exit"},
                {"name": "🔙  Volver", "value": "b"},
            ],
            pointer="▸",
        ).execute()
        if op in ("b", None):
            return
        if op == "audit":
            _ver_auditoria()
        elif op == "exit":
            raise SystemExit


async def main():
    CARPETA_BASE.mkdir(parents=True, exist_ok=True)
    client = await conectar()

    while True:
        console.clear()
        console.print()
        console.print(Panel(
            "[bold white]Telegram Toolbox[/bold white]\n"
            "[bold green]Descargas · Canales · Foros · Temas · Subida[/bold green]",
            title="📦 TELEGRAM TOOLBOX",
            border_style="blue"
        ))
        console.print()
        choice = inquirer.select(
            "Selecciona módulo:",
            choices=[
                {"name": "📥  Descargas", "value": "1"},
                {"name": "🔄  Clonar & Backup", "value": "2"},
                {"name": "🗂️  Chats y carpetas", "value": "3"},
                {"name": "🧭  Canales / Foros / Temas", "value": "4"},
                {"name": "🚚  Subida (pipeline)", "value": "5"},
                {"name": "👁️  Vigilante", "value": "6"},
                {"name": "📌  Fijar / Desfijar mensajes", "value": "10"},
                {"name": "🔎  Buscar fotos en Guardados", "value": "11"},
                {"name": "✏️  Editar descripciones en Guardados", "value": "12"},
                {"name": "🧭  Modo guiado (todo el flujo)", "value": "8"},
                {"name": "🧹  Limpieza / Programación", "value": "9"},
                Separator(),
                {"name": "⚙️  Config / Salir", "value": "7"},
            ],
            pointer="▸", mandatory=False, default="1",
        ).execute()
        if choice is None:
            break
        try:
            if choice == "1":
                await modulo_descargas(client)
            elif choice == "2":
                await modulo_clonar(client)
            elif choice == "3":
                await modulo_chats(client)
            elif choice == "4":
                await modulo_foros(client)
            elif choice == "5":
                await modulo_subida(client)
            elif choice == "6":
                await modulo_vigilante(client)
            elif choice == "10":
                await modulo_pin(client)
            elif choice == "11":
                await modulo_buscar_fotos(client)
            elif choice == "12":
                await modulo_editar_caption(client)
            elif choice == "8":
                await _modo_guiado(client)
            elif choice == "9":
                await _modo_limpieza(client)
            elif choice == "7":
                modulo_config(client)
                break
        except SystemExit:
            break
        except KeyboardInterrupt:
            styled_warn("Módulo cancelado.")
        styled_info("Pulsa Enter para continuar...")
        input()

    await client.disconnect()
    styled_success("Sistema cerrado.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript finalizado por el usuario.")