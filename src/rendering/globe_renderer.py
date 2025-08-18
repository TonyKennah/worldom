# c:/prj/WorldDom/src/rendering/globe_renderer.py
"""
Globe frame renderer for WorldDom.

- Safe imports with graceful fallback when Cartopy is unavailable.
- Non-interactive Agg backend to avoid GUI requirements for matplotlib.
- Generator-based progress reporting for smooth loading UI.
- Optional flat (equirectangular) fallback frames so the game still runs
  even without Cartopy/GEOS/PROJ installed.
"""

from __future__ import annotations

import os
from typing import Generator, List, Sequence, Tuple

import numpy as np
from matplotlib.colors import ListedColormap
import matplotlib

# Always use a non-GUI backend early to avoid backend switching warnings
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    _CARTOPY_AVAILABLE = True
except Exception:
    # Cartopy might be missing in lightweight installs; we can still produce frames.
    _CARTOPY_AVAILABLE = False

import src.utils.settings as settings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = ["warm_up_rendering_libraries", "render_map_as_globe"]


def warm_up_rendering_libraries() -> None:
    """
    Perform a tiny render to pay one-time library init cost up front.
    Runs even when Cartopy is missing.
    """
    try:
        if _CARTOPY_AVAILABLE:
            fig = plt.figure(figsize=(0.1, 0.1), dpi=10)
            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax.set_global()
            plt.close(fig)
        else:
            # Minimal figure to initialize just matplotlib
            fig = plt.figure(figsize=(0.1, 0.1), dpi=10)
            ax = fig.add_subplot(1, 1, 1)
            ax.plot([0], [0])
            plt.close(fig)
        print("Rendering libraries are warm.")
    except Exception as e:
        print(f"Warning: warm-up failed (non-fatal): {e}")


