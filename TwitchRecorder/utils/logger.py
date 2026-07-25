import logging
from datetime import datetime


class TimestampFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created).strftime("%H:%M:%S")


def setup_logger(name: str = "twitchrecorder") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(TimestampFormatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)

    return logger


log = setup_logger()
