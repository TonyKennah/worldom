"""
This module defines the Unit class, which represents a single unit in the game.
"""
from __future__ import annotations

import math
import random
from collections import deque
from typing import TYPE_CHECKING, Callable, Deque, Iterable, List, Optional, Tuple

import pygame

from src.utils.settings import (
    TILE_SIZE,
    UNIT_RADIUS,
    UNIT_MOVES_PER_SECOND,
    UNIT_COLOR,
    UNIT_SELECTED_COLOR,
    UNIT_INNER_CIRCLE_RATIO,
)

# Optional settings with sensible fallbacks (no changes required in your settings.py)
try:
    from src.utils.settings import (
        UNIT_HOVER_COLOR,       # e.g. (240, 220, 80)
        UNIT_HEALTHBAR_BG,      # e.g. (20, 20, 20)
        UNIT_HEALTHBAR_FG,      # e.g. (80, 220, 80)
        UNIT_SELECTION_RING_WIDTH,  # e.g. 2
    )
except Exception:
    UNIT_HOVER_COLOR = (240, 220, 80)
    UNIT_HEALTHBAR_BG = (20, 20, 20)
    UNIT_HEALTHBAR_FG = (80, 220, 80)
    UNIT_SELECTION_RING_WIDTH = 2

if TYPE_CHECKING:
    from src.core.camera import Camera


_EPS = 1e-3  # positional epsilon in pixels for "arrived" checks


def _tile_to_world_center(tile_xy: pygame.Vector2 | Tuple[int, int]) -> pygame.Vector2:
    v = pygame.Vector2(tile_xy)
    return (v * TILE_SIZE) + pygame.Vector2(TILE_SIZE / 2, TILE_SIZE / 2)


def _shortest_delta(a: pygame.Vector2, b: pygame.Vector2, w_px: int, h_px: int) -> pygame.Vector2:
    """Vector from a -> b on a toroidal map (shortest wrapped delta)."""
    dx = b.x - a.x
    dy = b.y - a.y
    if abs(dx) > w_px * 0.5:
        dx -= math.copysign(w_px, dx)
    if abs(dy) > h_px * 0.5:
        dy -= math.copysign(h_px, dy)
    return pygame.Vector2(dx, dy)


def _wrap_pos_inplace(p: pygame.Vector2, w_px: int, h_px: int) -> None:
    """Wrap in-place into [0, size) range (handles negatives)."""
    if w_px > 0:
        p.x = p.x % w_px
    if h_px > 0:
        p.y = p.y % h_px


