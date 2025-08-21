# c:/prj/WorldDom/src/ui/loading_screen.py
"""
A resilient loading screen with progress bar and asset preloader.
- Skips missing files, logs once
- Works in headless (prints progress)
- Returns a resources dict you can pass into Game
"""
from __future__ import annotations
import os
import math
import pygame
from typing import Any, Callable, Dict, Iterable, Tuple, Optional

# Try both layouts to cooperate with existing helper you might have
try:
    from src.ui.assets import resolve_path  # your improved assets helper
except Exception:
    # fallback if assets.py is top-level
    try:
        from assets import resolve_path
    except Exception:
        resolve_path = None  # last resort; we'll try raw paths

Color = Tuple[int, int, int]
WHITE: Color = (240, 240, 240)
GREY: Color  = (60, 60, 70)
DARK: Color  = (35, 38, 42)
ACCENT: Color = (98, 148, 255)

def _find_asset(path: str) -> Optional[str]:
    if resolve_path:
        p = resolve_path(path, subdirs=("assets", "image", "images", "sound", "sounds", "audio"))
        if p:
            return p
    # Fall back to raw
    return path if os.path.exists(path) else None

def _load_image(name: str) -> Optional[pygame.Surface]:
    p = _find_asset(name)
    if not p:
        print(f"[loader] image missing: {name}")
        return None
    try:
        return pygame.image.load(p).convert_alpha()
    except Exception as e:
        print(f"[loader] image load error: {name}: {e}")
        return None

def _load_sound(name: str) -> Optional[pygame.mixer.Sound]:
    if os.environ.get("WORLDDOM_AUDIO_AVAILABLE") != "1":
        return None
    p = _find_asset(name)
    if not p:
        print(f"[loader] sound missing: {name}")
        return None
    try:
        return pygame.mixer.Sound(p)
    except Exception as e:
        print(f"[loader] sound load error: {name}: {e}")
        return None

def _load_font(entry: Tuple[str, Optional[int]]) -> Optional[pygame.font.Font]:
    path, size = entry
    p = _find_asset(path)
    try:
        if p and size:
            return pygame.font.Font(p, size)
        # If missing, fall back to a system font with a similar size
        return pygame.font.SysFont("Arial", size or 18)
    except Exception:
        # Guaranteed fallback
        return pygame.font.SysFont("Arial", size or 18)

def preload_assets(manifest: Dict[str, Any], on_progress: Callable[[float, str], None]) -> Dict[str, Dict[str, Any]]:
    """
    Loads assets enumerated in `manifest`. Calls on_progress(0..1, label).
    Returns dict with 'images', 'sounds', 'fonts' subdicts keyed by basename.
    Missing entries are skipped.
    """
    images: Iterable[str] = manifest.get("images", [])
    sounds: Iterable[str] = manifest.get("sounds", [])
    fonts: Iterable[Tuple[str, Optional[int]]] = manifest.get("fonts", [])

    total = len(list(images)) + len(list(sounds)) + len(list(fonts))
    done = 0
    def step(label: str):
        nonlocal done
        done += 1
        on_progress(done / max(1, total), label)

    res: Dict[str, Dict[str, Any]] = {"images": {}, "sounds": {}, "fonts": {}}

    for name in images:
        surf = _load_image(name)
        key = os.path.basename(name)
        if surf:
            res["images"][key] = surf
        step(f"image: {key}")

    for name in sounds:
        snd = _load_sound(name)
        key = os.path.basename(name)
        if snd:
            res["sounds"][key] = snd
        step(f"sound: {key}")

    for entry in fonts:
        font = _load_font(entry)
        key = os.path.basename(entry[0]) if isinstance(entry, (tuple, list)) else str(entry)
        if font:
            res["fonts"][key] = font
        step(f"font: {key}")

    return res

class LoadingScreen:
    """
    Minimal GPU-friendly loading screen with progress bar + rotating spinner.
    """
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, *, title: str = "WorldDom") -> None:
        self.screen = screen
        self.clock = clock
        self.title = title
        self._font_big = pygame.font.SysFont("Arial", 28)
        self._font_small = pygame.font.SysFont("Arial", 18)
        self._spinner_angle = 0.0

    def _draw_bg(self) -> None:
        # Simple vertical gradient
        w, h = self.screen.get_size()
        self.screen.fill(DARK)
        for i in range(0, h, 8):
            shade = int(35 + 25 * math.sin(i * 0.02))
            pygame.draw.rect(self.screen, (shade, shade, shade+5), (0, i, w, 8))

    def _draw_spinner(self, center: Tuple[int, int]) -> None:
        self._spinner_angle = (self._spinner_angle + 6.0) % 360.0
        for i in range(12):
            a = math.radians(self._spinner_angle + i * 30)
            r = 14 + (i % 3)
            x = int(center[0] + math.cos(a) * 22)
            y = int(center[1] + math.sin(a) * 22)
            alpha = 70 + 15 * i
            color = (200, 200, 255, min(255, alpha))
            pygame.draw.circle(self.screen, (color[0], color[1], color[2]), (x, y), r // 5)

    def _progress_bar(self, rect: pygame.Rect, t: float) -> None:
        pygame.draw.rect(self.screen, GREY, rect, border_radius=6)
        filled = rect.copy()
        filled.width = int(rect.width * max(0.0, min(1.0, t)))
        pygame.draw.rect(self.screen, ACCENT, filled, border_radius=6)

    def pump_events(self) -> bool:
        """Return False if user tried to close the window."""
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_q):
                return False
        return True

    def draw(self, progress: float, label: str = "") -> None:
        w, h = self.screen.get_size()
        self._draw_bg()

        # Title
        title_surf = self._font_big.render(self.title, True, WHITE)
        self.screen.blit(title_surf, (20, 20))

        # Progress bar
        bar_rect = pygame.Rect(w // 6, int(h * 0.65), w * 2 // 3, 22)
        self._progress_bar(bar_rect, progress)

        # Label
        if label:
            lbl = self._font_small.render(label, True, WHITE)
            self.screen.blit(lbl, (bar_rect.left, bar_rect.bottom + 8))

        # Spinner
        self._draw_spinner((w // 2, int(h * 0.52)))

        pygame.display.flip()
        self.clock.tick(60)

    def run_preload(self, manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Visual preload loop. In headless mode (dummy driver) it prints progress.
        """
        headless = os.environ.get("SDL_VIDEODRIVER") == "dummy"
        progress_state = {"p": 0.0, "label": "initializing"}

        def on_progress(p: float, label: str):
            progress_state["p"] = p
            progress_state["label"] = label
            if headless:
                print(f"[loading] {int(p*100):02d}% {label}")

        # One initial frame
        if not headless:
            self.draw(0.0, "preparing…")

        resources = preload_assets(manifest, on_progress)
        # Stay one extra frame at 100% to avoid stutter
        if not headless:
            for _ in range(8):
                if not self.pump_events():
                    break
                self.draw(progress_state["p"], progress_state["label"])
        return resources
