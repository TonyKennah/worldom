# c:/game/worldom/settings.py
"""
Centralized settings and constants for the game.
"""

# --- General Settings ---
# These are placeholders. The actual values are set at runtime in game.py
# when the fullscreen display is initialized.
SCREEN_WIDTH = 0
SCREEN_HEIGHT = 0
FPS = 60
BG_COLOR = (25, 25, 112)  # Midnight Blue

# --- Camera Settings ---
CAMERA_SPEED = 500  # pixels per second for keyboard panning
EDGE_SCROLL_SPEED = 350 # pixels per second for edge scrolling
EDGE_SCROLL_BOUNDARY = 40 # pixels from the edge to start scrolling

# --- Map Settings ---
TILE_SIZE = 32
MAP_WIDTH_TILES = 100
MAP_HEIGHT_TILES = 100

# Terrain Colors
TERRAIN_COLORS = {
    "grass": (50, 150, 50),      # Lush green for grasslands
    "ocean": (60, 120, 180),     # Deep blue for oceans
    "lake": (80, 140, 200),      # Lighter blue for inland lakes
    "rock": (130, 130, 130),     # Gray for mountains
}
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
CONTEXT_MENU_TEXT_COLOR = (240, 240, 240)
CONTEXT_MENU_FONT_SIZE = 16
CONTEXT_MENU_PADDING = 8