class Unit:
    """Represents a single unit in the game."""

    # ---------- initialization ----------
    def __init__(
        self,
        tile_pos: Tuple[int, int],
        *,
        speed_tiles_per_sec: float = UNIT_MOVES_PER_SECOND,
        radius_px: float = UNIT_RADIUS,
        color: Tuple[int, int, int] = UNIT_COLOR,
    ) -> None:
        """
        Args:
            tile_pos: (col, row) starting tile.
            speed_tiles_per_sec: Base movement speed in tiles/sec.
            radius_px: Render radius in pixels (at 1.0x zoom).
            color: Main fill color.
        """
        # Logical & world positions
        self.tile_pos = pygame.Vector2(tile_pos)  # integer-like (col,row)
        self.world_pos = _tile_to_world_center(self.tile_pos)
        self.target_world_pos = self.world_pos.copy()

        # Path/waypoints
        self.path: List[Tuple[int, int]] = []  # public mirror for compatibility
        self._waypoints_px: Deque[pygame.Vector2] = deque()

        # Selection/hover
        self.selected: bool = False
        self.hovered: bool = False
        self._pulse_seed = random.random() * 1000.0

        # Appearance
        self.radius_px = float(radius_px)
        self.color = color
        self.inner_ratio = float(UNIT_INNER_CIRCLE_RATIO)

        # Movement/state
        self.speed_tiles_per_sec = float(speed_tiles_per_sec)
        self.speed_mult = 1.0
        self.arrival_epsilon_px = max(_EPS, self.radius_px * 0.05)
        self.facing_angle = 0.0  # radians, derived from motion
        self.is_paused: bool = False

        # Health (optional UI)
        self.max_hp = 100
        self.hp = 100
        self.show_health_bar = False

        # Callbacks (optional)
        self.on_reach_tile: Optional[Callable[[Unit, Tuple[int, int]], None]] = None
        self.on_reach_goal: Optional[Callable[[Unit], None]] = None

        # Debug
        self.debug_draw_path = False

    # ---------- public API (compatible + additions) ----------
    def get_world_rect(self) -> pygame.Rect:
        """Bounding box in world coordinates (for culling/selection)."""
        size = self.radius_px * 2
        top_left_x = self.world_pos.x - self.radius_px
        top_left_y = self.world_pos.y - self.radius_px
        return pygame.Rect(top_left_x, top_left_y, size, size)

    def set_path(self, path: List[Tuple[int, int]], *, append: bool = False) -> None:
        """Sets a new path (tile list). If append=True, queue after existing."""
        if not append:
            self.path = list(path)
            self._waypoints_px.clear()
        else:
            self.path.extend(path)

        for t in path:
            self._waypoints_px.append(_tile_to_world_center(t))

        if self._waypoints_px and (self.target_world_pos is None or self._arrived(self.target_world_pos)):
            self.target_world_pos = self._waypoints_px[0].copy()

    def clear_path(self) -> None:
        """Stops movement."""
        self.path.clear()
        self._waypoints_px.clear()
        self.target_world_pos = self.world_pos.copy()

    def issue_move_command(self, path: Iterable[Tuple[int, int]], *, append: bool = False) -> None:
        """Alias for set_path; clearer naming at call sites."""
        self.set_path(list(path), append=append)

    def warp_to_tile(self, tile_xy: Tuple[int, int]) -> None:
        """Instantly move the unit to a tile center, clearing its path."""
        self.tile_pos.update(tile_xy)
        self.world_pos = _tile_to_world_center(self.tile_pos)
        self.target_world_pos = self.world_pos.copy()
        self.clear_path()

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def is_moving(self) -> bool:
        return bool(self._waypoints_px)

    def distance_to(self, world_point: Tuple[float, float], map_width_tiles: int, map_height_tiles: int) -> float:
        """Shortest toroidal distance (pixels) to a world point."""
        w_px = map_width_tiles * TILE_SIZE
        h_px = map_height_tiles * TILE_SIZE
        d = _shortest_delta(self.world_pos, pygame.Vector2(world_point), w_px, h_px)
        return d.length()

    # ---------- update ----------
    def update(self, dt: float, map_width_tiles: int, map_height_tiles: int) -> None:
        """Moves smoothly along waypoints; handles toroidal wrapping."""
        if self.is_paused or dt <= 0:
            return

        map_w_px = map_width_tiles * TILE_SIZE
        map_h_px = map_height_tiles * TILE_SIZE

        # Advance to next waypoint if we have arrived (with tolerance)
        if self._waypoints_px:
            if self._arrived(self._waypoints_px[0]):
                reached_wp = self._waypoints_px.popleft()
                reached_tile = self._world_center_to_tile(reached_wp, map_width_tiles, map_height_tiles)
                if self.path:
                    self.path.pop(0)  # keep the public mirror in sync

                # Update callbacks
                if self.on_reach_tile:
                    self.on_reach_tile(self, (int(reached_tile.x), int(reached_tile.y)))

                if self._waypoints_px:
                    self.target_world_pos = self._waypoints_px[0].copy()
                else:
                    self.target_world_pos = self.world_pos.copy()
                    if self.on_reach_goal:
                        self.on_reach_goal(self)

        # If nothing to do, keep tile_pos consistent and exit
        if not self._waypoints_px:
            self._sync_tile_from_world(map_width_tiles, map_height_tiles)
            return

        # Move toward current target
        speed_px_per_sec = max(0.0, self.speed_tiles_per_sec * TILE_SIZE) * max(0.0, self.speed_mult)
        to_target = _shortest_delta(self.world_pos, self._waypoints_px[0], map_w_px, map_h_px)
        dist = to_target.length()

        if dist <= max(self.arrival_epsilon_px, speed_px_per_sec * dt):
            # Snap to target this frame
            self.world_pos = self._waypoints_px[0].copy()
        else:
            if dist > _EPS:
                direction = to_target / dist
                self.facing_angle = math.atan2(direction.y, direction.x)
                self.world_pos += direction * (speed_px_per_sec * dt)

        # Wrap into world and update logical tile
        _wrap_pos_inplace(self.world_pos, map_w_px, map_h_px)
        self._sync_tile_from_world(map_width_tiles, map_height_tiles)

    # ---------- drawing ----------
    def draw(
        self,
        surface: pygame.Surface,
        camera: Camera,
        map_width_pixels: int,
        map_height_pixels: int,
    ) -> None:
        """Draws the unit, handling toroidal wrapping."""
        # Choose 9-neighborhood draws to visualize wrap edges
        for dx in (-map_width_pixels, 0, map_width_pixels):
            for dy in (-map_height_pixels, 0, map_height_pixels):
                offset = pygame.Vector2(dx, dy)
                self._draw_single_unit_instance(surface, camera, self.world_pos + offset)

        if self.debug_draw_path and self._waypoints_px:
            self._draw_path_debug(surface, camera, map_width_pixels, map_height_pixels)

    def _draw_single_unit_instance(
        self,
        surface: pygame.Surface,
        camera: Camera,
        pos: pygame.Vector2,
    ) -> None:
        """Draws a single instance of the unit at a given position."""
        screen_pos = camera.world_to_screen(pos)
        radius = int(max(1.0, self.radius_px * camera.zoom))

        # Quick off-screen cull
        if screen_pos.x + radius < 0 or screen_pos.x - radius > camera.width:
            return
        if screen_pos.y + radius < 0 or screen_pos.y - radius > camera.height:
            return

        # Selection/hover ring (underlay)
        if self.selected or self.hovered:
            # The selection ring width is now constant to prevent a "flickering"
            # or "pulsing" effect that was distracting.
            ring_w = UNIT_SELECTION_RING_WIDTH
            # The unit should always use the global, theme-aware setting for its
            # selection color, rather than storing its own copy.
            ring_color = UNIT_SELECTED_COLOR if self.selected else UNIT_HOVER_COLOR
            pygame.draw.circle(surface, ring_color, screen_pos, int(radius * 1.15), int(max(1, ring_w)))

        # Fill + inner circle (classic look)
        pygame.draw.circle(surface, self.color, screen_pos, radius)
        inner_radius = max(1, int(radius * self.inner_ratio))
        pygame.draw.circle(surface, (0, 0, 0), screen_pos, inner_radius, 1)

        # Direction notch (facing)
        nx = math.cos(self.facing_angle)
        ny = math.sin(self.facing_angle)
        tip = pygame.Vector2(screen_pos.x + nx * (radius * 0.8), screen_pos.y + ny * (radius * 0.8))
        pygame.draw.line(surface, (0, 0, 0), screen_pos, tip, 2)

        # Health bar (optional)
        if self.show_health_bar and self.max_hp > 0:
            self._draw_health_bar(surface, screen_pos, radius)

    def _draw_health_bar(self, surface: pygame.Surface, screen_pos: pygame.Vector2, radius: int) -> None:
        bar_w = max(24, int(radius * 1.6))
        bar_h = max(4, int(radius * 0.3))
        x = int(screen_pos.x - bar_w / 2)
        y = int(screen_pos.y - radius - bar_h - 4)
        # background
        pygame.draw.rect(surface, UNIT_HEALTHBAR_BG, pygame.Rect(x, y, bar_w, bar_h))
        # foreground
        pct = max(0.0, min(1.0, self.hp / float(self.max_hp)))
        pygame.draw.rect(surface, UNIT_HEALTHBAR_FG, pygame.Rect(x + 1, y + 1, int((bar_w - 2) * pct), bar_h - 2))

    def _draw_path_debug(
        self,
        surface: pygame.Surface,
        camera: Camera,
        map_w_px: int,
        map_h_px: int,
    ) -> None:
        """Draws a continuous polyline representing the path, accounting for wraps."""
        pts_world: List[pygame.Vector2] = [self.world_pos.copy()]
        cur = self.world_pos
        for wp in self._waypoints_px:
            cur = cur + _shortest_delta(cur, wp, map_w_px, map_h_px)
            pts_world.append(cur)

        if len(pts_world) <= 1:
            return

        pts_screen = [camera.world_to_screen(p, include_shake=False) for p in pts_world]
        pts_int = [(int(p.x), int(p.y)) for p in pts_screen]
        pygame.draw.lines(surface, (30, 220, 255), False, pts_int, 2)

        # small dots on waypoints
        for p in pts_int[1:]:
            pygame.draw.circle(surface, (30, 220, 255), p, 3)

    # ---------- selection helpers ----------
    def hit_test_screen_point(
        self,
        screen_xy: Tuple[int, int],
        camera: Camera,
        map_width_pixels: int,
        map_height_pixels: int,
    ) -> bool:
        """
        Checks if a screen-space point (mouse) overlaps the unit,
        considering wrap clones near edges.
        """
        mx, my = screen_xy
        z = max(_EPS, camera.zoom)
        r = self.radius_px * z

        for dx in (-map_width_pixels, 0, map_width_pixels):
            for dy in (-map_height_pixels, 0, map_height_pixels):
                p = camera.world_to_screen(self.world_pos + (dx, dy), include_shake=False)
                if (p.x - mx) ** 2 + (p.y - my) ** 2 <= r * r:
                    return True
        return False

    # ---------- internal utilities ----------
    def _arrived(self, target_world: pygame.Vector2) -> bool:
        return (self.world_pos - target_world).length_squared() <= (self.arrival_epsilon_px ** 2)

    def _sync_tile_from_world(self, map_w_tiles: int, map_h_tiles: int) -> None:
        # wrap world -> tile index
        x = int((self.world_pos.x % (map_w_tiles * TILE_SIZE)) // TILE_SIZE) if map_w_tiles > 0 else 0
        y = int((self.world_pos.y % (map_h_tiles * TILE_SIZE)) // TILE_SIZE) if map_h_tiles > 0 else 0
        self.tile_pos.update(x, y)

    @staticmethod
    def _world_center_to_tile(world_center: pygame.Vector2, map_w_tiles: int, map_h_tiles: int) -> pygame.Vector2:
        x = int((world_center.x % (map_w_tiles * TILE_SIZE)) // TILE_SIZE) if map_w_tiles > 0 else 0
        y = int((world_center.y % (map_h_tiles * TILE_SIZE)) // TILE_SIZE) if map_h_tiles > 0 else 0
        return pygame.Vector2(x, y)
