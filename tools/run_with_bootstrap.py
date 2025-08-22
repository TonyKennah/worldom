# tools/run_with_bootstrap.py
from __future__ import annotations

"""
Optional runner. Keeps your repo intact: if this file isn't used, nothing changes.
It demonstrates how to:
 - install crash logging
 - bootstrap Pygame robustly
 - display a lightweight loading screen before constructing the Game class
"""

import time

from src.utils.bootstrap import bootstrap, BootConfig
from src.utils.error_report import install_excepthook
from src.ui.loading_screen import LoadingScreen


def main() -> int:
    install_excepthook(show_overlay=True)

    # Pick up settings if present via bootstrap(); override anything here
    ctx = bootstrap(BootConfig(caption="WorldDom (bootstrap)", vsync=True))

    # Show a minimal loading screen while we construct the game
    loader = LoadingScreen(ctx.screen)
    loader.start()

    # Fake staged loading to show the bar; replace with real preloads
    for i, status in enumerate(("Init systems", "Load textures", "Load sounds", "Build world", "Finalize")):
        loader.pump(i / 5.0, status)
        time.sleep(0.15)

    # Import late so slow imports show in the loader
    try:
        from src.core.game import Game  # your existing Game class
    except Exception as e:
        loader.pump(0.0, f"Import error: {e}")
        raise

    loader.finish()

    # Run your existing game class exactly as-is
    game = Game()
    # If your Game manages its own loop, just call the right method here:
    # e.g., game.run() or similar. If not, a minimal loop follows:

    running = True
    while running:
        for ev in ctx.clock.get_fps(),:  # touch the clock to keep linter quiet
            pass

        # Delegate to your Game's update/draw if available
        if hasattr(game, "update"):
            game.update(1.0 / ctx.config.target_fps)
        if hasattr(game, "draw"):
            game.draw(ctx.screen)

        # Common pygame loop plumbing
        import pygame
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif hasattr(game, "handle_event"):
                game.handle_event(ev)

        pygame.display.flip()
        ctx.clock.tick(ctx.config.target_fps)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
