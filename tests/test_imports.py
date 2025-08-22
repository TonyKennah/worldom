# tests/test_imports.py
"""
Smoke test that every Python module under `src/` imports successfully.

Key details:
- We add the project *root* to sys.path so `import src.*` resolves.
- We import the `src` package first, then walk using `src.__path__`
  and the `prefix="src."` to generate fully-qualified module names.
- Pygame is run headless to avoid requiring a window or audio device in CI.
"""

from __future__ import annotations

import os
import sys
import importlib
import pkgutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_import_all_modules_headless() -> None:
    # Run pygame headless in CI or environments without a display/audio device.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    # Ensure project root is on sys.path so `import src.*` works.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Import the `src` package to get its package path for walking.
    try:
        src_pkg = importlib.import_module("src")
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"Failed to import package 'src': {type(e).__name__}({e})")

    # Discover and import all modules below src/, using fully qualified names `src.*`.
    failures: list[tuple[str, Exception]] = []
    for mod in pkgutil.walk_packages(src_pkg.__path__, prefix="src."):
        name = mod.name
        # Skip weird dunders if any show up
        leaf = name.rsplit(".", 1)[-1]
        if leaf in {"__init__", "__main__"}:
            continue
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001 - aggregate all failures
            failures.append((name, e))

    if failures:
        msgs = "\n".join(f"{m}: {type(e).__name__}({e})" for m, e in failures)
        raise AssertionError(f"Import failures:\n{msgs}")
