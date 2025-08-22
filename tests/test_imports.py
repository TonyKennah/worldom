# tests/test_imports.py
"""
Smoke test that every Python module under `src/` imports successfully.

- Runs pygame headless (no window/audio) for CI stability.
- Adds project root to sys.path so `import src.*` works.
- Walks modules under the logical `src` package; if that import fails,
  falls back to the physical `src/` path.
"""

from __future__ import annotations

import os
import sys
import importlib
import pkgutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def test_import_all_modules_headless() -> None:
    # Headless env for pygame
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    # Ensure project root is on sys.path so `import src.*` works.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Prefer walking the *package* path of `src` (namespace package support).
    paths: list[str]
    try:
        src_pkg = importlib.import_module("src")
        # Convert namespace/package path to a list[str] for pkgutil
        paths = [str(p) for p in list(src_pkg.__path__)]  # type: ignore[attr-defined]
    except Exception:
        # Fallback: walk the physical src/ directory
        paths = [str(SRC)]

    failures: list[tuple[str, Exception]] = []
    for mod in pkgutil.walk_packages(paths, prefix="src."):
        name = mod.name
        # Skip dunder-only entries
        if name.rsplit(".", 1)[-1] in {"__init__", "__main__"}:
            continue
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            failures.append((name, e))

    if failures:
        msgs = "\n".join(f"{m}: {type(e).__name__}({e})" for m, e in failures)
        raise AssertionError(f"Import failures:\n{msgs}")
