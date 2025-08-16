"""
Path utilities for Unit: queued waypoints + helpers.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Iterable, List, Tuple

import pygame

from src.core.toroidal import TILE_SIZE, tile_to_world_center, shortest_delta


class PathQueue:
    """
    Maintains a pixel-precise waypoint queue with a public tile mirror.
    Ensures consecutive duplicates are removed and exposes helpers used by Unit.
    """
    __slots__ = ("_px", "tiles")

    def __init__(self) -> None:
        self._px: Deque[pygame.Vector2] = deque()
        self.tiles: List[Tuple[int, int]] = []

    # --- building ---

    def clear(self) -> None:
        self._px.clear()
        self.tiles.clear()

    def set_path(self, tiles: Iterable[Tuple[int, int]], *, append: bool = False,
                 current_tile: Tuple[int, int] | None = None) -> None:
        cleaned: List[Tuple[int, int]] = []
        prev = None
        for t in tiles:
            if prev is None or t != prev:
                if not cleaned and current_tile is not None and t == current_tile and not append:
                    prev = t
                    continue
                cleaned.append(t)
                prev = t
        if not cleaned:
            return

        if not append:
            self.clear()

        self.tiles.extend(cleaned)
        for t in cleaned:
            self._px.append(tile_to_world_center(t))

    def append_waypoint(self, tile_xy: Tuple[int, int]) -> None:
        self.set_path([tile_xy], append=True)

    def insert_front(self, tile_xy: Tuple[int, int]) -> None:
        wp = tile_to_world_center(tile_xy)
        self.tiles.insert(0, tile_xy)
        self._px.appendleft(wp)

    # --- queries / iteration ---

    def has_waypoints(self) -> bool:
        return bool(self._px)

    def peek(self) -> pygame.Vector2 | None:
        return self._px[0].copy() if self._px else None

    def advance_if_arrived(self, world_pos: pygame.Vector2, epsilon_px: float,
                           map_w_px: int, map_h_px: int) -> Tuple[bool, pygame.Vector2 | None]:
        """
        Pop and return reached pixel waypoint if within epsilon,
        returning (True, world_pos_of_reached_wp). Otherwise (False, None).
        """
        if not self._px:
            return False, None
        dvec = shortest_delta(world_pos, self._px[0], map_w_px, map_h_px)
        if dvec.length_squared() <= (epsilon_px * epsilon_px):
            reached = self._px.popleft()
            if self.tiles:
                self.tiles.pop(0)
            return True, reached
        return False, None

    def predicted_distance_px(self, world_pos: pygame.Vector2, target_tile: Tuple[int, int],
                              map_w_px: int, map_h_px: int) -> float:
        pts: List[pygame.Vector2] = [world_pos.copy()]
        pts.extend(list(self._px))
        pts.append(tile_to_world_center(target_tile))

        dist = 0.0
        for i in range(len(pts) - 1):
            dist += shortest_delta(pts[i], pts[i + 1], map_w_px, map_h_px).length()
        return dist

    # convenience for Unit.draw debug
    def as_world_polyline(self, start_world: pygame.Vector2, map_w_px: int, map_h_px: int) -> List[pygame.Vector2]:
        pts: List[pygame.Vector2] = [start_world.copy()]
        cur = start_world
        for wp in self._px:
            cur = cur + shortest_delta(cur, wp, map_w_px, map_h_px)
            pts.append(cur)
        return pts
