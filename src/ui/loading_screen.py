# src/ui/loading_screen.py
from __future__ import annotations

"""
Unified, resilient loading screen + asset preloader for pygame.

✅ Combines the simple start/pump/finish API from v1 with the richer v2 features:
   - Title, progress bar, status text, ETA + elapsed
   - Subtle animated spinner + gradient background
   - Headless-safe (prints progress if SDL_VIDEODRIVER=dummy)
   - Robust asset preloader (images/sounds/fonts) with graceful fallbacks
   - Logs missing assets once; continues without crashing
   - Optional path resolver integration (supports your existing `assets.resolve_path`)

USAGE (minimal):
    import pygame
    from src.ui.loading_screen import LoadingScreen

    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    loader = LoadingScreen(screen, clock, title="WorldDom")

    # Simple flow
    loader.start("Preparing…")
    for i in range(101):
        if not loader.pump_events(): break
        loader.pump(i/100, f"Step {i}/100")
    loader.finish("Ready")

USAGE (with preloading):
    manifest = {
        "images": ["assets/ui/logo.png", "assets/sprites/hero.png"],
        "sounds": ["assets/sfx/click.wav"],
        "fonts":  [("assets/fonts/Inter-Regular.ttf", 18)],
    }
    resources = loader.run_preload(manifest)  # returns {"images","sounds","fonts"}

You can pass the returned `resources` into your game systems directly.
"""

import os
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

import pygame

# --- Optional path resolver compatibility ------------------------------------
try:
    # Preferred location
    from src.ui.assets import resolve_path  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - best-effort import
    try:
        # Fallback if project keeps it top-level
        from assets import resolve_path  # type: ignore[attr-defined]
    except Exception:  # Final fallback: raw paths only
        resolve_path = None  # type: ignore[assignment]

# --- Types / Colors -----------------------------------------------------------
Color = Tuple[int, int, int]

WHITE: Color = (240, 240, 240)
MID:   Color = (200, 200, 205)
SOFT:  Color = (160, 160, 170)
GREY:  Color = (60, 60, 70)
DARK:  Color = (35, 38, 42)
ACCENT: Color = (88, 196, 255)  # matches original v1 default bar

# --- Helpers ------------------------------------------------------------------
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x

def _now() -> float:
    return time.perf_counter()

def _try_init_font() -> None:
    # Users often call pygame.init(); just be robust if they don't.
    if not pygame.font.get_init():
        pygame.font.init()

def _find_asset(path: str) -> Optional[str]:
    if resolve_path:
        # Let your resolver search typical asset subdirs
        p = resolve_path(path, subdirs=("assets", "image", "images", "sound", "sounds", "audio", "fonts"))
        if p:
            return p
    return path if os.path.exists(path) else None

# --- Asset loading ------------------------------------------------------------
class _AssetLogger:
    """Debounces 'missing' / 'error' messages so each asset logs at most once."""
    def __init__(self) -> None:
        self.missing_once: set[str] = set()
        self.error_once: set[str] = set()

    def missing(self, kind: str, name: str) -> None:
        key = f"missing:{kind}:{name}"
        if key not in self.missing_once:
            self.missing_once.add(key)
            print(f"[loader] {kind} missing: {name}")

    def error(self, kind: str, name: str, err: Exception) -> None:
        key = f"error:{kind}:{name}"
        if key not in self.error_once:
            self.error_once.add(key)
            print(f"[loader] {kind} load error: {name}: {err}")

_LOG = _AssetLogger()

def _load_image(name: str) -> Optional[pygame.Surface]:
    p = _find_asset(name)
    if not p:
        _LOG.missing("image", name)
        return None
    try:
        # convert_alpha requires a display; at this point screen should exist
        return pygame.image.load(p).convert_alpha()
    except Exception as e:  # pragma: no cover - depends on external files
        _LOG.error("image", name, e)
        return None

def _load_sound(name: str) -> Optional[pygame.mixer.Sound]:
    # Allow projects to disable audio in CI/servers by default
    if os.environ.get("WORLDDOM_AUDIO_AVAILABLE") not in ("1", "true", "True"):
        return None
    p = _find_asset(name)
    if not p:
        _LOG.missing("sound", name)
        return None
    try:
        # Mixer must be initialized by the app; if not, this will raise
        return pygame.mixer.Sound(p)
    except Exception as e:  # pragma: no cover
        _LOG.error("sound", name, e)
        return None

def _load_font(entry: Tuple[str, Optional[int]]) -> Optional[pygame.font.Font]:
    _try_init_font()
    path, size = entry
    p = _find_asset(path)
    try:
        if p and size:
            return pygame.font.Font(p, size)
        # On any issue, gracefully fall back to a system font
        return pygame.font.SysFont("Arial", size or 18)
    except Exception:  # pragma: no cover
        return pygame.font.SysFont("Arial", size or 18)

