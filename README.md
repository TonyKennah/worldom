# WorldDom  🚀 👽 (ination) 🔫

[![Pylint Status](https://github.com/TonyKennah/worldom/actions/workflows/pylint.yml/badge.svg)](https://github.com/TonyKennah/worldom/actions/workflows/pylint.yml)

[![Build Status](https://github.com/TonyKennah/worldom/actions/workflows/python-package-conda.yml/badge.svg)](https://github.com/TonyKennah/worldom/actions/workflows/python-package-conda.yml)

A 2D strategy game prototype created with Python and Pygame, featuring procedural world generation and tile-based unit movement.

## Features

*   **Procedural World Generation:** Creates unique, seamlessly tileable worlds using 4D Perlin noise. This ensures that the wrap-around map has no visible seams, creating a truly continuous world.
*   **Dynamic Camera:** A fully featured camera with stepped zooming (centered on the cursor) and smooth panning (using WASD keys and edge scrolling).
*   **Interactive Tile Map:** An efficient, tile-based map that only renders visible tiles and displays a grid at appropriate zoom levels.
*   **A\* Pathfinding:** Intelligent, natural-looking unit movement that navigates around obstacles. The pathfinding has been tuned to feel less "robotic" by introducing a small random cost to each step.
*   **UI Panel:** An on-screen UI panel displays key information like FPS, zoom level, and cursor coordinates, and includes a clickable Exit link.
*   **Unit Control:** Select single units with a left-click or multiple units by dragging a selection box with the left mouse button. Command selected units via a right-click context menu. The "Build" command opens a sub-menu with structure options.

## Tech Stack

*   **Language:** Python 3
*   **Core Library:** [Pygame](https://www.pygame.org/news)
*   **Map Generation:** `opensimplex` library for seamless Perlin/Simplex noise

## Getting Started

### Prerequisites

Make sure you have Python 3 installed on your system.

### Installation & Running

1.  **Set up the project:**
    If you have cloned this via git, you can skip this step. Otherwise, ensure all files are in the `worldom` directory as structured below.

2.  **Install the required libraries:**
    Navigate to the project's root directory in your terminal and run:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the game:**
    The main entry point is `main.py`. Run it from the root directory:
    ```bash
    python main.py
    ```

## Project Structure

The project uses a standard `src` layout to keep the source code organized and separated from other assets.

```
worldom/
├── src/
│   ├── camera.py
│   ├── game.py
│   ├── map.py
│   ├── settings.py
│   └── unit.py
└── main.py
└── requirements.txt
```


### Source Code Breakdown

*   **`main.py`**: The main entry point of the application. It initializes the `Game` object and runs the main game loop.

*   **`src/settings.py`**: Contains global constants and configuration settings for the game, such as screen dimensions, colors, tile sizes, and game speed. This file does not contain any classes.

*   **`src/game.py`**: The core game class that manages the main game loop, event handling, and game state.
    *   **`DebugPanel` class**: Handles rendering and interaction for the top debug panel.
        *   `__init__()`: Initializes the panel's font and state.
        *   `handle_event(event)`: Processes user input for the panel, like clicking the Exit link.
        *   `_draw_main_info(game)`: Renders the main informational text (FPS, zoom, etc.).
        *   `_draw_exit_link(game)`: Renders the clickable 'Exit' link.
        *   `draw(game)`: Renders the complete debug panel by calling its helper methods.
    *   **`SubMenuState` class**: Encapsulates the state of a context sub-menu.
    *   **`ContextMenuState` class**: Encapsulates all state related to the right-click context menu, including an instance of `SubMenuState`.
    *   **`WorldState` class**: A data class to hold the current state of all game entities, such as units, player selections, and an instance of `ContextMenuState`.
    *   **`Game` class**:
        *   `__init__()`: Initializes Pygame and creates a maximized window. It also creates instances of the map, camera, and the initial unit.
        *   `run()`: Contains the main game loop that processes events, updates game state, and draws to the screen.
        *   `_get_all_land_tiles()`: Returns a list of all valid land tiles (grass or rock).
        *   `_spawn_initial_units()`: Creates the first unit on a random land tile.
        *   `handle_events(events)`: The top-level event handler, called each frame to process the event queue (quit, key presses, etc.).
        *   `_is_click(start_pos, end_pos)`: Helper to determine if a mouse action is a click or a drag.
        *   `_handle_mouse_events(event)`: Dispatches mouse events to more specific handler methods.
        *   `_handle_mouse_button_down(event)`: Handles `MOUSEBUTTONDOWN` events for game world interactions.
        *   `_handle_mouse_button_up(event)`: Handles `MOUSEBUTTONUP` events for both buttons.
        *   `_handle_left_mouse_up(event)`: Differentiates between a left-click (for selection) and a left-drag (for creating a selection box).
        *   `_handle_right_mouse_up(event)`: Handles a right-click to open the context menu for selected units.
        *   `_handle_mouse_motion(event)`: Updates the selection box rectangle during a left-drag.
        *   `_open_context_menu(screen_pos)`: Displays the right-click command menu and stores the target tile.
        *   `_close_context_menu()`: Hides the right-click command menu.
        *   `_handle_context_menu_click(mouse_pos)`: Processes a click on or outside the context menu.
        *   `_handle_context_menu_hover(mouse_pos)`: Checks for hovering over context menu items to open sub-menus.
        *   `_open_sub_menu(...)`: Displays a sub-menu for a context menu item.
        *   `_close_sub_menu()`: Hides the sub-menu.
        *   `_issue_move_command_to_target()`: Issues a move command to all selected units by finding a path to the stored target tile.
        *   `_handle_left_click_selection(mouse_pos)`: Selects a single unit under the cursor, deselecting any other units.
        *   `_handle_drag_selection(selection_rect_screen)`: Selects all units within the dragged selection box.
        *   `update(dt, events)`: Updates all game objects. It also handles context menu hovering and updates the hovered tile.
        *   `_update_hovered_tile()`: Calculates which map tile is currently under the mouse cursor.
        *   `draw()`: Renders the map, units, selection box, context menu, and debug panel to the screen.
        *   `_draw_context_menu()`: Renders the context menu on the screen.
        *   `_draw_sub_menu()`: Renders the sub-menu on the screen.

*   **`src/camera.py`**: Implements the game camera for panning and zooming.
    *   **`ZoomState` class**: Encapsulates the state and logic for camera zooming, including discrete zoom levels.
    *   **`Camera` class**:
        *   `__init__(width, height)`: Initializes the camera's viewable area, position, and zoom/pan states.
        *   `screen_to_world(screen_pos)`: Converts screen pixel coordinates to in-game world coordinates, accounting for camera pan and zoom.
        *   `world_to_screen(world_pos)`: Converts in-game world coordinates to screen pixel coordinates.
        *   `apply(rect)`: Adjusts a `pygame.Rect`'s position and size based on the camera's offset and zoom. Used for rendering.
        *   `update(dt, events)`: The main update method for the camera, called once per frame. It calls helper methods to process input.
        *   `_handle_keyboard_movement(dt)`: Pans the camera smoothly based on WASD key presses.
        *   `_handle_mouse_input(events)`: Manages mouse-based camera controls, specifically zooming via the mouse wheel.
        *   `_handle_zoom(event)`: Processes mouse wheel events to zoom in or out, keeping the point under the cursor stationary.
        *   `_handle_edge_scrolling(dt)`: Pans the camera when the mouse cursor is near the edges of the screen, ignoring the area covered by the debug panel.

*   **`src/map.py`**: Handles the procedural generation, pathfinding logic, and rendering of the game world.
    *   **`VisibleArea` class**: A dataclass to represent the visible area of the map in tile coordinates for efficient rendering.
    *   **`AStarState` class**: A helper class to hold the state of an A* pathfinding search (priority queue, costs, etc.).
    *   **`Map` class**:
        *   `__init__(width, height)`: Generates a seamlessly tileable 100x100 world map using 4D OpenSimplex noise to create natural-looking continents, mountains, and lakes.
        *   `draw(screen, camera, hovered_tile)`: Renders the visible portion of the map to the screen. It efficiently culls off-screen tiles and highlights the tile under the cursor.
        *   `is_walkable(tile_pos)`: Checks if a given tile is not an obstacle (e.g., an ocean or lake).
        *   `find_path(start_tile, end_tile)`: Uses the A* algorithm to calculate the shortest valid path between two tiles, avoiding obstacles.

*   **`src/unit.py`**: Defines the behavior and appearance of controllable units in the game.
    *   **`Unit` class**:
        *   `__init__(tile_pos)`: Creates a new unit at a given starting tile position.
        *   `set_path(path)`: Assigns a new sequence of tiles (a path) for the unit to follow.
        *   `update(dt, map_width, map_height)`: Smoothly moves the unit along its path, correctly handling movement across the wrap-around edges of the toroidal map.
        *   `draw(screen, camera, map_width_pixels, map_height_pixels)`: Renders the unit, drawing multiple instances if necessary to create a seamless wrap-around effect.
        *   `get_world_rect()`: Returns the unit's bounding box in world coordinates, used for click detection and selection.
