# c:/game/worldom/map.py
"""
Map: world generation, rendering, and pathfinding (toroidal grid).

Additions:
- Deterministic RNG per-map
- Faster flood-fills (deque)
- Diagonal-aware A* with octile heuristic
- Terrain move-costs, jitter, corner-cutting guard, iteration cap (PathOptions)
- Nearest-walkable helper
- World/tile conversion helpers and optional hover by world-pos
- Small rendering and meshing tweaks
"""
from __future__ import annotations

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Generator, Iterable, List, Mapping, Optional, Tuple

import pygame
from opensimplex import OpenSimplex
import src.utils.settings as settings

if TYPE_CHECKING:
    from src.core.camera import Camera


# --- Data containers ---------------------------------------------------------

@dataclass(frozen=True)
class VisibleArea:
    """Visible area of the map in tile coordinates (half-open ranges)."""
    start_row: int
    end_row: int
    start_col: int
    end_col: int


@dataclass(frozen=True)
class PathOptions:
    """A* configuration."""
    allow_diagonals: bool = False
    avoid_corner_cut: bool = True  # if diagonals, disallow squeezing through corners
    jitter: float = 0.0            # [0..0.5] small random per-step cost for path variety
    costs: Optional[Mapping[str, float]] = None  # terrain move cost (>=1)
    max_iterations: Optional[int] = None         # safety cap for very large maps


class AStarState:
    """Helper state for A* pathfinding."""
    # pylint: disable=too-few-public-methods
    def __init__(self, start_node: Tuple[int, int]):
        self.priority_queue: List[Tuple[float, Tuple[int, int]]] = [(0.0, start_node)]
        self.came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start_node: None}
        self.g_cost: Dict[Tuple[int, int], float] = {start_node: 0.0}
        self.closed: set[Tuple[int, int]] = set()


# --- Map Generation Constants -----------------------------------------------

# Earth-like procedural generation
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


# --- Utilities ---------------------------------------------------------------

def _wrap_idx(i: int, size: int) -> int:
    return i % size


def _toroidal_delta(a: int, b: int, size: int) -> int:
    """Shortest signed delta (toroidal)."""
    d = abs(a - b)
    return min(d, size - d)


def _octile(dx: int, dy: int) -> float:
    """Octile distance for diagonal grids with cost(orth)=1, cost(diag)=sqrt(2)."""
    dmin = min(dx, dy)
    dmax = max(dx, dy)
    return (dmax - dmin) + math.sqrt(2.0) * dmin


# --- Map ---------------------------------------------------------------------

