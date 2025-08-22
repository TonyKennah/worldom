# tools/repo_doctor.py
"""
Tiny CI helper used by .github/workflows/ci.yml.

- Verifies Python + pygame + noise can import.
- Optionally runs a short, headless pygame smoke loop.
- Keeps CLI compatible with older names: `--headless` and `--smoke SECONDS`.

Safe to run locally; in CI SDL_* are set to "dummy".
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import math


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="repo_doctor",
        description="Minimal pygame/noise import check + optional headless smoke loop.",
    )
    # Backwards/forwards compatible flags
    p.add_argument("--headless", action="store_true",
                   help="Use SDL_VIDEODRIVER=dummy (no window).")
    p.add_argument("--smoke", type=float, default=0.0, metavar="SECONDS",
                   help="Run a short headless animation for SECONDS (default: 0).")
    # Alias used by tools/env_check.py in some forks
    p.add_argument("--seconds", type=float, default=None,
                   help="Alias for --smoke.")
    return p.parse_args(argv)


def _ensure_headless_env() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    # Hide the long pygame hello in CI logs
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _print_versions() -> None:
    print("Python:", sys.version.split()[0])
    try:
        import pygame  # noqa: F401
        import noise   # noqa: F401
    except Exception as e:
        print("Import error:", e)
        raise
    else:
        import pygame
        import noise
        print("pygame:", getattr(pygame, "version", getattr(pygame, "__version__", "unknown")))
        print("noise:", getattr(noise, "__version__", "unknown"))


def _smoke(seconds: float) -> None:
    """A tiny headless draw loop; bails out fast if something is wrong."""
    if seconds <= 0:
        return
    import pygame

    # Init in a safe way for dummy driver
    pygame.init()
    try:
        w, h = 160, 90
        screen = pygame.display.set_mode((w, h), flags=0)  # headless OK
        pygame.display.set_caption("repo_doctor smoke")
        clock = pygame.time.Clock()

        t0 = time.time()
        hue = 0.0
        while time.time() - t0 < seconds:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return

            hue = (hue + 0.02) % 1.0
            r = int(60 + 195 * abs(math.sin(hue * math.tau)))
            g = int(60 + 195 * abs(math.sin((hue + 1/3) * math.tau)))
            b = int(60 + 195 * abs(math.sin((hue + 2/3) * math.tau)))
            screen.fill((r, g, b))

            t = time.time() - t0
            x = int(w / 2 + math.cos(t * 3.0) * (w / 4))
            y = int(h / 2 + math.sin(t * 2.0) * (h / 4))
            pygame.draw.circle(screen, (240, 240, 255), (x, y), 10)

            pygame.display.flip()
            clock.tick(60)
    finally:
        pygame.quit()


def main(argv: list[str] | None = None) -> int:
    ns = _parse_args(argv)
    if ns.headless:
        _ensure_headless_env()

    # Prefer --seconds if passed (compatibility with env_check.py)
    smoke_secs = ns.seconds if ns.seconds is not None else ns.smoke

    try:
        _print_versions()
        _smoke(smoke_secs or 0.0)
        print("repo_doctor: OK")
        return 0
    except Exception as e:
        print("repo_doctor: FAILED:", e)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
