"""Workflow logging for the career assistant.

Callers should log each search, filter, score, and file write so a later
review can see why a role was drafted or held back.
"""

import logging
from pathlib import Path


def build_logger(log_path: Path) -> logging.Logger:
    """Return a logger that writes the same events to a file and stderr.

    Info is the normal workflow. Warning is a missing fact or a closed
    listing. Debug is the score breakdown.
    """
    logger = logging.getLogger("career_agent")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