class Map:
    """
    Manages the game's tile-based map: generation, rendering, and pathfinding.
    """

    def __init__(self, width: int, height: int, seed: Optional[int] = None) -> None:
        self.width = width
        self.height = height
        self.tile_size = settings.TILE_SIZE
        self.terrain_types = settings.TERRAIN_TYPES

        self.seed = seed if seed is not None else random.randint(0, 1_000_000)
        self.rng = random.Random(self.seed)  # deterministic per-map RNG

        # populated by generate()
        self.data: List[List[str]] = []
        self.data: List[List[str]] = [] # Will be populated by the generate() method
        self.lod_surface: Optional[pygame.Surface] = None


    def _fractal_noise(  # pylint: disable=too-many-arguments
        self,
        gen: OpenSimplex,
        x: float, y: float, z: float, w: float,
        *,
        octaves: int,
        persistence: float,
        lacunarity: float
    ) -> float:
        """Generates fractal noise using an OpenSimplex generator, normalized to [-1, 1]."""
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

    def _get_elevation_noise(self, gen: OpenSimplex, angle_x: float, angle_y: float) -> float:
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

    def _get_mountain_noise(self, gen: OpenSimplex, angle_x: float, angle_y: float) -> float:
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

    def _get_lake_noise(self, gen: OpenSimplex, angle_x: float, angle_y: float) -> float:
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

    # --- Generation ----------------------------------------------------------

    def generate(self) -> Generator[float, None, None]:
        """
        Generates terrain. Yields progress in [0..1].
        """
        # seeded, reproducible generators
        e_gen = OpenSimplex(seed=self.rng.randint(0, 10_000))
        m_gen = OpenSimplex(seed=self.rng.randint(0, 10_000))
        l_gen = OpenSimplex(seed=self.rng.randint(0, 10_000))

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

        # Post-processing phases
        self._convert_inland_oceans_to_lakes(self.data)
        yield 0.85
        self._fill_large_lakes(self.data)
        yield 1.0
        self._create_lod_surface()

    def _create_lod_surface(self) -> None:
        """Creates a pre-rendered surface of the entire map for high-performance drawing when zoomed out."""
        if self.width <= 0 or self.height <= 0:
            self.lod_surface = None
            return

        map_width_pixels = self.width * self.tile_size
        map_height_pixels = self.height * self.tile_size
        self.lod_surface = pygame.Surface((map_width_pixels, map_height_pixels))
        for y, row in enumerate(self.data):
            for x, terrain_key in enumerate(row):
                color = settings.TERRAIN_COLORS.get(terrain_key, (0, 0, 0))
                rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                pygame.draw.rect(self.lod_surface, color, rect)

    # --- Post processing (flood-fills) --------------------------------------

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
        """
        Finds all disconnected bodies of 'ocean' (toroidal), converts all but the largest to 'lake'.
        """
        w, h = self.width, self.height
        visited = [[False] * w for _ in range(h)]
        bodies: List[List[Tuple[int, int]]]= []

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

    # --- Rendering -----------------------------------------------------------

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

        map_width_pixels = self.width * self.tile_size
        map_height_pixels = self.height * self.tile_size

        if map_width_pixels <= 0 or map_height_pixels <= 0:
            return

        # --- Calculate required map instances to fill the screen ---
        visible_world_rect = camera.get_visible_world_rect()
        start_instance_x = math.floor(visible_world_rect.left / map_width_pixels)
        end_instance_x = math.floor(visible_world_rect.right / map_width_pixels)
        start_instance_y = math.floor(visible_world_rect.top / map_height_pixels)
        end_instance_y = math.floor(visible_world_rect.bottom / map_height_pixels)

        # --- Level of Detail (LOD) ---
        # If zoomed out far enough, draw the pre-rendered map image for performance.
        if self.lod_surface and camera.zoom < settings.MAP_LOD_ZOOM_THRESHOLD:
            for iy in range(start_instance_y, end_instance_y + 1):
                for ix in range(start_instance_x, end_instance_x + 1):
                    dx, dy = ix * map_width_pixels, iy * map_height_pixels
                    instance_rect = pygame.Rect(dx, dy, map_width_pixels, map_height_pixels)
                    screen_rect = camera.apply(instance_rect)
                    scaled_lod_surface = pygame.transform.scale(self.lod_surface, screen_rect.size)
                    surface.blit(scaled_lod_surface, screen_rect)

            # Draw hover highlight on top of all LOD instances
            if hovered_tile:
                for iy in range(start_instance_y, end_instance_y + 1):
                    for ix in range(start_instance_x, end_instance_x + 1):
                        dx, dy = ix * map_width_pixels, iy * map_height_pixels
                        # Calculate the world position of the hovered tile for this specific map instance
                        tile_world_x = hovered_tile[0] * self.tile_size + dx
                        tile_world_y = hovered_tile[1] * self.tile_size + dy
                        world_rect = pygame.Rect(tile_world_x, tile_world_y, self.tile_size, self.tile_size)
                        screen_rect = camera.apply(world_rect)
                        pygame.draw.rect(surface, settings.HIGHLIGHT_COLOR, screen_rect, 2)
            return # We're done drawing the map for this frame

        # --- High-Detail Drawing (Greedy Meshing) ---
        for iy in range(start_instance_y, end_instance_y + 1):
            for ix in range(start_instance_x, end_instance_x + 1):
                dx, dy = ix * map_width_pixels, iy * map_height_pixels
                instance_rect = pygame.Rect(dx, dy, map_width_pixels, map_height_pixels)
                if camera.is_world_rect_visible(instance_rect, margin=self.tile_size):
                    offset = pygame.math.Vector2(dx, dy)
                    self._draw_single_map_instance(surface, camera, hovered_tile, offset)

    def _draw_single_map_instance(
        self,
        surface: pygame.Surface,
        camera: Camera,
        hovered_tile: Optional[Tuple[int, int]],
        offset: pygame.math.Vector2  # pylint: disable=c-extension-no-member
    ) -> None:
        visible_area = self._calculate_visible_area(camera, offset)

        self._draw_terrain(surface, camera, area=visible_area, offset=offset)

        # Grid if zoomed in enough
        scaled_tile = self.tile_size * camera.zoom_state.current
        if scaled_tile >= settings.MIN_TILE_PIXELS_FOR_GRID:
            self._draw_grid_lines(surface, camera, visible_area, offset)

        # Hover highlight last
        if hovered_tile:
            self._draw_hover_highlight(surface, camera, visible_area, offset, hovered_tile)

    def _calculate_visible_area(
        self, camera: Camera, offset: pygame.math.Vector2  # pylint: disable=c-extension-no-member
    ) -> VisibleArea:
        top_left_world = camera.screen_to_world((0, 0)) - offset
        bottom_right_world = camera.screen_to_world((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)) - offset

        start_col = math.floor(top_left_world.x / self.tile_size)
        end_col = math.ceil(bottom_right_world.x / self.tile_size)
        start_row = math.floor(top_left_world.y / self.tile_size)
        end_row = math.ceil(bottom_right_world.y / self.tile_size)
        return VisibleArea(start_row, end_row, start_col, end_col)

    def _draw_terrain(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        surface: pygame.Surface,
        camera: Camera,
        *,
        area: VisibleArea,
        offset: pygame.math.Vector2  # pylint: disable=c-extension-no-member
    ) -> None:
        """Greedy meshing renderer for large solid rectangles."""
        rows = area.end_row - area.start_row
        cols = area.end_col - area.start_col
        if rows <= 0 or cols <= 0:
            return

        visited = [[False for _ in range(cols)] for _ in range(rows)]

        for y in range(area.start_row, area.end_row):
            map_y = _wrap_idx(y, self.height)
            for x in range(area.start_col, area.end_col):
                vy, vx = y - area.start_row, x - area.start_col
                if visited[vy][vx]:
                    continue

                map_x = _wrap_idx(x, self.width)
                terrain = self.data[map_y][map_x]
                color = settings.TERRAIN_COLORS[terrain]

                # Expand width
                width = 1
                while x + width < area.end_col:
                    nx = _wrap_idx(x + width, self.width)
                    if self.data[map_y][nx] != terrain or visited[vy][vx + width]:
                        break
                    width += 1

                # Expand height
                height = 1
                while y + height < area.end_row:
                    can_expand = True
                    next_my = _wrap_idx(y + height, self.height)
                    for i in range(width):
                        cx = x + i
                        if self.data[next_my][_wrap_idx(cx, self.width)] != terrain or visited[vy + height][vx + i]:
                            can_expand = False
                            break
                    if not can_expand:
                        break
                    height += 1

                # Mark visited
                for i in range(height):
                    rowv = visited[vy + i]
                    for j in range(width):
                        rowv[vx + j] = True

                # Draw rectangle
                world_x = x * self.tile_size + offset.x
                world_y = y * self.tile_size + offset.y
                world_rect = pygame.Rect(world_x, world_y, self.tile_size * width, self.tile_size * height)
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
        for y in range(area.start_row, area.end_row):
            for x in range(area.start_col, area.end_col):
                if (_wrap_idx(x, self.width), _wrap_idx(y, self.height)) == (hx, hy):
                    world_x = x * self.tile_size + offset.x
                    world_y = y * self.tile_size + offset.y
                    world_rect = pygame.Rect(world_x, world_y, self.tile_size, self.tile_size)
                    screen_rect = camera.apply(world_rect)
                    pygame.draw.rect(surface, settings.HIGHLIGHT_COLOR, screen_rect, 2)

    def _draw_vertical_grid_lines(
        self,
        surface: pygame.Surface,
        camera: Camera,
        area: VisibleArea,
        offset: pygame.math.Vector2  # pylint: disable=c-extension-no-member
    ) -> None:
        for col in range(area.start_col, area.end_col):
            world_x = col * self.tile_size + offset.x
            screen_x = round(camera.world_to_screen(pygame.math.Vector2(world_x, 0)).x)
            pygame.draw.line(surface, settings.GRID_LINE_COLOR, (screen_x, 0), (screen_x, settings.SCREEN_HEIGHT), 1)

    def _draw_horizontal_grid_lines(
        self,
        surface: pygame.Surface,
        camera: Camera,
        area: VisibleArea,
        offset: pygame.math.Vector2  # pylint: disable=c-extension-no-member
    ) -> None:
        for row in range(area.start_row, area.end_row):
            world_y = row * self.tile_size + offset.y
            screen_y = round(camera.world_to_screen(pygame.math.Vector2(0, world_y)).y)
            pygame.draw.line(surface, settings.GRID_LINE_COLOR, (0, screen_y), (settings.SCREEN_WIDTH, screen_y), 1)

    def _draw_grid_lines(
        self,
        surface: pygame.Surface,
        camera: Camera,
        area: VisibleArea,
        offset: pygame.math.Vector2  # pylint: disable=c-extension-no-member
    ) -> None:
        self._draw_vertical_grid_lines(surface, camera, area, offset)
        self._draw_horizontal_grid_lines(surface, camera, area, offset)

    # --- Tile helpers --------------------------------------------------------

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

    # --- Pathfinding ---------------------------------------------------------

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int], *, diagonals: bool) -> float:
        """Toroidal heuristic: Manhattan (4-way) or Octile (8-way)."""
        dx = _toroidal_delta(a[0], b[0], self.width)
        dy = _toroidal_delta(a[1], b[1], self.height)
        if diagonals:
            return float(_octile(dx, dy))
        return float(dx + dy)

    def _neighbors(
        self,
        node: Tuple[int, int],
        *,
        diagonals: bool,
        avoid_corner_cut: bool
    ) -> Iterable[Tuple[int, int]]:
        x, y = node
        w, h = self.width, self.height

        # Cardinal moves
        n4 = [
            ((_wrap_idx(x + 1, w), y), (1, 0)),
            ((_wrap_idx(x - 1, w), y), (-1, 0)),
            ((x, _wrap_idx(y + 1, h)), (0, 1)),
            ((x, _wrap_idx(y - 1, h)), (0, -1)),
        ]
        for nb, _ in n4:
            yield nb

        if not diagonals:
            return

        # Diagonals
        diag = [
            ((_wrap_idx(x + 1, w), _wrap_idx(y + 1, h)), (1, 1), ( (x+1, y), (x, y+1) )),
            ((_wrap_idx(x - 1, w), _wrap_idx(y + 1, h)), (-1,1), ( (x-1, y), (x, y+1) )),
            ((_wrap_idx(x + 1, w), _wrap_idx(y - 1, h)), (1,-1), ( (x+1, y), (x, y-1) )),
            ((_wrap_idx(x - 1, w), _wrap_idx(y - 1, h)), (-1,-1), ( (x-1, y), (x, y-1) )),
        ]

        for (nx, ny), _, blockers in diag:
            if avoid_corner_cut:
                # If both orthogonal neighbors are unwalkable, block the diagonal
                if not (self.is_walkable((_wrap_idx(blockers[0][0], w), _wrap_idx(blockers[0][1], h))) or
                        self.is_walkable((_wrap_idx(blockers[1][0], w), _wrap_idx(blockers[1][1], h)))):
                    continue
            yield (nx, ny)

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

    def _step_cost(
        self,
        to_node: Tuple[int, int],
        *,
        costs: Optional[Mapping[str, float]],
        jitter: float
    ) -> float:
        """Base step cost with optional terrain multiplier and small jitter."""
        terrain = self.get_tile(to_node)
        base = 1.0
        if costs is not None:
            base *= float(costs.get(terrain, 1.0))
        if jitter > 0.0:
            # Deterministic per-map RNG (not per-call). Keep jitter bounded.
            base += self.rng.uniform(0.0, min(0.5, float(jitter)))
        return base

    def find_path(
        self,
        start_tile: pygame.math.Vector2,  # pylint: disable=c-extension-no-member
        end_tile: pygame.math.Vector2,    # pylint: disable=c-extension-no-member
        options: Optional[PathOptions] = None
    ) -> Optional[List[Tuple[int, int]]]:
        """
        A* on a toroidal grid.

        - Diagonals supported (octile heuristic).
        - Optional terrain costs and small jitter.
        - Optional corner-cutting prevention and iteration cap.
        """
        opts = options or PathOptions()
        start_node = (int(start_tile.x), int(start_tile.y))
        end_node = (int(end_tile.x), int(end_tile.y))

        if not self.is_walkable(start_node) or not self.is_walkable(end_node):
            return None
        if start_node == end_node:
            return []

        state = AStarState(start_node)

        iterations = 0
        while state.priority_queue:
            if opts.max_iterations is not None and iterations >= opts.max_iterations:
                return None
            iterations += 1

            _, current = heapq.heappop(state.priority_queue)
            if current in state.closed:
                continue
            state.closed.add(current)

            if current == end_node:
                return self._reconstruct_path(state.came_from, current)

            for nxt in self._neighbors(current, diagonals=opts.allow_diagonals, avoid_corner_cut=opts.avoid_corner_cut):
                if not self.is_walkable(nxt):
                    continue
                step = self._step_cost(nxt, costs=opts.costs, jitter=opts.jitter)
                tentative_g = state.g_cost[current] + step
                if nxt not in state.g_cost or tentative_g < state.g_cost[nxt]:
                    state.g_cost[nxt] = tentative_g
                    f_cost = tentative_g + self._heuristic(nxt, end_node, diagonals=opts.allow_diagonals)
                    heapq.heappush(state.priority_queue, (f_cost, nxt))
                    state.came_from[nxt] = current

        return None  # no path

    # --- Utilities for gameplay/analytics -----------------------------------

    def find_nearest_walkable(
        self,
        start: Tuple[int, int],
        max_radius: Optional[int] = None
    ) -> Optional[Tuple[int, int]]:
        """BFS search for the nearest walkable tile from 'start' (toroidal)."""
        sx, sy = start
        sx, sy = _wrap_idx(sx, self.width), _wrap_idx(sy, self.height)
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
        if total <= 0:
            return {}
        counts: Dict[str, int] = {terrain: 0 for terrain in settings.TERRAIN_TYPES}
        for row in self.data:
            for tile in row:
                if tile in counts:
                    counts[tile] += 1
        return {terrain: (count / total) * 100.0 for terrain, count in counts.items()}
