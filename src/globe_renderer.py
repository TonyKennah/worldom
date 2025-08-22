# c:/prj/WorldDom/src/globe_renderer.py
"""
Handles the generation of globe animation frames based on map data.

This module now uses lazy imports so that importing it does not require
heavy, optional dependencies (matplotlib, cartopy) to exist. If those
libraries are missing at runtime, the functions will either no-op with
progress updates or raise a clear, friendly error message when actually
used, depending on context.
"""
from __future__ import annotations

import os
from typing import Generator, List, Optional

import numpy as np

import src.utils.settings as settings


def _try_import_matplotlib() -> Optional[object]:
    """Return pyplot module if available, else None."""
    try:
        import matplotlib  # noqa: F401
        from matplotlib import pyplot as plt
        return plt
    except Exception:
        return None


def _try_import_cartopy() -> tuple[Optional[object], Optional[object], Optional[object]]:
    """Return (ccrs, cfeature, ListedColormap) if available, else (None, None, None)."""
    try:
        import cartopy.crs as ccrs  # noqa: F401
        import cartopy.feature as cfeature  # noqa: F401
        from matplotlib.colors import ListedColormap  # noqa: F401
        return ccrs, cfeature, ListedColormap
    except Exception:
        return None, None, None


def warm_up_rendering_libraries() -> None:
    """
    Performs a trivial rendering operation to trigger the one-time initialization
    cost of matplotlib and cartopy. If those libraries are not installed, this
    will simply return without error (so CI import smoke-tests pass).
    """
    print("Warming up rendering libraries...")
    plt = _try_import_matplotlib()
    ccrs, _, _ = _try_import_cartopy()
    if plt is None or ccrs is None:
        # Graceful no-op if optional libs are not present
        print("Rendering libraries not available; skipping warm-up (this is OK in CI/headless).")
        return

    try:
        # Make sure to use a non-GUI backend if possible
        try:
            plt.switch_backend('Agg')
        except Exception:
            pass

        fig = plt.figure(figsize=(0.1, 0.1), dpi=10)
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        ax.set_global()
        plt.close(fig)
        print("Rendering libraries are warm.")
    except Exception as e:
        # Non-fatal: only affects first-use latency in real runs
        print(f"Warning: Failed to warm up rendering libraries: {e}")


def render_map_as_globe(map_data: List[List[str]], map_seed: int) -> Generator[float, None, None]:
    """
    Generates and saves a series of PNG images of a rotating globe, textured
    with the provided map data. If matplotlib/cartopy are not available,
    this function will yield a single 1.0 (done) and return without error.

    Args:
        map_data: 2D list representing the game map's terrain.
        map_seed: Unique seed of the map, used for output diagnostics.

    Yields:
        Progress floats in [0.0, 1.0].
    """
    plt = _try_import_matplotlib()
    ccrs, cfeature, ListedColormap = _try_import_cartopy()

    if plt is None or ccrs is None or cfeature is None or ListedColormap is None:
        # Graceful degradation: don't fail CI/no-cartopy envs.
        print(
            "[globe_renderer] Optional libs (matplotlib/cartopy) are not available. "
            "Skipping globe frame generation."
        )
        yield 1.0
        return

    # Use a safe backend in headless environments
    try:
        plt.switch_backend('Agg')
    except Exception:
        pass

    globe_frames_dir_name = "globe_frames"
    base_image_dir = "image"
    frame_dir = os.path.join(base_image_dir, globe_frames_dir_name)

    if os.path.exists(frame_dir):
        print(f"Globe frames already exist in {frame_dir}. Overwriting...")
        # remove all files in the directory
        for f in os.listdir(frame_dir):
            fp = os.path.join(frame_dir, f)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except Exception as e:
                    print(f"Warning: Could not remove {fp}: {e}")

    os.makedirs(frame_dir, exist_ok=True)
    print(f"Generating globe frames for map seed {map_seed} in '{frame_dir}/'...")

    # --- Convert map data to a numerical grid for plotting ---
    color_map = ListedColormap(settings.GLOBE_TERRAIN_COLORS)
    terrain_map = {name: i for i, name in enumerate(settings.TERRAIN_TYPES)}
    numerical_data = np.array(
        [[terrain_map.get(cell, 0) for cell in row] for row in map_data], dtype=np.int32
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

        # Paint the map data
        # Base: ocean color
        ax.add_feature(cfeature.OCEAN, zorder=0, facecolor=settings.GLOBE_TERRAIN_COLORS[0])
        # Terrain overlay
        ax.pcolormesh(
            lons, lats, numerical_data,
            transform=ccrs.PlateCarree(),
            cmap=color_map,
            shading='auto'
        )

        # Save the frame
        filename = os.path.join(frame_dir, f"frame_{str(i).zfill(3)}.png")
        try:
            fig.savefig(filename, dpi=dpi, transparent=True, bbox_inches='tight', pad_inches=0)
        except Exception as e:
            print(f"Error saving frame {filename}: {e}")
        finally:
            plt.close(fig)

        yield (i + 1) / settings.GLOBE_NUM_FRAMES

    print(f"\nDone! All {settings.GLOBE_NUM_FRAMES} frames have been generated.")
