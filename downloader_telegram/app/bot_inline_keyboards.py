"""bot_inline_keyboards.py — Teclados inline reutilizables para el bot."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def kb_help() -> InlineKeyboardMarkup:
    """Botón en /help para ir a /status."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Ver estado del pipeline", callback_data="status:refresh")]
    ])


def kb_status() -> InlineKeyboardMarkup:
    """Botones después de /status."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Actualizar", callback_data="status:refresh"),
            InlineKeyboardButton("📋 Cola", callback_data="queue:show"),
            InlineKeyboardButton("📝 Logs", callback_data="logs:show"),
        ]
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


def kb_cola() -> InlineKeyboardMarkup:
    """Botones después de /cola."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Actualizar", callback_data="queue:refresh"),
            InlineKeyboardButton("⬆️ Subir primero", callback_data="upload:force"),
        ]
    ])


def kb_grabar() -> InlineKeyboardMarkup:
    """Botones después de /grabar."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pausar", callback_data="pipeline:pause"),
            InlineKeyboardButton("📊 Estado", callback_data="status:refresh"),
        ]
    ])


def kb_pausar() -> InlineKeyboardMarkup:
    """Botones después de /pausar."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Reanudar", callback_data="pipeline:resume"),
            InlineKeyboardButton("📊 Estado", callback_data="status:refresh"),
        ]
    ])


def kb_noticias() -> InlineKeyboardMarkup:
    """Botones después de /noticias."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📰 Más noticias", callback_data="noticias:more"),
            InlineKeyboardButton("💡 Tip", callback_data="tip:next"),
        ]
    ])
