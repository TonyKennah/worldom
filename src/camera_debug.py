# camera_debug.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

import pygame


# -----------------------------
# Colors
# -----------------------------
YELLOW = (245, 220, 120)
CYAN   = (120, 210, 230)
WHITE  = (255, 255, 255)
RED    = (235, 95, 95)
PANEL_BG = (0, 0, 0, 160)


# -----------------------------
# Camera protocol (for type checkers)
# -----------------------------
@runtime_checkable
class CameraLike(Protocol):
    position: pygame.math.Vector2
    velocity: pygame.math.Vector2
    zoom: float
    screen_center: pygame.math.Vector2
    follow_deadzone_frac: pygame.math.Vector2

    # Optional, but used if present for precise grid/origin:
    def world_to_screen(self, pt: pygame.math.Vector2) -> pygame.math.Vector2: ...
    def screen_to_world(self, pt: pygame.math.Vector2) -> pygame.math.Vector2: ...


# -----------------------------
# Config
# -----------------------------
@dataclass
class CameraDebugConfig:
    show_crosshair: bool = True
    show_deadzone: bool = True
    show_velocity: bool = True
    show_text: bool = True
    show_grid: bool = False
    show_origin_axes: bool = False  # draws world origin axes if transform is known
    velocity_scale: float = 0.25    # pixels per (world-unit/second) * zoom
    velocity_max_len_px: int = 140
    grid_world_step: int = 64       # base world units between grid lines
    grid_min_px: int = 24           # don't draw if spacing would be tighter
    font_name: str = "consolas"
    font_size: int = 14
    panel_margin: int = 8
    panel_pad_x: int = 8
    panel_pad_y: int = 6


