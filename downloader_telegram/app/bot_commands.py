"""bot_commands.py — Handlers de comandos del bot (/tip, /descarga, etc.)."""
import asyncio
import json
import os
import random
import re
import sys
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot_inline_keyboards import (
    kb_help, kb_tip, kb_concept, kb_tool,
    kb_saludo, kb_noticias,
)

# ── Ruta a test_githubActions para importar generadores ──
TEST_GH_DIR = Path(os.environ.get("TEST_GH_DIR", "/data/test_githubActions"))
if str(TEST_GH_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(TEST_GH_DIR / "scripts"))

# ── Config descarga ──
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "/data/descargas"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════

def extract_url(text: str) -> str | None:
    """Extrae la primera URL de un texto."""
    url_pattern = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
        re.IGNORECASE
    )
    match = url_pattern.search(text)
    return match.group(0) if match else None


def get_video_duration(file_path: Path) -> float:
    """Obtiene la duración del vídeo en segundos con ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def compress_for_telegram(input_path: Path, output_dir: Path, max_size_mb: int = 50) -> dict:
    """Comprime vídeo para Telegram igual que el monitor (CRF 28, 2 pasadas si hace falta)."""
    file_size_mb = input_path.stat().st_size / (1024 * 1024)

    output_path = output_dir / f"{input_path.stem}_tele.mp4"
    tmp_path = output_dir / f"{input_path.stem}_tele.mp4.tmp"

    # Obtener duración
    duration = get_video_duration(input_path)

    # ffmpeg args iguales al monitor: CRF 28, fast, solo v+1er audio
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-c:v", "libx264", "-crf", "28", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0", "-map", "0:a:0",
        "-map_metadata", "0",
        "-movflags", "+faststart",
        "-f", "mp4",
        str(tmp_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

    if result.returncode != 0 or not tmp_path.exists():
        if tmp_path.exists():
            tmp_path.unlink()
        return {"success": True, "file": str(input_path)}

    # Si pesa más de max_size_mb, 2 pasadas
    tmp_size = tmp_path.stat().st_size
    max_bytes = max_size_mb * 1024 * 1024
    if tmp_size > max_bytes and duration > 0:
        # Calcular bitrate para caber
        audio_bps = 128000
        audio_bytes = int(duration * audio_bps / 8)
        video_bytes = max_bytes - audio_bytes
        video_bps = int(video_bytes * 8 / duration)
        if video_bps > 0:
            # Pasada 1
            subprocess.run([
                "ffmpeg", "-y", "-i", str(input_path),
                "-c:v", "libx264", "-b:v", str(video_bps),
                "-preset", "fast", "-pass", "1", "-an", "-f", "null", "-"
            ], capture_output=True, timeout=1800)
            # Pasada 2
            subprocess.run([
                "ffmpeg", "-y", "-i", str(input_path),
                "-c:v", "libx264", "-b:v", str(video_bps),
                "-preset", "fast", "-pass", "2",
                "-c:a", "aac", "-b:a", "128k",
                "-map", "0:v:0", "-map", "0:a:0",
                "-map_metadata", "0",
                "-movflags", "+faststart",
                "-f", "mp4", str(tmp_path)
            ], capture_output=True, timeout=1800)
            # Limpiar logs de 2 pasadas
            for f in Path(".").glob("ffmpeg2pass-*.log*"):
                f.unlink(missing_ok=True)

    # Renombrar tmp → final
    tmp_path.rename(output_path)
    new_size = output_path.stat().st_size / (1024 * 1024)

    return {"success": True, "file": str(output_path), "new_size": new_size}


def download_with_ytdlp(url: str, output_dir: Path) -> dict:
    """Descarga un vídeo con yt-dlp. Devuelve {success, file, error}."""
    try:
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(output_dir / "%(title)s.%(ext)s"),
            "--no-overwrites",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return {"success": False, "error": result.stderr[:500]}

        # Buscar el archivo descargado
        files = sorted(output_dir.glob("*.*"), key=os.path.getmtime, reverse=True)
        for f in files:
            if f.suffix in ('.mp4', '.mkv', '.webm', '.mp3', '.m4a'):
                return {"success": True, "file": str(f)}
        return {"success": False, "error": "No se encontró el archivo descargado"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout: la descarga tardó más de 5 minutos"}
    except FileNotFoundError:
        return {"success": False, "error": "yt-dlp no está instalado"}


# ══════════════════════════════════════════════════════════════
#  COMANDOS BÁSICOS
# ══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — Mensaje de bienvenida."""
    text = (
        "👋 ¡Hola! Soy @jorbencas_bot\n\n"
        "Puedo ayudarte con:\n"
        "• Descargar vídeos de cualquier web\n"
        "• Tips de programación\n"
        "• Conceptos y herramientas IA\n"
        "• Noticias de tecnología\n\n"
        "Usa /ayuda para ver todos los comandos."
    )
    await update.message.reply_text(text)


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ayuda — Pantalla de ayuda."""
    text = (
        "🤖 @jorbencas_bot\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📥 DESCARGAS\n"
        "  /descarga URL — Descargar y comprimir para Telegram\n"
        "  /download URL — Igual que /descarga\n"
        "  También puedes mencionarme con una URL\n"
        "  En privado, envía directamente una URL\n\n"
        "💡 CONTENIDO\n"
        "  /tip — Tip de programación\n"
        "  /concepto — Concepto con código\n"
        "  /tool — Herramienta IA\n"
        "  /saludo — Imagen de saludo\n"
        "  /noticias — Últimas noticias tech\n\n"
        "⚙️ UTILIDADES\n"
        "  /ping — Comprobar conexión\n"
        "  /ayuda — Esta pantalla\n\n"
        "💡 Tip: Los vídeos >50MB se comprimen automáticamente"
    )
    await update.message.reply_text(text, reply_markup=kb_help())


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ping — Comprobar conexión."""
    await update.message.reply_text("🏓 Pong! Bot activo.")


