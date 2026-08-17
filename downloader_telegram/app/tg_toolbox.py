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
import json
import os
import shutil
import subprocess
import sys
import platform
import getpass
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
from cryptography.fernet import Fernet  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from InquirerPy import inquirer  # noqa: E402
from InquirerPy.separator import Separator  # noqa: E402

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
    atributos_video,
    sync_ya_subido,
    sync_marcar,
    _log_auditoria,
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

SPAM_LIST = ["crypto", "ganar dinero", "casino", "poker", "estafa", "bet", "sex", "porn", "gore", "nude"]


def styled_panel(content, title="", style=BG):
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
    from telethon.tl.functions.messages import GetForumTopicsRequest
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
    import re
    nombre = re.sub(r'[\\/*?:"<>|]', "_", nombre)
    return nombre.strip().strip(".") or "sin_nombre"


def _ruta_segura(destino):
    """Convierte una ruta de usuario en una Path segura y crea los padres."""
    p = Path(str(destino)).expanduser()
    p = p.resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


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
            from mtranslate import translate
            return translate(texto, "es")
        except Exception:
            return texto
    return texto


async def download_media_robust(client, message, folder):
    if not message or not getattr(message, "media", None):
        return False
    file_name = message.file.name if message.file and message.file.name else f"file_{message.id}{message.file.ext if message.file and message.file.ext else '.bin'}"
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
    from telethon.tl.types import (
        MessageMediaDocument, MessageMediaPhoto, MessageMediaWebPage,
    )
    if isinstance(m, MessageMediaPhoto):
        return "foto"
    if isinstance(m, MessageMediaDocument):
        d = getattr(m, "document", None)
        nm = (getattr(d, "attributes", None) or [])
        names = [getattr(a, "file_name", "") for a in nm]
        fname = next((n for n in names if n), "")
        ext = (fname or "").lower()
        import re
        if re.search(r"\.(mp[34]|mkv|avi|mov|webm|ts)$", ext):
            return "vídeo"
        if re.search(r"\.(mp3|flac|aac|ogg|opus|wav|m4a)$", ext):
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
    tipos_ok = {"vídeo": True, "foto": True, "audio": True, "documento": True}
    if inquirer.confirm("¿Filtrar por tipo de medio?", default=False).execute():
        tipos_ok["vídeo"] = inquirer.confirm("¿Descargar vídeos?", default=True).execute()
        tipos_ok["foto"] = inquirer.confirm("¿Descargar fotos?", default=True).execute()
        tipos_ok["audio"] = inquirer.confirm("¿Descargar audios?", default=True).execute()
        tipos_ok["documento"] = inquirer.confirm("¿Descargar documentos?", default=True).execute()
    if not any(tipos_ok.values()):
        styled_warn("Ningún tipo seleccionado; se descargará todo.")
        tipos_ok = {"vídeo": True, "foto": True, "audio": True, "documento": True}

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


def _str_id(x):
    return str(x)


