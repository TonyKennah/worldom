# c:/game/worldom/map.py
from __future__ import annotations
import pygame
import random
import math
import noise

import heapq
from typing import List, Tuple, Optional, Dict
from typing import TYPE_CHECKING
from settings import (TILE_SIZE, TERRAIN_COLORS, GRID_LINE_COLOR, 
                      HIGHLIGHT_COLOR, MIN_TILE_PIXELS_FOR_GRID, 
                      SCREEN_WIDTH, SCREEN_HEIGHT)

if TYPE_CHECKING:
    from camera import Camera

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
        # --- Elevation Noise (for continents and mountains) ---
        e_scale = 60.0
        e_octaves = 5
        e_persistence = 0.6
        e_lacunarity = 2.0
        e_seed = random.randint(0, 100)

        # --- Lake Noise (for inland water bodies) ---
        l_scale = 35.0  # Smaller scale for more, smaller lakes
        l_octaves = 4
        l_persistence = 0.5
        l_lacunarity = 2.0
        l_seed = random.randint(0, 100) # Different seed for a different pattern

        # Thresholds for terrain types.
        water_threshold = -0.15 # Raised to increase ocean size slightly.
        rock_threshold = 0.2    # Lowered again to make rocks even more common, increasing their coverage.
        lake_threshold = -0.35  # Raised to make inland lakes more common.

        world: List[List[str]] = [["" for _ in range(self.width)] for _ in range(self.height)]
        
        for y in range(self.height):
            for x in range(self.width):
                # Generate elevation value
                nx_e, ny_e = x / e_scale, y / e_scale
                elevation = noise.pnoise2(nx_e, ny_e,
                                          octaves=e_octaves,
                                          persistence=e_persistence,
                                          lacunarity=e_lacunarity,
                                          base=e_seed)

                # Assign terrain based on the elevation and lake values
                if elevation < water_threshold:
                    world[y][x] = "water"  # Ocean
                elif elevation > rock_threshold:
                    world[y][x] = "rock"   # Mountains
                else: # Potential land tile
                    nx_l, ny_l = x / l_scale, y / l_scale
                    lake_value = noise.pnoise2(nx_l, ny_l, octaves=l_octaves, persistence=l_persistence, lacunarity=l_lacunarity, base=l_seed)
                    if lake_value < lake_threshold:
                        world[y][x] = "water" # Lake
                    else:
                        world[y][x] = "grass"  # Grassland
        return world

    def draw(self, surface: pygame.Surface, camera: Camera, hovered_tile: Optional[Tuple[int, int]] = None) -> None:
        """Renders only the visible portion of the map."""
        # Determine the visible tile range based on camera view
        top_left_world = camera.screen_to_world((0, 0))
        bottom_right_world = camera.screen_to_world((SCREEN_WIDTH, SCREEN_HEIGHT))

        # Use the more precise calculation for the visible tile range
        start_col = math.floor(top_left_world.x / self.tile_size)
        end_col = math.ceil(bottom_right_world.x / self.tile_size)
        start_row = math.floor(top_left_world.y / self.tile_size)
        end_row = math.ceil(bottom_right_world.y / self.tile_size)

        # --- 1. Draw Terrain Tiles ---
        for y in range(start_row, end_row):
            for x in range(start_col, end_col):
                if 0 <= x < self.width and 0 <= y < self.height: # Check bounds
                    terrain = self.data[y][x]
                    world_rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                    screen_rect = camera.apply(world_rect)
                    pygame.draw.rect(surface, TERRAIN_COLORS[terrain], screen_rect)

        # --- 2. Draw Grid Lines (if zoomed in) ---
        scaled_tile_size = self.tile_size * camera.zoom
        if scaled_tile_size >= MIN_TILE_PIXELS_FOR_GRID:
            for col in range(start_col, end_col):
                world_x = col * self.tile_size
                screen_x = round(camera.world_to_screen((world_x, 0)).x)
                pygame.draw.line(surface, GRID_LINE_COLOR, (screen_x, 0), (screen_x, SCREEN_HEIGHT), 1)
            for row in range(start_row, end_row):
                world_y = row * self.tile_size
                screen_y = round(camera.world_to_screen((0, world_y)).y)
                pygame.draw.line(surface, GRID_LINE_COLOR, (0, screen_y), (SCREEN_WIDTH, screen_y), 1)

        # --- 3. Draw Hovered Tile Highlight (on top of grid) ---
        if hovered_tile:
            world_rect = pygame.Rect(hovered_tile[0] * self.tile_size, hovered_tile[1] * self.tile_size, self.tile_size, self.tile_size)
            screen_rect = camera.apply(world_rect)
            pygame.draw.rect(surface, HIGHLIGHT_COLOR, screen_rect, 3)

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        """Calculates the Manhattan distance between two points for the A* heuristic."""
        (x1, y1) = a
        (x2, y2) = b
        return abs(x1 - x2) + abs(y1 - y2)

    def find_path(self, start_tile: pygame.math.Vector2, end_tile: pygame.math.Vector2) -> Optional[List[Tuple[int, int]]]:
        """Finds a path between two tiles using the A* algorithm."""
        start_node = tuple(map(int, start_tile))
        end_node = tuple(map(int, end_tile))

        if start_node == end_node:
            return []

        # The priority queue will store (f_cost, node)
        priority_queue: List[Tuple[float, Tuple[int, int]]] = [(0, start_node)]
        # came_from stores the node we came from to reach the key node
        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start_node: None}
        # g_cost stores the cost of the cheapest path from start to the key node
        g_cost: Dict[Tuple[int, int], float] = {start_node: 0}

        while priority_queue:
            # Get the node with the lowest f_cost
            _, current_node = heapq.heappop(priority_queue)

            if current_node == end_node:
                # Reconstruct path by backtracking
                path = []
                while current_node is not None:
                    path.append(current_node)
                    current_node = came_from[current_node]
                return path[::-1][1:]

            (x, y) = current_node
            for next_node in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                nx, ny = next_node
                if not (0 <= nx < self.width and 0 <= ny < self.height and self.data[ny][nx] != 'water'):
                    continue

                # Add a small random cost to each step to make the path less straight.
                move_cost = 1.0 + random.uniform(0.0, 0.5)
                new_g_cost = g_cost[current_node] + move_cost
                if next_node not in g_cost or new_g_cost < g_cost[next_node]:
                    g_cost[next_node] = new_g_cost
                    f_cost = new_g_cost + self._heuristic(next_node, end_node)
                    heapq.heappush(priority_queue, (f_cost, next_node))
                    came_from[next_node] = current_node
        return None # No path found