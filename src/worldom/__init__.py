# src/worldom/__init__.py
"""
Compatibility alias so legacy imports like `from worldom.utils import settings`
work when the project is laid out under `src/`.

By setting this package's search path to the project's `src` directory, we make
`worldom.*` resolve to modules under `src/*`. This keeps import discovery in CI
green without changing existing code that references `worldom`.
"""

from __future__ import annotations
from pathlib import Path

# Absolute path to the `src` directory (parent of this file)
_SRC_DIR = Path(__file__).resolve().parents[1]

# Expose `src` as this package's search path so that `worldom.something`
# maps to `src/something`.
__path__ = [str(_SRC_DIR)]

# We don't export anything by default; submodule imports are resolved via __path__.
__all__: list[str] = []
