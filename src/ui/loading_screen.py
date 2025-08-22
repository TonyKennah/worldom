# src/ui/loading_screen.py
from __future__ import annotations

"""
Unified, resilient loading screen + step runner + asset preloader for pygame.

What you get (superset of both originals):
- Simple .start() / .pump(progress, status) / .finish() API
- Time-driven .update(dt, message=?, progress=?) + .draw() API
- Smooth spinner (two styles: 'dots' and 'ticks') + subtle gradient background
- Flexible progress bar placement via negative-aware bar_rect (x, y, w, h)
  · Negative x/y are from right/bottom; negative w/h mean "to right/bottom edge"
- ETA + elapsed above the bar; status line below the bar
- Headless-safe:
  · If screen is None or SDL_VIDEODRIVER='dummy', prints every 5% and skips drawing
- Asset preloader with graceful fallbacks and optional path resolver
  · Images/Sounds/Fonts; logs missing or errors once; returns resources dict
- drive_loader(...) utility to run arbitrary (message, callable) steps with progress

USAGE (minimal loop):
    import pygame
    from src.ui.loading_screen import LoadingScreen

    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    loader = LoadingScreen(screen, clock, title="WorldDom")

    loader.start("Preparing…")
    for i in range(101):
        if not loader.pump_events(): break
        loader.pump(i/100, f"Step {i}/100")
    loader.finish("Ready")

USAGE (time-driven loop + steps):
    from src.ui.loading_screen import drive_loader

    steps = [
        ("Load textures", lambda: None),
        ("Init world",    lambda: None),
        ("Bake navmesh",  lambda: 0.5),  # return a partial delta (0..1) if you want
    ]
    drive_loader(screen, steps)  # shows progress bar + spinner

USAGE (with preloading):
    manifest = {
        "images": ["assets/ui/logo.png", "assets/sprites/hero.png"],
        "sounds": ["assets/sfx/click.wav"],
        "fonts":  [("assets/fonts/Inter-Regular.ttf", 18)],
    }
    resources = loader.run_preload(manifest)  # -> {"images","sounds","fonts"}
"""

import os
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

# --- Lazy pygame import (tools can import this module without pygame present) --
def _pg():
    import pygame
    return pygame

# --- Optional path resolver compatibility ------------------------------------
try:
    # Preferred location in your project
    from src.ui.assets import resolve_path  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - best-effort import
    try:
        from assets import resolve_path  # type: ignore[attr-defined]
    except Exception:
        resolve_path = None  # type: ignore[assignment]

# --- Types / Colors -----------------------------------------------------------
Color = Tuple[int, int, int]

WHITE: Color = (240, 240, 240)
MID:   Color = (200, 200, 205)
SOFT:  Color = (160, 160, 170)
GREY:  Color = (60, 60, 70)
DARK:  Color = (35, 38, 42)
ACCENT: Color = (88, 196, 255)  # matches your original v1 bar color

# --- Helpers ------------------------------------------------------------------
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x

def _now() -> float:
    return time.perf_counter()

def _try_init_font(pg) -> None:
    if not pg.font.get_init():
        pg.font.init()

def _find_asset(path: str) -> Optional[str]:
    # Let your resolver search typical asset subdirs
    if resolve_path:
        p = resolve_path(path, subdirs=("assets", "image", "images", "sound", "sounds", "audio", "fonts"))
        if p:
            return p
    return path if os.path.exists(path) else None

# --- Asset loading (logs once per missing/error) ------------------------------
class _AssetLogger:
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

def _load_image(name: str) -> Optional[Any]:
    pg = _pg()
    p = _find_asset(name)
    if not p:
        _LOG.missing("image", name)
        return None
    try:
        return pg.image.load(p).convert_alpha()
    except Exception as e:  # pragma: no cover
        _LOG.error("image", name, e)
        return None

def _load_sound(name: str) -> Optional[Any]:
    pg = _pg()
    if os.environ.get("WORLDDOM_AUDIO_AVAILABLE") not in ("1", "true", "True"):
        return None
    p = _find_asset(name)
    if not p:
        _LOG.missing("sound", name)
        return None
    try:
        return pg.mixer.Sound(p)
    except Exception as e:  # pragma: no cover
        _LOG.error("sound", name, e)
        return None

