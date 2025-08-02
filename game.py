# c:/game/game.py
import pygame
import sys
import random
import math
import noise

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
BG_COLOR = (25, 25, 112)  # Midnight Blue

CAMERA_SPEED = 500  # pixels per second
ZOOM_SENSITIVITY = 0.1

# Map Constants
TILE_SIZE = 32
MAP_WIDTH_TILES = 100
MAP_HEIGHT_TILES = 100

# Terrain Colors
TERRAIN_COLORS = {
    "grass": (50, 150, 50),
    "water": (60, 120, 180),
    "rock": (130, 130, 130),
}
GRID_LINE_COLOR = (40, 40, 40)
HIGHLIGHT_COLOR = (255, 255, 0)  # Yellow

# Unit Constants
UNIT_COLOR = (255, 0, 0)  # Red
UNIT_SELECTED_COLOR = (255, 255, 255) # White
UNIT_RADIUS = TILE_SIZE // 3
MIN_TILE_PIXELS_FOR_GRID = 4 # Lowered to ensure grid is visible at max zoom-out.

# --- Camera Class ---
class Camera:
    """Manages the game's viewport, handling zoom and panning."""
    def __init__(self, width, height):
        """Initializes the camera."""
        self.width = width
        self.height = height
        self.position = pygame.math.Vector2(0, 0)
        self.screen_center = pygame.math.Vector2(width / 2, height / 2)

        # Stepped zoom implementation
        self.zoom_levels = [0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
        self.zoom_index = self.zoom_levels.index(1.0)
        self.zoom = self.zoom_levels[self.zoom_index]
        
        # Mouse panning state
        self.dragging = False
        self.drag_pos = None

    def screen_to_world(self, screen_pos):
        """Converts screen coordinates to world coordinates."""
        return (pygame.math.Vector2(screen_pos) - self.screen_center) / self.zoom + self.position

    def world_to_screen(self, world_pos):
        """Converts world coordinates to screen coordinates."""
        return (pygame.math.Vector2(world_pos) - self.position) * self.zoom + self.screen_center

    def apply(self, rect):
        """Applies camera transformation to a pygame.Rect."""
        top_left = self.world_to_screen(rect.topleft)
        w = rect.width * self.zoom
        h = rect.height * self.zoom
        # Rounding all values to prevent gaps/jitter from float truncation.
        return pygame.Rect(round(top_left.x), round(top_left.y), round(w), round(h))

    def update(self, dt, events):
        """Updates camera position based on user input."""
        keys = pygame.key.get_pressed()

        # --- WASD Movement ---
        move_vec = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w]:
            move_vec.y -= 1
        if keys[pygame.K_s]:
            move_vec.y += 1
        if keys[pygame.K_a]:
            move_vec.x -= 1
        if keys[pygame.K_d]:
            move_vec.x += 1

        if move_vec.length_squared() > 0:
            move_vec.normalize_ip()
            # Scale movement by zoom level to feel consistent
            self.position += move_vec * CAMERA_SPEED / self.zoom * dt

        # --- Mouse Panning and Zooming ---
        for event in events:
            # Zooming (centered on mouse)
            if event.type == pygame.MOUSEWHEEL:
                mouse_pos_before_zoom = self.screen_to_world(pygame.mouse.get_pos())

                # Increment/decrement the zoom index
                if event.y > 0: # Zoom in
                    self.zoom_index = min(len(self.zoom_levels) - 1, self.zoom_index + 1)
                elif event.y < 0: # Zoom out
                    self.zoom_index = max(0, self.zoom_index - 1)
                
                self.zoom = self.zoom_levels[self.zoom_index]
                
                mouse_pos_after_zoom = self.screen_to_world(pygame.mouse.get_pos())
                self.position += mouse_pos_before_zoom - mouse_pos_after_zoom

            # Panning (drag with left mouse button)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.dragging = True
                self.drag_pos = pygame.math.Vector2(event.pos)

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging = False
                self.drag_pos = None

            if event.type == pygame.MOUSEMOTION and self.dragging:
                drag_vec = pygame.math.Vector2(event.pos) - self.drag_pos
                self.position -= drag_vec / self.zoom
                self.drag_pos = pygame.math.Vector2(event.pos)

# --- Map Class ---
class Map:
    """
    Manages the game's tile-based map.

    Handles map generation and rendering, ensuring only visible tiles are drawn.
    """
    def __init__(self, width, height, tile_size):
        """Initializes the map."""
        self.width = width
        self.height = height
        self.tile_size = tile_size
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
        # This robust method draws the grid only if tiles are large enough on screen to be distinguished.
        scaled_tile_size = self.tile_size * camera.zoom
        if scaled_tile_size >= MIN_TILE_PIXELS_FOR_GRID:
            # Draw vertical lines
            for col in range(start_col, end_col):
                world_x = col * self.tile_size
                screen_x = round(camera.world_to_screen((world_x, 0)).x)
                pygame.draw.line(surface, GRID_LINE_COLOR, (screen_x, 0), (screen_x, SCREEN_HEIGHT), 1)

            # Draw horizontal lines
            for row in range(start_row, end_row):
                world_y = row * self.tile_size
                screen_y = round(camera.world_to_screen((0, world_y)).y)
                pygame.draw.line(surface, GRID_LINE_COLOR, (0, screen_y), (SCREEN_WIDTH, screen_y), 1)

        # --- 3. Draw Hovered Tile Highlight (on top of grid) ---
        if hovered_tile:
            world_rect = pygame.Rect(hovered_tile[0] * self.tile_size, hovered_tile[1] * self.tile_size, self.tile_size, self.tile_size)
            screen_rect = camera.apply(world_rect)
            pygame.draw.rect(surface, HIGHLIGHT_COLOR, screen_rect, 3)

