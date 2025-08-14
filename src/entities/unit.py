"""
This module defines the Unit class, which represents a single unit in the game.
"""
from __future__ import annotations

import math
import random
from collections import deque
from typing import TYPE_CHECKING, Callable, Deque, Iterable, List, Optional, Tuple, Dict, Any

import pygame

import src.utils.settings as settings

# For convenience, we can still alias some constants that are not expected to change at runtime.
TILE_SIZE = settings.TILE_SIZE
UNIT_RADIUS = settings.UNIT_RADIUS
UNIT_MOVES_PER_SECOND = settings.UNIT_MOVES_PER_SECOND
UNIT_COLOR = settings.UNIT_COLOR
UNIT_INNER_CIRCLE_RATIO = settings.UNIT_INNER_CIRCLE_RATIO

# Optional settings with sensible fallbacks (no changes required in your settings.py)
try:
    from src.utils.settings import (
        UNIT_HOVER_COLOR,            # e.g. (240, 220, 80)
        UNIT_HEALTHBAR_BG,           # e.g. (20, 20, 20)
        UNIT_HEALTHBAR_FG,           # e.g. (80, 220, 80)
        UNIT_SELECTION_RING_WIDTH,   # e.g. 2
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

        # Optional arrival smoothing (0 disables; non-zero radius slows on approach)
        self.arrive_slowdown_radius_px: float = 0.0  # NEW: default keeps old behavior

        # Temporary speed boost (handled in update)
        self._speed_boost_time: float = 0.0          # NEW
        self._speed_boost_mult: float = 1.0          # NEW

        # Health (optional UI)
        self.max_hp = 100
        self.hp = 100
        self.show_health_bar = False
        self._health_bar_timer: float = 0.0          # NEW: auto-hide timer

        # Visual feedback
        self._flash_time: float = 0.0                # NEW: quick highlight timer
        self._flash_color: Tuple[int, int, int] = (255, 255, 255)

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
        if not path:
            return

        # Drop duplicate consecutive tiles and an initial current-tile waypoint
        cleaned: List[Tuple[int, int]] = []
        prev = None
        cur_tile = (int(self.tile_pos.x), int(self.tile_pos.y))
        for t in path:
            if prev is None or t != prev:
                if not cleaned and t == cur_tile and not append:
                    # Skip an immediate 'start-at-current' tile
                    prev = t
                    continue
                cleaned.append(t)
                prev = t

        if not cleaned:
            return

        if not append:
            self.path = list(cleaned)
            self._waypoints_px.clear()
        else:
            self.path.extend(cleaned)

        for t in cleaned:
            self._waypoints_px.append(_tile_to_world_center(t))

        if self._waypoints_px and (self.target_world_pos is None or self._arrived(self.target_world_pos)):
            self.target_world_pos = self._waypoints_px[0].copy()

    def append_waypoint(self, tile_xy: Tuple[int, int]) -> None:
        """NEW: Append a single tile waypoint to the end of the current path."""
        self.set_path([tile_xy], append=True)

    def insert_waypoint_front(self, tile_xy: Tuple[int, int]) -> None:
        """NEW: Insert a waypoint as the next immediate target (front of the queue)."""
        wp = _tile_to_world_center(tile_xy)
        self.path.insert(0, tile_xy)
        self._waypoints_px.appendleft(wp)
        self.target_world_pos = wp.copy()

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

    def look_at(self, world_point: Tuple[float, float]) -> None:
        """NEW: Manually set facing toward a world point (without moving)."""
        v = pygame.Vector2(world_point) - self.world_pos
        if v.length_squared() > 0:
            self.facing_angle = math.atan2(v.y, v.x)

    def set_speed_boost(self, multiplier: float, duration: float) -> None:
        """NEW: Temporarily boost (or reduce) speed by `multiplier` for `duration` seconds."""
        self._speed_boost_mult = max(0.0, float(multiplier))
        self._speed_boost_time = max(0.0, float(duration))

    def apply_damage(self, amount: int, *, show_bar: bool = True) -> bool:
        """NEW: Apply damage, optionally revealing the health bar briefly. Returns True if unit 'dies'."""
        amt = max(0, int(amount))
        if amt <= 0:
            return False
        self.hp = max(0, self.hp - amt)
        if show_bar:
            self.show_health_bar = True
            self._health_bar_timer = max(self._health_bar_timer, 2.0)  # keep visible for at least 2s
        # Quick flash feedback
        self.flash((255, 120, 120), duration=0.12)
        return self.hp <= 0

    def heal(self, amount: int, *, show_bar: bool = True) -> None:
        """NEW: Heal the unit (clamped to max_hp)."""
        amt = max(0, int(amount))
        if amt <= 0:
            return
        self.hp = min(self.max_hp, self.hp + amt)
        if show_bar:
            self.show_health_bar = True
            self._health_bar_timer = max(self._health_bar_timer, 1.6)
        self.flash((120, 220, 120), duration=0.10)

    def predict_time_to_reach_tile(self, tile_xy: Tuple[int, int], map_w_tiles: int, map_h_tiles: int) -> float:
        """
        NEW: Predict time (seconds) to reach a given tile.
        Uses queued waypoints + straight-line to the requested tile at current effective speed.
        Returns math.inf if speed is zero.
        """
        map_w_px = map_w_tiles * TILE_SIZE
        map_h_px = map_h_tiles * TILE_SIZE

        # Build a pixel-position sequence starting from the current world position
        positions: List[pygame.Vector2] = [self.world_pos.copy()]
        positions.extend(list(self._waypoints_px))
        positions.append(_tile_to_world_center(tile_xy))

        # Sum toroidal segment distances
        dist_px = 0.0
        for i in range(len(positions) - 1):
            dist_px += _shortest_delta(positions[i], positions[i + 1], map_w_px, map_h_px).length()

        effective_mult = self.speed_mult * (self._speed_boost_mult if self._speed_boost_time > 0 else 1.0)
        speed_px_per_sec = max(0.0, self.speed_tiles_per_sec * TILE_SIZE * effective_mult)
        return math.inf if speed_px_per_sec <= 0 else dist_px / speed_px_per_sec

    def to_dict(self) -> Dict[str, Any]:
        """NEW: Serialize minimal state for savegames/debug."""
        return {
            "tile_pos": (int(self.tile_pos.x), int(self.tile_pos.y)),
            "world_pos": (float(self.world_pos.x), float(self.world_pos.y)),
            "speed_tiles_per_sec": self.speed_tiles_per_sec,
            "radius_px": self.radius_px,
            "color": tuple(self.color),
            "speed_mult": self.speed_mult,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "path": list(self.path),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Unit:
        """NEW: Deserialize a unit from a dict produced by to_dict()."""
        u = cls(
            tuple(data.get("tile_pos", (0, 0))),
            speed_tiles_per_sec=float(data.get("speed_tiles_per_sec", UNIT_MOVES_PER_SECOND)),
            radius_px=float(data.get("radius_px", UNIT_RADIUS)),
            color=tuple(data.get("color", UNIT_COLOR)),
        )
        # Restore world pos if provided
        wp = data.get("world_pos")
        if wp:
            u.world_pos = pygame.Vector2(float(wp[0]), float(wp[1]))
            u.target_world_pos = u.world_pos.copy()
        u.speed_mult = float(data.get("speed_mult", 1.0))
        u.max_hp = int(data.get("max_hp", 100))
        u.hp = int(data.get("hp", u.max_hp))
        # Restore path
        pth = data.get("path") or []
        if pth:
            u.set_path(list(map(tuple, pth)), append=False)
        return u

    def flash(self, color: Tuple[int, int, int], duration: float = 0.12) -> None:
        """NEW: Brief visual highlight (light ring) to signal hits/heals/selection."""
        self._flash_color = color
        self._flash_time = max(self._flash_time, float(duration))

    # ---------- update ----------
    def update(self, dt: float, map_width_tiles: int, map_height_tiles: int) -> None:
        """Moves smoothly along waypoints; handles toroidal wrapping."""
        if self.is_paused or dt <= 0:
            return

        # Tick timers
        if self._speed_boost_time > 0.0:
            self._speed_boost_time = max(0.0, self._speed_boost_time - dt)
        if self._health_bar_timer > 0.0:
            self._health_bar_timer = max(0.0, self._health_bar_timer - dt)
            if self._health_bar_timer == 0.0:
                self.show_health_bar = False
        if self._flash_time > 0.0:
            self._flash_time = max(0.0, self._flash_time - dt)

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
        effective_mult = self.speed_mult * (self._speed_boost_mult if self._speed_boost_time > 0 else 1.0)
        base_speed = max(0.0, self.speed_tiles_per_sec * TILE_SIZE)
        speed_px_per_sec = base_speed * max(0.0, effective_mult)

        to_target = _shortest_delta(self.world_pos, self._waypoints_px[0], map_w_px, map_h_px)
        dist = to_target.length()

        # Optional 'arrive' smoothing near waypoint
        if self.arrive_slowdown_radius_px > 0.0 and dist < self.arrive_slowdown_radius_px and dist > _EPS:
            # Scale speed smoothly in [0.35, 1.0] to prevent visible snaps
            k = max(0.35, dist / self.arrive_slowdown_radius_px)
            speed_px_per_sec *= k

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
            ring_w = UNIT_SELECTION_RING_WIDTH
            ring_color = settings.UNIT_SELECTED_COLOR if self.selected else UNIT_HOVER_COLOR
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

        # Flash ring (quick feedback)
        if self._flash_time > 0.0:
            pygame.draw.circle(surface, self._flash_color, screen_pos, int(radius * 1.25), 2)

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
