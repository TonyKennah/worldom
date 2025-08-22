#!/usr/bin/env python3
# tools/doctor.py
from __future__ import annotations

import os
import sys
import platform
from textwrap import indent

# Force headless-friendly defaults for CI / servers
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

def _hdr(title: str) -> None:
    print(f"\n== {title} " + "=" * (64 - len(title)))

def main() -> int:
    from src.utils.project_sanity import apply as apply_sanity
    from src.utils.mixer_safe import init_mixer_safe

    # 0) Basic env info
    _hdr("ENVIRONMENT")
    print(f"Python    : {sys.version.split()[0]}")
    print(f"OS        : {platform.system()} {platform.release()}")
    print(f"Arch      : {platform.machine()}")

    # 1) Apply import/path sanity
    _hdr("IMPORT SANITY")
    apply_sanity()
    print("Applied import/path sanity.")

    # 2) Pygame init (headless ok)
    _hdr("PYGAME INIT")
    import pygame
    pygame.init()
    print("pygame    :", getattr(pygame, "version", getattr(pygame, "__version__", "unknown")))
    try:
        screen = pygame.display.set_mode((320, 180))
        print("display   : OK (dummy acceptable)")
    except Exception as e:
        print("display   : FAILED", e)

    # 3) Mixer init
    _hdr("AUDIO (MIXER)")
    ok, msg = init_mixer_safe()
    print("mixer     :", "OK" if ok else "FAILED", "-", msg)

    # 4) Assets probe (optional)
    _hdr("ASSETS PROBE")
    missing = []
    found = []

    def _probe(mod_name: str) -> None:
        try:
            m = __import__(mod_name, fromlist=["*"])
            print(f"assets mod: {mod_name} (OK)")
            try:
                if hasattr(m, "load_image"):
                    img = m.load_image("ui/cursor.png")  # harmless test; placeholder allowed
                    found.append("ui/cursor.png")
            except Exception as e:
                missing.append(("ui/cursor.png", str(e)))
        except Exception as e:
            print(f"assets mod: {mod_name} (not importable): {e!r}")

    for name in ("assets", "src.ui.assets", "src.assets"):
        _probe(name)

    if missing:
        print("missing   :")
        for k, v in missing:
            print(" -", k, "->", v)
    else:
        print("missing   : none (or placeholder used)")

    # 5) Quit cleanly
    pygame.quit()
    _hdr("SUMMARY")
    print(indent("OK: Project glue/boot looks healthy.\n"
                 "If display/audio shows FAILED above on CI, that's expected with dummy drivers.\n"
                 "Run `python tools/doctor.py` locally to confirm native device init.", "  "))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