# --- Unit Class ---
class Unit:
    """Represents a single unit in the game."""
    def __init__(self, tile_pos, tile_size):
        """
        Initializes a unit.
        Args:
            tile_pos (tuple): The (col, row) starting tile position.
            tile_size (int): The size of a tile in pixels.
        """
        self.tile_pos = pygame.math.Vector2(tile_pos)
        self.tile_size = tile_size
        self.selected = False

    def get_world_pos(self):
        """Calculates the unit's center position in world coordinates."""
        return (self.tile_pos * self.tile_size) + pygame.math.Vector2(self.tile_size / 2, self.tile_size / 2)

    def get_world_rect(self):
        """Gets the unit's bounding box in world coordinates for selection."""
        world_pos = self.get_world_pos()
        return pygame.Rect(world_pos.x - UNIT_RADIUS, world_pos.y - UNIT_RADIUS, UNIT_RADIUS * 2, UNIT_RADIUS * 2)

    def move_to_tile(self, tile_pos):
        """Sets the unit's new target tile position."""
        self.tile_pos = pygame.math.Vector2(tile_pos)

    def draw(self, surface, camera):
        """Draws the unit on the screen."""
        screen_pos = camera.world_to_screen(self.get_world_pos())
        radius = int(UNIT_RADIUS * camera.zoom)
        
        # Draw selection circle first (underneath the unit)
        if self.selected:
            pygame.draw.circle(surface, UNIT_SELECTED_COLOR, screen_pos, radius)
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, int(radius * 0.8)) # Inner circle
        else:
            pygame.draw.circle(surface, UNIT_COLOR, screen_pos, radius)

# --- Game Class ---
class Game:
    """The main game class, orchestrating all game components."""
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Strategy Game with Camera")
        self.clock = pygame.time.Clock()
        self.running = True
        self.events = []

        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)

        self.map = Map(MAP_WIDTH_TILES, MAP_HEIGHT_TILES, TILE_SIZE)
        self.hovered_tile = None
        
        # Game object management
        self.units = []
        self.selected_unit = None
        self.left_mouse_down_pos = None # For detecting clicks vs. drags
        initial_unit = self._spawn_initial_units()

        # Center camera on the initial unit
        if initial_unit:
            self.camera.position = initial_unit.get_world_pos()

    def run(self):
        """The main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()

    def _spawn_initial_units(self):
        """Creates the starting units for the game and returns the first one."""
        # Find a valid starting position on a grass tile
        while True:
            x, y = random.randint(0, self.map.width - 1), random.randint(0, self.map.height - 1)
            if self.map.data[y][x] == 'grass':
                new_unit = Unit((x, y), TILE_SIZE)
                self.units.append(new_unit)
                return new_unit

    def handle_events(self):
        """Processes all user input and events."""
        self.events = pygame.event.get()
        for event in self.events:
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.left_mouse_down_pos = event.pos
                elif event.button == 3: # Right-click for commands
                    if self.selected_unit and self.hovered_tile:
                        terrain = self.map.data[self.hovered_tile[1]][self.hovered_tile[0]]
                        if terrain != "water":
                            self.selected_unit.move_to_tile(self.hovered_tile)
                        else:
                            print("Unit cannot move into water.") # Added feedback

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.left_mouse_down_pos:
                    # Check if it was a click or a drag
                    dist = pygame.math.Vector2(self.left_mouse_down_pos).distance_to(event.pos)
                    if dist < 5: # Threshold for a click
                        # --- This is a click, handle selection ---
                        world_pos = self.camera.screen_to_world(event.pos)
                        
                        clicked_on_unit = False
                        for unit in self.units:
                            if unit.get_world_rect().collidepoint(world_pos):
                                if self.selected_unit:
                                    self.selected_unit.selected = False
                                self.selected_unit = unit
                                unit.selected = True
                                clicked_on_unit = True
                                break
                        
                        # If we didn't click a unit, deselect any active one
                        if not clicked_on_unit and self.selected_unit:
                            self.selected_unit.selected = False


    def update(self, dt):
        self.camera.update(dt, self.events)

        # Determine which tile is under the mouse for highlighting
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.camera.screen_to_world(mouse_pos)
        tile_col = int(world_pos.x // self.map.tile_size)
        tile_row = int(world_pos.y // self.map.tile_size)

        if 0 <= tile_col < self.map.width and 0 <= tile_row < self.map.height:
            self.hovered_tile = (tile_col, tile_row)
        else:
            self.hovered_tile = None

    def draw(self):
        self.screen.fill(BG_COLOR)
        self.map.draw(self.screen, self.camera, self.hovered_tile)

        # Draw all units
        for unit in self.units:
            unit.draw(self.screen, self.camera)

        # Update window title with helpful info
        world_pos = self.camera.screen_to_world(pygame.mouse.get_pos())
        caption = f"Strategy Game | World: ({int(world_pos.x)}, {int(world_pos.y)})"
        if self.hovered_tile:
            terrain = self.map.data[self.hovered_tile[1]][self.hovered_tile[0]]
            caption += f" | Tile: {self.hovered_tile} ({terrain.capitalize()})"
        pygame.display.set_caption(caption)
        pygame.display.flip()

if __name__ == '__main__':
    game = Game()
    game.run()