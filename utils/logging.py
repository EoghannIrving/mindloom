from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


def configure_logger(
    name: str, log_file: Path, level: int = logging.INFO
) -> logging.Logger:
    """Return a configured logger that writes to the given file."""

    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