# ============================================================================
# MÓDULO 2: Clonar & Backup
# ============================================================================
async def modulo_clonar(client):
    console.print(styled_panel("[bold white]MÓDULO CLONACIÓN / BACKUP[/bold white]", title="🔄", style=BG))
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
    _tabla_resumen(
        ["Origen", "Destino", "Límite", "Multimedia", "Traducir"],
        [(sel_origen["nombre"], sel_destino["nombre"], str(limite),
          "sí" if descargar else "no", "sí" if trad else "no")],
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
                async def _enviar(m=message, txt=texto):
                    if trad and txt:
                        return await client.send_message(destino, txt,
                                                         file=m.media if not descargar else None)
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


async def modulo_chats(client):
    console.print(styled_panel("[bold white]MÓDULO CHATS Y CARPETAS[/bold white]", title="🗂️", style=BG))
    while True:
        op = inquirer.select(
            "Opciones:",
            choices=[
                {"name": "📋  Listar chats (con filtros)", "value": "l"},
                {"name": "🗄️  Archivar / Desarchivar chat", "value": "a"},
                {"name": "🏷️  Listar por carpeta", "value": "f"},
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
    from telethon.tl.functions.folders import EditPeerFoldersRequest
    from telethon.tl.types import InputFolderPeer
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
    from telethon.tl.functions.channels import CreateChannelRequest
    titulo = inquirer.text("Título del canal:").execute().strip()
    about = inquirer.text("Descripción (vacío = nada):").execute().strip()
    foro = inquirer.confirm("¿Activar foro (temas)?", default=True).execute()
    res = await client(CreateChannelRequest(title=titulo, about=about, broadcast=True, megagroup=False, forum=bool(foro)))
    chat = res.chats[0]
    _log_auditoria("CREAR_CANAL", f"{chat.title} (id={chat.id}) foro={bool(foro)}")
    styled_success(f"Canal '{chat.title}' id={chat.id} foro={bool(foro)}")


async def _gestionar_temas(client):
    from telethon.tl.functions.messages import (
        CreateForumTopicRequest, EditForumTopicRequest, DeleteTopicHistoryRequest, GetForumTopicsRequest,
    )
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
        for i, titulo in enumerate([x.strip() for x in titulos.split(",") if x.strip()]):
            r = await client(CreateForumTopicRequest(peer=foro_ent, title=titulo, random_id=int(asyncio.get_event_loop().time() * 1000) + i))
            _log_auditoria("CREAR_TEMA", f"{sel['nombre']}: {titulo}")
            styled_success(f"Tema '{titulo}' creado (id={getattr(r.updates[0], 'message', None).id if r.updates else '?'})")
    elif op == "r":
        tid = await _seleccionar_tema(client, foro_ent, "Elegir tema a renombrar:")
        if tid is None:
            return
        nuevo = inquirer.text("Nuevo título:").execute().strip()
        if nuevo:
            await client(EditForumTopicRequest(peer=foro_ent, topic_id=tid, title=nuevo))
            _log_auditoria("RENOMBRAR_TEMA", f"{sel['nombre']}/tema{tid} → {nuevo}")
            styled_success("Tema renombrado.")
    elif op == "d":
        tid = await _seleccionar_tema(client, foro_ent, "Elegir tema a vaciar:")
        if tid is None:
            return
        titulo = temas.get(tid, str(tid))
        if not inquirer.confirm("¿Vaciar TODO el contenido del tema?", default=False).execute():
            styled_info("Cancelado.")
            return
        escribir = inquirer.text(f"Escribe el título exacto del tema '{titulo}' para confirmar:").execute().strip()
        if escribir != titulo:
            styled_warn("El texto no coincide. Cancelado.")
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
    borrar_origen = False
    if inquirer.confirm("¿BORRAR el origen tras migrar correctamente? (irreversible)", default=False).execute():
        escribir = inquirer.text(f"Escribe el nombre exacto '{sel_origen['nombre']}' para confirmar el BORRADO:").execute().strip()
        borrar_origen = escribir == sel_origen["nombre"]
        if not borrar_origen:
            styled_warn("El texto no coincide. Se migrará sin borrar.")

    nenv = ntxt = 0
    styled_info(f"Migrando {n} mensajes...")
    async for msg in client.iter_messages(source_ent, reverse=True):
        if not await _comprobar_conexion(client):
            break
        try:
            if msg.message and getattr(msg, "media", None) and getattr(msg, "document", None):
                async def _f(m=msg):
                    return await client.send_file(foro_ent, m.media, caption=m.message, reply_to=tema_id)
                if await _reintentar(_f, etiqueta=f"migrar msg {msg.id}"):
                    nenv += 1
            elif msg.message and not getattr(msg, "media", None):
                async def _t(m=msg):
                    return await client.send_message(foro_ent, m.message, reply_to=tema_id)
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
    from telethon.tl.functions.messages import DeleteHistoryRequest
    styled_warn(f"BORRADO DE CANAL: '{nombre}' — SE BORRARÁ TODO EL HISTORIAL. ¡IRREVERSIBLE!")
    escribir = inquirer.text(f"Escribe el nombre exacto '{nombre}' para CONFIRMAR el borrado:").execute().strip()
    if escribir != nombre:
        styled_warn("El texto no coincide. Borrado cancelado.")
        return
    if not inquirer.confirm("¿Seguro? Esta acción NO se puede deshacer.", default=False).execute():
        styled_info("Cancelado.")
        return
    await client(DeleteHistoryRequest(peer=ent, max_id=0))
    _log_auditoria("VACIAR_CANAL", nombre)
    styled_success("Historial del canal borrado.")


async def _borrar_canal(client):
    from telethon.tl.functions.channels import DeleteChannelRequest
    sel = await _seleccionar_chat(client, "Canal a BORRAR (con filtro):",
                                  tipos=["canal", "foro"], filtro=None)
    if not sel:
        return
    ent = sel["ent"]
    titulo = getattr(ent, "title", sel["nombre"])
    styled_warn(f"Vas a borrar '{titulo}' (id={ent.id}). ¡IRREVERSIBLE!")
    if not inquirer.confirm("¿Confirmas?", default=False).execute():
        styled_info("Cancelado.")
        return
    escribir = inquirer.text(f"Escribe el título exacto '{titulo}' para confirmar:").execute().strip()
    if escribir != titulo:
        styled_warn("El texto no coincide. Cancelado.")
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
        import shutil
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
        import shutil
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
# MÓDULO 6: Vigilante
# ============================================================================
async def modulo_vigilante(client):
    filtro_ent = None
    if inquirer.confirm("¿Vigilar solo un canal concreto?", default=False).execute():
        sel = await _seleccionar_chat(client, "Canal a vigilar (con filtro):", tipos=["canal", "grupo", "foro"], filtro=None)
        if not sel:
            return
        filtro_ent = sel["ent"]
        styled_info(f"Vigilando SOLO: {sel['nombre']}")
    log("INFO", "Modo Vigilante activo. Ctrl+C para salir.")
    extra_str = inquirer.text("Palabras clave extra (separadas por coma):", default="").execute()
    extra = [p.lower() for p in extra_str.split(",") if p.strip()]

    @client.on(events.NewMessage)
    async def handler(event):
        if filtro_ent is not None and getattr(event, "chat_id", None) != getattr(filtro_ent, "id", None):
            return
        texto = event.message.message or ""
        if procesar_texto_inteligente(texto) == "FILTERED_CONTENT" or any(p in texto.lower() for p in extra):
            log("SPAM", f"Contenido detectado → {texto[:60]}")
            try:
                await client.send_message("me", f"🔔 Alerta:\n{texto[:400]}")
            except Exception:
                pass

    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        styled_warn("Vigilante detenido.")


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
    tipos_ok = {"vídeo": True, "foto": True, "audio": True, "documento": True}
    if inquirer.confirm("¿Filtrar por tipo de medio?", default=False).execute():
        tipos_ok["vídeo"] = inquirer.confirm("¿Vídeos?", default=True).execute()
        tipos_ok["foto"] = inquirer.confirm("¿Fotos?", default=True).execute()
        tipos_ok["audio"] = inquirer.confirm("¿Audios?", default=True).execute()
        tipos_ok["documento"] = inquirer.confirm("¿Documentos?", default=True).execute()

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
    from cli_base import _sync_cargar, _sync_guardar
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
# CONFIG / main
# ============================================================================
def _ver_auditoria():
    from cli_base import AUDIT_FILE
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
        console.print(styled_panel(
            "[bold white]Telegram Toolbox[/bold white]\n[dim]Gestión: descargas · canales · foros · temas · subida[/dim]",
            title="📦 TELEGRAM TOOLBOX", style=f"bold {FG}"))
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