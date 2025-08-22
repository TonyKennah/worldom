# src/globe_renderer.py
from __future__ import annotations

from typing import Generator, List, Optional
import os


__all__ = [
    "warm_up_rendering_libraries",
    "render_map_as_globe",
]


def _lazy_imports():
    """
    Import heavy, optional deps only when needed so the module can be imported
    in CI without numpy/matplotlib/cartopy installed.
    """
    import importlib

    np = importlib.import_module("numpy")
    plt = importlib.import_module("matplotlib.pyplot")
    ccrs = importlib.import_module("cartopy.crs")
    cfeature = importlib.import_module("cartopy.feature")
    return np, plt, ccrs, cfeature


def warm_up_rendering_libraries() -> None:
    """
    Best-effort warm-up. Skips silently if optional deps are missing.
    """
    try:
        _, plt, ccrs, _ = _lazy_imports()
        # prefer Agg for headless CI
        try:
            plt.switch_backend("Agg")
        except Exception:
            pass

        fig = plt.figure(figsize=(0.1, 0.1), dpi=10)
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        ax.set_global()
        plt.close(fig)
        print("globe_renderer: rendering libraries warmed.")
    except Exception as e:
        # Do not fail import paths in CI—only warn.
        print(f"globe_renderer: warm-up skipped ({e}).")


def render_map_as_globe(
    map_data: List[List[str]],
    map_seed: int,
    *,
    out_dir: str = os.path.join("image", "globe_frames"),
    num_frames: int = 60,
    image_size_px: int = 512,
    center_lat: float = 20.0,
) -> Generator[float, None, None]:
    """
    Generate a sequence of globe frames. Imports heavy deps only when called.

    Yields:
        Progress in [0,1].
    """
    try:
        np, plt, ccrs, cfeature = _lazy_imports()
    except Exception as e:
        raise RuntimeError(
            "render_map_as_globe requires optional dependencies: numpy, matplotlib, cartopy"
        ) from e

    # headless-friendly backend
    try:
        plt.switch_backend("Agg")
    except Exception:
        pass

    # Prepare output folder
    os.makedirs(out_dir, exist_ok=True)

    # Build categorical colormap from terrain names (fallback colors)
    terrain_names = sorted({cell for row in map_data for cell in row})
    color_table = {
        name: (0.2, 0.4, 0.8) if i == 0 else (0.2 + 0.6 * (i / max(1, len(terrain_names) - 1)), 0.7, 0.3)
        for i, name in enumerate(terrain_names)
    }
    index_map = {name: i for i, name in enumerate(terrain_names)}
    numerical = np.array([[index_map.get(cell, 0) for cell in row] for row in map_data], dtype=np.int32)

    # Build lon/lat grids
    h, w = numerical.shape
    lons = np.linspace(-180.0, 180.0, w)
    lats = np.linspace(90.0, -90.0, h)
    lons, lats = np.meshgrid(lons, lats)

    # Create a color map for matplotlib
    from matplotlib.colors import ListedColormap  # local import

    palette = [color_table[name] for name in terrain_names]
    cmap = ListedColormap(palette)

    dpi = max(1, image_size_px // 5)

    for i in range(num_frames):
        lon = -180.0 + (360.0 * i / max(1, num_frames))
        proj = ccrs.Orthographic(central_longitude=lon, central_latitude=center_lat)

        fig = plt.figure(figsize=(5, 5), dpi=dpi)
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        ax.set_global()

        # base ocean color (index 0 if exists)
        ocean_color = palette[0] if palette else (0.2, 0.4, 0.8)
        try:
            ax.add_feature(cfeature.OCEAN, zorder=0, facecolor=ocean_color)
        except Exception:
            # cartopy feature may fail in constrained envs: just skip
            pass

        ax.pcolormesh(
            lons,
            lats,
            numerical,
            transform=ccrs.PlateCarree(),
            cmap=cmap,
            shading="auto",
        )

        fname = os.path.join(out_dir, f"frame_{i:03d}.png")
        try:
            fig.savefig(fname, bbox_inches="tight", pad_inches=0, transparent=True)
        finally:
            plt.close(fig)

        yield (i + 1) / float(num_frames)
