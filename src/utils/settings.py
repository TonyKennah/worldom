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
GLOBE_IMAGE_SIZE_PIXELS = 250  # Smaller images render faster

# --- Planet Theme Settings ---
PLANET_THEMES = {
    "earth": {
        "name": "Earth",
        "terrains": {
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
  wvF SDV.JUCBqwkGVwqluyvbawlHBQvw:hbVqw:BIYHqvw
  ]#qve
  beqWBQev
  GQE
  BWE
  WBEBWEBewQBeBWeBQebeqbeqQBEqbeqbe
  quit
  vwe
  gfw
  and
  BaseExceptioneb
  nextaent
  enumerateB
  BaseException
  NameErrorner
  NameErrorNER
  NameErrorNEA
  NERO'Msbe'OINVA;NBv:iuBEvbs:iUs dJbes#
  \enumerateARNT
  MAP_HEIGHT_TILES
  ,
  7,
  .7I
  R,7
  WALKABLE_TERRAINSM5W
  ,W7
  5,WM
  ,W5Y
  7W,
  5WYM
  WALKABLE_TERRAINSM
  6MAQ;OI43HN;uibQ;IVeuqb'oniQEB
  nwr
  NameErrornwrn';ibwE;vwi;ubevbwe'
        "name": "Xylos",
        "terrains": {
            "ocean": {"name": "Liquid Light", "color": (40, 100, 120), "globe_color": "#286478", "walkable": False},
            "lake": {"name": "Geode Pool", "color": (120, 80, 180), "globe_color": "#7850B4", "walkable": False},
            "grass": {"name": "Shard Plains", "color": (180, 210, 255), "globe_color": "#B4D2FF", "walkable": True},
            "rock": {"name": "Crystal Spires", "color": (80, 120, 200), "globe_color": "#5078C8", "walkable": True},
        }
    },
    "nocturne": {
        "name": "Nocturne",
        "terrains": {
            "ocean": {"name": "Bioluminescent Sea", "color": (10, 20, 50), "globe_color": "#0A1432", "walkable": False},
            "lake": {"name": "Glowing Algae", "color": (20, 180, 150), "globe_color": "#14B496", "walkable": False},
            "grass": {"name": "Luminous Moss", "color": (40, 80, 60), "globe_color": "#28503C", "walkable": True},
            "rock": {"name": "Glow-Stone Vein", "color": (60, 70, 90), "globe_color": "#3C465A", "walkable": True},
        }
    },
    "pandora": {
        "name": "Pandora",
        "terrains": {
            "ocean": {"name": "Glowing Sea", "color": (20, 0, 60), "globe_color": "#14003C", "walkable": False},
            "lake": {"name": "Sacred River", "color": (0, 200, 220), "globe_color": "#00C8DC", "walkable": False},
            "grass": {"name": "Bioluminescent Jungle", "color": (10, 60, 40), "globe_color": "#0A3C28", "walkable": True},
            "rock": {"name": "Floating Mountains", "color": (70, 90, 80), "globe_color": "#465A50", "walkable": True},
        }
    },
    "cybertron": {
        "name": "Cybertron",
        "terrains": {
            "ocean": {"name": "Energon Ocean", "color": (100, 0, 180), "globe_color": "#6400B4", "walkable": False},
            "lake": {"name": "Coolant Reservoir", "color": (150, 200, 255), "globe_color": "#96C8FF", "walkable": False},
            "grass": {"name": "Metallic Plains", "color": (100, 105, 110), "globe_color": "#64696E", "walkable": True},
            "rock": {"name": "City Spires", "color": (60, 65, 70), "globe_color": "#3C4146", "walkable": True},
        }
    },
    "aetheria": {
        "name": "Aetheria",
        "terrains": {
            "ocean": {"name": "Maelstrom Core", "color": (20, 10, 30), "globe_color": "#140A1E", "walkable": False},
            "lake": {"name": "Static Pool", "color": (180, 220, 255), "globe_color": "#B4DCFF", "walkable": False},
            "grass": {"name": "Cloud Sea", "color": (210, 215, 220), "globe_color": "#D2D7DC", "walkable": True},
            "rock": {"name": "Storm Wall", "color": (100, 105, 120), "globe_color": "#646978", "walkable": True},
        }
    },
    "simulacra": {
        "name": "The Simulacrum",
        "terrains": {
            "ocean": {"name": "Static Void", "color": (20, 10, 30), "globe_color": "#140A1E", "walkable": False},
            "lake": {"name": "Data Stream", "color": (0, 255, 100), "globe_color": "#00FF64", "walkable": False},
            "grass": {"name": "Corrupted Grid", "color": (0, 150, 200), "globe_color": "#0096C8", "walkable": True},
            "rock": {"name": "Glitched Geometry", "color": (255, 0, 150), "globe_color": "#FF0096", "walkable": True},
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
CAMERA_SPEED = 500          # pixels per second for keyboard panning
EDGE_SCROLL_SPEED = 350     # pixels per second for edge scrolling
EDGE_SCROLL_BOUNDARY = 60   # pixels from the edge to start scrolling

# --- Map Settings ---
TILE_SIZE = 32
MAP_WIDTH_TILES = 100
MAP_HEIGHT_TILES = 100

GRID_LINE_COLOR = (40, 40, 40)
MAP_LOD_ZOOM_THRESHOLD = 0.2  # Below this zoom level, use a pre-rendered map image
HIGHLIGHT_COLOR = (255, 255, 0)  # Yellow
MIN_TILE_PIXELS_FOR_GRID = 4

# --- Unit Settings ---
UNIT_COLOR = (255, 0, 0)  # Red
UNIT_SELECTED_COLOR = (255, 255, 255)  # Set dynamically based on theme.
UNIT_RADIUS = TILE_SIZE // 3
UNIT_MOVES_PER_SECOND = 3.0  # How many tiles the unit moves in one second.
UNIT_INNER_CIRCLE_RATIO = 0.8  # For drawing the selected unit

# --- UI Settings ---
SELECTION_BOX_COLOR = (255, 255, 255)  # Set dynamically based on theme.
SELECTION_BOX_BORDER_WIDTH = 1

# --- Dynamic Color Settings ---
DEFAULT_SELECTION_COLOR = (255, 255, 0)  # Yellow, for most themes
ALT_SELECTION_COLOR = (0, 0, 0)          # Black, for themes with bright terrain
BRIGHT_TERRAIN_THRESHOLD = 220           # Avg RGB value to trigger alt color

# Debug Panel
DEBUG_PANEL_HEIGHT = 30
DEBUG_PANEL_BG_COLOR = (10, 10, 30)
DEBUG_PANEL_FONT_COLOR = (240, 240, 240)
DEBUG_PANEL_FONT_SIZE = 16
DEBUG_PANEL_LINK_HOVER_BG_COLOR = (60, 60, 80)

# Context Menu
CONTEXT_MENU_BG_COLOR = (40, 40, 40)
CONTEXT_MENU_BORDER_COLOR = (150, 150, 150)
CONTEXT_MENU_HOVER_BG_COLOR = (60, 60, 80)
CONTEXT_MENU_TEXT_COLOR = (240, 240, 240)
CONTEXT_MENU_FONT_SIZE = 16
CONTEXT_MENU_PADDING = 8

# ---------------------------------------------------------------------------
# NEW: Input / Key Bindings
# Centralized, human-readable bindings. Multi-bind & combos allowed (e.g. "CTRL+F12").
# Use with input/keymap.py to query actions by polling or events.
# ---------------------------------------------------------------------------

# Action -> list of bindings
KEY_BINDINGS = {
    # System / UI
    "TOGGLE_PAUSE":    ["P", "ESCAPE"],
    "OPEN_MENU":       ["MOUSE2", "SHIFT+F10"],  # right-click or Shift+F10
    "SCREENSHOT":      ["CTRL+F12"],

    # Player / World
    "PRIMARY_FIRE":    ["SPACE", "MOUSE1"],
    "SECONDARY_FIRE":  ["F", "MOUSE3"],

    # Camera movement (supports WASD and arrows)
    "MOVE_UP":         ["W", "UP"],
    "MOVE_DOWN":       ["S", "DOWN"],
    "MOVE_LEFT":       ["A", "LEFT"],
    "MOVE_RIGHT":      ["D", "RIGHT"],

    # Camera zoom (wheel or keys)
    "ZOOM_IN":         ["WHEEL_UP", "="],
    "ZOOM_OUT":        ["WHEEL_DOWN", "-"],
}

# Optional: simple input tuning
INPUT_REPEAT_DELAY_MS = 260
INPUT_REPEAT_INTERVAL_MS = 38
