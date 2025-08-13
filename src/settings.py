# c:/game/worldom/settings.py
"""
Centralized settings and constants for the game.
"""
import math

# Frame durations for globe animation. A shorter duration means a faster speed.
# The multiplier is calculated relative to the 1.0x speed (0.04s).
GLOBE_ANIMATION_SPEEDS = (math.inf, 0.4, 0.08, 0.04, 0.02, 0.01)  # Paused, 0.1x, 0.5x, 1x, 2x, 4x
GLOBE_ANIMATION_DEFAULT_SPEED_INDEX = 3  # Default to 1x speed (0.04)

# --- Globe Generation Settings ---
GLOBE_NUM_FRAMES = 60  # A good compromise for speed vs. smoothness
GLOBE_IMAGE_SIZE_PIXELS = 250 # Smaller images render faster

# --- Planet Theme Settings ---
PLANET_THEMES = {
    "earth": {
        "name": "Earth",
        "terrains": {
            # logical_name: {display_name, color, globe_color, is_walkable}
            "ocean": {"name": "Ocean", "color": (30, 70, 130), "globe_color": "#4d73a8", "walkable": False},
            "lake": {"name": "Lake", "color": (80, 140, 200), "globe_color": "#6495ED", "walkable": False},
            "grass": {"name": "Grass", "color": (50, 150, 50), "globe_color": "#669966", "walkable": True},
            "rock": {"name": "Rock", "color": (130, 130, 130), "globe_color": "#8c8c8c", "walkable": True},
        }
    },
    "titan": {
        "name": "Titan",
        "terrains": {
            "ocean": {"name": "Methane Sea", "color": (104, 60, 144), "globe_color": "#683c90", "walkable": False},
            "lake": {"name": "Tar Pit", "color": (40, 40, 40), "globe_color": "#282828", "walkable": False},
            "grass": {"name": "Crystalline Plains", "color": (200, 200, 220), "globe_color": "#c8c8dc", "walkable": True},
            "rock": {"name": "Obsidian Spires", "color": (20, 20, 30), "globe_color": "#14141e", "walkable": True},
        }
    },
    "phoebe": {
        "name": "Phoebe",
        "terrains": {
            "ocean": {"name": "Dimethyl Sulfide Sea", "color": (5,36,65), "globe_color": "#052441", "walkable": False},
            "lake": {"name": "Colbalt Crystal", "color": (73,243,206), "globe_color": "#49F3CE", "walkable": False},
            "grass": {"name": "Sand", "color": (168,166,19), "globe_color": "#a8a613", "walkable": True},
            "rock": {"name": "Ammonia Lake", "color": (147,147,192), "globe_color": "#9393c0", "walkable": True},
        }
    },
    "vulcan": {
        "name": "Vulcan",
        "terrains": {
            "ocean": {"name": "Lava Sea", "color": (139, 28, 16), "globe_color": "#8B1C10", "walkable": False},
            "lake": {"name": "Magma Flow", "color": (255, 100, 0), "globe_color": "#FF6400", "walkable": False},
            "grass": {"name": "Ash Fields", "color": (80, 80, 80), "globe_color": "#505050", "walkable": True},
            "rock": {"name": "Basalt Columns", "color": (40, 40, 50), "globe_color": "#282832", "walkable": True},
        }
    },
    "hoth": {
        "name": "Hoth",
        "terrains": {
            "ocean": {"name": "Subglacial Ocean", "color": (20, 40, 80), "globe_color": "#142850", "walkable": False},
            "lake": {"name": "Brine Pool", "color": (170, 220, 220), "globe_color": "#AADCDC", "walkable": False},
            "grass": {"name": "Snow Plains", "color": (240, 240, 255), "globe_color": "#F0F0FF", "walkable": True},
            "rock": {"name": "Glacial Ice", "color": (180, 200, 240), "globe_color": "#B4C8F0", "walkable": True},
        }
    },
}

# --- Active Theme Selection ---
# This is now handled dynamically in the Game class.
# The variables below are placeholders that will be updated at runtime.
ACTIVE_THEME_NAME: str = ""
ACTIVE_THEME: dict = {}

# --- Derived Settings (do not change directly) ---
TERRAIN_TYPES: list = []
TERRAIN_DATA: dict = {}
TERRAIN_COLORS: dict = {}
WALKABLE_TERRAINS: set = set()
GLOBE_TERRAIN_COLORS: list = []

# --- General Settings ---
# These are placeholders. The actual values are set at runtime in game.py
# when the fullscreen display is initialized.
SCREEN_WIDTH = 0
SCREEN_HEIGHT = 0
FPS = 60
BG_COLOR = (0, 0, 0)  # Black, for the void outside the map

# --- Camera Settings ---
CAMERA_SPEED = 500  # pixels per second for keyboard panning
EDGE_SCROLL_SPEED = 350 # pixels per second for edge scrolling
EDGE_SCROLL_BOUNDARY = 60 # pixels from the edge to start scrolling

# --- Map Settings ---
TILE_SIZE = 32
MAP_WIDTH_TILES = 100
MAP_HEIGHT_TILES = 100

GRID_LINE_COLOR = (40, 40, 40)
HIGHLIGHT_COLOR = (255, 255, 0)  # Yellow
MIN_TILE_PIXELS_FOR_GRID = 4

# --- Unit Settings ---
UNIT_COLOR = (255, 0, 0)  # Red
UNIT_SELECTED_COLOR = (255, 255, 255) # White
UNIT_RADIUS = TILE_SIZE // 3
UNIT_MOVES_PER_SECOND = 3.0 # How many tiles the unit moves in one second.
UNIT_INNER_CIRCLE_RATIO = 0.8 # For drawing the selected unit

# --- UI Settings ---
SELECTION_BOX_COLOR = (255, 255, 255)  # White
SELECTION_BOX_BORDER_WIDTH = 1

# Debug Panel
DEBUG_PANEL_HEIGHT = 30
DEBUG_PANEL_BG_COLOR = (10, 10, 30)
DEBUG_PANEL_FONT_COLOR = (240, 240, 240)
DEBUG_PANEL_FONT_SIZE = 16

# Context Menu
CONTEXT_MENU_BG_COLOR = (40, 40, 40)
CONTEXT_MENU_BORDER_COLOR = (150, 150, 150)
CONTEXT_MENU_HOVER_BG_COLOR = (60, 60, 80)
CONTEXT_MENU_TEXT_COLOR = (240, 240, 240)
CONTEXT_MENU_FONT_SIZE = 16
CONTEXT_MENU_PADDING = 8
