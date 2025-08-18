# src/rendering/globe_renderer.py
"""
Handles the generation of globe animation frames based on map data.
"""
from __future__ import annotations

import os
import sys
from typing import Generator, List

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import cartopy.feature as cfeature
import numpy as np
from matplotlib.colors import ListedColormap
from concurrent.futures import ProcessPoolExecutor, as_completed

import src.utils.settings as settings

_LINUX = sys.platform.startswith("linux")


def _maybe_set_spawn() -> None:
    """Safer for matplotlib/cartopy in multiprocessing on Linux."""
    import multiprocessing as mp
    try:
        mp.set_start_method("spawn", force=False)
    except RuntimeError:
        # Already set; ignore
        pass


# src/globe_renderer.py
import os
from typing import Generator, List

import cartopy.crs as ccrs
import matplotlib
matplotlib.use("Agg")  # Headless-safe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

import src.utils.settings as settings

def warm_up_rendering_libraries() -> None:
    try:
        plt.switch_backend('Agg')
        fig = plt.figure(figsize=(0.1, 0.1), dpi=10)
        _ = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        plt.close(fig)
    except Exception as e:
        print(f"Warning: warm-up failed: {e}")

def render_map_as_globe(map_data: List[List[str]], map_seed: int) -> Generator[float, None, None]:
    # fresh, *no* coastlines/land features – we only draw our synthetic data
    base_dir = os.path.join("image", "globe_frames")
    os.makedirs(base_dir, exist_ok=True)
    for f in os.listdir(base_dir):
        fp = os.path.join(base_dir, f)
        if os.path.isfile(fp):
            try: os.remove(fp)
            except OSError: pass

    color_map = ListedColormap(settings.GLOBE_TERRAIN_COLORS)
    terrain_map = {name: i for i, name in enumerate(settings.TERRAIN_TYPES)}
    data = np.array([[terrain_map.get(cell, 0) for cell in row] for row in map_data])

    h, w = data.shape
    lons = np.linspace(-180, 180, w)
    lats = np.linspace(90, -90, h)
    LONS, LATS = np.meshgrid(lons, lats)

    for i in range(settings.GLOBE_NUM_FRAMES):
        lon = -180 + (360 * i / settings.GLOBE_NUM_FRAMES)
        proj = ccrs.Orthographic(central_longitude=lon, central_latitude=20)

        dpi = settings.GLOBE_IMAGE_SIZE_PIXELS / 5
        fig = plt.figure(figsize=(5, 5), dpi=dpi)
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        ax.set_global()

        # Fill with the first terrain color as "ocean" background
        ax.background_patch.set_facecolor(settings.GLOBE_TERRAIN_COLORS[0])

        # Our synthetic raster
        ax.pcolormesh(LONS, LATS, data, transform=ccrs.PlateCarree(),
                      cmap=color_map, shading='auto')

        out = os.path.join(base_dir, f"frame_{i:03d}.png")
        try:
            plt.savefig(out, dpi=dpi, transparent=True, bbox_inches='tight', pad_inches=0)
        finally:
            plt.close(fig)
        yield (i + 1) / settings.GLOBE_NUM_FRAMES



def _render_single_frame(
    i: int,
    numerical_data: np.ndarray,
    lons: np.ndarray,
    lats: np.ndarray,
    frame_dir: str
) -> str:
    """
    Worker function to render a single globe frame to disk.
    Runs in a separate process in parallel mode.
    """
    # Ensure Agg backend in workers
    try:
        plt.switch_backend("Agg")
    except Exception:
        pass

    longitude = -180 + (360 * i / settings.GLOBE_NUM_FRAMES)
    projection = ccrs.Orthographic(central_longitude=longitude, central_latitude=20)

    dpi = settings.GLOBE_IMAGE_SIZE_PIXELS / 5
    fig = plt.figure(figsize=(5, 5), dpi=dpi)
    ax = fig.add_subplot(1, 1, 1, projection=projection)
    ax.set_global()

    # Paint: base ocean then terrain data
    ax.add_feature(cfeature.OCEAN, zorder=0, facecolor=settings.GLOBE_TERRAIN_COLORS[0])

    color_map = ListedColormap(settings.GLOBE_TERRAIN_COLORS)
    ax.pcolormesh(
        lons, lats, numerical_data,
        transform=ccrs.PlateCarree(),
        cmap=color_map,
        shading="auto",
    )

    filename = os.path.join(frame_dir, f"frame_{str(i).zfill(3)}.png")
    try:
        plt.savefig(
            filename, dpi=dpi, transparent=True,
            bbox_inches="tight", pad_inches=0
        )
    finally:
        plt.close(fig)
    return filename


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
        for f in os.listdir(frame_dir):
            p = os.path.join(frame_dir, f)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception as e:
                    print(f"Warning: Could not remove {p}: {e}")

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
    parallel = _LINUX and os.environ.get("WORLDDOM_GLOBE_PARALLEL", "0") == "1"
    if parallel:
        print("Globe rendering: parallel mode enabled on Linux.")
        _maybe_set_spawn()
        workers = max(2, (os.cpu_count() or 4) // 2)
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [
                ex.submit(_render_single_frame, i, numerical_data, lons, lats, frame_dir)
                for i in range(settings.GLOBE_NUM_FRAMES)
            ]
            complete = 0
            for fut in as_completed(futures):
                _ = fut.result()  # raise if any worker failed
                complete += 1
                yield complete / settings.GLOBE_NUM_FRAMES
    else:
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
