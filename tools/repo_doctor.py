#!/usr/bin/env python3
"""
Repo Doctor: quick diagnostics for WorldDom (safe to run locally or in CI).

- Detects duplicate module basenames (e.g., multiple 'assets.py' files).
- Checks for missing __init__.py in packages under src/.
- Tries importing all modules under src/ and reports failures.
- Optionally runs a headless pygame smoke test.

Usage:
  python tools/repo_doctor.py --headless --smoke 2.0
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path
import importlib
import traceback
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

def _py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if ".venv" not in p.parts and "site-packages" not in p.parts]

def _pkg_name(p: Path) -> str:
    # Turn src/foo/bar.py into module path foo.bar
    rel = p.relative_to(SRC)
    parts = list(rel.parts)
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)

def find_duplicate_basenames() -> dict[str, list[Path]]:
    buckets: dict[str, list[Path]] = defaultdict(list)
    for p in _py_files(SRC):
        buckets[p.name].append(p)
    return {k: v for k, v in buckets.items() if len(v) > 1}

def find_missing_inits() -> list[Path]:
    missing: list[Path] = []
    for d in SRC.rglob("*"):
        if d.is_dir() and any(child.suffix == ".py" for child in d.iterdir() if child.is_file()):
            if not (d / "__init__.py").exists():
                missing.append(d)
    return missing

def try_import_all(headless: bool) -> list[tuple[str, str]]:
    """
    Attempt to import every top-level module under src/. Returns list of (module, error).
    """
    if headless:
        # Safe headless defaults; won't interfere with normal runs.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    sys.path.insert(0, str(SRC))
    failures: list[tuple[str, str]] = []
    for py in _py_files(SRC):
        # skip __init__.py – its package will be imported through children anyway
        if py.name == "__init__.py":
            continue
        mod = _pkg_name(py)
        if not mod or mod.endswith(".__init__"):
            continue
        try:
            importlib.invalidate_caches()
            importlib.import_module(mod)
        except Exception as e:
            failures.append((mod, f"{e.__class__.__name__}: {e}\n{traceback.format_exc()}"))
    return failures

def smoke_test(seconds: float) -> str:
    """
    Very small headless pygame smoke test to catch backend failures.
    """
    import time, math
    import pygame
    pygame.display.init()
    pygame.font.init()
    try:
        pygame.display.set_mode((160, 90))
    except Exception as e:
        return f"[smoke] display set_mode failed: {e}"
    surf = pygame.display.get_surface()
    clock = pygame.time.Clock()
    t0 = time.time()
    hue = 0.0
    while time.time() - t0 < max(0.2, seconds):
        hue = (hue + 0.03) % 1.0
        r = int(60 + 195 * abs(math.sin(hue * math.tau)))
        g = int(60 + 195 * abs(math.sin((hue + 1/3) * math.tau)))
        b = int(60 + 195 * abs(math.sin((hue + 2/3) * math.tau)))
        surf.fill((r, g, b))
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    return "[smoke] OK"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", help="Force SDL dummy backends for imports.")
    ap.add_argument("--smoke", type=float, default=0.0, help="Run headless pygame smoke test for N seconds.")
    args = ap.parse_args()

    print(f"[doctor] Root: {ROOT}")
    print(f"[doctor] Src : {SRC}")

    dups = find_duplicate_basenames()
    if dups:
        print("\n[doctor] Duplicate module basenames found (can cause import ambiguity):")
        for name, paths in dups.items():
            for p in paths:
                print(f"  - {name}  ->  {p.relative_to(ROOT)}")
    else:
        print("\n[doctor] No duplicate module basenames found.")

    missing = find_missing_inits()
    if missing:
        print("\n[doctor] Missing __init__.py in packages:")
        for d in missing:
            print(f"  - {d.relative_to(ROOT)}")
    else:
        print("\n[doctor] No missing __init__.py detected.")

    failures = try_import_all(args.headless)
    if failures:
        print("\n[doctor] Import failures:")
        for mod, err in failures:
            print(f"  - {mod}\n{err}")
    else:
        print("\n[doctor] All modules imported successfully.")

    if args.smoke > 0:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            print("\n" + smoke_test(args.smoke))
        except Exception as e:
            print(f"[doctor] Smoke test failed: {e}")

    return 0 if not failures else 2

if __name__ == "__main__":
    raise SystemExit(main())