def render_map_as_globe(map_data: List[List[str]], map_seed: int) -> Generator[float, None, None]:
    """
    Generate and save a series of PNG images of a rotating globe (or a flat fallback),
    textured with the provided map data.

    Yields:
        Progress floats in [0.0, 1.0].
    """
    # Validate input
    if not map_data or not map_data[0]:
        raise ValueError("render_map_as_globe: empty map_data")

    # Prepare output directory
    base_image_dir = "image"
    frame_dir_name = "globe_frames"
    frame_dir = os.path.join(base_image_dir, frame_dir_name)
    os.makedirs(frame_dir, exist_ok=True)

    # If frames exist, clear them to avoid mixing themes/seeds
    for fname in list_files(frame_dir):
        try:
            os.remove(os.path.join(frame_dir, fname))
        except OSError:
            pass

    print(f"Generating globe frames for map seed {map_seed} in '{frame_dir}/'...")

    # Convert categorical terrain map -> numeric grid
    color_map = ListedColormap(_terrain_colors())
    numeric_grid = _encode_map(map_data)

    # Choose renderer
    if _CARTOPY_AVAILABLE:
        yield from _render_with_cartopy(numeric_grid, color_map, frame_dir)
    else:
        print("Cartopy not available: using flat fallback renderer.")
        yield from _render_flat_fallback(numeric_grid, color_map, frame_dir)

    print(f"Done! All {settings.GLOBE_NUM_FRAMES} frames have been generated.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def list_files(path: str) -> Sequence[str]:
    try:
        return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    except Exception:
        return []


def _terrain_colors() -> List[Tuple[float, float, float]]:
    """
    Return list of RGB colors (0-1 float) for terrain in settings order.
    """
    # settings.GLOBE_TERRAIN_COLORS likely are integer RGB tuples 0..255
    cols = []
    for col in settings.GLOBE_TERRAIN_COLORS:
        if isinstance(col, (tuple, list)) and len(col) >= 3:
            r, g, b = col[:3]
            cols.append((r / 255.0, g / 255.0, b / 255.0))
        else:
            # fallback gray
            cols.append((0.5, 0.5, 0.5))
    if not cols:
        cols = [(0.2, 0.4, 0.8), (0.2, 0.7, 0.3), (0.6, 0.6, 0.6)]
    return cols


def _encode_map(map_data: List[List[str]]) -> np.ndarray:
    """
    Encode terrain strings -> numeric indices based on settings.TERRAIN_TYPES.
    Unknown keys map to 0.
    """
    terrain_index = {name: i for i, name in enumerate(settings.TERRAIN_TYPES)}
    h = len(map_data)
    w = len(map_data[0])
    out = np.zeros((h, w), dtype=np.int16)
    for y in range(h):
        row = map_data[y]
        for x in range(w):
            out[y, x] = terrain_index.get(row[x], 0)
    return out


# ---------------------------------------------------------------------------
# Cartopy path (preferred)
# ---------------------------------------------------------------------------

def _render_with_cartopy(numeric_grid: np.ndarray,
                         cmap: ListedColormap,
                         frame_dir: str) -> Generator[float, None, None]:
    # Longitude/latitude grids
    map_h, map_w = numeric_grid.shape
    lons = np.linspace(-180, 180, map_w)
    lats = np.linspace(90, -90, map_h)
    lons, lats = np.meshgrid(lons, lats)

    total = max(1, settings.GLOBE_NUM_FRAMES)
    dpi = float(settings.GLOBE_IMAGE_SIZE_PIXELS) / 5.0

    for i in range(total):
        longitude = -180.0 + (360.0 * i / total)
        projection = ccrs.Orthographic(central_longitude=longitude, central_latitude=20)

        fig = plt.figure(figsize=(5, 5), dpi=dpi)
        ax = fig.add_subplot(1, 1, 1, projection=projection)
        ax.set_global()

        # Base ocean fill (zorder=0)
        try:
            ax.add_feature(cfeature.OCEAN, zorder=0, facecolor=cmap.colors[0])
        except Exception:
            # If cfeature is problematic, just clear the face
            ax.background_patch.set_facecolor(cmap.colors[0])

        # Project the terrain data
        ax.pcolormesh(
            lons, lats, numeric_grid,
            transform=ccrs.PlateCarree(),
            cmap=cmap,
            shading="auto",
            zorder=1
        )

        fname = os.path.join(frame_dir, f"frame_{i:03d}.png")
        try:
            plt.savefig(fname, dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0)
        finally:
            plt.close(fig)

        yield (i + 1) / total


# ---------------------------------------------------------------------------
# Flat fallback (no Cartopy required)
# ---------------------------------------------------------------------------

def _render_flat_fallback(numeric_grid: np.ndarray,
                          cmap: ListedColormap,
                          frame_dir: str) -> Generator[float, None, None]:
    """
    Simple equirectangular "rotation": roll columns across frames and save.
    Produces square PNGs sized to GLOBE_IMAGE_SIZE_PIXELS. Not a real sphere,
    but good enough to keep the game running on minimal installs.
    """
    total = max(1, settings.GLOBE_NUM_FRAMES)
    size = int(settings.GLOBE_IMAGE_SIZE_PIXELS)
    h, w = numeric_grid.shape

    # Convert numeric grid -> RGB image (0..255)
    colors = np.asarray(cmap.colors, dtype=np.float32)  # (N, 3)
    rgb = colors[numeric_grid.clip(0, len(colors) - 1)]
    rgb8 = (rgb * 255.0).astype(np.uint8)  # (h, w, 3)

    # Precompute a circular alpha mask for a "disc" look
    yy, xx = np.mgrid[:size, :size]
    cx, cy = (size - 1) / 2.0, (size - 1) / 2.0
    r = size * 0.5 * 0.98
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    alpha = (dist <= r).astype(np.uint8) * 255  # (size, size)

    for i in range(total):
        # Horizontal shift to simulate rotation
        shift = int(round((i / total) * w))
        rolled = np.roll(rgb8, shift=shift, axis=1)  # (h, w, 3)

        # Resize equirectangular map to the target square "disc"
        # Use matplotlib's imresize via plt.imshow + save, to avoid extra deps.
        fig = plt.figure(figsize=(5, 5), dpi=size / 5.0)
        ax = fig.add_subplot(1, 1, 1)
        ax.axis("off")
        ax.imshow(rolled, interpolation="nearest")
        ax.set_position([0.0, 0.0, 1.0, 1.0])

        # Render into a buffer and apply circular alpha
        fname = os.path.join(frame_dir, f"frame_{i:03d}.png")
        fig.canvas.draw()
        wbuf, hbuf = fig.canvas.get_width_height()
        # RGB string to array
        buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        buf = buf.reshape((hbuf, wbuf, 3))

        # Center-crop/pad to exact (size, size)
        buf_sq = _center_square(buf, size)

        # Apply circular alpha mask
        rgba = np.dstack([buf_sq, alpha])

        plt.imsave(fname, rgba.astype(np.uint8))
        plt.close(fig)

        yield (i + 1) / total


def _center_square(img: np.ndarray, size: int) -> np.ndarray:
    """
    Center-crop or pad `img` to an exact square of `size` x `size`.
    Assumes img is HxWx3 uint8.
    """
    h, w = img.shape[:2]
    # Scale shortest side to match size, then center-crop/pad
    scale = size / min(h, w)
    nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))

    # Resize using matplotlib (keeps dependencies minimal)
    fig = plt.figure(figsize=(5, 5), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    ax.axis("off")
    ax.imshow(img, interpolation="bilinear")
    ax.set_position([0.0, 0.0, 1.0, 1.0])
    fig.set_size_inches(nw / 100.0, nh / 100.0)
    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
    buf = buf.reshape((nh, nw, 3))
    plt.close(fig)

    # Center crop/pad to (size, size)
    out = np.zeros((size, size, 3), dtype=np.uint8)
    y0 = max(0, (size - nh) // 2)
    x0 = max(0, (size - nw) // 2)
    ys = max(0, (nh - size) // 2)
    xs = max(0, (nw - size) // 2)
    y1 = min(size, y0 + nh)
    x1 = min(size, x0 + nw)
    out[y0:y1, x0:x1] = buf[ys:ys + (y1 - y0), xs:xs + (x1 - x0)]
    return out


