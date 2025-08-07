# WorldDom(ination)

[![Pylint Status](https://github.com/TonyKennah/worldom/actions/workflows/pylint.yml/badge.svg)](https://github.com/TonyKennah/worldom/actions/workflows/pylint.yml)

[![Package with Aconda Status](https://github.com/TonyKennah/worldom/actions/workflows/python-package-conda.yml/badge.svg)](https://github.com/TonyKennah/worldom/actions/workflows/python-package-conda.yml)



A 2D strategy game prototype created with Python and Pygame, featuring procedural world generation and tile-based unit movement.

## Features

*   **Procedural World Generation:** Creates unique, natural-looking maps using two-layer Perlin noise for continents, mountain ranges, and inland lakes.
*   **Dynamic Camera:** A fully featured camera with stepped zooming (centered on the cursor) and smooth panning (using WASD keys or mouse drag).
*   **Interactive Tile Map:** An efficient, tile-based map that only renders visible tiles and displays a grid at appropriate zoom levels.
*   **A\* Pathfinding:** Intelligent, natural-looking unit movement that navigates around obstacles. The pathfinding has been tuned to feel less "robotic" by introducing a small random cost to each step.
*   **Unit Control:** Select single units with a left-click or multiple units by dragging a selection box with the right mouse button. Command selected units via a right-click context menu with "Attack", "Build", and "MoveTo" options.

## Tech Stack

*   **Language:** Python 3
*   **Core Library:** [Pygame](https://www.pygame.org/news)
*   **Map Generation:** `noise` library for Perlin noise

## Getting Started

### Prerequisites

Make sure you have Python 3 installed on your system.

**Note for Windows Users:** One of the dependencies (`noise`) may need to be compiled from source. If you see an error message like `Microsoft Visual C++ 14.0 or greater is required`, you must install the Microsoft C++ Build Tools.

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

## Running Tests

The project includes a basic test suite using Python's built-in `unittest` module. To run the tests, navigate to the project's root directory and run:

```bash
python -m unittest discover tests
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
    *   **`ContextMenuState` class**: Encapsulates all state related to the right-click context menu, such as its position, options, and visibility.
    *   **`WorldState` class**: A data class to hold the current state of all game entities, such as units, player selections, and an instance of `ContextMenuState`.
    *   **`Game` class**:
        *   `__init__()`: Initializes Pygame, the screen, clock, and creates instances of the map, camera, and the initial unit.
        *   `run()`: Contains the main game loop that processes events, updates game state, and draws to the screen.
        *   `_spawn_initial_units()`: Creates the first unit and places it on a valid starting tile.
        *   `handle_events()`: The top-level event handler, called each frame to process the event queue (quit, key presses, etc.).
        *   `_is_click(start_pos, end_pos)`: Helper to determine if a mouse action is a click or a drag.
        *   `_handle_mouse_events(event)`: Dispatches mouse events to more specific handler methods.
        *   `_handle_mouse_button_down(event)`: Handles `MOUSEBUTTONDOWN` events for both buttons.
        *   `_handle_mouse_button_up(event)`: Handles `MOUSEBUTTONUP` events for both buttons.
        *   `_handle_left_mouse_up(event)`: Differentiates between a left-click (for selection) and a left-drag (for camera).
        *   `_handle_right_mouse_up(event)`: Differentiates between a right-click (for context menu) and a right-drag (for selection box).
        *   `_handle_mouse_motion(event)`: Updates the selection box rectangle during a right-drag.
        *   `_open_context_menu(screen_pos)`: Displays the right-click command menu and stores the target tile.
        *   `_close_context_menu()`: Hides the right-click command menu.
        *   `_handle_context_menu_click(mouse_pos)`: Processes a click on or outside the context menu.
        *   `_issue_move_command_to_target()`: Issues a move command to all selected units by finding a path to the stored target tile.
        *   `_handle_left_click_selection(mouse_pos)`: Selects a single unit under the cursor, deselecting any other units.
        *   `_handle_drag_selection(selection_rect_screen)`: Selects all units within the dragged selection box.
        *   `update(dt)`: Updates all game objects. It also updates the hovered tile, unless the context menu is active.
        *   `_update_hovered_tile()`: Calculates which map tile is currently under the mouse cursor.
        *   `draw()`: Renders the map, units, selection box, and context menu to the screen.
        *   `_draw_context_menu()`: Renders the context menu on the screen.
        *   `_update_caption()`: Updates the window title with helpful debug info like FPS and cursor coordinates.

*   **`src/camera.py`**: Implements the game camera for panning and zooming.
    *   **`ZoomState` class**: Encapsulates the state and logic for camera zooming, including discrete zoom levels.
    *   **`PanningState` class**: Encapsulates the state for mouse-based camera panning (dragging).
    *   **`Camera` class**:
        *   `__init__(width, height)`: Initializes the camera's viewable area, position, and zoom/pan states.
        *   `screen_to_world(screen_pos)`: Converts screen pixel coordinates to in-game world coordinates, accounting for camera pan and zoom.
        *   `world_to_screen(world_pos)`: Converts in-game world coordinates to screen pixel coordinates.
        *   `apply(rect)`: Adjusts a `pygame.Rect`'s position and size based on the camera's offset and zoom. Used for rendering.
        *   `update(dt, events)`: The main update method for the camera, called once per frame. It calls helper methods to process input.
        *   `_handle_keyboard_movement(dt)`: Pans the camera smoothly based on WASD key presses.
        *   `_handle_mouse_input(events)`: Manages mouse-based camera controls, including drag-to-pan and calling the zoom handler.
        *   `_handle_zoom(event)`: Processes mouse wheel events to zoom in or out, keeping the point under the cursor stationary.
        *   `_handle_edge_scrolling(dt)`: Pans the camera when the mouse cursor is near the edges of the screen.

*   **`src/map.py`**: Handles the procedural generation, pathfinding logic, and rendering of the game world.
    *   **`VisibleArea` class**: A dataclass to represent the visible area of the map in tile coordinates for efficient rendering.
    *   **`AStarState` class**: A helper class to hold the state of an A* pathfinding search (priority queue, costs, etc.).
    *   **`Map` class**:
        *   `__init__(width, height)`: Generates the procedural world map using Perlin noise, creating different terrain types like grass, water, and rock.
        *   `draw(screen, camera, hovered_tile)`: Renders the visible portion of the map to the screen. It efficiently culls off-screen tiles and highlights the tile under the cursor.
        *   `is_walkable(tile_pos)`: Checks if a given tile is within bounds and not an obstacle (e.g., water).
        *   `find_path(start_tile, end_tile)`: Uses the A* algorithm to calculate the shortest valid path between two tiles, avoiding obstacles.

*   **`src/unit.py`**: Defines the behavior and appearance of controllable units in the game.
    *   **`Unit` class**:
        *   `__init__(tile_pos)`: Creates a new unit at a given starting tile position.
        *   `set_path(path)`: Assigns a new sequence of tiles (a path) for the unit to follow. This can interrupt any existing movement.
        *   `update(dt)`: Smoothly moves the unit along its assigned path from one tile to the next, interpolating its position each frame.
        *   `draw(screen, camera)`: Renders the unit on the screen, changing its appearance if it is selected.
        *   `get_world_rect()`: Returns the unit's bounding box in world coordinates, used for click detection and selection.
