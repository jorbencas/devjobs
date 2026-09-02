#!/usr/bin/env python3
"""telegram_bot.py — Bot API interactivo con python-telegram-bot.

Combina:
  - Contenido IA (tips, conceptos, tools, saludos, noticias)
  - Descarga de vídeos por URL (/descarga, /download)
"""
import asyncio
import logging
import os
import re
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
BOT_ADMINS = [int(x) for x in os.environ.get("BOT_ADMINS", "").split(",") if x.strip()]

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("telegram_bot")


# ══════════════════════════════════════════════════════════════
#  URL EXTRACTION
# ══════════════════════════════════════════════════════════════

def extract_url(text: str) -> str | None:
    """Extrae la primera URL de un texto."""
    url_pattern = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
        re.IGNORECASE
    )
    match = url_pattern.search(text)
    return match.group(0) if match else None


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
        cmd_tip, cmd_concepto, cmd_tool, cmd_saludo, cmd_noticias,
        cmd_descarga,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("help", cmd_ayuda))
    app.add_handler(CommandHandler("ping", cmd_ping))

    app.add_handler(CommandHandler("tip", cmd_tip))
    app.add_handler(CommandHandler("concepto", cmd_concepto))
    app.add_handler(CommandHandler("tool", cmd_tool))
    app.add_handler(CommandHandler("saludo", cmd_saludo))
    app.add_handler(CommandHandler("noticias", cmd_noticias))

    app.add_handler(CommandHandler("descarga", cmd_descarga))
    app.add_handler(CommandHandler("download", cmd_descarga))

    # ── Callbacks (botones inline) ──
    from bot_callbacks import (
        cb_tip, cb_concept, cb_tool, cb_saludo, cb_noticias,
    )

    app.add_handler(CallbackQueryHandler(cb_tip, pattern="^tip:"))
    app.add_handler(CallbackQueryHandler(cb_concept, pattern="^concept:"))
    app.add_handler(CallbackQueryHandler(cb_tool, pattern="^tool:"))
    app.add_handler(CallbackQueryHandler(cb_saludo, pattern="^saludo:"))
    app.add_handler(CallbackQueryHandler(cb_noticias, pattern="^noticias:"))

    # ── @Mención con URL en grupos ──
    async def handle_mention_with_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Responde cuando el bot es mencionado con una URL."""
        if not update.message or not update.message.text:
            return
        text = update.message.text
        bot_username = context.bot.username
        if f"@{bot_username}" not in text:
            return
        url = extract_url(text)
        if url:
            await cmd_descarga(update, context, url=url)
        else:
            await update.message.reply_text(
                "¿En qué puedo ayudarte?\n"
                "Envíame una URL con /descarga o mencíoname con una URL para descargarla."
            )

    mention_filter = filters.Entity("mention") & filters.ChatType.GROUPS
    app.add_handler(MessageHandler(mention_filter, handle_mention_with_url))

    # ── Iniciar polling ──
    logger.info("Bot listo. Polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