# -----------------------------
# Overlay
# -----------------------------
class CameraDebugOverlay:
    def __init__(self, config: Optional[CameraDebugConfig] = None) -> None:
        self.cfg = config or CameraDebugConfig()
        # Cache a mono-like font; pygame will fallback if not found
        self.font = pygame.font.SysFont(self.cfg.font_name, self.cfg.font_size)
        self.enabled = True

    # ---- public API -------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        """Basic hotkeys: F1 toggles overlay, G toggles grid."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F1:
                self.enabled = not self.enabled
            elif event.key == pygame.K_g:
                self.cfg.show_grid = not self.cfg.show_grid

    def draw(
        self,
        screen: pygame.Surface,
        camera: CameraLike,
        dt: Optional[float] = None,
        fps: Optional[float] = None,
    ) -> None:
        """Draw the camera debug overlay. Pass dt (seconds) or fps if you have them."""
        if not self.enabled:
            return

        w, h = screen.get_width(), screen.get_height()
        center = self._get_screen_center(screen, camera)
        zoom = self._get_zoom(camera)
        pos = self._get_vec(camera, "position")
        vel = self._get_vec(camera, "velocity")
        dz_frac = self._get_vec(camera, "follow_deadzone_frac", default=(0.35, 0.35))

        # Optional world transforms (prefer camera methods if present)
        world_to_screen = self._build_world_to_screen(camera, center, pos, zoom)
        screen_to_world = self._build_screen_to_world(camera, center, pos, zoom)

        if self.cfg.show_grid:
            self._draw_grid(screen, world_to_screen, screen_to_world, zoom)

        if self.cfg.show_origin_axes:
            self._draw_origin_axes(screen, world_to_screen)

        if self.cfg.show_crosshair:
            self._draw_crosshair(screen, center)

        if self.cfg.show_deadzone:
            self._draw_deadzone(screen, center, (w, h), dz_frac)

        if self.cfg.show_velocity:
            self._draw_velocity_arrow(screen, center, vel, zoom)

        if self.cfg.show_text:
            self._draw_info_panel(
                screen=screen,
                pos=pos,
                vel=vel,
                zoom=zoom,
                center=center,
                dz_frac=dz_frac,
                dt=dt,
                fps=fps,
                screen_to_world=screen_to_world,
            )

    # ---- drawing helpers -------------------------------------------

    def _draw_crosshair(self, screen: pygame.Surface, center: pygame.math.Vector2) -> None:
        cx, cy = int(center.x), int(center.y)
        pygame.draw.line(screen, CYAN, (cx - 8, cy), (cx + 8, cy), 1)
        pygame.draw.line(screen, CYAN, (cx, cy - 8), (cx, cy + 8), 1)

    def _draw_deadzone(
        self,
        screen: pygame.Surface,
        center: pygame.math.Vector2,
        screen_size: tuple[int, int],
        dz_frac: pygame.math.Vector2,
    ) -> None:
        w, h = screen_size
        dz_w = int(w * float(dz_frac.x))
        dz_h = int(h * float(dz_frac.y))
        rect = pygame.Rect(center.x - dz_w // 2, center.y - dz_h // 2, dz_w, dz_h)
        pygame.draw.rect(screen, YELLOW, rect, 1)

    def _draw_velocity_arrow(
        self,
        screen: pygame.Surface,
        start: pygame.math.Vector2,
        velocity_world: pygame.math.Vector2,
        zoom: float,
    ) -> None:
        if velocity_world.length_squared() <= 1e-9:
            return
        # Scale world velocity to screen space (heuristic)
        scale = self.cfg.velocity_scale * max(zoom, 1e-6)
        end = pygame.math.Vector2(start.x, start.y) + velocity_world * scale

        # Clamp the arrow length to avoid huge draws
        vec = end - start
        length = vec.length()
        if length > self.cfg.velocity_max_len_px:
            vec.scale_to_length(self.cfg.velocity_max_len_px)
            end = start + vec

        pygame.draw.line(screen, RED, start, end, 2)
        self._draw_arrow_head(screen, end, start, RED, 2)

    def _draw_arrow_head(
        self,
        screen: pygame.Surface,
        tip: pygame.math.Vector2,
        tail: pygame.math.Vector2,
        color: tuple[int, int, int],
        width: int = 1,
    ) -> None:
        direction = (tail - tip)
        if direction.length_squared() <= 1e-9:
            return
        direction.scale_to_length(12)
        left = direction.rotate(25)
        right = direction.rotate(-25)
        p1 = tip + left
        p2 = tip + right
        pygame.draw.line(screen, color, tip, p1, width)
        pygame.draw.line(screen, color, tip, p2, width)

    def _draw_grid(
        self,
        screen: pygame.Surface,
        world_to_screen,
        screen_to_world,
        zoom: float,
    ) -> None:
        w, h = screen.get_width(), screen.get_height()

        # Determine a sensible world step so lines aren't too dense/thin
        step = float(self.cfg.grid_world_step)
        # Keep on-screen spacing within [grid_min_px, 6*grid_min_px]
        while step * zoom < self.cfg.grid_min_px:
            step *= 2.0
        while step * zoom > self.cfg.grid_min_px * 6:
            step *= 0.5

        # World rect covered by the screen
        top_left_world = screen_to_world(pygame.math.Vector2(0, 0))
        bottom_right_world = screen_to_world(pygame.math.Vector2(w, h))

        x0 = int(step * (top_left_world.x // step))
        y0 = int(step * (top_left_world.y // step))
        x1 = int(bottom_right_world.x) + 1
        y1 = int(bottom_right_world.y) + 1

        # Safety caps
        max_lines = 400

        # Vertical lines
        count = 0
        x = x0
        while x <= x1 and count < max_lines:
            a = world_to_screen(pygame.math.Vector2(x, top_left_world.y))
            b = world_to_screen(pygame.math.Vector2(x, bottom_right_world.y))
            color = (80, 110, 120) if (int(x / step) % 4) else (120, 150, 160)
            pygame.draw.line(screen, color, a, b, 1)
            x += step
            count += 1

        # Horizontal lines
        count = 0
        y = y0
        while y <= y1 and count < max_lines:
            a = world_to_screen(pygame.math.Vector2(top_left_world.x, y))
            b = world_to_screen(pygame.math.Vector2(bottom_right_world.x, y))
            color = (80, 110, 120) if (int(y / step) % 4) else (120, 150, 160)
            pygame.draw.line(screen, color, a, b, 1)
            y += step
            count += 1

    def _draw_origin_axes(self, screen: pygame.Surface, world_to_screen) -> None:
        origin = world_to_screen(pygame.math.Vector2(0, 0))
        # Draw a small cross to mark world origin
        cx, cy = int(origin.x), int(origin.y)
        pygame.draw.line(screen, (190, 100, 100), (cx - 10, cy), (cx + 10, cy), 2)
        pygame.draw.line(screen, (100, 190, 100), (cx, cy - 10), (cx, cy + 10), 2)

    def _draw_info_panel(
        self,
        screen: pygame.Surface,
        pos: pygame.math.Vector2,
        vel: pygame.math.Vector2,
        zoom: float,
        center: pygame.math.Vector2,
        dz_frac: pygame.math.Vector2,
        dt: Optional[float],
        fps: Optional[float],
        screen_to_world,
    ) -> None:
        mx, my = pygame.mouse.get_pos()
        mouse_world = screen_to_world(pygame.math.Vector2(mx, my))

        # Estimate FPS if not provided
        est_fps = fps
        if est_fps is None and dt and dt > 1e-6:
            est_fps = 1.0 / dt

        lines = [
            f"cam pos=({pos.x:.1f}, {pos.y:.1f})  zoom={zoom:.3f}",
            f"vel=({vel.x:.1f}, {vel.y:.1f})  speed={vel.length():.1f}",
            f"center=({center.x:.1f}, {center.y:.1f})  deadzone=({dz_frac.x:.2f}, {dz_frac.y:.2f})",
            f"mouse_screen=({mx}, {my})  mouse_world=({mouse_world.x:.1f}, {mouse_world.y:.1f})",
            (
                f"fps={est_fps:.1f}  dt_ms={dt * 1000.0:.2f}"
                if dt is not None
                else (f"fps={est_fps:.1f}" if est_fps is not None else "fps=?")
            ),
            "F1: toggle overlay   G: toggle grid",
        ]

        # Measure panel size
        max_w = 0
        total_h = 0
        rendered = []
        for line in lines:
            surf = self.font.render(line, True, WHITE)
            rendered.append(surf)
            w, h = surf.get_size()
            max_w = max(max_w, w)
            total_h += h

        pad_x, pad_y = self.cfg.panel_pad_x, self.cfg.panel_pad_y
        margin = self.cfg.panel_margin
        panel = pygame.Surface((max_w + pad_x * 2, total_h + pad_y * 2), pygame.SRCALPHA)
        panel.fill(PANEL_BG)

        # Blit lines to panel
        y = pad_y
        for surf in rendered:
            panel.blit(surf, (pad_x, y))
            y += surf.get_height()

        # Final blit to screen (top-left corner)
        screen.blit(panel, (margin, margin))

    # ---- camera helpers --------------------------------------------

    def _get_vec(
        self,
        camera: CameraLike,
        name: str,
        default: tuple[float, float] = (0.0, 0.0),
    ) -> pygame.math.Vector2:
        if hasattr(camera, name):
            v = getattr(camera, name)
            # If user passes tuples instead of Vector2, coerce
            if not isinstance(v, pygame.math.Vector2):
                v = pygame.math.Vector2(v)
            return v
        return pygame.math.Vector2(default)

    def _get_zoom(self, camera: CameraLike) -> float:
        return float(getattr(camera, "zoom", 1.0)) or 1.0

    def _get_screen_center(
        self, screen: pygame.Surface, camera: CameraLike
    ) -> pygame.math.Vector2:
        if hasattr(camera, "screen_center"):
            v = getattr(camera, "screen_center")
            return v if isinstance(v, pygame.math.Vector2) else pygame.math.Vector2(v)
        # Fallback: assume true screen center
        return pygame.math.Vector2(screen.get_width() * 0.5, screen.get_height() * 0.5)

    def _build_world_to_screen(
        self,
        camera: CameraLike,
        center: pygame.math.Vector2,
        pos: pygame.math.Vector2,
        zoom: float,
    ):
        # Prefer camera's own transform if present
        if hasattr(camera, "world_to_screen"):
            return getattr(camera, "world_to_screen")

        # Fallback mapping: screen = (world - camera_pos) * zoom + center
        def _w2s(p: pygame.math.Vector2) -> pygame.math.Vector2:
            return (p - pos) * zoom + center

        return _w2s

    def _build_screen_to_world(
        self,
        camera: CameraLike,
        center: pygame.math.Vector2,
        pos: pygame.math.Vector2,
        zoom: float,
    ):
        # Prefer camera's own transform if present
        if hasattr(camera, "screen_to_world"):
            return getattr(camera, "screen_to_world")

        inv = 1.0 / max(zoom, 1e-6)

        # Fallback mapping: world = (screen - center) / zoom + camera_pos
        def _s2w(p: pygame.math.Vector2) -> pygame.math.Vector2:
            return (p - center) * inv + pos

        return _s2w


# -----------------------------
# Legacy API for drop-in use
# -----------------------------
# If you just want a function like the original:
_overlay_singleton: Optional[CameraDebugOverlay] = None

def draw_camera_debug_overlay(
    screen: pygame.Surface, camera: CameraLike, dt: Optional[float] = None, fps: Optional[float] = None
) -> None:
    """Render a richer debug overlay (keeps a cached font)."""
    global _overlay_singleton
    if _overlay_singleton is None:
        _overlay_singleton = CameraDebugOverlay()
    _overlay_singleton.draw(screen, camera, dt=dt, fps=fps)
