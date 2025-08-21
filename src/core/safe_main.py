# src/core/safe_main.py
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

def configure_environment(headless: Optional[bool] = None) -> None:
    """Robust SDL/Pygame defaults for Linux/CI/headless."""
    ci = os.getenv("CI", "").lower() == "true"
    no_display = not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    if headless is None:
        headless = ci or no_display
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    os.environ.setdefault("SDL_HINT_RENDER_DRIVER", "software")
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

def init_pygame_display(size: Tuple[int, int] = (1280, 720), *, caption: str = "WorldDom"):
    """Initialize pygame and return a display surface (or None if headless)."""
    import pygame
    pygame.init()
    pygame.font.init()
    try:
        surf = pygame.display.set_mode(size)
        pygame.display.set_caption(caption)
        return surf
    except Exception:
        return None  # headless/CI

def run_game(entry_ctor: str = "src.core.game:Game", *, size=(1280, 720)) -> int:
    """
    Safe entrypoint runner:
      - Configures env for Linux/headless.
      - Initializes logging.
      - Catches exceptions and writes a crash log.
      - Instantiates and runs your Game (constructor path 'module:Class').
    """
    from importlib import import_module
    from src.utils.logging_setup import setup_logging, get_logger

    configure_environment()
    setup_logging()
    log = get_logger("safe_main")

    screen = init_pygame_display(size)
    if screen is None:
        log.warning("Running without a visible display (SDL dummy).")

    try:
        mod_name, cls_name = entry_ctor.split(":")
        mod = import_module(mod_name)
        GameClass = getattr(mod, cls_name)
    except Exception as e:
        log.exception("Failed to import game entry %s: %s", entry_ctor, e)
        return 2

    try:
        game = GameClass()
        # Convention: prefer a `.run()`; otherwise fall back to pygame loop.
        if hasattr(game, "run"):
            return int(game.run() or 0)
        else:
            # Minimal fallback loop (60fps) if your Game exposes `update/draw/quit`.
            import pygame
            clock = pygame.time.Clock()
            running = True
            while running:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        running = False
                    if hasattr(game, "handle_event"):
                        game.handle_event(ev)
                if hasattr(game, "update"):
                    game.update(clock.get_time() / 1000.0)
                if screen is not None and hasattr(game, "draw"):
                    game.draw(screen)
                    pygame.display.flip()
                clock.tick(60)
            if hasattr(game, "quit"):
                game.quit()
            if screen is not None:
                pygame.quit()
            return 0
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:
        # Write a crash report
        log.exception("Unhandled exception in game loop: %s", e)
        crash_dir = Path("logs")
        crash_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        (crash_dir / f"crash_{stamp}.txt").write_text(
            "Unexpected crash.\n\n" + "".join(__import__("traceback").format_exc()),
            encoding="utf-8",
        )
        return 1

if __name__ == "__main__":
    raise SystemExit(run_game())
