# tests/test_imports.py
"""
Smoke test that every Python module under `src/` imports successfully.

Key details:
- We add the project *root* to sys.path so intra-package imports like
  `import src.foo.bar` work (instead of pointing sys.path at `src` itself).
- We walk packages starting from the physical `src/` directory, but prefix the
  discovered module names with `src.` so imports resolve consistently.
- Pygame is run headless to avoid needing a window/audio device in CI.
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
    # Run pygame headless in CI or environments without a display/audio device.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    # Ensure 'src' is importable as a package (i.e., allow `import src.*`).
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Discover modules under the physical src/ directory, importing them as `src.*`
    failures: list[tuple[str, Exception]] = []
    for mod in pkgutil.walk_packages([str(SRC)], prefix="src."):
        name = mod.name
        # Skip dunder-only entries if any show up oddly
        if name.rsplit(".", 1)[-1] in {"__init__", "__main__"}:
            continue
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001 - we want full visibility here
            failures.append((name, e))

    if failures:
        msgs = "\n".join(f"{m}: {type(e).__name__}({e})" for m, e in failures)
        raise AssertionError(f"Import failures:\n{msgs}")
