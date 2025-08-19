# tools/env_check.py
from __future__ import annotations
import argparse
import json
import os
import platform
import sys
import time
import math
from typing import Any, Dict, Tuple

EXIT_OK = 0
EXIT_IMPORT_ERR = 1
EXIT_PYGAME_FAIL = 2

def _print(*args: Any) -> None:
    """Small wrapper so we can turn this into a logger later if desired."""
    print(*args)

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify Python, pygame, and noise; run a headless-friendly pygame smoke test.\n"
            "Auto-fallback to SDL_VIDEODRIVER=dummy if display init fails."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python tools/env_check.py --headless --seconds 2\n"
            "  WORLD_DOM_HEADLESS=1 python tools/env_check.py --no-audio\n"
            "  python tools/env_check.py --json\n"
        ),
    )
    parser.add_argument("--headless", action="store_true",
                        help="Use SDL_VIDEODRIVER=dummy (no window).")
    parser.add_argument("--seconds", type=float, default=1.5,
                        help="How long to run the smoke test loop (default: 1.5s).")
    parser.add_argument("--width", type=int, default=320, help="Window width (default: 320).")
    parser.add_argument("--height", type=int, default=180, help="Window height (default: 180).")
    parser.add_argument("--no-audio", action="store_true",
                        help="Skip audio (mixer) init to avoid ALSA/driver errors.")
    parser.add_argument("--no-noise", action="store_true",
                        help="Skip drawing a Perlin noise surface (still imports 'noise').")
    parser.add_argument("--json", action="store_true",
                        help="Print machine-readable JSON summary (in addition to text).")
    return parser.parse_args()

def _safe_imports() -> Tuple[Any, Any]:
    """Import pygame + noise with readable errors."""
    try:
        import pygame  # type: ignore
    except Exception as e:
        _print("Import error: pygame:", e)
        raise

    try:
        import noise  # type: ignore
    except Exception as e:
        _print("Import error: noise:", e)
        raise
    return pygame, noise

def _maybe_set_headless(headless_flag: bool) -> bool:
    """Set SDL dummy drivers if explicit headless or CI detected."""
    headless = bool(headless_flag or os.environ.get("CI") or os.environ.get("WORLD_DOM_HEADLESS"))
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    return headless

def _try_init_display(pygame: Any, size: Tuple[int, int], headless: bool) -> Tuple[Any, Dict[str, Any]]:
    """Initialize display; fallback to dummy driver if needed."""
    summary: Dict[str, Any] = {}
    summary["requested_size"] = {"w": size[0], "h": size[1]}
    summary["env"] = {
        "SDL_VIDEODRIVER": os.environ.get("SDL_VIDEODRIVER", ""),
        "SDL_AUDIODRIVER": os.environ.get("SDL_AUDIODRIVER", ""),
    }

    try:
        # Initialize display & font only (skip pygame.init() to avoid audio)
        pygame.display.init()
        try:
            pygame.font.init()
        except Exception:
            pass

        screen = pygame.display.set_mode(size, 0)
        info = pygame.display.Info()
        summary["display"] = {
            "driver": os.environ.get("SDL_VIDEODRIVER", ""),
            "current_w": getattr(info, "current_w", None),
            "current_h": getattr(info, "current_h", None),
        }
        pygame.display.set_caption("env_check (headless OK)")
        return screen, summary
    except Exception as e:
        if not headless:
            # Fallback to dummy driver and try again
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
            try:
                pygame.display.quit()
            except Exception:
                pass
            pygame.display.init()
            screen = pygame.display.set_mode((1, 1), 0)  # tiny surface
            info = pygame.display.Info()
            summary["display"] = {
                "driver": "dummy (fallback)",
                "current_w": getattr(info, "current_w", None),
                "current_h": getattr(info, "current_h", None),
            }
            return screen, summary
        raise

