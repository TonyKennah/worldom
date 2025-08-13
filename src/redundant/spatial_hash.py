# c:/prj/WorldDom/src/spatial_hash.py
from __future__ import annotations
from typing import Dict, Set, Iterable, Tuple, List
import math
import pygame

Vec2 = pygame.math.Vector2
Cell = Tuple[int, int]

class SpatialHash:
    """
    A simple spatial hash for fast radius/rect queries over moving units.

    Store (id -> (pos, radius)), and maintain buckets keyed by integer grid cells.
    """
    def __init__(self, cell_size: int = 128) -> None:
        self.cell_size = max(8, int(cell_size))
        self._id_to_cells: Dict[int, Set[Cell]] = {}
        self._id_to_data: Dict[int, Tuple[Vec2, float]] = {}
        self._grid: Dict[Cell, Set[int]] = {}

    # ---- cell math ----
    def _cell_coords(self, x: float, y: float) -> Cell:
        c = self.cell_size
        return (int(math.floor(x / c)), int(math.floor(y / c)))

    def _cells_for_bounds(self, x0: float, y0: float, x1: float, y1: float) -> Iterable[Cell]:
        c = self.cell_size
        min_cx, min_cy = self._cell_coords(x0, y0)
        max_cx, max_cy = self._cell_coords(x1, y1)
        for cy in range(min_cy, max_cy + 1):
            for cx in range(min_cx, max_cx + 1):
                yield (cx, cy)

    # ---- mutators ----
    def add(self, obj_id: int, pos: Vec2, radius: float = 16.0) -> None:
        self._id_to_data[obj_id] = (Vec2(pos), float(radius))
        self._reindex(obj_id)

    def update(self, obj_id: int, pos: Vec2, radius: float | None = None) -> None:
        if obj_id not in self._id_to_data:
            self.add(obj_id, pos, radius or 16.0)
            return
        old_pos, old_rad = self._id_to_data[obj_id]
        new_rad = float(old_rad if radius is None else radius)
        # Only reindex if moved across a cell boundary or radius changed
        self._id_to_data[obj_id] = (Vec2(pos), new_rad)
        self._reindex(obj_id)

    def remove(self, obj_id: int) -> None:
        cells = self._id_to_cells.pop(obj_id, set())
        for cell in cells:
            bucket = self._grid.get(cell)
            if bucket:
                bucket.discard(obj_id)
                if not bucket:
                    self._grid.pop(cell, None)
        self._id_to_data.pop(obj_id, None)

    def clear(self) -> None:
        self._id_to_cells.clear()
        self._id_to_data.clear()
        self._grid.clear()

    # ---- queries ----
    def query_rect(self, rect: pygame.Rect) -> Iterable[int]:
        x0, y0 = rect.left, rect.top
        x1, y1 = rect.right, rect.bottom
        seen: Set[int] = set()
        for cell in self._cells_for_bounds(x0, y0, x1, y1):
            for obj_id in self._grid.get(cell, ()):
                if obj_id in seen:
                    continue
                pos, rad = self._id_to_data[obj_id]
                if rect.inflate(2 * rad, 2 * rad).collidepoint(pos.x, pos.y):
                    seen.add(obj_id)
                    yield obj_id

    def query_radius(self, center: Vec2, radius: float) -> Iterable[int]:
        r = float(radius)
        rect = pygame.Rect(int(center.x - r), int(center.y - r), int(2 * r), int(2 * r))
        rr = r * r
        for obj_id in self.query_rect(rect):
            pos, rad = self._id_to_data[obj_id]
            d2 = (pos.x - center.x) ** 2 + (pos.y - center.y) ** 2
            if d2 <= (r + rad) ** 2:
                yield obj_id

    # ---- internals ----
    def _reindex(self, obj_id: int) -> None:
        pos, rad = self._id_to_data[obj_id]
        bounds = (pos.x - rad, pos.y - rad, pos.x + rad, pos.y + rad)
        new_cells = set(self._cells_for_bounds(*bounds))
        old_cells = self._id_to_cells.get(obj_id, set())

        # cells to remove
        for cell in old_cells - new_cells:
            bucket = self._grid.get(cell)
            if bucket:
                bucket.discard(obj_id)
                if not bucket:
                    self._grid.pop(cell, None)

        # cells to add
        for cell in new_cells - old_cells:
            self._grid.setdefault(cell, set()).add(obj_id)

        self._id_to_cells[obj_id] = new_cells

    # Accessors
    def get(self, obj_id: int) -> Tuple[Vec2, float] | None:
        return self._id_to_data.get(obj_id)
