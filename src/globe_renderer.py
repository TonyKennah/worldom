# c:/prj/WorldDom/src/globe_renderer.py
"""
Handles the generation of globe animation frames based on map data.
"""
import os
from typing import Generator, List

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import cartopy.feature as cfeature
import numpy as np
from matplotlib.colors import ListedColormap

import settings


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
    globe_frames_dir_name = "globe_frames"
    base_image_dir = "image"
    frame_dir = os.path.join(base_image_dir, globe_frames_dir_name)
    if os.path.exists(frame_dir):
        print(f"Globe frames already exist. Overwriting...")
        # remove all files in the directory
        [os.remove(os.path.join(frame_dir, f)) for f in os.listdir(frame_dir) if os.path.isfile(os.path.join(frame_dir, f))]

    os.makedirs(frame_dir, exist_ok=True)
    print(f"Generating globe frames for map seed {map_seed} in '{frame_dir}/'...")

    # --- Convert map data to a numerical grid for plotting ---
    color_map = ListedColormap(settings.GLOBE_TERRAIN_COLORS)
    terrain_map = {name: i for i, name in enumerate(settings.TERRAIN_TYPES)}
    numerical_data = np.array(
        [[terrain_map.get(cell, 0) for cell in row] for row in map_data]
    )

    # --- Create longitude and latitude grids that span the globe ---
    map_height, map_width = numerical_data.shape
    lons = np.linspace(-180, 180, map_width)
    lats = np.linspace(90, -90, map_height)
    lons, lats = np.meshgrid(lons, lats)

    # --- Frame Generation Loop ---
    for i in range(settings.GLOBE_NUM_FRAMES):
        longitude = -180 + (360 * i / settings.GLOBE_NUM_FRAMES)

        projection = ccrs.Orthographic(central_longitude=longitude, central_latitude=20)

        dpi = settings.GLOBE_IMAGE_SIZE_PIXELS / 5
        fig = plt.figure(figsize=(5, 5), dpi=dpi)
        ax = fig.add_subplot(1, 1, 1, projection=projection)
        ax.set_global()

        # --- Paint the map data onto the globe ---
        # First, draw a solid ocean color as the base layer.
        ax.add_feature(cfeature.OCEAN, zorder=0, facecolor=settings.GLOBE_TERRAIN_COLORS[0])

        # Then, draw the generated terrain data over the ocean.
        ax.pcolormesh(
            lons, lats, numerical_data,
            transform=ccrs.PlateCarree(),
            cmap=color_map,
            shading='auto'
        )

        # --- Save the frame ---
        filename = os.path.join(frame_dir, f"frame_{str(i).zfill(3)}.png")
        try:
            plt.savefig(
                filename, dpi=dpi, transparent=True,
                bbox_inches='tight', pad_inches=0
            )
        except Exception as e:
            print(f"Error saving frame {filename}: {e}")
        finally:
            # Close the plot to free up memory
            plt.close(fig)

        # Yield the progress after each frame is saved
        yield (i + 1) / settings.GLOBE_NUM_FRAMES

    print(f"\nDone! All {settings.GLOBE_NUM_FRAMES} frames have been generated.")