# c:/game/worldom/map.py
"""
Defines the Map class for world generation, rendering, and pathfinding.
"""
from __future__ import annotations
import heapq
import math
import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import noise
import pygame

from settings import (TILE_SIZE, TERRAIN_COLORS, GRID_LINE_COLOR,
                      HIGHLIGHT_COLOR, MIN_TILE_PIXELS_FOR_GRID,
                      SCREEN_WIDTH, SCREEN_HEIGHT)

if TYPE_CHECKING:
    from camera import Camera

class AStarState:
    """Helper class to hold the state of an A* pathfinding search."""
    # pylint: disable=too-few-public-methods
    def __init__(self, start_node: Tuple[int, int]):
        self.priority_queue: List[Tuple[float, Tuple[int, int]]] = [(0, start_node)]
        self.came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start_node: None}
        self.g_cost: Dict[Tuple[int, int], float] = {start_node: 0}

# --- Map Generation Constants ---
# These can be tweaked to change the world's appearance
ELEVATION_SCALE = 60.0
ELEVATION_OCTAVES = 5
ELEVATION_PERSISTENCE = 0.6
ELEVATION_LACUNARITY = 2.0

LAKE_SCALE = 35.0
LAKE_OCTAVES = 4
LAKE_PERSISTENCE = 0.5
LAKE_LACUNARITY = 2.0

# Thresholds for terrain types.
WATER_THRESHOLD = -0.15
ROCK_THRESHOLD = 0.2
LAKE_THRESHOLD = -0.35