# ══════════════════════════════════════════════════════════════
#  DESCARGA
# ══════════════════════════════════════════════════════════════

async def cmd_descarga(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str = None):
    """/descarga URL — Descargar vídeo."""
    if url is None:
        args = context.args if context.args else []
        url = args[0] if args else None

    if not url:
        await update.message.reply_text(
            "📥 Uso: /descarga URL\n"
            "Ejemplo: /descarga https://www.youtube.com/watch?v=..."
        )
        return

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ URL no válida. Debe empezar con http:// o https://")
        return

    await update.message.reply_chat_action("upload_video")
    status_msg = await update.message.reply_text(f"⬇️ Descargando...\n{url[:60]}...")

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, download_with_ytdlp, url, DOWNLOAD_DIR
        )

        if result["success"]:
            file_path = Path(result["file"])
            file_size = file_path.stat().st_size / (1024 * 1024)

            # Si es vídeo, comprimir para Telegram (siempre)
            if file_path.suffix in ('.mp4', '.mkv', '.webm'):
                await status_msg.edit_text(
                    f"⬇️ Descargado: {file_size:.1f} MB\n"
                    f"⚙️ Convirtiendo para Telegram..."
                )
                compress_result = await asyncio.get_event_loop().run_in_executor(
                    None, compress_for_telegram, file_path, DOWNLOAD_DIR, 50
                )
                if compress_result["success"]:
                    file_path = Path(compress_result["file"])
                    file_size = file_path.stat().st_size / (1024 * 1024)

            await status_msg.edit_text(
                f"✅ Descarga completada\n"
                f"📁 {file_path.name}\n"
                f"📊 {file_size:.1f} MB"
            )
            # Enviar como vídeo con thumbnail
            thumb_path = file_path.parent / f"{file_path.stem}_thumb.jpg"
            thumb_bytes = None
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(file_path),
                    "-ss", "00:00:01", "-vframes", "1",
                    "-vf", "scale=320:-1",
                    str(thumb_path)
                ], capture_output=True, timeout=30)
                if thumb_path.exists():
                    thumb_bytes = thumb_path.read_bytes()
                    thumb_path.unlink(missing_ok=True)
            except Exception:
                pass

            with open(file_path, "rb") as f:
                kwargs = {
                    "video": f,
                    "filename": file_path.name,
                    "caption": f"📥 {file_path.name}"
                }
                if thumb_bytes:
                    kwargs["thumbnail"] = thumb_bytes
                await update.message.reply_video(**kwargs)
            # Borrar archivo local después de enviar
            file_path.unlink(missing_ok=True)
        else:
            await status_msg.edit_text(f"❌ Error: {result['error'][:200]}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Error inesperado: {str(e)[:200]}")


# ══════════════════════════════════════════════════════════════
#  CONTENIDO IA
# ══════════════════════════════════════════════════════════════

