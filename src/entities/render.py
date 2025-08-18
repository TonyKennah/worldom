"""
Render helpers for Unit (rings, healthbar, path debug).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, List, Tuple

import pygame
import src.utils.settings as settings

if TYPE_CHECKING:
    from src.core.camera import Camera  # noqa: F401
else:
    Camera = Any  # type: ignore[assignment,misc]

# Optional settings with fallbacks
try:
    from src.utils.settings import (
        UNIT_HOVER_COLOR,
        UNIT_HEALTHBAR_BG,
        UNIT_HEALTHBAR_FG,
        UNIT_SELECTION_RING_WIDTH,
    )
except Exception:  # pragma: no cover - dev fallback
    UNIT_HOVER_COLOR = (240, 220, 80)
    UNIT_HEALTHBAR_BG = (20, 20, 20)
    UNIT_HEALTHBAR_FG = (80, 220, 80)
    UNIT_SELECTION_RING_WIDTH = 2


def draw_unit(surface: pygame.Surface,
              camera: "Camera",
              pos_world: pygame.Vector2,
              *,
              radius_px: float,
              color: Tuple[int, int, int],
              inner_ratio: float,
              facing_angle: float,
              selected: bool,
              hovered: bool,
              flash: Tuple[Tuple[int, int, int], float] | None,
              health: Tuple[int, int] | None) -> None:
    """Draw one instance of a unit at world position."""
    screen_pos = camera.world_to_screen(pos_world)
    radius = int(max(1.0, radius_px * camera.zoom))

    # Off-screen cull
    if screen_pos.x + radius < 0 or screen_pos.x - radius > camera.width:
        return
    if screen_pos.y + radius < 0 or screen_pos.y - radius > camera.height:
        return

    # Selection / hover ring
    if selected or hovered:
        ring_w = UNIT_SELECTION_RING_WIDTH
        ring_color = settings.UNIT_SELECTED_COLOR if selected else UNIT_HOVER_COLOR
        pygame.draw.circle(surface, ring_color, screen_pos, int(radius * 1.15), int(max(1, ring_w)))

    # Body
    pygame.draw.circle(surface, color, screen_pos, radius)
    inner_radius = max(1, int(radius * inner_ratio))
    pygame.draw.circle(surface, (0, 0, 0), screen_pos, inner_radius, 1)

    # Heading notch
    nx = math.cos(facing_angle)
    ny = math.sin(facing_angle)
    tip = pygame.Vector2(screen_pos.x + nx * (radius * 0.8), screen_pos.y + ny * (radius * 0.8))
    pygame.draw.line(surface, (0, 0, 0), screen_pos, tip, 2)

    # Flash ring
    if flash:
        color_f, _time = flash
        pygame.draw.circle(surface, color_f, screen_pos, int(radius * 1.25), 2)

    # Health bar
    if health:
        hp, max_hp = health
        _draw_health_bar(surface, screen_pos, radius, hp, max_hp)


def _draw_health_bar(surface: pygame.Surface, screen_pos: pygame.Vector2, radius: int, hp: int, max_hp: int) -> None:
    if max_hp <= 0:
        return
    bar_w = max(24, int(radius * 1.6))
    bar_h = max(4, int(radius * 0.3))
    x = int(screen_pos.x - bar_w / 2)
    y = int(screen_pos.y - radius - bar_h - 4)
    pygame.draw.rect(surface, UNIT_HEALTHBAR_BG, pygame.Rect(x, y, bar_w, bar_h))
    pct = max(0.0, min(1.0, hp / float(max_hp)))
    pygame.draw.rect(surface, UNIT_HEALTHBAR_FG, pygame.Rect(x + 1, y + 1, int((bar_w - 2) * pct), bar_h - 2))


def draw_path_debug(surface: pygame.Surface, camera: "Camera", pts_world: List[pygame.Vector2]) -> None:
    """Polyline path + dots (toroidal-aware path already precomputed)."""
    if len(pts_world) <= 1:
        return
    pts_screen = [camera.world_to_screen(p, include_shake=False) for p in pts_world]
    pts_int = [(int(p.x), int(p.y)) for p in pts_screen]
    pygame.draw.lines(surface, (30, 220, 255), False, pts_int, 2)
    for p in pts_int[1:]:
        pygame.draw.circle(surface, (30, 220, 255), p, 3)