class Map:
    """
    Manages the game's tile-based map.

    Handles map generation and rendering, ensuring only visible tiles are drawn.
    """
    def __init__(self, width: int, height: int) -> None:
        """Initializes the map."""
        self.width = width
        self.height = height
        self.tile_size = TILE_SIZE
        self.terrain_types = list(TERRAIN_COLORS.keys())
        self.data: List[List[str]] = self._generate_map()

    def _generate_map(self) -> List[List[str]]:
        """Creates a natural-looking map using two layers of Perlin noise."""
        e_seed = random.randint(0, 100)
        l_seed = random.randint(0, 100)  # Different seed for a different pattern

        world: List[List[str]] = [["" for _ in range(self.width)] for _ in range(self.height)]

        for y in range(self.height):
            for x in range(self.width):
                # Generate elevation value
                nx_e, ny_e = x / ELEVATION_SCALE, y / ELEVATION_SCALE
                elevation = noise.pnoise2(nx_e, ny_e,
                                          octaves=ELEVATION_OCTAVES,
                                          persistence=ELEVATION_PERSISTENCE,
                                          lacunarity=ELEVATION_LACUNARITY,
                                          base=e_seed)

                # Assign terrain based on the elevation and lake values
                if elevation < WATER_THRESHOLD:
                    world[y][x] = "water"  # Ocean
                elif elevation > ROCK_THRESHOLD:
                    world[y][x] = "rock"   # Mountains
                else: # Potential land tile
                    nx_l, ny_l = x / LAKE_SCALE, y / LAKE_SCALE
                    lake_value = noise.pnoise2(nx_l, ny_l,
                                               octaves=LAKE_OCTAVES,
                                               persistence=LAKE_PERSISTENCE,
                                               lacunarity=LAKE_LACUNARITY,
                                               base=l_seed)
                    if lake_value < LAKE_THRESHOLD:
                        world[y][x] = "water" # Lake
                    else:
                        world[y][x] = "grass"  # Grassland
        return world

    def draw(
        self,
        surface: pygame.Surface,
        camera: Camera,
        hovered_tile: Optional[Tuple[int, int]] = None
    ) -> None:
        """Renders only the visible portion of the map."""
        # Determine the visible tile range based on camera view
        top_left_world = camera.screen_to_world((0, 0))
        bottom_right_screen_pos = (SCREEN_WIDTH, SCREEN_HEIGHT)
        bottom_right_world = camera.screen_to_world(bottom_right_screen_pos)

        start_col = math.floor(top_left_world.x / self.tile_size)
        end_col = math.ceil(bottom_right_world.x / self.tile_size)
        start_row = math.floor(top_left_world.y / self.tile_size)
        end_row = math.ceil(bottom_right_world.y / self.tile_size)

        self._draw_terrain(surface, camera, start_row, end_row, start_col, end_col)
        self._draw_grid_lines(surface, camera, start_row, end_row, start_col, end_col)
        self._draw_hover_highlight(surface, camera, hovered_tile)

    def _draw_terrain(self, surface: pygame.Surface, camera: Camera,
                      start_row: int, end_row: int, start_col: int, end_col: int) -> None:
        """Draws the terrain tiles."""
        for y in range(start_row, end_row):
            for x in range(start_col, end_col):
                if 0 <= x < self.width and 0 <= y < self.height: # Check bounds
                    terrain = self.data[y][x]
                    world_x = x * self.tile_size
                    world_y = y * self.tile_size
                    world_rect = pygame.Rect(world_x, world_y, self.tile_size, self.tile_size)
                    screen_rect = camera.apply(world_rect)
                    pygame.draw.rect(surface, TERRAIN_COLORS[terrain], screen_rect)

    def _draw_grid_lines(self, surface: pygame.Surface, camera: Camera,
                         start_row: int, end_row: int, start_col: int, end_col: int) -> None:
        """Draws the grid lines over the terrain."""
        scaled_tile_size = self.tile_size * camera.zoom_state.current
        if scaled_tile_size >= MIN_TILE_PIXELS_FOR_GRID:
            for col in range(start_col, end_col):
                world_x = col * self.tile_size
                screen_x = round(camera.world_to_screen(pygame.math.Vector2(world_x, 0)).x)
                start_pos = (screen_x, 0)
                end_pos = (screen_x, SCREEN_HEIGHT)
                pygame.draw.line(surface, GRID_LINE_COLOR, start_pos, end_pos, 1)
            for row in range(start_row, end_row):
                world_y = row * self.tile_size
                screen_y = round(camera.world_to_screen(pygame.math.Vector2(0, world_y)).y)
                start_pos = (0, screen_y)
                end_pos = (SCREEN_WIDTH, screen_y)
                pygame.draw.line(surface, GRID_LINE_COLOR, start_pos, end_pos, 1)

    def _draw_hover_highlight(self, surface: pygame.Surface, camera: Camera,
                              hovered_tile: Optional[Tuple[int, int]]) -> None:
        """Draws the highlight for the currently hovered tile."""
        if hovered_tile:
            tile_x, tile_y = hovered_tile
            world_x, world_y = tile_x * self.tile_size, tile_y * self.tile_size
            world_rect = pygame.Rect(world_x, world_y, self.tile_size, self.tile_size)
            screen_rect = camera.apply(world_rect)
            pygame.draw.rect(surface, HIGHLIGHT_COLOR, screen_rect, 3)

    def is_walkable(self, tile_pos: Tuple[int, int]) -> bool:
        """Checks if a given tile is within bounds and not water."""
        x, y = tile_pos
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return self.data[y][x] != 'water'

    @staticmethod
    def _heuristic(pos_a: Tuple[int, int], pos_b: Tuple[int, int]) -> float:
        """Calculates the Manhattan distance between two points for the A* heuristic."""
        return float(abs(pos_a[0] - pos_b[0]) + abs(pos_a[1] - pos_b[1]))

    def _reconstruct_path(self, came_from: Dict, current: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Reconstructs a path from the came_from dictionary."""
        path = []
        while current in came_from:
            path.append(current)
            current = came_from[current]
        return path[::-1]

    def _process_path_neighbor(
        self,
        current_node: Tuple[int, int],
        next_node: Tuple[int, int],
        end_node: Tuple[int, int],
        state: AStarState
    ) -> None:
        """Processes a single neighbor in the A* search."""
        if not self.is_walkable(next_node):
            return

        # Add a small random cost to each step to make the path less straight.
        move_cost = 1.0 + random.uniform(0.0, 0.5)
        new_g_cost = state.g_cost[current_node] + move_cost
        if next_node not in state.g_cost or new_g_cost < state.g_cost[next_node]:
            state.g_cost[next_node] = new_g_cost
            f_cost = new_g_cost + Map._heuristic(next_node, end_node)
            heapq.heappush(state.priority_queue, (f_cost, next_node))
            state.came_from[next_node] = current_node

    def find_path(
        self,
        start_tile: pygame.math.Vector2,
        end_tile: pygame.math.Vector2
    ) -> Optional[List[Tuple[int, int]]]:
        """Finds a path between two tiles using the A* algorithm."""
        start_node = tuple(map(int, start_tile))
        end_node = tuple(map(int, end_tile))

        if start_node == end_node:
            return []

        state = AStarState(start_node)

        while state.priority_queue:
            # Get the node with the lowest f_cost
            _, current_node = heapq.heappop(state.priority_queue)

            if current_node == end_node:
                return self._reconstruct_path(state.came_from, current_node)

            (x, y) = current_node
            for next_node in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                self._process_path_neighbor(
                    current_node, next_node, end_node, state
                )
        return None # No path found
