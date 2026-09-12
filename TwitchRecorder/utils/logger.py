import logging
from datetime import datetime

try:
    from rich.logging import RichHandler
    from rich.console import Console
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class CustomFormatter(logging.Formatter):
    """Formatter personalizado con colores y emojis por nivel."""
    
    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Verde
        logging.WARNING: "\033[33m",   # Amarillo
        logging.ERROR: "\033[31m",     # Rojo
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record):
        """Formatea cada log con color por nivel + timestamp HH:MM:SS."""
        color = self.COLORS.get(record.levelno, "")
        level = record.levelname.ljust(8)
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = record.getMessage()
        return f"{color}{timestamp} [{level}]{self.RESET} {msg}"


def setup_logger(name: str = "twitchrecorder") -> logging.Logger:
    """Crea el logger raíz con un único handler con colores:
    Rich si está disponible, si no un CustomFormatter ANSI."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        if HAS_RICH:
            handler = RichHandler(
                console=Console(),
                show_path=False,
                show_time=True,
                rich_tracebacks=True,
                markup=True,
                log_time_format="%H:%M:%S",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(CustomFormatter())

        logger.addHandler(handler)

    return logger


log = setup_logger()
