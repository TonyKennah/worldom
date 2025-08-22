# src/worldom.py
"""
Lightweight shim for `import worldom` used by code paths like `src/core/map_io.py`.

Why this exists:
- CI import discovery imports every Python module under `src/` without optional
  dependencies installed. Some modules do `import worldom` as if it were an
  installed package. In source checkouts, that package is typically not present,
  which causes ModuleNotFoundError during import-time discovery.
- This shim allows `import worldom` to succeed. If you later install/provide a
  real `worldom` package, that package will shadow this file on sys.path.

This file intentionally stays minimal. Only add symbols that call-sites
actually rely on to avoid masking real integration issues.
"""

from __future__ import annotations
from pathlib import Path
import os

# Repository roots (best-effort)
# src/worldom.py -> parents[0] is src/, parents[1] is repo root
ROOT: Path = Path(__file__).resolve().parents[1]
SRC_DIR: Path = ROOT / "src"
ASSETS_DIR: Path = ROOT / "assets"
IMAGE_DIR: Path = ROOT / "image"
AUDIO_DIR: Path = ROOT / "audio"
DATA_DIR: Path = ROOT / "data"

def get_version() -> str:
    """Return a best-effort version string; override via WORLDDOM_VERSION env var."""
    return os.getenv("WORLDDOM_VERSION", "dev")

__all__ = [
    "ROOT",
    "SRC_DIR",
    "ASSETS_DIR",
    "IMAGE_DIR",
    "AUDIO_DIR",
    "DATA_DIR",
    "get_version",
]
