# c:/prj/WorldDom/src/globe_renderer.py
"""
Handles the generation of globe animation frames based on map data.
"""
import os
from dataclasses import dataclass
from typing import Generator, List

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from numpy.typing import NDArray

import settings


@dataclass
class GlobeRenderData:
    """Holds the data required to render the globe's surface."""
    lons: NDArray
    lats: NDArray
    numerical_data: NDArray
    color_map: ListedColormap


def _prepare_globe_data(map_data: List[List[str]]) -> GlobeRenderData:
    """Converts map data to numerical grid, creates lat/lon coordinates and colormap."""
    terrain_map = {'water': 0, 'sand': 1, 'grass': 2, 'rock': 3}
    numerical_data = np.array(
        [[terrain_map.get(cell, 0) for cell in row] for row in map_data]
    )

    map_height, map_width = numerical_data.shape
    lons = np.linspace(-180, 180, map_width)
    lats = np.linspace(90, -90, map_height)
    lons, lats = np.meshgrid(lons, lats)
    color_map = ListedColormap(settings.GLOBE_TERRAIN_COLORS)

    return GlobeRenderData(
        lons=lons, lats=lats, numerical_data=numerical_data, color_map=color_map
    )


def _render_globe_frame(
    frame_index: int,
    frame_dir: str,
    render_data: GlobeRenderData
) -> None:
    """Renders and saves a single frame of the globe animation."""
    longitude = -180 + (360 * frame_index / settings.GLOBE_NUM_FRAMES)
    projection = ccrs.Orthographic(central_longitude=longitude, central_latitude=20)
    dpi = settings.GLOBE_IMAGE_SIZE_PIXELS / 5
    fig = plt.figure(figsize=(5, 5), dpi=dpi)
    ax = fig.add_subplot(1, 1, 1, projection=projection)
    ax.set_global()

    # Paint the map data onto the globe
    ax.pcolormesh(
        render_data.lons, render_data.lats, render_data.numerical_data,
        transform=ccrs.PlateCarree(),
        cmap=render_data.color_map,
        shading='auto'
    )
    ax.coastlines(linewidth=0.5, color='white', alpha=0.5)

    # Save the frame
    filename = os.path.join(frame_dir, f"frame_{str(frame_index).zfill(3)}.png")
    try:
        plt.savefig(
            filename, dpi=dpi, transparent=True,
            bbox_inches='tight', pad_inches=0
        )
    except IOError as e:
        print(f"Error saving frame {filename}: {e}")
    finally:
        # Close the plot to free up memory
        plt.close(fig)


def render_map_as_globe(map_data: List[List[str]], map_seed: int) -> Generator[float, None, None]:
    """
    Generates and saves a series of PNG images of a rotating globe,
    textured with the provided map data.

    Args:
        map_data: A 2D list representing the game map's terrain.
        map_seed: The unique seed of the map, used for caching frames.
    Yields:
        A float representing the progress of the generation (from 0.0 to 1.0).
    """
    frame_dir = f"globe_frames_{map_seed}"
    if os.path.exists(frame_dir):
        print(f"Globe frames for map seed {map_seed} already exist. Skipping generation.")
        return

    os.makedirs(frame_dir)
    print(f"Generating globe frames for map seed {map_seed} in '{frame_dir}/'...")

    render_data = _prepare_globe_data(map_data)

    for i in range(settings.GLOBE_NUM_FRAMES):
        _render_globe_frame(i, frame_dir, render_data)
        # Yield the progress after each frame is saved
        yield (i + 1) / settings.GLOBE_NUM_FRAMES

    print(f"\nDone! All {settings.GLOBE_NUM_FRAMES} frames have been generated.")
