"""bot_callbacks.py — Handlers de botones inline (callbacks)."""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("bot_callbacks")

from bot_commands import (
    _format_status, _format_queue, _format_logs,
)
from bot_inline_keyboards import (
    kb_status, kb_tip, kb_concept, kb_tool,
    kb_saludo, kb_cola, kb_pausar, kb_noticias,
)
from pipeline_bridge import get_status, get_queue_count, get_logs, send_control


async def cb_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: refrescar status."""
    query = update.callback_query
    await query.answer()
    status = get_status()
    text = _format_status(status)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb_status())


async def cb_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: ver cola."""
    query = update.callback_query
    await query.answer()
    queue = get_queue_count()
    text = _format_queue(queue)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb_cola())


async def cb_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: ver logs."""
    query = update.callback_query
    await query.answer()
    logs = get_logs(count=15)
    text = _format_logs(logs)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb_status())


async def cb_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: otro tip."""
    query = update.callback_query
    logger.info(f"cb_tip called: data={query.data}")
    await query.answer()
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
            await query.edit_message_text("❌ No hay tips disponibles.", reply_markup=kb_tip())
            return
        msg = build_daily_message(tips)
        logger.info(f"cb_tip: msg len={len(msg)}")
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb_tip())
        logger.info("cb_tip: sent OK")
    except Exception as e:
        logger.error(f"cb_tip error: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=kb_tip())


async def cb_concept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: otro concepto."""
    query = update.callback_query
    logger.info(f"cb_concept called: data={query.data}")
    await query.answer()
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
            await query.edit_message_text("❌ No hay conceptos.", reply_markup=kb_concept())
            return
        c = concepts[0]
        text = (
            f"💡 **{c.get('title', 'Concepto')}**\n\n"
            f"{c.get('explanation', c.get('summary', ''))[:1000]}\n\n"
            f"```{c.get('code_example', '')[:1500]}```"
        )
        logger.info(f"cb_concept: text len={len(text)}")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb_concept())
        logger.info("cb_concept: sent OK")
    except Exception as e:
        logger.error(f"cb_concept error: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=kb_concept())


async def cb_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: otro tool."""
    query = update.callback_query
    await query.answer()
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
            await query.edit_message_text("❌ No hay tools.", reply_markup=kb_tool())
            return
        msg = build_daily_message(tools)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb_tool())
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=kb_tool())


async def cb_saludo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: otro saludo."""
    query = update.callback_query
    await query.answer()
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
            # Para fotos no podemos edit, enviar nueva
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image_bytes,
                caption=f"✨ {frase} ✨\n{saludo}!",
                reply_markup=kb_saludo()
            )
        else:
            await query.edit_message_text("❌ No se pudo generar imagen.", reply_markup=kb_saludo())
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=kb_saludo())


async def cb_noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: más noticias."""
    query = update.callback_query
    await query.answer()
    # Reutilizar cmd_noticias
    from bot_commands import cmd_noticias
    await cmd_noticias(update, context)


async def cb_pipeline_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: pausar pipeline."""
    query = update.callback_query
    await query.answer()
    send_control("pause")
    await query.edit_message_text("⏸ Grabación pausada.", reply_markup=kb_pausar())


async def cb_pipeline_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: reanudar pipeline."""
    query = update.callback_query
    await query.answer()
    send_control("resume")
    await query.edit_message_text("▶️ Grabación reanudada.", reply_markup=kb_status())


async def cb_upload_force(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: forzar subida."""
    query = update.callback_query
    await query.answer()
    send_control("force_upload")
    await query.edit_message_text("⬆️ Subida forzada enviada.", reply_markup=kb_status())
