"""bot_inline_keyboards.py — Teclados inline reutilizables para el bot."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def kb_help() -> InlineKeyboardMarkup:
    """Botón en /help."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Descargar vídeo", callback_data="download:start")]
    ])


def kb_tip() -> InlineKeyboardMarkup:
    """Botones después de /tip."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Otro tip", callback_data="tip:next"),
            InlineKeyboardButton("💡 Concepto", callback_data="concept:next"),
            InlineKeyboardButton("🛠 Tool", callback_data="tool:next"),
        ]
    ])


def kb_concept() -> InlineKeyboardMarkup:
    """Botones después de /concepto."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Otro concepto", callback_data="concept:next"),
            InlineKeyboardButton("💡 Tip", callback_data="tip:next"),
            InlineKeyboardButton("🛠 Tool", callback_data="tool:next"),
        ]
    ])


def kb_tool() -> InlineKeyboardMarkup:
    """Botones después de /tool."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Otro tool", callback_data="tool:next"),
            InlineKeyboardButton("💡 Tip", callback_data="tip:next"),
            InlineKeyboardButton("📖 Concepto", callback_data="concept:next"),
        ]
    ])


def kb_saludo() -> InlineKeyboardMarkup:
    """Botones después de /saludo."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Otro saludo", callback_data="saludo:next")]
    ])


def kb_noticias() -> InlineKeyboardMarkup:
    """Botones después de /noticias."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📰 Más noticias", callback_data="noticias:more"),
            InlineKeyboardButton("💡 Tip", callback_data="tip:next"),
        ]
    ])
