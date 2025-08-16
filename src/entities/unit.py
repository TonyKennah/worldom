"""
Unit: movement, selection, effects, and rendering (toroidal world).
This preserves your previous Unit API and behavior while delegating to helpers.
"""
from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pygame
import src.utils.settings as settings
from src.core.toroidal import (
    TILE_SIZE,
    shortest_delta,
    tile_to_world_center,
    world_center_to_tile,
    wrap_pos_inplace,
)
from .effects import EffectManager
from .pathing import PathQueue
from .render import draw_unit, draw_path_debug

if settings is None:  # pragma: no cover - safety for static analyzers
    raise RuntimeError("settings module missing")

# Constants (alias for convenience)
UNIT_RADIUS = settings.UNIT_RADIUS
UNIT_MOVES_PER_SECOND = settings.UNIT_MOVES_PER_SECOND
UNIT_COLOR = settings.UNIT_COLOR
UNIT_INNER_CIRCLE_RATIO = settings.UNIT_INNER_CIRCLE_RATIO

_EPS = 1e-3

if False:  # typing-only forward ref
    from src.core.camera import Camera


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
        # Logical & world positions
        self.tile_pos = pygame.Vector2(tile_pos)  # integer-like (col,row)
        self.world_pos = tile_to_world_center(self.tile_pos)
        self.target_world_pos = self.world_pos.copy()

        # Path/waypoints (public mirror retained)
        self._path = PathQueue()
        self.path: List[Tuple[int, int]] = self._path.tiles  # public view

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
        self.facing_angle = 0.0  # radians
        self.turn_rate_rad_per_sec: float = math.inf  # NEW: set finite to smooth facing
        self.is_paused: bool = False

        # Optional arrival smoothing
        self.arrive_slowdown_radius_px: float = 0.0  # (kept from your version)

        # Health
        self.max_hp = 100
        self.hp = 100

        # Effects/visuals
        self._fx = EffectManager()

        # Callbacks
        self.on_reach_tile: Optional[Callable[[Unit, Tuple[int, int]], None]] = None
        self.on_reach_goal: Optional[Callable[[Unit], None]] = None

        # Debug
        self.debug_draw_path = False

    # ---------- public API (compatible + additions) ----------
    def get_world_rect(self) -> pygame.Rect:
        size = self.radius_px * 2
        return pygame.Rect(self.world_pos.x - self.radius_px,
                           self.world_pos.y - self.radius_px, size, size)

    # Path control (kept API)
    def set_path(self, path: List[Tuple[int, int]], *, append: bool = False) -> None:
        if not path:
            return
        cur_tile = (int(self.tile_pos.x), int(self.tile_pos.y))
        self._path.set_path(path, append=append, current_tile=cur_tile)
        if self._path.has_waypoints():
            self.target_world_pos = self._path.peek().copy()

    def append_waypoint(self, tile_xy: Tuple[int, int]) -> None:
        self._path.append_waypoint(tile_xy)

    def insert_waypoint_front(self, tile_xy: Tuple[int, int]) -> None:
        self._path.insert_front(tile_xy)
        self.target_world_pos = tile_to_world_center(tile_xy)

    def clear_path(self) -> None:
        self._path.clear()
        self.target_world_pos = self.world_pos.copy()

    def issue_move_command(self, path: Iterable[Tuple[int, int]], *, append: bool = False) -> None:
        self.set_path(list(path), append=append)

    def warp_to_tile(self, tile_xy: Tuple[int, int]) -> None:
        self.tile_pos.update(tile_xy)
        self.world_pos = tile_to_world_center(self.tile_pos)
        self.target_world_pos = self.world_pos.copy()
        self.clear_path()

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def is_moving(self) -> bool:
        return self._path.has_waypoints()

    def distance_to(self, world_point: Tuple[float, float], map_width_tiles: int, map_height_tiles: int) -> float:
        w_px = map_width_tiles * TILE_SIZE
        h_px = map_height_tiles * TILE_SIZE
        return shortest_delta(self.world_pos, pygame.Vector2(world_point), w_px, h_px).length()

    def look_at(self, world_point: Tuple[float, float]) -> None:
        v = pygame.Vector2(world_point) - self.world_pos
        if v.length_squared() > 0:
            self.facing_angle = math.atan2(v.y, v.x)

    # New: expose fx methods while keeping old names
    def set_speed_boost(self, multiplier: float, duration: float) -> None:
        self._fx.add_speed_boost(multiplier, duration)

    def apply_damage(self, amount: int, *, show_bar: bool = True) -> bool:
        amt = max(0, int(amount))
        if amt <= 0:
            return False
        self.hp = max(0, self.hp - amt)
        if show_bar:
            self._fx.show_health_for(2.0)
        self._fx.flash((255, 120, 120), duration=0.12)
        return self.hp <= 0

    def heal(self, amount: int, *, show_bar: bool = True) -> None:
        amt = max(0, int(amount))
        if amt <= 0:
            return
        self.hp = min(self.max_hp, self.hp + amt)
        if show_bar:
            self._fx.show_health_for(1.6)
        self._fx.flash((120, 220, 120), duration=0.10)

    def predict_time_to_reach_tile(self, tile_xy: Tuple[int, int], map_w_tiles: int, map_h_tiles: int) -> float:
        map_w_px = map_w_tiles * TILE_SIZE
        map_h_px = map_h_tiles * TILE_SIZE
        dist_px = self._path.predicted_distance_px(self.world_pos, tile_xy, map_w_px, map_h_px)

        eff_mult = self.speed_mult * self._fx.speed_multiplier()
        speed_px_per_sec = max(0.0, self.speed_tiles_per_sec * TILE_SIZE * eff_mult)
        return math.inf if speed_px_per_sec <= 0 else dist_px / speed_px_per_sec

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "Unit":
        u = cls(
            tuple(data.get("tile_pos", (0, 0))),
            speed_tiles_per_sec=float(data.get("speed_tiles_per_sec", UNIT_MOVES_PER_SECOND)),
            radius_px=float(data.get("radius_px", UNIT_RADIUS)),
            color=tuple(data.get("color", UNIT_COLOR)),
        )
        wp = data.get("world_pos")
        if wp:
            u.world_pos = pygame.Vector2(float(wp[0]), float(wp[1]))
            u.target_world_pos = u.world_pos.copy()
        u.speed_mult = float(data.get("speed_mult", 1.0))
        u.max_hp = int(data.get("max_hp", 100))
        u.hp = int(data.get("hp", u.max_hp))
        pth = data.get("path") or []
        if pth:
            u.set_path(list(map(tuple, pth)), append=False)
        return u

    def flash(self, color: Tuple[int, int, int], duration: float = 0.12) -> None:
        self._fx.flash(color, duration)

    # ---------- update ----------
    def update(self, dt: float, map_width_tiles: int, map_height_tiles: int) -> None:
        if dt <= 0:
            return

        self._fx.update(self, dt)

        # Pause or stun stops movement but still updates effects.
        if self.is_paused or self._fx.is_stunned():
            return

        map_w_px = map_width_tiles * TILE_SIZE
        map_h_px = map_height_tiles * TILE_SIZE

        # Advance waypoint on arrival
        reached, reached_wp = self._path.advance_if_arrived(
            self.world_pos, self.arrival_epsilon_px, map_w_px, map_h_px
        )
        if reached and reached_wp is not None:
            reached_tile = world_center_to_tile(reached_wp, map_width_tiles, map_height_tiles)
            if self.on_reach_tile:
                self.on_reach_tile(self, (int(reached_tile.x), int(reached_tile.y)))
            if not self._path.has_waypoints():
                self.target_world_pos = self.world_pos.copy()
                if self.on_reach_goal:
                    self.on_reach_goal(self)
            else:
                self.target_world_pos = self._path.peek().copy()

        if not self._path.has_waypoints():
            self._sync_tile_from_world(map_width_tiles, map_height_tiles)
            return

        # Effective movement speed
        eff_mult = self.speed_mult * self._fx.speed_multiplier()
        speed_px_per_sec = max(0.0, self.speed_tiles_per_sec * TILE_SIZE * max(0.0, eff_mult))

        # Move toward target
        target = self._path.peek()
        to_target = shortest_delta(self.world_pos, target, map_w_px, map_h_px)
        dist = to_target.length()

        # Optional arrival slowdown
        if self.arrive_slowdown_radius_px > 0.0 and dist < self.arrive_slowdown_radius_px and dist > _EPS:
            k = max(0.35, dist / self.arrive_slowdown_radius_px)
            speed_px_per_sec *= k

        step = speed_px_per_sec * dt

        if dist <= max(self.arrival_epsilon_px, step):
            self.world_pos = target.copy()
        else:
            if dist > _EPS:
                direction = to_target / dist
                self._update_facing(direction, dt)
                self.world_pos += direction * step

        wrap_pos_inplace(self.world_pos, map_w_px, map_h_px)
        self._sync_tile_from_world(map_width_tiles, map_height_tiles)

    def _update_facing(self, direction: pygame.Vector2, dt: float) -> None:
        """Optionally smooth-facing toward 'direction' given a turn-rate limit."""
        desired = math.atan2(direction.y, direction.x)
        if not math.isfinite(self.turn_rate_rad_per_sec) or self.turn_rate_rad_per_sec <= 0 or self.turn_rate_rad_per_sec == math.inf:
            self.facing_angle = desired
            return
        # Shortest angular delta
        delta = (desired - self.facing_angle + math.pi) % (2 * math.pi) - math.pi
        max_step = self.turn_rate_rad_per_sec * dt
        if abs(delta) <= max_step:
            self.facing_angle = desired
        else:
            self.facing_angle += math.copysign(max_step, delta)

    # ---------- drawing ----------
    def draw(
        self,
        surface: pygame.Surface,
        camera: "Camera",
        map_width_pixels: int,
        map_height_pixels: int,
    ) -> None:
        # 9-neighborhood clones for wrap visuals
        flash = self._fx.flash_ring()
        health = (self.hp, self.max_hp) if self._fx.healthbar_visible() else None

        for dx in (-map_width_pixels, 0, map_width_pixels):
            for dy in (-map_height_pixels, 0, map_height_pixels):
                draw_unit(
                    surface,
                    camera,
                    self.world_pos + pygame.Vector2(dx, dy),
                    radius_px=self.radius_px,
                    color=self.color,
                    inner_ratio=self.inner_ratio,
                    facing_angle=self.facing_angle,
                    selected=self.selected,
                    hovered=self.hovered,
                    flash=flash,
                    health=health,
                )

        if self.debug_draw_path and self._path.has_waypoints():
            pts = self._path.as_world_polyline(self.world_pos, map_width_pixels, map_height_pixels)
            draw_path_debug(surface, camera, pts)

    # ---------- selection helpers ----------
    def hit_test_screen_point(
        self,
        screen_xy: Tuple[int, int],
        camera: "Camera",
        map_width_pixels: int,
        map_height_pixels: int,
    ) -> bool:
        mx, my = screen_xy
        z = max(_EPS, camera.zoom)
        r = self.radius_px * z
        r2 = r * r
        wp = self.world_pos

        for dx in (-map_width_pixels, 0, map_width_pixels):
            for dy in (-map_height_pixels, 0, map_height_pixels):
                p = camera.world_to_screen(wp + (dx, dy), include_shake=False)
                if (p.x - mx) ** 2 + (p.y - my) ** 2 <= r2:
                    return True
        return False

    # ---------- internal ----------
    def _sync_tile_from_world(self, map_w_tiles: int, map_h_tiles: int) -> None:
        self.tile_pos.update(world_center_to_tile(self.world_pos, map_w_tiles, map_h_tiles))