def _build_noise_surface(pygame: Any, noise_mod: Any, w: int, h: int) -> Any:
    """
    Build a tiny Perlin noise surface to exercise 'noise'.
    Keep it small and scale up to avoid heavy CPU work in CI.
    """
    tiny_w, tiny_h = max(32, w // 4), max(18, h // 4)
    surf = pygame.Surface((tiny_w, tiny_h))
    # Fill grayscale with Perlin noise
    scale = 32.0
    for y in range(tiny_h):
        for x in range(tiny_w):
            v = noise_mod.pnoise2(x / scale, y / scale, octaves=1, repeatx=1024, repeaty=1024, base=0)
            # pnoise2 -> [-1,1], map to [0,255]
            c = int((v * 0.5 + 0.5) * 255)
            surf.set_at((x, y), (c, c, c))
    return surf

def main() -> int:
    args = _parse_args()

    # Basic environment info
    summary: Dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "headless_requested": bool(args.headless or os.environ.get("WORLD_DOM_HEADLESS")),
        "ci": bool(os.environ.get("CI")),
        "result": "unknown",
        "frames": 0,
        "avg_fps": None,
        "error": None,
    }

    _print("Python:", summary["python"])
    _print("Platform:", summary["platform"])

    # Headless environment
    headless = _maybe_set_headless(args.headless)
    if headless:
        _print("Video driver: dummy (headless)")
    elif os.environ.get("SDL_VIDEODRIVER"):
        _print("Video driver:", os.environ["SDL_VIDEODRIVER"])

    # Imports
    try:
        pygame, noise_mod = _safe_imports()
    except Exception as e:
        summary["result"] = "import_error"
        summary["error"] = f"{e}"
        if args.json:
            print(json.dumps(summary, indent=2))
        return EXIT_IMPORT_ERR

    _print("pygame:", getattr(pygame, "version", getattr(pygame, "__version__", "unknown")))
    _print("noise:", getattr(noise_mod, "__version__", "unknown"))

    # Display init (with fallback)
    try:
        screen, disp = _try_init_display(pygame, (args.width, args.height), headless=headless)
        summary.update(disp)
    except Exception as e:
        _print("Pygame display init failed:", e)
        summary["result"] = "pygame_fail"
        summary["error"] = f"{e}"
        if args.json:
            print(json.dumps(summary, indent=2))
        return EXIT_PYGAME_FAIL

    # Optional audio probe
    audio_inited = False
    if not args.no_audio:
        try:
            pygame.mixer.init()
            audio_inited = True
        except Exception:
            # Don’t fail the check just because audio init is unavailable
            pass
    summary["audio_inited"] = audio_inited
    if audio_inited:
        _print("Audio: initialized")
    else:
        _print("Audio: skipped or unavailable")

    clock = pygame.time.Clock()

    # Prepare optional Perlin surface (once)
    perlin_surf = None
    if not args.no_noise:
        try:
            perlin_surf = _build_noise_surface(pygame, noise_mod, args.width, args.height)
        except Exception as e:
            # Still OK if noise draw fails, we already tested import
            _print("Perlin draw setup failed (continuing):", e)

    # Simple smoke loop
    t0 = time.monotonic()
    hue = 0.0
    frames = 0

    try:
        while (time.monotonic() - t0) < args.seconds:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    raise SystemExit

            # Animated background (RGB hue-ish)
            hue = (hue + 0.02) % 1.0
            r = int(60 + 195 * abs(math.sin(hue * math.tau)))
            g = int(60 + 195 * abs(math.sin((hue + 1/3) * math.tau)))
            b = int(60 + 195 * abs(math.sin((hue + 2/3) * math.tau)))
            screen.fill((r, g, b))

            # Blit Perlin surface scaled up with some alpha
            if perlin_surf is not None:
                try:
                    scaled = pygame.transform.smoothscale(perlin_surf, screen.get_size())
                    scaled.set_alpha(96)
                    screen.blit(scaled, (0, 0))
                except Exception:
                    perlin_surf = None  # disable if transform fails

            # A moving circle (also tests alpha blend paths)
            t = time.monotonic() - t0
            w, h = screen.get_size()
            x = int(w / 2 + math.cos(t * 3.0) * (w / 4))
            y = int(h / 2 + math.sin(t * 2.0) * (h / 4))
            pygame.draw.circle(screen, (240, 240, 255), (x, y), 16)

            pygame.display.flip()
            # Busy loop is more stable for CI timing; plain tick is fine too
            clock.tick_busy_loop(60)
            frames += 1

        summary["frames"] = frames
        # Approximate FPS (avoid division by zero)
        elapsed = max(1e-6, time.monotonic() - t0)
        summary["avg_fps"] = round(frames / elapsed, 2)
        summary["result"] = "ok"
        _print("Pygame smoke test: OK  (frames:", frames, "avg_fps:", summary["avg_fps"], ")")
        return_code = EXIT_OK
    except Exception as e:
        _print("Pygame smoke test failed:", e)
        summary["result"] = "pygame_fail"
        summary["error"] = f"{e}"
        return_code = EXIT_PYGAME_FAIL
    finally:
        try:
            pygame.quit()
        except Exception:
            pass

    if args.json:
        print(json.dumps(summary, indent=2))
    return return_code

if __name__ == "__main__":
    raise SystemExit(main())
