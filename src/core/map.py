# c:/game/worldom/map.py
"""
Map: world generation, rendering, and pathfinding (toroidal grid).

Additions:
- Deterministic RNG per-map
- Faster flood-fills (deque)
- Diagonal-aware A* with octile heuristic
- Terrain move-costs, jitter, corner-cutting guard, iteration cap (PathOptions)
- Weighted, admissible heuristic w.r.t. min terrain cost
- Proper diagonal vs orthogonal step costs (√2 vs 1), optional custom weights
- Path simplification (collinearity) with toroidal awareness
- Optional pathfinding debug capture (closed/open/costs/came_from), view via overlay
- Nearest-walkable helper
- LOS (line-of-sight) helper (toroidal, Bresenham-style)
- World/tile conversion helpers and optional hover by world-pos
- Robust LOD drawing; fixed camera zoom property; smoothscale option
- Export helpers (to Surface / PNG)
- Noise backend adapter (OpenSimplex → python-noise fallback) via noise_adapter.py
"""
from __future__ import annotations

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple, TYPE_CHECKING

import pygame
import src.utils.settings as settings

# Local helper modules (new)
from .noise_adapter import Noise4
from .path_debug import PathDebug

if TYPE_CHECKING:
    from src.core.camera import Camera  # camera.apply, zoom_state.current expected

# -----------------------------------------------------------------------------
# Data containers
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class VisibleArea:
    """Visible area of the map in tile coordinates (half-open ranges)."""
    start_row: int
    end_row: int
    start_col: int
    end_col: int


@dataclass(frozen=True)
class PathOptions:
    """A* configuration (sane defaults remain backwards-compatible)."""
    allow_diagonals: bool = True
    avoid_corner_cut: bool = True      # disallow squeezing through blocked corners (requires both adjacents walkable)
    jitter: float = 0.3                # [0..0.5] small random per-step cost for variety
    costs: Optional[Mapping[str, float]] = None  # terrain move cost (>= 1)
    max_iterations: Optional[int] = None         # safety cap
    heuristic_weight: float = 1.0      # Weighted A*; keep 1.0 for A*
    orth_cost: float = 1.0             # orthogonal step cost base
    diag_cost: float = math.sqrt(2.0)  # diagonal step cost base
    simplify_path: bool = True         # run collinearity simplifier
    capture_debug: bool = False        # capture debug info (see PathDebug)


class AStarState:
    """Helper state for A* pathfinding."""
    # pylint: disable=too-few-public-methods
    def __init__(self, start_node: Tuple[int, int]):
        self.priority_queue: List[Tuple[float, Tuple[int, int]]] = [(0.0, start_node)]
        self.came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start_node: None}
        self.g_cost: Dict[Tuple[int, int], float] = {start_node: 0.0}
        self.closed: set[Tuple[int, int]] = set()
        self.open: set[Tuple[int, int]] = {start_node}

# -----------------------------------------------------------------------------
# Map Generation Constants (earth-like procedural flavor)
# -----------------------------------------------------------------------------

ELEVATION_SCALE = 1.5
ELEVATION_OCTAVES = 4
ELEVATION_PERSISTENCE = 0.5
ELEVATION_LACUNARITY = 2.0

MOUNTAIN_SCALE = 2.5
MOUNTAIN_OCTAVES = 4
MOUNTAIN_PERSISTENCE = 0.6
MOUNTAIN_LACUNARITY = 2.0

LAKE_SCALE = 3.0
LAKE_OCTAVES = 3
LAKE_PERSISTENCE = 0.5
LAKE_LACUNARITY = 2.0

OCEAN_THRESHOLD = 0.0     # values below -> ocean
COASTAL_THRESHOLD = 0.1   # land below cannot be lake
ROCK_THRESHOLD = 0.2      # land above -> rock
LAKE_THRESHOLD = -0.3     # remaining land below -> lake

LAKE_SIZE_LIMIT = 40      # lakes larger than this are filled to grass

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def _wrap_idx(i: int, size: int) -> int:
    return i % size

def _toroidal_delta(a: int, b: int, size: int) -> int:
    """Shortest *unsigned* delta (for heuristic)."""
    d = abs(a - b)
    return min(d, size - d)

def _toroidal_step_delta(a: int, b: int, size: int) -> int:
    """Step delta in {-1,0,1} across a toroidal axis (direction only)."""
    d = b - a
    if d > 1:
        d -= size
    elif d < -1:
        d += size
    return max(-1, min(1, d))

