from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

def test_import_all_modules_headless():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    sys.path.insert(0, str(SRC))
    import importlib, pkgutil

    failures = []
    for m in pkgutil.walk_packages([str(SRC)], prefix=""):
        name = m.name.replace("/", ".")
        if name.endswith("__init__"):
            continue
        try:
            importlib.import_module(name)
        except Exception as e:
            failures.append((name, e))
    if failures:
        msgs = "\n".join([f"{m}: {e}" for m, e in failures])
        raise AssertionError(f"Import failures:\n{msgs}")
