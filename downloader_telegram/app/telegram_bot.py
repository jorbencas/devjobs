#!/usr/bin/env python3
"""telegram_bot.py — Bot API interactivo con python-telegram-bot.

Combina:
  - Pipeline control (status, grabar, pausar, subir)
  - Contenido IA (tips, conceptos, tools, saludos, noticias)
  - Bot IA por @mención (Qwen 2.5 via Ollama)
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ── Config ──
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
BOT_MENTION_MODE = os.environ.get("BOT_MENTION_MODE", "true").lower() == "true"
BOT_ADMINS = [int(x) for x in os.environ.get("BOT_ADMINS", "").split(",") if x.strip()]

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("telegram_bot")


# ══════════════════════════════════════════════════════════════
#  BOT IA POR @MENCIÓN (Qwen via Ollama)
# ══════════════════════════════════════════════════════════════

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde cuando el bot es mencionado en un grupo."""
    if not BOT_MENTION_MODE:
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text
    # Extraer el texto después de la @mención
    bot_username = context.bot.username
    clean = text.replace(f"@{bot_username}", "").strip()
    if not clean:
        await update.message.reply_text("¿En qué puedo ayudarte? Usa /ayuda para ver los comandos.")
        return

    await update.message.reply_chat_action("typing")

    try:
        import requests
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": (
                        "Eres un asistente de programación y tecnología. "
                        "Responde en español, sé conciso y da ejemplos de código cuando sea útil."
                    )},
                    {"role": "user", "content": clean},
                ],
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        reply = data.get("message", {}).get("content", "No pude generar una respuesta.")
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Error en Ollama: {e}")
        await update.message.reply_text(f"❌ Error conectando con IA: {e}")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN no configurado. Sale.")
        sys.exit(1)

    logger.info("Iniciando Telegram Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Comandos ──
    from bot_commands import (
        cmd_start, cmd_ayuda, cmd_ping,
        cmd_status, cmd_cola, cmd_logs,
        cmd_grabar, cmd_pausar, cmd_reanudar, cmd_subir,
        cmd_tip, cmd_concepto, cmd_tool, cmd_saludo, cmd_noticias,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))
    app.add_handler(CommandHandler("ping", cmd_ping))

    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cola", cmd_cola))
    app.add_handler(CommandHandler("logs", cmd_logs))
    app.add_handler(CommandHandler("grabar", cmd_grabar))
    app.add_handler(CommandHandler("pausar", cmd_pausar))
    app.add_handler(CommandHandler("reanudar", cmd_reanudar))
    app.add_handler(CommandHandler("subir", cmd_subir))

    app.add_handler(CommandHandler("tip", cmd_tip))
    app.add_handler(CommandHandler("concepto", cmd_concepto))
    app.add_handler(CommandHandler("tool", cmd_tool))
    app.add_handler(CommandHandler("saludo", cmd_saludo))
    app.add_handler(CommandHandler("noticias", cmd_noticias))

    # ── Callbacks (botones inline) ──
    from bot_callbacks import (
        cb_status, cb_queue, cb_logs,
        cb_tip, cb_concept, cb_tool, cb_saludo, cb_noticias,
        cb_pipeline_pause, cb_pipeline_resume, cb_upload_force,
    )

    app.add_handler(CallbackQueryHandler(cb_status, pattern="^status:"))
    app.add_handler(CallbackQueryHandler(cb_queue, pattern="^queue:"))
    app.add_handler(CallbackQueryHandler(cb_logs, pattern="^logs:"))
    app.add_handler(CallbackQueryHandler(cb_tip, pattern="^tip:"))
    app.add_handler(CallbackQueryHandler(cb_concept, pattern="^concept:"))
    app.add_handler(CallbackQueryHandler(cb_tool, pattern="^tool:"))
    app.add_handler(CallbackQueryHandler(cb_saludo, pattern="^saludo:"))
    app.add_handler(CallbackQueryHandler(cb_noticias, pattern="^noticias:"))
    app.add_handler(CallbackQueryHandler(cb_pipeline_pause, pattern="^pipeline:pause"))
    app.add_handler(CallbackQueryHandler(cb_pipeline_resume, pattern="^pipeline:resume"))
    app.add_handler(CallbackQueryHandler(cb_upload_force, pattern="^upload:"))

    # ── @Mención en grupos ──
    # Deshabilitado: Ollama corre en local, no necesita integración externa
    # if BOT_MENTION_MODE:
    #     mention_filter = filters.Entity("mention") & filters.ChatType.GROUPS
    #     app.add_handler(MessageHandler(mention_filter, handle_mention))
    #     logger.info(f"Modo @mención activo (modelo: {OLLAMA_MODEL})")

    # ── Iniciar polling ──
    logger.info("Bot listo. Polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
