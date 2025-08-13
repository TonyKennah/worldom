# c:/prj/WorldDom/src/spatial_hash.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Set, Iterable, Tuple, List, Deque, Optional, Iterator
import math
from collections import deque, defaultdict
import pygame

Vec2 = pygame.math.Vector2
Cell = Tuple[int, int]


@dataclass(slots=True)
class Entry:
    """Stored object record."""
    pos: Vec2
    radius: float
    layer: int = 1            # bitmask for filtering (default layer 1)
    payload: object | None = None  # arbitrary user data


class SpatialHash:
    """
    Spatial hash for fast neighborhood queries over moving circles (pos+radius).

    - Grid buckets keyed by integer cells of size `cell_size` pixels
    - O(1) average insert/update/remove; queries visit only overlapped cells
    - Optional toroidal "wrap" support if `world_size` is set (width,height)
    - Layer bitmask filtering for selective queries
    """

    def __init__(self, cell_size: int = 128, *, world_size: Tuple[int, int] | None = None) -> None:
        self.cell_size = max(8, int(cell_size))
        self.world_size = world_size  # (W,H) in pixels, enables wrap-aware queries

        self._id_to_cells: Dict[int, Set[Cell]] = {}
        self._id_to_data: Dict[int, Entry] = {}
        self._grid: Dict[Cell, Set[int]] = {}

        # lightweight stats (resettable)
        self.last_query_cells_visited: int = 0
        self.last_query_candidates: int = 0

    # ---------------------------------------------------------------------
    # Cell math
    # ---------------------------------------------------------------------
    def _cell_coords(self, x: float, y: float) -> Cell:
        c = self.cell_size
        return (int(math.floor(x / c)), int(math.floor(y / c)))

    def _cells_for_bounds(self, x0: float, y0: float, x1: float, y1: float) -> Iterator[Cell]:
        c = self.cell_size
        min_cx, min_cy = self._cell_coords(x0, y0)
        max_cx, max_cy = self._cell_coords(x1, y1)
        for cy in range(min_cy, max_cy + 1):
            for cx in range(min_cx, max_cx + 1):
                yield (cx, cy)

    def _wrap_offsets_for_rect(self, x0: float, y0: float, x1: float, y1: float) -> List[Tuple[int, int]]:
        """Return offsets to replicate a rect across wrap boundaries, if enabled."""
        if not self.world_size:
            return [(0, 0)]
        w, h = self.world_size
        xs: Set[int] = {0}
        ys: Set[int] = {0}
        if x0 < 0:
            xs.add(w)
        if x1 > w:
            xs.add(-w)
        if y0 < 0:
            ys.add(h)
        if y1 > h:
            ys.add(-h)
        return [(dx, dy) for dx in xs for dy in ys]

    # ---------------------------------------------------------------------
    # Mutators
    # ---------------------------------------------------------------------
    def add(self, obj_id: int, pos: Vec2, radius: float = 16.0, *, layer: int = 1, payload: object | None = None) -> None:
        """Insert or replace an object."""
        self._id_to_data[obj_id] = Entry(Vec2(pos), float(radius), int(layer), payload)
        self._reindex(obj_id)

    def bulk_add(self, items: Iterable[Tuple[int, Vec2, float, int | None, object | None]]) -> None:
        """
        Batch insert: iterable of (obj_id, pos, radius, layer, payload).
        `layer` may be None -> defaults to 1.
        """
        for obj_id, pos, radius, layer, payload in items:
            self._id_to_data[obj_id] = Entry(Vec2(pos), float(radius), 1 if layer is None else int(layer), payload)
        # one pass reindex
        for obj_id in [i[0] for i in items]:
            self._reindex(obj_id)

    def update(self, obj_id: int, pos: Vec2, radius: float | None = None, *, layer: int | None = None, payload: object | None = None) -> None:
        """Move and/or resize an object. Creates it if missing."""
        if obj_id not in self._id_to_data:
            self.add(obj_id, pos, radius or 16.0, layer=1 if layer is None else layer, payload=payload)
            return
        e = self._id_to_data[obj_id]
        new_rad = float(e.radius if radius is None else radius)
        new_layer = int(e.layer if layer is None else layer)
        new_payload = e.payload if payload is None else payload
        self._id_to_data[obj_id] = Entry(Vec2(pos), new_rad, new_layer, new_payload)
        self._reindex(obj_id)

    def move_by(self, obj_id: int, delta: Vec2) -> None:
        """Translate an object by delta and reindex."""
        if obj_id not in self._id_to_data:
            return
        e = self._id_to_data[obj_id]
        new_pos = e.pos + Vec2(delta)
        self._id_to_data[obj_id] = Entry(new_pos, e.radius, e.layer, e.payload)
        self._reindex(obj_id)

    def set_layer(self, obj_id: int, layer: int) -> None:
        if obj_id in self._id_to_data:
            e = self._id_to_data[obj_id]
            self._id_to_data[obj_id] = Entry(e.pos, e.radius, int(layer), e.payload)
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

    def rebuild(self, *, cell_size: int | None = None) -> None:
        """Rebuild buckets (optionally with a new cell size)."""
        if cell_size is not None:
            self.cell_size = max(8, int(cell_size))
        self._grid.clear()
        self._id_to_cells.clear()
        for obj_id in list(self._id_to_data.keys()):
            self._reindex(obj_id)

    # ---------------------------------------------------------------------
    # Queries
    # ---------------------------------------------------------------------
    def query_rect(self, rect: pygame.Rect, *, layer_mask: int = 0xFFFFFFFF) -> Iterable[int]:
        """
        IDs overlapping a rect (expanded by each object's radius).
        Wrap-aware if world_size is set.
        """
        x0, y0 = float(rect.left), float(rect.top)
        x1, y1 = float(rect.right), float(rect.bottom)
        seen: Set[int] = set()
        self.last_query_cells_visited = 0
        self.last_query_candidates = 0

        for dx, dy in self._wrap_offsets_for_rect(x0, y0, x1, y1):
            ox0, oy0, ox1, oy1 = x0 + dx, y0 + dy, x1 + dx, y1 + dy
            for cell in self._cells_for_bounds(ox0, oy0, ox1, oy1):
                self.last_query_cells_visited += 1
                for obj_id in self._grid.get(cell, ()):
                    if obj_id in seen:
                        continue
                    e = self._id_to_data[obj_id]
                    if not (e.layer & layer_mask):
                        continue
                    self.last_query_candidates += 1
                    # fast AABB vs point radius check without new Rect allocations
                    if (ox0 - e.radius) <= e.pos.x <= (ox1 + e.radius) and (oy0 - e.radius) <= e.pos.y <= (oy1 + e.radius):
                        seen.add(obj_id)
                        yield obj_id

    def query_radius(self, center: Vec2, radius: float, *, layer_mask: int = 0xFFFFFFFF) -> Iterable[int]:
        """IDs within a circle centered at `center` with radius `radius` (object radii included). Wrap-aware."""
        c = Vec2(center)
        r = float(radius)
        rect = pygame.Rect(int(c.x - r), int(c.y - r), int(2 * r), int(2 * r))
        rr = r * r
        W, H = (self.world_size or (None, None))

        for obj_id in self.query_rect(rect, layer_mask=layer_mask):
            e = self._id_to_data[obj_id]
            # shortest toroidal delta if world_size present
            dx = e.pos.x - c.x
            dy = e.pos.y - c.y
            if W is not None and H is not None:
                # wrap to [-W/2, +W/2] range for shortest distance
                dx = (dx + W * 0.5) % W - W * 0.5
                dy = (dy + H * 0.5) % H - H * 0.5
            d2 = dx * dx + dy * dy
            if d2 <= (r + e.radius) * (r + e.radius):
                yield obj_id

    def query_capsule(self, a: Vec2, b: Vec2, radius: float, *, layer_mask: int = 0xFFFFFFFF) -> Iterable[int]:
        """
        IDs overlapping a capsule defined by segment (a,b) with thickness `radius`.
        Wrap-aware for bounds & distance if world_size set.
        """
        ax, ay = a.x, a.y
        bx, by = b.x, b.y
        x0, y0 = min(ax, bx) - radius, min(ay, by) - radius
        x1, y1 = max(ax, bx) + radius, max(ay, by) + radius
        rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
        W, H = (self.world_size or (None, None))

        def seg_point_dist2(p: Vec2, sa: Vec2, sb: Vec2) -> float:
            vx, vy = sb.x - sa.x, sb.y - sa.y
            wx, wy = p.x - sa.x, p.y - sa.y
            vv = vx * vx + vy * vy
            if vv <= 1e-12:
                dx, dy = wx, wy
                return dx * dx + dy * dy
            t = max(0.0, min(1.0, (wx * vx + wy * vy) / vv))
            px, py = sa.x + t * vx, sa.y + t * vy
            dx, dy = p.x - px, p.y - py
            return dx * dx + dy * dy

        # For wrap: test against replicated segments if rect crosses edges
        offsets = self._wrap_offsets_for_rect(x0, y0, x1, y1)

        for obj_id in self.query_rect(rect, layer_mask=layer_mask):
            e = self._id_to_data[obj_id]
            ok = False
            if W is None or H is None or len(offsets) == 1:
                if seg_point_dist2(e.pos, Vec2(ax, ay), Vec2(bx, by)) <= (radius + e.radius) ** 2:
                    ok = True
            else:
                # test the minimal distance across wrapped segment reps
                min_d2 = float("inf")
                for dx, dy in offsets:
                    d2 = seg_point_dist2(e.pos, Vec2(ax + dx, ay + dy), Vec2(bx + dx, by + dy))
                    if d2 < min_d2:
                        min_d2 = d2
                if min_d2 <= (radius + e.radius) ** 2:
                    ok = True
            if ok:
                yield obj_id

    def nearest(self, center: Vec2, *, k: int = 1, max_radius: float = float("inf"), layer_mask: int = 0xFFFFFFFF) -> List[Tuple[int, float]]:
        """
        k‑nearest IDs to `center`. Returns [(id, distance_pixels), ...] sorted by distance.
        Expands search radius geometrically until enough are found or `max_radius` reached.
        """
        if k <= 0 or not self._id_to_data:
            return []
        found: Dict[int, float] = {}
        r = max(self.cell_size * 0.75, 1.0)
        limit = max_radius if math.isfinite(max_radius) else float("inf")
        while True:
            for obj_id in self.query_radius(center, r, layer_mask=layer_mask):
                if obj_id in found:
                    continue
                e = self._id_to_data[obj_id]
                dx, dy = e.pos.x - center.x, e.pos.y - center.y
                if self.world_size:
                    W, H = self.world_size
                    dx = (dx + W * 0.5) % W - W * 0.5
                    dy = (dy + H * 0.5) % H - H * 0.5
                found[obj_id] = math.hypot(dx, dy)
            if len(found) >= k or r >= limit:
                break
            r = min(limit, r * 2.0)
        out = sorted(found.items(), key=lambda kv: kv[1])
        return out[:k]

    # ---------------------------------------------------------------------
    # Internals
    # ---------------------------------------------------------------------
    def _reindex(self, obj_id: int) -> None:
        e = self._id_to_data[obj_id]
        x0, y0 = e.pos.x - e.radius, e.pos.y - e.radius
        x1, y1 = e.pos.x + e.radius, e.pos.y + e.radius
        new_cells = set(self._cells_for_bounds(x0, y0, x1, y1))
        old_cells = self._id_to_cells.get(obj_id, set())

        # remove
        for cell in old_cells - new_cells:
            bucket = self._grid.get(cell)
            if bucket:
                bucket.discard(obj_id)
                if not bucket:
                    self._grid.pop(cell, None)

        # add
        for cell in new_cells - old_cells:
            self._grid.setdefault(cell, set()).add(obj_id)

        self._id_to_cells[obj_id] = new_cells

    # ---------------------------------------------------------------------
    # Accessors / helpers
    # ---------------------------------------------------------------------
    def get(self, obj_id: int) -> Tuple[Vec2, float] | None:
        """Back‑compat: return (pos, radius) or None."""
        e = self._id_to_data.get(obj_id)
        return (Vec2(e.pos), float(e.radius)) if e else None

    def get_entry(self, obj_id: int) -> Entry | None:
        """Full entry (pos, radius, layer, payload)."""
        return self._id_to_data.get(obj_id)

    def count(self) -> int:
        return len(self._id_to_data)

    def num_buckets(self) -> int:
        return len(self._grid)

    def avg_bucket_load(self) -> float:
        if not self._grid:
            return 0.0
        return sum(len(s) for s in self._grid.values()) / float(len(self._grid))

    # ---------------------------------------------------------------------
    # Debug draw (optional)
    # ---------------------------------------------------------------------
    def debug_draw(
        self,
        surface: pygame.Surface,
        view_world_rect: pygame.Rect,
        *,
        color: Tuple[int, int, int] = (0, 255, 0),
        alpha: int = 60,
        show_counts: bool = False,
        to_screen: callable | None = None,  # function(world_vec2) -> screen (x,y)
    ) -> None:
        """
        Draw grid lines covering `view_world_rect`.
        If `to_screen` is provided, it's used to map world positions to screen coords.
        """
        if surface is None:
            return

        # default mapping if none provided
        def _default_to_screen(v: Vec2) -> Tuple[int, int]:
            return int(v.x), int(v.y)

        map_fn = to_screen or _default_to_screen

        c = self.cell_size
        left, top, right, bottom = view_world_rect.left, view_world_rect.top, view_world_rect.right, view_world_rect.bottom
        min_cx, min_cy = self._cell_coords(left, top)
        max_cx, max_cy = self._cell_coords(right, bottom)

        grid_color = (*color, max(0, min(255, alpha)))
        line_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        # vertical lines
        for cx in range(min_cx, max_cx + 1):
            x = cx * c
            a = map_fn(Vec2(x, top))
            b = map_fn(Vec2(x, bottom))
            pygame.draw.line(line_surf, grid_color, a, b, 1)

        # horizontal lines
        for cy in range(min_cy, max_cy + 1):
            y = cy * c
            a = map_fn(Vec2(left, y))
            b = map_fn(Vec2(right, y))
            pygame.draw.line(line_surf, grid_color, a, b, 1)

        surface.blit(line_surf, (0, 0))

        # optional occupancy counts
        if show_counts:
            if not pygame.font.get_init():
                try:
                    pygame.font.init()
                except Exception:
                    return
            font = pygame.font.Font(None, 14)
            for cy in range(min_cy, max_cy + 1):
                for cx in range(min_cx, max_cx + 1):
                    cell = (cx, cy)
                    count = len(self._grid.get(cell, ()))
                    if count == 0:
                        continue
                    # draw number at cell center
                    cx_px = (cx + 0.5) * c
                    cy_px = (cy + 0.5) * c
                    sx, sy = map_fn(Vec2(cx_px, cy_px))
                    img = font.render(str(count), True, color)
                    rect = img.get_rect(center=(sx, sy))
                    surface.blit(img, rect)
