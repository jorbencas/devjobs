"""bot_callbacks.py — Handlers de botones inline (callbacks)."""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("bot_callbacks")

from bot_inline_keyboards import (
    kb_tip, kb_concept, kb_tool,
    kb_noticias,
)


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
        await query.edit_message_text(msg, reply_markup=kb_tip())
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
            f"💡 {c.get('title', 'Concepto')}\n\n"
            f"{c.get('explanation', c.get('summary', ''))[:1000]}\n\n"
            f"```\n{c.get('code_example', '')[:1500]}\n```"
        )
        logger.info(f"cb_concept: text len={len(text)}")
        await query.edit_message_text(text, reply_markup=kb_concept())
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
        await query.edit_message_text(msg, reply_markup=kb_tool())
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=kb_tool())


async def cb_noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botón: más noticias."""
    query = update.callback_query
    await query.answer()
    from bot_commands import cmd_noticias
    await cmd_noticias(update, context)