def _load_font(entry: Tuple[str, Optional[int]]) -> Optional[Any]:
    pg = _pg()
    _try_init_font(pg)
    path, size = entry
    p = _find_asset(path)
    try:
        if p and size:
            return pg.font.Font(p, size)
        return pg.font.SysFont("Arial", size or 18)
    except Exception:  # pragma: no cover
        return pg.font.SysFont("Arial", size or 18)

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
        key = os.path.basename(entry[0]) if isinstance(entry, (tuple, list)) else str(entry)
        if font:
            res["fonts"][key] = font
        step(f"font: {key}")

    return res

# --- Theme & Fonts ------------------------------------------------------------
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
    big: Any = field(init=False)
    small: Any = field(init=False)

    def __post_init__(self) -> None:
        pg = _pg()
        _try_init_font(pg)
        self.big = pg.font.SysFont(self.name, self.big_size)
        self.small = pg.font.SysFont(self.name, self.small_size)

# --- Loading Screen -----------------------------------------------------------
class LoadingScreen:
    """
    Minimal GPU-friendly loading screen that merges both APIs:

    - v1: start(), pump(progress, status), finish(), pump_events()
    - v2: update(dt, message=?, progress=?), draw(), flexible bar_rect with negatives
    - Extra: run_preload(manifest) -> resources, headless printing

    spinner_style: 'dots' (alpha-faded orbit) or 'ticks' (12 tick marks)
    """

    def __init__(
        self,
        screen: Optional[Any],
        clock: Optional[Any] = None,
        *,
        title: str = "Loading…",
        theme: Theme = Theme(),
        font_name: str = "Arial",
        show_spinner: bool = True,
        spinner_style: str = "dots",           # 'dots' | 'ticks'
        bar_rect: Tuple[int, int, int, int] = (60, -80, -120, 18),
        show_eta: bool = True,
        smooth_progress: bool = True,
    ) -> None:
        self.pg = _pg()
        self.screen = screen
        self.clock = clock or self.pg.time.Clock()
        self.title = title
        self.theme = theme
        self.fonts = Fonts(name=font_name)
        self.show_spinner = show_spinner
        self.spinner_style = spinner_style
        self.bar_rect_spec = bar_rect
        self.show_eta = show_eta
        self.smooth_progress = smooth_progress

        self._spinner_time = 0.0
        self._start_time = _now()
        self._display_progress = 0.0  # smoothed visual value
        self._target_progress = 0.0   # target (what user requested)
        self._last_status = "Starting…"
        self._last_printed_pct = -1

        # Headless if SDL uses 'dummy' or no screen provided
        self._headless = (self.screen is None) or (os.environ.get("SDL_VIDEODRIVER") == "dummy")

    # ---- Rectangle utility (supports negative from right/bottom) -------------
    def _resolve_rect(self, w: int, h: int, rect: Tuple[int, int, int, int]):
        x, y, rw, rh = rect
        if rw < 0: rw = w + rw - x
        if rh < 0: rh = h + rh - y
        if x  < 0: x  = w + x + rw
        if y  < 0: y  = h + y + rh
        return self.pg.Rect(x, y, rw, rh)

    # ---- v1 API ---------------------------------------------------------------
    def start(self, status: str = "Starting…") -> None:
        self._start_time = _now()
        self._spinner_time = 0.0
        self._display_progress = 0.0
        self._target_progress = 0.0
        self._last_status = status
        self.pump(0.0, status)

    def pump(self, progress: float, status: str) -> None:
        """Render one frame. Keeps 60 fps using the clock if provided."""
        dt = self.clock.tick(60) / 1000.0
        self.update(dt, message=status, progress=progress)

    def finish(self, status: str = "Ready") -> None:
        self.pump(1.0, status)
        if not self._headless:
            # Keep 100% filled briefly to avoid visual stutter on transition
            for _ in range(8):
                if not self.pump_events():
                    break
                dt = self.clock.tick(60) / 1000.0
                self.update(dt, message=status, progress=1.0)

    def pump_events(self) -> bool:
        """Return False if the user tries to close the window (QUIT/ESC/Q)."""
        if self._headless:
            return True
        for ev in self.pg.event.get():
            if ev.type == self.pg.QUIT:
                return False
            if ev.type == self.pg.KEYDOWN and ev.key in (self.pg.K_ESCAPE, self.pg.K_q):
                return False
        return True

    # ---- v2 API ---------------------------------------------------------------
    def update(self, dt: float, *, message: Optional[str] = None, progress: Optional[float] = None) -> None:
        self._spinner_time += max(0.0, dt)
        if message is not None:
            self._last_status = message
        if progress is not None:
            self._target_progress = clamp(float(progress))

        # Headless: print every 5%
        if self._headless:
            pct = int(self._target_progress * 100)
            if pct // 5 > self._last_printed_pct // 5:
                self._last_printed_pct = pct
                print(f"[loading] {pct:02d}% {self._last_status}")
            return

        # Smooth visual progress toward target
        if self.smooth_progress:
            self._display_progress += (self._target_progress - self._display_progress) * 0.25
        else:
            self._display_progress = self._target_progress

        self.draw()

    def draw(self) -> None:
        if self._headless or self.screen is None:
            return

        W, H = self.screen.get_width(), self.screen.get_height()
        self._draw_bg(W, H)
        self._draw_title()
        if self.show_spinner:
            self._draw_spinner(W, H)
        self._draw_bar_and_text(W, H, self._display_progress, self._last_status)

        self.pg.display.flip()

    # ---- Preloader loop -------------------------------------------------------
    def run_preload(self, manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Runs the visual preload loop. Calls `preload_assets` and renders progress.
        Returns: {"images": {name: Surface}, "sounds": {name: Sound}, "fonts": {name: Font}}
        """
        self.start("preparing…")

        def on_progress(p: float, label: str) -> None:
            if self._headless:
                pct = int(p * 100)
                if pct // 5 > self._last_printed_pct // 5:
                    self._last_printed_pct = pct
                    print(f"[loading] {pct:02d}% {label}")
                return
            if self.pump_events():
                dt = self.clock.tick(60) / 1000.0
                self.update(dt, message=label, progress=p)

        resources = preload_assets(manifest, on_progress)

        if not self._headless:
            # Ensure we end visibly at 100%
            for _ in range(8):
                if not self.pump_events():
                    break
                dt = self.clock.tick(60) / 1000.0
                self.update(dt, message="finalizing…", progress=1.0)

        return resources

    # ---- Drawing primitives ---------------------------------------------------
    def _draw_bg(self, w: int, h: int) -> None:
        self.screen.fill(self.theme.bg)
        # Subtle vertical wave/stripes
        for i in range(0, h, 8):
            shade = int(35 + 25 * math.sin(i * 0.02))
            self.pg.draw.rect(self.screen, (shade, shade, shade + 5), (0, i, w, 8))

    def _draw_title(self) -> None:
        title_surf = self.fonts.big.render(self.title, True, self.theme.title)
        self.screen.blit(title_surf, (60, 40))

    def _draw_spinner(self, w: int, h: int) -> None:
        cx, cy = w // 2, int(h * 0.52)
        if self.spinner_style == "ticks":
            # 12 tick marks rotating (classic)
            angle_deg = (self._spinner_time * 330.0) % 360.0  # ~0.9 rev/sec
            for i in range(12):
                a = math.radians(angle_deg + i * 30)
                r = 14 + (i % 3)
                x = int(cx + math.cos(a) * 22)
                y = int(cy + math.sin(a) * 22)
                self.pg.draw.circle(self.screen, (200, 200, 255), (x, y), r // 5)
        else:
            # 'dots' style with alpha fade (from your second snippet)
            r_outer = 18
            r_inner = 8
            angle = self._spinner_time * 5.5
            for i in range(10):
                a = angle + i * (math.tau / 10.0)
                x = int(cx + math.cos(a) * r_outer)
                y = int(cy + math.sin(a) * r_outer)
                alpha = 40 + int(180 * (i / 9.0))
                color = (self.theme.bar_fg[0], self.theme.bar_fg[1], self.theme.bar_fg[2], alpha)
                dot = self.pg.Surface((r_inner * 2, r_inner * 2), self.pg.SRCALPHA)
                self.pg.draw.circle(dot, color, (r_inner, r_inner), r_inner)
                self.screen.blit(dot, (x - r_inner, y - r_inner))

    def _draw_bar_and_text(self, w: int, h: int, progress: float, status: str) -> None:
        bar_rect = self._resolve_rect(w, h, self.bar_rect_spec)

        # Bar background & fill
        self.pg.draw.rect(self.screen, self.theme.bar_bg, bar_rect, border_radius=6)
        fill = bar_rect.copy()
        fill.width = int(bar_rect.width * clamp(progress))
        if fill.width > 0:
            self.pg.draw.rect(self.screen, self.theme.bar_fg, fill, border_radius=6)

        # Status line (under the bar)
        if status:
            lbl = self.fonts.small.render(status, True, self.theme.text)
            self.screen.blit(lbl, (bar_rect.x, bar_rect.bottom + 12))

        # Percent + elapsed/ETA (above the bar)
        pct = int(clamp(progress) * 100)
        elapsed = max(0.01, _now() - self._start_time)
        if self.show_eta and progress > 0.001:
            eta_s = elapsed * (1.0 - progress) / progress
            eta_txt = f"{pct}%  •  {elapsed:.1f}s  •  ETA {eta_s:.1f}s"
        else:
            eta_txt = f"{pct}%  •  {elapsed:.1f}s"
        eta = self.fonts.small.render(eta_txt, True, SOFT)
        self.screen.blit(eta, (bar_rect.x, bar_rect.y - 26))

    # ---- Compatibility no-op (kept for symmetry) -----------------------------
    def close(self) -> None:
        pass

# --- Step runner utility ------------------------------------------------------
def drive_loader(
    screen: Optional[Any],
    steps: Iterable[tuple[str, Callable[[], Optional[float]]]],
    clock: Optional[Any] = None,
    *,
    fps: int = 60,
    title: str = "Loading…",
    spinner_style: str = "dots",
) -> None:
    """
    Run a sequence of (message, callable) steps, showing progress.
    Each callable may return None (counts as +1) or a float delta in 0..1.

    Example:
        steps = [
            ("Loading A", load_a),
            ("Loading B", lambda: 0.5),
        ]
        drive_loader(screen, steps)
    """
    pg = _pg()
    loader = LoadingScreen(screen, clock or pg.time.Clock(), title=title, spinner_style=spinner_style)
    steps_list = list(steps)
    total = max(1, len(steps_list))
    done = 0.0

    for message, func in steps_list:
        # Pre-step draw to keep UI alive
        dt = (clock or loader.clock).tick(fps) / 1000.0
        loader.update(dt, message=message, progress=done / total)

        try:
            result = func()
            done += float(result) if isinstance(result, (int, float)) else 1.0
        except Exception as e:
            # Show the error briefly, then re-raise
            loader.update(0.0, message=f"Error: {e}", progress=done / total)
            if not loader._headless:
                pg.display.flip()
            raise
        finally:
            dt = (clock or loader.clock).tick(fps) / 1000.0
            loader.update(dt, progress=min(0.999, done / total))

    # Finish with a few frames at 100% for a smooth handoff
    for _ in range(6):
        dt = (clock or loader.clock).tick(fps) / 1000.0
        loader.update(dt, progress=1.0)
    loader.close()

# --- Optional demo ------------------------------------------------------------
if __name__ == "__main__":  # Quick visual smoke test
    pg = _pg()
    pg.init()
    try:
        screen = pg.display.set_mode((960, 540))
        clock = pg.time.Clock()
        ls = LoadingScreen(
            screen,
            clock,
            title="WorldDom",
            font_name="Arial",
            spinner_style="dots",   # try "ticks"
            bar_rect=(60, -80, -120, 20),
        )

        manifest = {
            "images": ["assets/ui/logo.png", "assets/sprites/hero.png", "missing.png"],
            "sounds": ["assets/sfx/click.wav"],  # requires mixer + WORLDDOM_AUDIO_AVAILABLE=1
            "fonts":  [("assets/fonts/Inter-Regular.ttf", 18),
                       ("assets/fonts/Inter-Bold.ttf", 28)],
        }
        res = ls.run_preload(manifest)  # noqa: F841
        ls.finish("Ready")

        # Hold a moment so the user can see 100%
        t0 = _now()
        running = True
        while running and _now() - t0 < 1.0:
            running = ls.pump_events()
            clock.tick(60)
    finally:
        pg.quit()
