import logging
from datetime import datetime

try:
    from rich.logging import RichHandler
    from rich.console import Console
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def setup_logger(name: str = "twitchrecorder") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        if HAS_RICH:
            handler = RichHandler(
                console=Console(),
                show_path=False,
                show_time=False,
                rich_tracebacks=True,
                markup=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

        logger.addHandler(handler)

    return logger


log = setup_logger()
