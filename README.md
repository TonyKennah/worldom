# Worldom

A 2D strategy game prototype created with Python and Pygame, featuring procedural world generation and tile-based unit movement.

## Features

*   **Procedural World Generation:** Creates unique, natural-looking maps using two-layer Perlin noise for continents, mountain ranges, and inland lakes.
*   **Dynamic Camera:** A fully featured camera with stepped zooming (centered on the cursor) and smooth panning (using WASD keys or mouse drag).
*   **Interactive Tile Map:** An efficient, tile-based map that only renders visible tiles and displays a grid at appropriate zoom levels.
*   **A\* Pathfinding:** Intelligent, natural-looking unit movement that navigates around obstacles. The pathfinding has been tuned to feel less "robotic" by introducing a small random cost to each step.
*   **Unit Control:** A basic unit that can be selected with a left-click and commanded with a right-click, with the ability to interrupt its current path with a new command.

## Tech Stack

*   **Language:** Python 3
*   **Core Library:** [Pygame](https://www.pygame.org/news)
*   **Map Generation:** `noise` library for Perlin noise

## Getting Started

### Prerequisites

Make sure you have Python 3 installed on your system.

### Installation & Running

1.  **Set up the project:**
    If you have cloned this via git, you can skip this step. Otherwise, ensure all files are in the `worldom` directory as structured below.

2.  **Install the required libraries:**
    Navigate to the project's root directory (`c:\game\worldom\`) in your terminal and run:
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
