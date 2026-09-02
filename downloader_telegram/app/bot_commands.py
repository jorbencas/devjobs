"""bot_commands.py — Handlers de comandos del bot (/status, /tip, etc.)."""
import asyncio
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from bot_inline_keyboards import (
    kb_help, kb_status, kb_tip, kb_concept, kb_tool,
    kb_saludo, kb_cola, kb_grabar, kb_pausar, kb_noticias,
)
from pipeline_bridge import get_status, get_queue_count, get_logs, send_control

# ── Ruta a test_githubActions para importar generadores ──
TEST_GH_DIR = Path(os.environ.get("TEST_GH_DIR", "/data/test_githubActions"))
if str(TEST_GH_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(TEST_GH_DIR / "scripts"))

# ══════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════

def _format_status(status: dict) -> str:
    """Formatea el estado del pipeline para Telegram."""
    if not status:
        return "📡 **Pipeline sin actividad**\n\nNo hay servicios reportando estado."

    lines = ["📡 **Estado del Pipeline**\n"]

    rec = status.get("recorder", {})
    if rec:
        ch = rec.get("channel", "?")
        plat = rec.get("platform", "?")
        file = rec.get("file", "")
        lines.append(f"🎬 **Grabando:** {ch} ({plat})")
        if file:
            lines.append(f"   📁 {file}")
    else:
        lines.append("🎬 **Grabando:** inactivo")

    mon = status.get("monitor", {})
    if mon:
        mf = mon.get("file", "?")
        lines.append(f"⚙️ **Comprimiendo:** {mf}")
    else:
        lines.append("⚙️ **Comprimiendo:** inactivo")

    upl = status.get("uploader", {})
    if upl:
        uf = upl.get("file", "?")
        lines.append(f"⬆️ **Subiendo:** {uf}")
    else:
        lines.append("⬆️ **Subiendo:** inactivo")

    queue = get_queue_count()
    lines.append(f"\n📋 **Cola:** {queue['grabaciones']} grabaciones · {queue['comprimidos']} comprimidos")

    return "\n".join(lines)


def _format_queue(queue: dict) -> str:
    """Formatea la cola de archivos."""
    lines = ["📋 **Cola de archivos**\n"]
    lines.append(f"📹 Grabaciones/test: {queue['grabaciones']}")
    lines.append(f"📦 Comprimidos: {queue['comprimidos']}")
    lines.append(f"⬆️ Subiendo: {queue['subiendo']}")
    return "\n".join(lines)


def _format_logs(logs: list) -> str:
    """Formatea las líneas de log."""
    if not logs:
        return "📝 Sin logs recientes."
    lines = ["📝 **Últimos logs**\n"]
    for entry in logs:
        ts = entry.get("ts", "")[-8:]  # HH:MM:SS
        src = entry.get("src", "?")
        msg = entry.get("msg", "")
        lines.append(f"`{ts}` [{src}] {msg}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  COMANDOS BÁSICOS
# ══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — Mensaje de bienvenida."""
    text = (
        "🤖 **Bienvenido al Bot Pipeline & IA**\n\n"
        "Usa /ayuda para ver todos los comandos disponibles.\n"
        "También puedes mencionarme (@mencion) en el grupo para preguntarme cualquier cosa."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ayuda — Pantalla de ayuda con todos los comandos."""
    text = (
        "╔══════════════════════════════════════╗\n"
        "║       🤖 BOT PIPELINE & IA          ║\n"
        "╠══════════════════════════════════════╣\n"
        "║                                      ║\n"
        "║  📡 **PIPELINE**                     ║\n"
        "║  /status    — Estado del sistema     ║\n"
        "║  /grabar    — Forzar grabación       ║\n"
        "║  /pausar    — Pausar grabación       ║\n"
        "║  /reanudar  — Reanudar grabación     ║\n"
        "║  /cola      — Ver archivos en cola   ║\n"
        "║  /subir     — Forzar subida          ║\n"
        "║  /logs      — Últimos logs           ║\n"
        "║                                      ║\n"
        "║  💡 **CONTENIDO IA**                 ║\n"
        "║  /tip       — Tip de programación    ║\n"
        "║  /concepto  — Concepto con código    ║\n"
        "║  /tool      — Herramienta AI        ║\n"
        "║  /saludo    — Imagen de saludo       ║\n"
        "║  /noticias  — Últimas noticias       ║\n"
        "║                                      ║\n"
        "║  ⚙️ **UTILIDADES**                   ║\n"
        "║  /ping      — Comprobar conexión     ║\n"
        "║  /ayuda     — Esta pantalla          ║\n"
        "║                                      ║\n"
        "║  💡 TIP: Usa botones para navegar    ║\n"
        "╚══════════════════════════════════════╝"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_help())


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ping — Comprobar conexión."""
    await update.message.reply_text("🏓 Pong! Bot activo.")


# ══════════════════════════════════════════════════════════════
#  PIPELINE
# ══════════════════════════════════════════════════════════════

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status — Estado del pipeline."""
    status = get_status()
    text = _format_status(status)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_status())


async def cmd_cola(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/cola — Ver archivos en cola."""
    queue = get_queue_count()
    text = _format_queue(queue)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_cola())


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/logs — Últimos logs."""
    logs = get_logs(count=15)
    text = _format_logs(logs)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_status())


async def cmd_grabar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/grabar @canal — Forzar grabación."""
    canal = " ".join(context.args) if context.args else None
    if not canal:
        await update.message.reply_text(
            "Uso: /grabar @canal\nEjemplo: /grabar @midudev",
            reply_markup=kb_grabar()
        )
        return
    send_control("force_record", channel=canal)
    await update.message.reply_text(
        f"🎬 Orden enviada: grabar **{canal}**",
        parse_mode="Markdown",
        reply_markup=kb_grabar()
    )


async def cmd_pausar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pausar — Pausar grabación."""
    send_control("pause")
    await update.message.reply_text(
        "⏸ Grabación pausada.",
        reply_markup=kb_pausar()
    )


async def cmd_reanudar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reanudar — Reanudar grabación."""
    send_control("resume")
    await update.message.reply_text(
        "▶️ Grabación reanudada.",
        reply_markup=kb_status()
    )


async def cmd_subir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/subir — Forzar subida."""
    send_control("force_upload")
    await update.message.reply_text(
        "⬆️ Orden de subida forzada enviada.",
        reply_markup=kb_status()
    )


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

        # Intentar Gemini primero, fallback a DB
        tips = generate_tips_gemini(1, None, sent_titles)
        if not tips:
            tips = select_tips_from_db(database, history, count=1)
        if not tips:
            await update.message.reply_text("❌ No hay tips disponibles.", reply_markup=kb_tip())
            return

        msg = build_daily_message(tips)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb_tip())
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
            f"💡 **{c.get('title', 'Concepto')}**\n\n"
            f"{c.get('explanation', c.get('summary', ''))[:1000]}\n\n"
            f"```{c.get('code_example', '')[:1500]}```"
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_concept())
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
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb_tool())
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
        # Mostrar las 5 más recientes
        recent = items[:5]
        lines = ["📰 **Últimas noticias**\n"]
        for i, item in enumerate(recent, 1):
            title = item.get("title", item.get("titulo", "Sin título"))
            source = item.get("source", item.get("fuente", ""))
            lines.append(f"{i}. **{title}**")
            if source:
                lines.append(f"   _{source}_")
        text = "\n".join(lines)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb_noticias())
    except Exception as e:
        await update.message.reply_text(f"❌ Error leyendo noticias: {e}", reply_markup=kb_noticias())