def preload_assets(
    manifest: Dict[str, Any],
    on_progress: Callable[[float, str], None],
) -> Dict[str, Dict[str, Any]]:
    """
    Loads assets enumerated in `manifest`. Calls on_progress(0..1, label).
    Returns dict with 'images', 'sounds', 'fonts' subdicts keyed by basename.
    Missing entries are skipped, errors logged once.
    """
    images: Iterable[str] = manifest.get("images", []) or []
    sounds: Iterable[str] = manifest.get("sounds", []) or []
    fonts: Iterable[Tuple[str, Optional[int]]] = manifest.get("fonts", []) or []

    # Materialize to count reliably even if generators are passed
    images = list(images)
    sounds = list(sounds)
    fonts  = list(fonts)
    total = max(1, len(images) + len(sounds) + len(fonts))
    done = 0

    def step(label: str) -> None:
        nonlocal done
        done += 1
        on_progress(done / total, label)

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
        # key is filename for stable dict access
        key = os.path.basename(entry[0]) if isinstance(entry, (tuple, list)) else str(entry)
        if font:
            res["fonts"][key] = font
        step(f"font: {key}")

    return res

# --- Theme & UI ---------------------------------------------------------------
@dataclass(frozen=True)
class Theme:
    bg: Color = DARK
    bar_bg: Color = GREY
    bar_fg: Color = ACCENT
    title: Color = WHITE
    text: Color = WHITE
    subtext: Color = MID

@dataclass
class Fonts:
    name: str = "Arial"
    big_size: int = 28
    small_size: int = 18
    big: pygame.font.Font = field(init=False)
    small: pygame.font.Font = field(init=False)

    def __post_init__(self) -> None:
        _try_init_font()
        self.big = pygame.font.SysFont(self.name, self.big_size)
        self.small = pygame.font.SysFont(self.name, self.small_size)

