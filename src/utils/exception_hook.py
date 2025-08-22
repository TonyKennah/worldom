# src/utils/exception_hook.py
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from typing import Optional

def install_crash_handler() -> None:
    """
    Install a sys.excepthook that writes a crash report and tries
    to save a final screenshot (if pygame display is active).
    """
    def _hook(exctype, value, tb):
        os.makedirs("crash_dumps", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")

        # Write traceback
        crash_path = os.path.join("crash_dumps", f"trace-{ts}.log")
        with open(crash_path, "w", encoding="utf-8") as f:
            traceback.print_exception(exctype, value, tb, file=f)

        # Try to snapshot the last frame
        try:
            import pygame
            surf = pygame.display.get_surface()
            if surf:
                img_path = os.path.join("crash_dumps", f"screenshot-{ts}.png")
                pygame.image.save(surf, img_path)
        except Exception:
            pass

        # Also print to stderr, then exit
        traceback.print_exception(exctype, value, tb, file=sys.stderr)
        sys.exit(1)

    sys.excepthook = _hook