async def cmd_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tip — Tip de programación."""
    await update.message.reply_chat_action("typing")
    try:
        from tips_generator import (
            load_database, load_history, select_tips_from_db,
            generate_tips_gemini, build_daily_message
        )
        database = load_database()
        history = load_history()
        sent_titles = history.get("sent_titles", [])

        tips = generate_tips_gemini(1, None, sent_titles)
        if not tips:
            tips = select_tips_from_db(database, history, count=1)
        if not tips:
            await update.message.reply_text("❌ No hay tips disponibles.", reply_markup=kb_tip())
            return

        msg = build_daily_message(tips)
        await update.message.reply_text(msg, reply_markup=kb_tip())
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando tip: {e}", reply_markup=kb_tip())


async def cmd_concepto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/concepto — Concepto de programación con código."""
    await update.message.reply_chat_action("typing")
    try:
        from tips_generator import (
            load_concepts_database, load_history, select_concepts_from_db,
            generate_concepts_gemini
        )
        concepts_db = load_concepts_database()
        history = load_history()
        sent_titles = history.get("sent_titles", [])

        concepts = generate_concepts_gemini(1, None, sent_titles)
        if not concepts:
            concepts = select_concepts_from_db(concepts_db, sent_titles, None, count=1)
        if not concepts:
            await update.message.reply_text("❌ No hay conceptos disponibles.", reply_markup=kb_concept())
            return

        c = concepts[0]
        text = (
            f"💡 {c.get('title', 'Concepto')}\n\n"
            f"{c.get('explanation', c.get('summary', ''))[:1000]}\n\n"
            f"```\n{c.get('code_example', '')[:1500]}\n```"
        )
        await update.message.reply_text(text, reply_markup=kb_concept())
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando concepto: {e}", reply_markup=kb_concept())


async def cmd_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tool — Herramienta AI."""
    await update.message.reply_chat_action("typing")
    try:
        from ai_tools_generator import (
            load_categories, load_database, load_history,
            select_tools_from_db, generate_tools_gemini, build_daily_message
        )
        load_categories()
        database = load_database()
        history = load_history()
        sent_titles = history.get("sent_titles", [])

        tools = generate_tools_gemini(1, None, sent_titles)
        if not tools:
            tools = select_tools_from_db(database, history, count=1)
        if not tools:
            await update.message.reply_text("❌ No hay tools disponibles.", reply_markup=kb_tool())
            return

        msg = build_daily_message(tools)
        await update.message.reply_text(msg, reply_markup=kb_tool())
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando tool: {e}", reply_markup=kb_tool())


async def cmd_saludo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/saludo — Imagen de saludo generada por IA."""
    await update.message.reply_chat_action("upload_photo")
    try:
        from saludo_imagen import (
            load_config, load_history, now_local,
            _greeting_for_hour, _festivo, _temporada,
            _pick, _pick_frase, _build_prompt,
            generate_image, fallback_pollinations, fallback_pil,
            _superponer_texto
        )
        load_config()
        history = load_history()
        now = now_local()
        saludo = _greeting_for_hour(now.hour)
        festivo_nombre, festivo_temas = _festivo(now)
        temporada = _temporada(now)
        estilo = _pick("estilos", history.get("keys", []), "estilo")
        publico = _pick("publicos", history.get("keys", []), "publico")
        emocion = _pick("emociones", history.get("keys", []), "emocion")
        materia = _pick("materias", history.get("keys", []), "materia")
        frase = _pick_frase(saludo, history.get("keys", []))

        prompt = _build_prompt(saludo, frase, now, festivo_nombre, festivo_temas,
                               estilo, publico, emocion, materia, temporada)
        image_bytes = generate_image(prompt)
        if not image_bytes:
            image_bytes = fallback_pollinations(saludo, publico, materia, estilo, emocion, temporada)
        if not image_bytes:
            image_bytes = fallback_pil(saludo, publico)
        if image_bytes:
            image_bytes = _superponer_texto(image_bytes, frase, saludo)
            await update.message.reply_photo(
                photo=image_bytes,
                caption=f"✨ {frase} ✨\n{saludo}!",
                reply_markup=kb_saludo()
            )
        else:
            await update.message.reply_text("❌ No se pudo generar la imagen.", reply_markup=kb_saludo())
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando saludo: {e}", reply_markup=kb_saludo())


async def cmd_noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/noticias — Últimas noticias scrapeadas."""
    await update.message.reply_chat_action("typing")
    news_file = TEST_GH_DIR / "files" / "noticias_historico.json"
    if not news_file.exists():
        await update.message.reply_text("❌ No hay noticias disponibles.", reply_markup=kb_noticias())
        return
    try:
        data = json.loads(news_file.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("items", [])
        if not items:
            await update.message.reply_text("📰 Sin noticias nuevas.", reply_markup=kb_noticias())
            return
        recent = items[:5]
        lines = ["📰 Últimas noticias\n"]
        for i, item in enumerate(recent, 1):
            title = item.get("title", item.get("titulo", "Sin título"))
            source = item.get("source", item.get("fuente", ""))
            lines.append(f"{i}. {title}")
            if source:
                lines.append(f"   _{source}_")
        text = "\n".join(lines)
        await update.message.reply_text(text, reply_markup=kb_noticias())
    except Exception as e:
        await update.message.reply_text(f"❌ Error leyendo noticias: {e}", reply_markup=kb_noticias())
