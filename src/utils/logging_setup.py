# src/utils/logging_setup.py
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
import os
from typing import Optional

DEFAULT_LEVEL = os.getenv("WORLDDOM_LOG_LEVEL", "INFO").upper()
DEFAULT_DIR = Path(os.getenv("WORLDDOM_LOG_DIR", "logs")).resolve()
DEFAULT_DIR.mkdir(parents=True, exist_ok=True)

def _console_handler(level: str) -> logging.Handler:
    h = logging.StreamHandler()
    h.setLevel(level)
    fmt = "[%(levelname).1s] %(asctime)s %(name)s: %(message)s"
    h.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    return h

def _file_handler(level: str) -> logging.Handler:
    logfile = DEFAULT_DIR / "worlddom.log"
    h = logging.handlers.RotatingFileHandler(
        logfile, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    h.setLevel(level)
    fmt = "%(asctime)s %(levelname)s %(process)d %(threadName)s %(name)s: %(message)s"
    h.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    return h

def setup_logging(level: str = DEFAULT_LEVEL, *, quiet_third_party: bool = True) -> None:
    """Idempotent logging setup for app and tools."""
    root = logging.getLogger()
    if getattr(root, "_worlddom_configured", False):
        return  # already configured

    root.setLevel(level)
    root.addHandler(_console_handler(level))
    root.addHandler(_file_handler(level))
    root._worlddom_configured = True  # type: ignore[attr-defined]

    if quiet_third_party:
        for noisy in ("PIL", "urllib3", "matplotlib", "asyncio"):
            logging.getLogger(noisy).setLevel("WARNING")

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Convenience accessor used across the project."""
    setup_logging()
    return logging.getLogger(name or "worlddom")