# --- Loading Screen -----------------------------------------------------------
class LoadingScreen:
    """
    Minimal GPU-friendly loading screen with:
      - start()/pump(progress, status)/finish(status) API (from v1)
      - spinner, gradient-ish background, robust asset preloader (from v2)
      - headless-friendly output (prints progress)

    Methods:
      start(status="Starting…")
      pump(progress: float, status: str)        # draw one frame
      finish(status="Ready")
      pump_events() -> bool                     # returns False if user closed window
      run_preload(manifest: dict) -> resources  # loads while rendering progress
    """

    def __init__(
        self,
        screen: pygame.Surface,
        clock: Optional[pygame.time.Clock] = None,
        *,
        title: str = "Loading",
        theme: Theme = Theme(),
        font_name: str = "Arial",
        show_spinner: bool = True,
    ) -> None:
        self.screen = screen
        self.clock = clock or pygame.time.Clock()
        self.title = title
        self.theme = theme
        self.fonts = Fonts(name=font_name)
        self.show_spinner = show_spinner

        self._spinner_angle = 0.0
        self._start_time = _now()
        self._last_draw = 0.0
        self._display_progress = 0.0  # smoothed
        self._target_progress = 0.0
        self._last_status = "Starting…"

        # Headless if SDL runs with the "dummy" driver
        self._headless = os.environ.get("SDL_VIDEODRIVER") == "dummy"

    # ---- Public API (v1-compatible) -----------------------------------------
    def start(self, status: str = "Starting…") -> None:
        self._start_time = _now()
        self._display_progress = 0.0
        self._target_progress = 0.0
        self._last_status = status
        self.pump(0.0, status)

    def pump(self, progress: float, status: str) -> None:
        """Render a frame with 'progress' in [0..1] and a short 'status' string."""
        p = clamp(float(progress))
        self._target_progress = p
        self._last_status = status or self._last_status

        if self._headless:
            # Print sparingly (every 5%)
            percent = int(p * 100)
            if percent % 5 == 0:
                print(f"[loading] {percent:02d}% {self._last_status}")
            return

        # Smooth the displayed progress to reduce visual stutter
        self._display_progress += (self._target_progress - self._display_progress) * 0.25

        self._draw_bg()
        self._draw_title()
        if self.show_spinner:
            self._draw_spinner()
        self._draw_bar_and_text(self._display_progress, self._last_status)

        pygame.display.flip()
        self.clock.tick(60)

    def finish(self, status: str = "Ready") -> None:
        self.pump(1.0, status)
        # Leave the bar filled for a few frames to avoid stutter at transition
        if not self._headless:
            for _ in range(8):
                if not self.pump_events():
                    break
                self.pump(1.0, status)

    # ---- Event pump ----------------------------------------------------------
    def pump_events(self) -> bool:
        """Return False if the user tries to close the window (QUIT/ESC/Q)."""
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_q):
                return False
        return True

    # ---- Preloader loop ------------------------------------------------------
    def run_preload(self, manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Runs the visual preload loop. Calls `preload_assets` and renders progress
        on each step. In headless mode it only prints progress.

        Returns:
            resources: {"images": {name: Surface}, "sounds": {name: Sound}, "fonts": {name: Font}}
        """
        self.start("preparing…")
        progress_state = {"p": 0.0, "label": "initializing"}

        # Throttle draws from on_progress to at most 60 fps
        def on_progress(p: float, label: str) -> None:
            progress_state["p"] = p
            progress_state["label"] = label
            if self._headless:
                # Headless printing handled by pump(), but we also print here to ensure visibility
                percent = int(p * 100)
                if percent % 5 == 0:
                    print(f"[loading] {percent:02d}% {label}")
                return

            # Draw immediately but throttle to ~60 fps
            now = _now()
            if now - self._last_draw >= (1.0 / 60.0):
                if self.pump_events():
                    self.pump(p, label)
                self._last_draw = now

        resources = preload_assets(manifest, on_progress)

        # Ensure we end at 100% visibly
        if not self._headless:
            self.pump(1.0, "finalizing…")
            for _ in range(8):
                if not self.pump_events():
                    break
                self.pump(1.0, "finalizing…")

        return resources

    # ---- Drawing primitives --------------------------------------------------
    def _draw_bg(self) -> None:
        """Subtle vertical 'wave' for depth without heavy fills."""
        w, h = self.screen.get_size()
        self.screen.fill(self.theme.bg)
        # Light, cheap scanlines/stripes
        for i in range(0, h, 8):
            shade = int(35 + 25 * math.sin(i * 0.02))
            pygame.draw.rect(self.screen, (shade, shade, shade + 5), (0, i, w, 8))

    def _draw_title(self) -> None:
        title_surf = self.fonts.big.render(self.title, True, self.theme.title)
        self.screen.blit(title_surf, (20, 20))

    def _draw_spinner(self) -> None:
        w, h = self.screen.get_size()
        cx, cy = w // 2, int(h * 0.52)
        self._spinner_angle = (self._spinner_angle + 6.0) % 360.0
        for i in range(12):
            a = math.radians(self._spinner_angle + i * 30)
            r = 14 + (i % 3)
            x = int(cx + math.cos(a) * 22)
            y = int(cy + math.sin(a) * 22)
            pygame.draw.circle(self.screen, (200, 200, 255), (x, y), r // 5)

    def _draw_bar_and_text(self, progress: float, status: str) -> None:
        w, h = self.screen.get_size()
        bar_rect = pygame.Rect(w // 6, int(h * 0.65), w * 2 // 3, 22)

        # Bar background & fill
        pygame.draw.rect(self.screen, self.theme.bar_bg, bar_rect, border_radius=6)
        filled = bar_rect.copy()
        filled.width = int(bar_rect.width * clamp(progress))
        if filled.width > 0:
            pygame.draw.rect(self.screen, self.theme.bar_fg, filled, border_radius=6)

        # Status line (under the bar)
        if status:
            lbl = self.fonts.small.render(status, True, self.theme.text)
            self.screen.blit(lbl, (bar_rect.left, bar_rect.bottom + 8))

        # Percent + elapsed/ETA (above the bar)
        elapsed = max(0.01, _now() - self._start_time)
        pct = int(clamp(progress) * 100)
        if progress > 0.001:
            eta_s = elapsed * (1.0 - progress) / progress
            eta_txt = f"{pct}%  •  {elapsed:.1f}s  •  ETA {eta_s:.1f}s"
        else:
            eta_txt = f"{pct}%  •  {elapsed:.1f}s"
        eta = self.fonts.small.render(eta_txt, True, SOFT)
        self.screen.blit(eta, (bar_rect.left, bar_rect.top - 26))

# --- Optional demo ------------------------------------------------------------
if __name__ == "__main__":  # Quick visual smoke test
    pygame.init()
    try:
        screen = pygame.display.set_mode((960, 540))
        clock = pygame.time.Clock()
        ls = LoadingScreen(screen, clock, title="WorldDom", font_name="Arial")

        manifest = {
            "images": ["assets/ui/logo.png", "assets/sprites/hero.png", "missing.png"],
            "sounds": ["assets/sfx/click.wav"],  # requires mixer + WORLDDOM_AUDIO_AVAILABLE=1
            "fonts":  [("assets/fonts/Inter-Regular.ttf", 18),
                       ("assets/fonts/Inter-Bold.ttf", 28)],
        }
        res = ls.run_preload(manifest)  # noqa: F841
        ls.finish("Ready")
        # Hold for a moment so the user can see 100%
        t0 = _now()
        running = True
        while running and _now() - t0 < 1.0:
            running = ls.pump_events()
            clock.tick(60)
    finally:
        pygame.quit()
