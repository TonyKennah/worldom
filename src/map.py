# c:/game/worldom/map.py
import pygame
import random
import math
import noise
from settings import (TILE_SIZE, TERRAIN_COLORS, GRID_LINE_COLOR, 
                      HIGHLIGHT_COLOR, MIN_TILE_PIXELS_FOR_GRID, 
                      SCREEN_WIDTH, SCREEN_HEIGHT)

class Map:
    """
    Manages the game's tile-based map.

    Handles map generation and rendering, ensuring only visible tiles are drawn.
    """
    def __init__(self, width, height):
        """Initializes the map."""
        self.width = width
        self.height = height
        self.tile_size = TILE_SIZE
        self.terrain_types = list(TERRAIN_COLORS.keys())
        self.data = self._generate_map()

    def _generate_map(self):
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

        world = [[None for _ in range(self.width)] for _ in range(self.height)]
        
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

    def draw(self, surface, camera, hovered_tile=None):
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