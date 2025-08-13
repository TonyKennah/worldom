# tools/env_check.py
from __future__ import annotations
import argparse
import os
import sys
import textwrap

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Python, pygame, and noise; run a headless pygame smoke test.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--headless", action="store_true",
                        help="Use SDL_VIDEODRIVER=dummy (no window).")
    parser.add_argument("--seconds", type=float, default=1.5,
                        help="How long to run the smoke test loop (default: 1.5s).")
    args = parser.parse_args()

    if args.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    print("Python:", sys.version.split()[0])

    try:
        import pygame
        import noise
    except Exception as e:
        print("Import error:", e)
        return 1

    print("pygame:", getattr(pygame, "version", getattr(pygame, "__version__", "unknown")))
    print("noise:", getattr(noise, "__version__", "unknown"))

    # Init pygame in a safe way
    import math
    import time

    try:
        pygame.init()
        w, h = 320, 180
        flags = 0
        screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption("env_check (headless OK)")
        clock = pygame.time.Clock()

        # Simple draw loop
        t0 = time.time()
        hue = 0.0
        while time.time() - t0 < args.seconds:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    raise SystemExit

            # Animated background
            hue = (hue + 0.02) % 1.0
            r = int(60 + 195 * abs(math.sin(hue * math.tau)))
            g = int(60 + 195 * abs(math.sin((hue + 1/3) * math.tau)))
            b = int(60 + 195 * abs(math.sin((hue + 2/3) * math.tau)))
            screen.fill((r, g, b))

            # A moving circle
            t = time.time() - t0
            x = int(w / 2 + math.cos(t * 3.0) * (w / 4))
            y = int(h / 2 + math.sin(t * 2.0) * (h / 4))
            pygame.draw.circle(screen, (240, 240, 255), (x, y), 16)

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        print("Pygame smoke test: OK")
        return 0
    except Exception as e:
        print("Pygame smoke test failed:", e)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
