# src/utils/logging_setup.py
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

def configure_logging(level: int = logging.INFO, *, log_to_file: bool = True) -> None:
    """
    Configure root logging with a readable format and optional file sink.
    Silences noisy third-party loggers by default.
    """
    fmt = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    datefmt = "%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt)

    # Tone down chatty libraries
    for noisy in ("PIL", "matplotlib", "urllib3", "asyncio", "OpenGL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if log_to_file:
        os.makedirs("logs", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        fh = logging.FileHandler(f"logs/worlddom-{ts}.log", encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(fmt, datefmt))
        logging.getLogger().addHandler(fh)
