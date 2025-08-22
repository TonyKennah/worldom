# tests/test_imports.py
"""
Smoke test: ensure every Python module under `src/` imports successfully.

Implementation notes:
- We add the project *root* to sys.path so `import src.*` resolves cleanly.
- We discover .py files with pathlib (more robust than pkgutil in mixed/namespace setups),
  then convert file paths to `src.*` module names.
- We run pygame in headless mode to avoid display/audio requirements in CI.
"""

from __future__ import annotations

import os
import sys
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _discover_src_modules() -> list[str]:
    """
    Find all modules beneath `src/` and return fully-qualified names
    like 'src.ui.menu_theme'. Includes the top-level 'src' package too.
    """
    modules: set[str] = set()

    # Ensure src exists so relative conversion works
    if not SRC.exists():
        return ["src"]

    # Convert each *.py path into a module name
    for py in SRC.rglob("*.py"):
        # Skip obvious generated caches
        if "__pycache__" in py.parts:
            continue

        rel = py.relative_to(SRC).with_suffix("")  # remove ".py"
        parts = list(rel.parts)

        # Drop trailing __init__ to represent the package
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        # If parts is empty here, that was src/__init__.py (we'll add 'src' below)
        if parts:
            modules.add(".".join(["src", *parts]))

    # Always include the package itself first
    return ["src", *sorted(modules)]


def test_import_all_modules_headless() -> None:
    # Headless env for pygame
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    # Ensure project root is on sys.path so `import src.*` works.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    failures: list[tuple[str, Exception]] = []
    for mod_name in _discover_src_modules():
        try:
            importlib.import_module(mod_name)
        except Exception as e:  # we want full visibility on any import failure
            failures.append((mod_name, e))

    if failures:
        msgs = "\n".join(f"{m}: {type(e).__name__}({e})" for m, e in failures)
        raise AssertionError(f"Import failures:\n{msgs}")