def _toroidal_dir_and_dist(a: int, b: int, size: int) -> Tuple[int, int]:
    """
    Return (step_dir, distance) along the shortest toroidal path from a to b.
    step_dir in {-1,0,1}, distance >= 0 (integer).
    """
    raw = b - a
    ad = abs(raw)
    if ad <= size - ad:  # direct is shorter or equal
        return (0 if raw == 0 else (1 if raw > 0 else -1)), ad
    # wrap is shorter
    return (-1 if raw > 0 else (1 if raw < 0 else 0)), size - ad

def _octile(dx: int, dy: int) -> float:
    """Octile distance for diagonal grids with cost(orth)=1, cost(diag)=sqrt(2)."""
    dmin = min(dx, dy)
    dmax = max(dx, dy)
    return (dmax - dmin) + math.sqrt(2.0) * dmin

# -----------------------------------------------------------------------------
# Map
# -----------------------------------------------------------------------------

class Map:
    """
    Manages the game's tile-based map: generation, rendering, and pathfinding.
    """

    def __init__(self, width: int, height: int, seed: Optional[int] = None) -> None:
        self.width = int(width)
        self.height = int(height)
        self.tile_size = settings.TILE_SIZE
        self.terrain_types = settings.TERRAIN_TYPES

        self.seed = int(seed if seed is not None else random.randint(0, 1_000_000))
        self.rng = random.Random(self.seed)  # deterministic per-map RNG

        # Populated by generate() or load
        self.data: List[List[str]] = []
        self.lod_surface: Optional[pygame.Surface] = None

        # Optional path debug info (last search)
        self.last_path_debug: Optional[PathDebug] = None

    # ---- Noise helpers (via noise_adapter.Noise4) ---------------------------

    def _fractal_noise(
        self,
        gen: Noise4,
        x: float, y: float, z: float, w: float,
        *,
        octaves: int,
        persistence: float,
        lacunarity: float
    ) -> float:
        """Generates fractal noise (normalized to [-1, 1])."""
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0
        for _ in range(octaves):
            total += gen.noise4(x * frequency, y * frequency, z * frequency, w * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= lacunarity
        return total / max_value if max_value > 0 else 0.0

    def _get_elevation_noise(self, gen: Noise4, angle_x: float, angle_y: float) -> float:
        ex = math.cos(angle_x) * ELEVATION_SCALE
        ey = math.sin(angle_x) * ELEVATION_SCALE
        ez = math.cos(angle_y) * ELEVATION_SCALE
        ew = math.sin(angle_y) * ELEVATION_SCALE
        return self._fractal_noise(
            gen, ex, ey, ez, ew,
            octaves=ELEVATION_OCTAVES,
            persistence=ELEVATION_PERSISTENCE,
            lacunarity=ELEVATION_LACUNARITY
        )

    def _get_mountain_noise(self, gen: Noise4, angle_x: float, angle_y: float) -> float:
        mx = math.cos(angle_x) * MOUNTAIN_SCALE
        my = math.sin(angle_x) * MOUNTAIN_SCALE
        mz = math.cos(angle_y) * MOUNTAIN_SCALE
        mw = math.sin(angle_y) * MOUNTAIN_SCALE
        return self._fractal_noise(
            gen, mx, my, mz, mw,
            octaves=MOUNTAIN_OCTAVES,
            persistence=MOUNTAIN_PERSISTENCE,
            lacunarity=MOUNTAIN_LACUNARITY
        )

    def _get_lake_noise(self, gen: Noise4, angle_x: float, angle_y: float) -> float:
        lx = math.cos(angle_x) * LAKE_SCALE
        ly = math.sin(angle_x) * LAKE_SCALE
        lz = math.cos(angle_y) * LAKE_SCALE
        lw = math.sin(angle_y) * LAKE_SCALE
        return self._fractal_noise(
            gen, lx, ly, lz, lw,
            octaves=LAKE_OCTAVES,
            persistence=LAKE_PERSISTENCE,
            lacunarity=LAKE_LACUNARITY
        )

    # ---- Generation ---------------------------------------------------------

    def generate(self):
        """
        Generates terrain. Yields progress in [0..1].
        """
        # Seeded, reproducible generators (OpenSimplex or python-noise fallback)
        e_gen = Noise4(self.rng.randint(0, 10_000))
        m_gen = Noise4(self.rng.randint(0, 10_000))
        l_gen = Noise4(self.rng.randint(0, 10_000))

        self.data = [["" for _ in range(self.width)] for _ in range(self.height)]

        for y in range(self.height):
            angle_y = (y / self.height) * 2 * math.pi
            for x in range(self.width):
                angle_x = (x / self.width) * 2 * math.pi

                elevation = self._get_elevation_noise(e_gen, angle_x, angle_y)

                if elevation < OCEAN_THRESHOLD:
                    terrain_type = "ocean"
                else:
                    mountain_value = self._get_mountain_noise(m_gen, angle_x, angle_y)
                    if mountain_value > ROCK_THRESHOLD:
                        terrain_type = "rock"
                    elif elevation < COASTAL_THRESHOLD:
                        terrain_type = "grass"
                    else:
                        lake_value = self._get_lake_noise(l_gen, angle_x, angle_y)
                        terrain_type = "lake" if lake_value < LAKE_THRESHOLD else "grass"

                self.data[y][x] = terrain_type

            # Yield progress every 4 rows (balance UI vs. speed)
            if (y + 1) % 4 == 0 or (y + 1) == self.height:
                yield 0.7 * ((y + 1) / self.height)  # first phase up to 70%

        # Post processing
        self._convert_inland_oceans_to_lakes(self.data)
        yield 0.85
        self._fill_large_lakes(self.data)
        yield 1.0
        self._create_lod_surface()

    def reseed_and_regenerate(self, seed: Optional[int] = None):
        """Convenience: reseed RNG and regenerate."""
        self.seed = int(seed if seed is not None else random.randint(0, 1_000_000))
        self.rng = random.Random(self.seed)
        yield from self.generate()

    def _create_lod_surface(self) -> None:
        """Creates a pre-rendered surface of the entire map for high-performance drawing when zoomed out."""
        if self.width <= 0 or self.height <= 0:
            self.lod_surface = None
            return

        map_width_pixels = self.width * self.tile_size
        map_height_pixels = self.height * self.tile_size
        s = pygame.Surface((map_width_pixels, map_height_pixels))
        get_color = settings.TERRAIN_COLORS.get
        tw = self.tile_size
        # Tight loop: avoid repeated attribute lookups where possible
        for y, row in enumerate(self.data):
            sy = y * tw
            for x, terrain_key in enumerate(row):
                pygame.draw.rect(s, get_color(terrain_key, (0, 0, 0)),
                                 (x * tw, sy, tw, tw))
        self.lod_surface = s

    # ---- Post processing (flood-fills) -------------------------------------

    def _flood_fill_collect(
        self,
        world: List[List[str]],
        start_x: int,
        start_y: int,
        target: str
    ) -> List[Tuple[int, int]]:
        """Collects all connected tiles of type 'target' using a fast deque BFS (toroidal)."""
        if world[start_y][start_x] != target:
            return []

        w, h = self.width, self.height
        visited = [[False] * w for _ in range(h)]
        out: List[Tuple[int, int]] = []

        dq: deque[Tuple[int, int]] = deque()
        dq.append((start_x, start_y))
        visited[start_y][start_x] = True

        while dq:
            cx, cy = dq.popleft()
            out.append((cx, cy))
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                nx = _wrap_idx(nx, w)
                ny = _wrap_idx(ny, h)
                if not visited[ny][nx] and world[ny][nx] == target:
                    visited[ny][nx] = True
                    dq.append((nx, ny))
        return out

    def _fill_large_lakes(self, world: List[List[str]]) -> None:
        """Convert very large lakes to grass to reduce inland seas."""
        w, h = self.width, self.height
        visited = [[False] * w for _ in range(h)]

        for y in range(h):
            for x in range(w):
                if visited[y][x] or world[y][x] != "lake":
                    continue

                # BFS collect
                body: List[Tuple[int, int]] = []
                dq: deque[Tuple[int, int]] = deque([(x, y)])
                visited[y][x] = True

                while dq:
                    cx, cy = dq.popleft()
                    body.append((cx, cy))
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        nx = _wrap_idx(nx, w)
                        ny = _wrap_idx(ny, h)
                        if not visited[ny][nx] and world[ny][nx] == "lake":
                            visited[ny][nx] = True
                            dq.append((nx, ny))

                if len(body) > LAKE_SIZE_LIMIT:
                    for bx, by in body:
                        world[by][bx] = "grass"

    def _convert_inland_oceans_to_lakes(self, world: List[List[str]]) -> None:
        """Finds all disconnected bodies of 'ocean' (toroidal), converts all but the largest to 'lake'."""
        w, h = self.width, self.height
        visited = [[False] * w for _ in range(h)]
        bodies: List[List[Tuple[int, int]]] = []

        for y in range(h):
            for x in range(w):
                if visited[y][x] or world[y][x] != "ocean":
                    continue

                body: List[Tuple[int, int]] = []
                dq: deque[Tuple[int, int]] = deque([(x, y)])
                visited[y][x] = True

                while dq:
                    cx, cy = dq.popleft()
                    body.append((cx, cy))
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        nx = _wrap_idx(nx, w)
                        ny = _wrap_idx(ny, h)
                        if not visited[ny][nx] and world[ny][nx] == "ocean":
                            visited[ny][nx] = True
                            dq.append((nx, ny))
                bodies.append(body)

        if len(bodies) <= 1:
            return

        bodies.sort(key=len, reverse=True)
        for body in bodies[1:]:
            for x, y in body:
                world[y][x] = "lake"

    # ---- Rendering ----------------------------------------------------------

    def draw(
        self,
        surface: pygame.Surface,
        camera: Camera,
        hovered_tile: Optional[Tuple[int, int]] = None,
        hovered_world_pos: Optional[pygame.math.Vector2] = None
    ) -> None:
        """Renders the map, drawing wrapped instances for toroidal continuity."""
        # If only world pos is provided, derive the wrapped tile under cursor
        if hovered_tile is None and hovered_world_pos is not None:
            hovered_tile = self.world_to_tile(hovered_world_pos)

        map_w_px = self.width * self.tile_size
        map_h_px = self.height * self.tile_size
        if map_w_px <= 0 or map_h_px <= 0:
            return

        # Determine which toroidal instances are needed
        visible_world_rect = camera.get_visible_world_rect()
        start_ix = math.floor(visible_world_rect.left / map_w_px)
        end_ix   = math.floor(visible_world_rect.right / map_w_px)
        start_iy = math.floor(visible_world_rect.top / map_h_px)
        end_iy   = math.floor(visible_world_rect.bottom / map_h_px)

        # Read zoom robustly (supports both Camera.zoom or Camera.zoom_state.current)
        zoom = getattr(camera, "zoom", None)
        if zoom is None:
            zoom = camera.zoom_state.current if hasattr(camera, "zoom_state") else 1.0

        # LOD (zoomed out) — draw only the visible sub-rect of each toroidal instance (big win)
        if self.lod_surface and zoom < settings.MAP_LOD_ZOOM_THRESHOLD:
            for iy in range(start_iy, end_iy + 1):
                for ix in range(start_ix, end_ix + 1):
                    dx, dy = ix * map_w_px, iy * map_h_px
                    instance_world = pygame.Rect(dx, dy, map_w_px, map_h_px)

                    # Clip the instance to the current viewport to avoid scaling the full map
                    src_world = instance_world.clip(visible_world_rect)
                    if src_world.width <= 0 or src_world.height <= 0:
                        continue

                    # Local (in the LOD surface) source area for this instance
                    src_local = pygame.Rect(
                        src_world.x - dx, src_world.y - dy,
                        src_world.width, src_world.height
                    )

                    dest_screen = camera.apply(src_world)  # transform world → screen
                    if dest_screen.width <= 0 or dest_screen.height <= 0:
                        continue

                    # Scale the clipped region only (saves a ton of work)
                    subsurf = self.lod_surface.subsurface(src_local)
                    src_area = src_local.width * src_local.height
                    dst_area = dest_screen.width * dest_screen.height
                    if dst_area < src_area:
                        lod_scaled = pygame.transform.smoothscale(subsurf, dest_screen.size)
                    else:
                        lod_scaled = pygame.transform.scale(subsurf, dest_screen.size)
                    surface.blit(lod_scaled, dest_screen)

            if hovered_tile:
                # Draw hover highlight on top of all instances
                for iy in range(start_iy, end_iy + 1):
                    for ix in range(start_ix, end_ix + 1):
                        dx, dy = ix * map_w_px, iy * map_h_px
                        twx = hovered_tile[0] * self.tile_size + dx
                        twy = hovered_tile[1] * self.tile_size + dy
                        world_rect = pygame.Rect(twx, twy, self.tile_size, self.tile_size)
                        screen_rect = camera.apply(world_rect)
                        pygame.draw.rect(surface, settings.HIGHLIGHT_COLOR, screen_rect, 2)
            return

        # High-detail greedy meshing
        for iy in range(start_iy, end_iy + 1):
            for ix in range(start_ix, end_ix + 1):
                dx, dy = ix * map_w_px, iy * map_h_px
                instance_rect = pygame.Rect(dx, dy, map_w_px, map_h_px)
                if camera.is_world_rect_visible(instance_rect, margin=self.tile_size):
                    offset = pygame.math.Vector2(dx, dy)
                    self._draw_single_map_instance(surface, camera, hovered_tile, offset)

    def _calculate_visible_area(
        self, camera: Camera, offset: pygame.math.Vector2
    ) -> VisibleArea:
        # Use the camera's current window size (not static settings) for correctness on resize
        top_left_world = camera.screen_to_world((0, 0)) - offset
        bottom_right_world = camera.screen_to_world((camera.width, camera.height)) - offset

        start_col = math.floor(top_left_world.x / self.tile_size)
        end_col = math.ceil(bottom_right_world.x / self.tile_size)
        start_row = math.floor(top_left_world.y / self.tile_size)
        end_row = math.ceil(bottom_right_world.y / self.tile_size)
        return VisibleArea(start_row, end_row, start_col, end_col)

    def _draw_single_map_instance(
        self,
        surface: pygame.Surface,
        camera: Camera,
        hovered_tile: Optional[Tuple[int, int]],
        offset: pygame.math.Vector2
    ) -> None:
        area = self._calculate_visible_area(camera, offset)
        self._draw_terrain(surface, camera, area=area, offset=offset)

        # Grid (zoom threshold)
        scaled_tile = self.tile_size * (camera.zoom_state.current if hasattr(camera, "zoom_state") else getattr(camera, "zoom", 1.0))
        if scaled_tile >= settings.MIN_TILE_PIXELS_FOR_GRID:
            self._draw_grid_lines(surface, camera, area, offset)

        # Hover highlight
        if hovered_tile:
            self._draw_hover_highlight(surface, camera, area, offset, hovered_tile)

    def _draw_terrain(
        self,
        surface: pygame.Surface,
        camera: Camera,
        *,
        area: VisibleArea,
        offset: pygame.math.Vector2
    ) -> None:
        """Greedy meshing renderer for large solid rectangles."""
        rows = area.end_row - area.start_row
        cols = area.end_col - area.start_col
        if rows <= 0 or cols <= 0:
            return

        visited = [[False for _ in range(cols)] for _ in range(rows)]
        get_color = settings.TERRAIN_COLORS.get
        ts = self.tile_size
        data = self.data  # local for speed

        for y in range(area.start_row, area.end_row):
            map_y = _wrap_idx(y, self.height)
            vy = y - area.start_row
            rowv_base = visited[vy]
            for x in range(area.start_col, area.end_col):
                vx = x - area.start_col
                if rowv_base[vx]:
                    continue

                map_x = _wrap_idx(x, self.width)
                terrain = data[map_y][map_x]
                color = get_color(terrain, (0, 0, 0))

                # Expand width
                width = 1
                while x + width < area.end_col:
                    nx = _wrap_idx(x + width, self.width)
                    if data[map_y][nx] != terrain or visited[vy][vx + width]:
                        break
                    width += 1

                # Expand height
                height = 1
                while y + height < area.end_row:
                    next_my = _wrap_idx(y + height, self.height)
                    can_expand = True
                    vrow_next = visited[vy + height]
                    for i in range(width):
                        cx = x + i
                        if data[next_my][_wrap_idx(cx, self.width)] != terrain or vrow_next[vx + i]:
                            can_expand = False
                            break
                    if not can_expand:
                        break
                    height += 1

                # Mark visited
                for i in range(height):
                    vrow = visited[vy + i]
                    for j in range(width):
                        vrow[vx + j] = True

                # Draw rectangle
                world_x = x * ts + offset.x
                world_y = y * ts + offset.y
                world_rect = pygame.Rect(world_x, world_y, ts * width, ts * height)
                screen_rect = camera.apply(world_rect)
                pygame.draw.rect(surface, color, screen_rect)

    def _draw_hover_highlight(
        self,
        surface: pygame.Surface,
        camera: Camera,
        area: VisibleArea,
        offset: pygame.math.Vector2,
        hovered_tile: Tuple[int, int]
    ) -> None:
        hx, hy = hovered_tile
        ts = self.tile_size
        for y in range(area.start_row, area.end_row):
            for x in range(area.start_col, area.end_col):
                if (_wrap_idx(x, self.width), _wrap_idx(y, self.height)) == (hx, hy):
                    world_x = x * ts + offset.x
                    world_y = y * ts + offset.y
                    world_rect = pygame.Rect(world_x, world_y, ts, ts)
                    screen_rect = camera.apply(world_rect)
                    pygame.draw.rect(surface, settings.HIGHLIGHT_COLOR, screen_rect, 2)

    def _draw_vertical_grid_lines(
        self,
        surface: pygame.Surface,
        camera: Camera,
        area: VisibleArea,
        offset: pygame.math.Vector2
    ) -> None:
        surf_w, surf_h = surface.get_width(), surface.get_height()
        for col in range(area.start_col, area.end_col):
            world_x = col * self.tile_size + offset.x
            screen_x = round(camera.world_to_screen(pygame.math.Vector2(world_x, 0)).x)
            pygame.draw.line(surface, settings.GRID_LINE_COLOR, (screen_x, 0), (screen_x, surf_h), 1)

    def _draw_horizontal_grid_lines(
        self,
        surface: pygame.Surface,
        camera: Camera,
        area: VisibleArea,
        offset: pygame.math.Vector2
    ) -> None:
        surf_w, surf_h = surface.get_width(), surface.get_height()
        for row in range(area.start_row, area.end_row):
            world_y = row * self.tile_size + offset.y
            screen_y = round(camera.world_to_screen(pygame.math.Vector2(0, world_y)).y)
            pygame.draw.line(surface, settings.GRID_LINE_COLOR, (0, screen_y), (surf_w, screen_y), 1)

    def _draw_grid_lines(
        self,
        surface: pygame.Surface,
        camera: Camera,
        area: VisibleArea,
        offset: pygame.math.Vector2
    ) -> None:
        self._draw_vertical_grid_lines(surface, camera, area, offset)
        self._draw_horizontal_grid_lines(surface, camera, area, offset)

    # ---- Tile & world helpers ----------------------------------------------

    def tile_center_world(self, tile: Tuple[int, int]) -> pygame.math.Vector2:
        """World-space center for a tile (wrapped)."""
        x = _wrap_idx(tile[0], self.width) * self.tile_size + self.tile_size * 0.5
        y = _wrap_idx(tile[1], self.height) * self.tile_size + self.tile_size * 0.5
        return pygame.math.Vector2(x, y)

    def is_walkable(self, tile_pos: Tuple[int, int]) -> bool:
        """Tile walkability based on terrain."""
        x, y = tile_pos
        return self.data[_wrap_idx(y, self.height)][_wrap_idx(x, self.width)] in settings.WALKABLE_TERRAINS

    def get_tile(self, tile_pos: Tuple[int, int]) -> str:
        x, y = tile_pos
        return self.data[_wrap_idx(y, self.height)][_wrap_idx(x, self.width)]

    def world_to_tile(self, world_pos: pygame.math.Vector2) -> Tuple[int, int]:
        """World-space position -> wrapped tile coordinates."""
        tx = _wrap_idx(int(math.floor(world_pos.x / self.tile_size)), self.width)
        ty = _wrap_idx(int(math.floor(world_pos.y / self.tile_size)), self.height)
        return tx, ty

    # ---- Line of Sight (toroidal) ------------------------------------------

    def line_of_sight(self, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        """
        Bresenham-style LOS on a toroidal grid; returns True if all tiles along the
        shortest toroidal line are walkable.
        """
        ax, ay = _wrap_idx(a[0], self.width), _wrap_idx(a[1], self.height)
        bx, by = _wrap_idx(b[0], self.width), _wrap_idx(b[1], self.height)

        # Determine shortest-direction steps and distances per axis
        sx, dx = _toroidal_dir_and_dist(ax, bx, self.width)
        sy, dy = _toroidal_dir_and_dist(ay, by, self.height)

        x, y = ax, ay
        err = dx - dy
        while True:
            if not self.is_walkable((x, y)):
                return False
            if x == bx and y == by:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x = _wrap_idx(x + sx, self.width)
            if e2 < dx:
                err += dx
                y = _wrap_idx(y + sy, self.height)
        return True

    # ---- Pathfinding --------------------------------------------------------

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int], *, diagonals: bool, min_step_cost: float) -> float:
        """Toroidal heuristic: Manhattan (4-way) or Octile (8-way), scaled by min step cost to remain admissible."""
        dx = _toroidal_delta(a[0], b[0], self.width)
        dy = _toroidal_delta(a[1], b[1], self.height)
        if diagonals:
            return float(_octile(dx, dy)) * min_step_cost
        return float(dx + dy) * min_step_cost

    def _neighbors(
        self,
        node: Tuple[int, int],
        *,
        diagonals: bool,
        avoid_corner_cut: bool
    ) -> Iterable[Tuple[Tuple[int, int], bool]]:
        """Yields (neighbor_tile, is_diagonal)."""
        x, y = node
        w, h = self.width, self.height

        # Cardinals
        for nb in ((_wrap_idx(x + 1, w), y),
                   (_wrap_idx(x - 1, w), y),
                   (x, _wrap_idx(y + 1, h)),
                   (x, _wrap_idx(y - 1, h))):
            yield nb, False

        if not diagonals:
            return

        # Diagonals (+ corner-cut guard)
        diag = [
            ((_wrap_idx(x + 1, w), _wrap_idx(y + 1, h)), (x + 1, y), (x, y + 1)),
            ((_wrap_idx(x - 1, w), _wrap_idx(y + 1, h)), (x - 1, y), (x, y + 1)),
            ((_wrap_idx(x + 1, w), _wrap_idx(y - 1, h)), (x + 1, y), (x, y - 1)),
            ((_wrap_idx(x - 1, w), _wrap_idx(y - 1, h)), (x - 1, y), (x, y - 1)),
        ]
        for nb, bl_a, bl_b in diag:
            if avoid_corner_cut:
                # Require BOTH adjacent cardinals to be walkable to traverse the diagonal (true corner-cut prevention)
                if not (self.is_walkable((_wrap_idx(bl_a[0], w), _wrap_idx(bl_a[1], h))) and
                        self.is_walkable((_wrap_idx(bl_b[0], w), _wrap_idx(bl_b[1], h)))):
                    continue
            yield nb, True

    def _step_cost(
        self,
        to_node: Tuple[int, int],
        *,
        is_diag: bool,
        costs: Optional[Mapping[str, float]],
        jitter: float,
        orth_cost: float,
        diag_cost: float
    ) -> float:
        """Base step cost with terrain multiplier and small jitter; diag vs orth aware."""
        terrain = self.get_tile(to_node)
        base = diag_cost if is_diag else orth_cost
        if costs is not None:
            base *= float(costs.get(terrain, 1.0))
        if jitter > 0.0:
            base += self.rng.uniform(0.0, min(0.5, float(jitter)))
        return base

    @staticmethod
    def _simplify_path_toroidal(path: List[Tuple[int, int]], w: int, h: int) -> List[Tuple[int, int]]:
        """Drops collinear points; respects toroidal step deltas so wrap steps work."""
        if len(path) <= 2:
            return path
        out = [path[0]]
        prev = path[0]
        dxp = dyp = None
        for i in range(1, len(path)):
            cur = path[i]
            dx = _toroidal_step_delta(prev[0], cur[0], w)
            dy = _toroidal_step_delta(prev[1], cur[1], h)
            if dxp is None:
                dxp, dyp = dx, dy
                out.append(cur)
            else:
                if dx == dxp and dy == dyp:
                    # Still collinear; replace last with cur
                    out[-1] = cur
                else:
                    out.append(cur)
                    dxp, dyp = dx, dy
            prev = cur
        return out

    def _reconstruct_path(self, came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]],
                          current: Tuple[int, int]) -> List[Tuple[int, int]]:
        path: List[Tuple[int, int]] = [current]
        while True:
            prev = came_from.get(current)
            if prev is None:
                break
            path.append(prev)
            current = prev
        path.reverse()
        return path

    def find_path(
        self,
        start_tile: pygame.math.Vector2,
        end_tile: pygame.math.Vector2,
        options: Optional[PathOptions] = None
    ) -> Optional[List[Tuple[int, int]]]:
        """
        A* on a toroidal grid.

        - Diagonals supported (octile heuristic).
        - Optional terrain costs and small jitter.
        - Optional corner-cutting prevention and iteration cap.
        - Weighted heuristic (>=1 faster, =1 optimal).
        - Captures debug info if options.capture_debug is True (see self.last_path_debug).
        """
        opts = options or PathOptions()
        start_node = (int(start_tile.x), int(start_tile.y))
        end_node   = (int(end_tile.x),   int(end_tile.y))

        if not self.is_walkable(start_node) or not self.is_walkable(end_node):
            return None
        if start_node == end_node:
            return []

        # Heuristic scaling by min step cost to remain admissible with terrain costs
        min_terrain = 1.0
        if opts.costs:
            try:
                min_terrain = max(1e-6, min(float(v) for v in opts.costs.values()))
            except ValueError:
                min_terrain = 1.0
        min_step_cost = min_terrain * min(opts.orth_cost, opts.diag_cost)

        state = AStarState(start_node)
        self.last_path_debug = None  # clear previous

        iterations = 0
        while state.priority_queue:
            if opts.max_iterations is not None and iterations >= opts.max_iterations:
                return None
            iterations += 1

            _, current = heapq.heappop(state.priority_queue)
            if current in state.closed:
                continue
            state.closed.add(current)
            state.open.discard(current)

            if current == end_node:
                raw_path = self._reconstruct_path(state.came_from, current)
                path = self._simplify_path_toroidal(raw_path, self.width, self.height) if opts.simplify_path else raw_path
                if opts.capture_debug:
                    self.last_path_debug = PathDebug(
                        start=start_node, goal=end_node, path=path,
                        closed=set(state.closed), open=set(state.open),
                        g_cost=dict(state.g_cost), came_from=dict(state.came_from)
                    )
                return path

            for nxt, is_diag in self._neighbors(current, diagonals=opts.allow_diagonals, avoid_corner_cut=opts.avoid_corner_cut):
                if not self.is_walkable(nxt):
                    continue
                step = self._step_cost(nxt, is_diag=is_diag, costs=opts.costs, jitter=opts.jitter,
                                       orth_cost=opts.orth_cost, diag_cost=opts.diag_cost)
                tentative_g = state.g_cost[current] + step
                if nxt not in state.g_cost or tentative_g < state.g_cost[nxt]:
                    state.g_cost[nxt] = tentative_g
                    h = self._heuristic(nxt, end_node, diagonals=opts.allow_diagonals, min_step_cost=min_step_cost)
                    f_cost = tentative_g + opts.heuristic_weight * h
                    heapq.heappush(state.priority_queue, (f_cost, nxt))
                    state.came_from[nxt] = current
                    state.open.add(nxt)

        if opts.capture_debug:
            self.last_path_debug = PathDebug(
                start=start_node, goal=end_node, path=[],
                closed=set(state.closed), open=set(state.open),
                g_cost=dict(state.g_cost), came_from=dict(state.came_from)
            )
        return None  # no path

    # ---- Utilities for gameplay/analytics -----------------------------------

    def find_nearest_walkable(
        self,
        start: Tuple[int, int],
        max_radius: Optional[int] = None
    ) -> Optional[Tuple[int, int]]:
        """BFS search for the nearest walkable tile from 'start' (toroidal)."""
        sx, sy = _wrap_idx(start[0], self.width), _wrap_idx(start[1], self.height)
        if self.is_walkable((sx, sy)):
            return (sx, sy)

        dq: deque[Tuple[int, int]] = deque([(sx, sy)])
        seen = {(sx, sy)}
        radius = 0
        while dq:
            qlen = len(dq)
            for _ in range(qlen):
                x, y = dq.popleft()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    nx = _wrap_idx(nx, self.width)
                    ny = _wrap_idx(ny, self.height)
                    if (nx, ny) in seen:
                        continue
                    if self.is_walkable((nx, ny)):
                        return (nx, ny)
                    seen.add((nx, ny))
                    dq.append((nx, ny))
            radius += 1
            if max_radius is not None and radius > max_radius:
                break
        return None

    def get_terrain_percentages(self) -> Dict[str, float]:
        """Percentage share per terrain across the whole map."""
        if not self.data:
            return {}
        total = self.width * self.height
        counts: Dict[str, int] = {terrain: 0 for terrain in self.terrain_types}
        for row in self.data:
            for tile in row:
                if tile in counts:
                    counts[tile] += 1
        return {terrain: (count / total) * 100.0 for terrain, count in counts.items()}

    # ---- Export helpers ------------------------------------------------------

    def to_surface(self) -> pygame.Surface:
        """
        Returns a high-resolution surface for the entire map (same as LOD size).
        """
        if self.lod_surface is None:
            self._create_lod_surface()
        assert self.lod_surface is not None
        return self.lod_surface.copy()

    def save_png(self, path: str) -> None:
        """Save the pre-rendered map image to PNG."""
        if self.lod_surface is None:
            self._create_lod_surface()
        if self.lod_surface is not None:
            pygame.image.save(self.lod_surface, path)
