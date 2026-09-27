"""Application-wide logging configuration -> console + logs/app.log"""
import logging
import os
from app.core.config import settings


def setup_logging() -> logging.Logger:
    log_dir = os.path.dirname(settings.log_file)
    os.makedirs(log_dir, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    if root.handlers:
        return logging.getLogger("novatech")

    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(settings.log_file)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    return logging.getLogger("novatech")


logger = setup_logging()
