diff --git a/src/rendering/globe_renderer.py b/src/rendering/globe_renderer.py
index 0000000..0000001 100644
--- a/src/rendering/globe_renderer.py
+++ b/src/rendering/globe_renderer.py
@@
-"""
-Handles the generation of globe animation frames based on map data.
-"""
+"""
+Handles the generation of globe animation frames based on map data.
+Fix for Issue #37: avoid drawing real-world coastlines/outlines by not using
+Natural Earth features (OCEAN/LAND). We color the globe via the axes'
+background patch and render only our procedural data.
+"""
 import os
 from typing import Generator, List
 
 import cartopy.crs as ccrs
 import matplotlib.pyplot as plt
-import cartopy.feature as cfeature
 import numpy as np
 from matplotlib.colors import ListedColormap
 
 import src.utils.settings as settings
 
@@ def warm_up_rendering_libraries() -> None:
         ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
         ax.set_global()  # A simple cartopy operation.
+        ax.set_axis_off()
 
         # Immediately close it to free memory.
         plt.close(fig)
         print("Rendering libraries are warm.")
     except Exception as e:
         # If this fails, it's not critical, but we should log it.
         print(f"Warning: Failed to warm up rendering libraries: {e}")
 
 def render_map_as_globe(map_data: List[List[str]], map_seed: int) -> Generator[float, None, None]:
@@
-    for i in range(settings.GLOBE_NUM_FRAMES):
+    for i in range(settings.GLOBE_NUM_FRAMES):
         longitude = -180 + (360 * i / settings.GLOBE_NUM_FRAMES)
 
         projection = ccrs.Orthographic(central_longitude=longitude, central_latitude=20)
 
-        dpi = settings.GLOBE_IMAGE_SIZE_PIXELS / 5
-        fig = plt.figure(figsize=(5, 5), dpi=dpi)
-        ax = fig.add_subplot(1, 1, 1, projection=projection)
+        dpi = settings.GLOBE_IMAGE_SIZE_PIXELS / 5
+        fig = plt.figure(figsize=(5, 5), dpi=dpi, facecolor="none")
+        ax = fig.add_subplot(1, 1, 1, projection=projection)
         ax.set_global()
+        ax.set_axis_off()  # no ticks/frames
 
-        # --- Paint the map data onto the globe ---
-        # First, draw a solid ocean color as the base layer.
-        ax.add_feature(cfeature.OCEAN, zorder=0, facecolor=settings.GLOBE_TERRAIN_COLORS[0])
+        # --- Paint the map data onto the globe ---
+        # Base ocean color without Natural Earth features (prevents real Earth outlines).
+        # Using the axes' background patch colors the sphere region only.
+        ax.background_patch.set_facecolor(settings.GLOBE_TERRAIN_COLORS[0])
+        # Remove any default outline around the globe boundary (ring).
+        if hasattr(ax, "outline_patch"):
+            ax.outline_patch.set_edgecolor("none")
 
         # Then, draw the generated terrain data over the ocean.
         ax.pcolormesh(
             lons, lats, numerical_data,
             transform=ccrs.PlateCarree(),
-            cmap=color_map,
-            shading='auto'
+            cmap=color_map,
+            shading="auto",
+            zorder=1
         )
 
         # --- Save the frame ---
         filename = os.path.join(frame_dir, f"frame_{str(i).zfill(3)}.png")
         try:
             plt.savefig(
-                filename, dpi=dpi, transparent=True,
+                filename, dpi=dpi, transparent=True,
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


# --------------------------------- Defaults / toggles ---------------------------------
# These reads are defensive, so the module works even if settings doesn't define them.
GLOBE_TILT_LAT: float = getattr(settings, "GLOBE_TILT_LAT", 20.0)
GLOBE_DRAW_COASTLINES: bool = getattr(settings, "GLOBE_DRAW_COASTLINES", True)
GLOBE_DRAW_BORDERS: bool = getattr(settings, "GLOBE_DRAW_BORDERS", False)
GLOBE_DRAW_GRIDLINES: bool = getattr(settings, "GLOBE_DRAW_GRIDLINES", False)
GLOBE_COASTLINE_COLOR: Tuple[float, float, float] = getattr(
    settings, "GLOBE_COASTLINE_COLOR", (0.1, 0.1, 0.1)
)
GLOBE_BORDER_COLOR: Tuple[float, float, float] = getattr(
    settings, "GLOBE_BORDER_COLOR", (0.1, 0.1, 0.1)
)
GLOBE_GRIDLINE_COLOR: Tuple[float, float, float] = getattr(
    settings, "GLOBE_GRIDLINE_COLOR", (0.2, 0.2, 0.2)
)
GLOBE_FRAME_PREFIX: str = getattr(settings, "GLOBE_FRAME_PREFIX", "frame_")
GLOBE_CACHE_DIRNAME: str = getattr(settings, "GLOBE_CACHE_DIRNAME", "globe_cache")
GLOBE_FRAMES_DIRNAME: str = getattr(settings, "GLOBE_FRAMES_DIRNAME", "globe_frames")
GLOBE_USE_TRANSPARENT: bool = getattr(settings, "GLOBE_USE_TRANSPARENT", True)

# --------------------------------- Small datatypes ------------------------------------
@dataclass(frozen=True)
class GlobeMeta:
    seed: int
    width: int
    height: int
    frames: int
    colors_hash: str  # hash of palette for quick mismatch detection


# --------------------------------- Backend warm-up ------------------------------------
def warm_up_rendering_libraries() -> None:
    """
    Performs a trivial rendering operation to trigger the one-time
    initialization cost of matplotlib and cartopy. This avoids a long
    pause during the first real globe generation.
    """
    print("Warming up rendering libraries...")
    try:
        # Ensure a non-GUI backend for headless safety.
        try:
            plt.switch_backend("Agg")
        except Exception:
            # It's already set in some envs; ignore.
            pass

        # Tiny throwaway figure
        fig = plt.figure(figsize=(0.1, 0.1), dpi=10)
        ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        ax.set_global()
        plt.close(fig)
        print("Rendering libraries are warm.")
    except Exception as e:
        print(f"Warning: Failed to warm up rendering libraries: {e}")


# --------------------------------- Utilities / cache ----------------------------------
def _hash_colors(colors: Sequence[Tuple[int, int, int]]) -> str:
    """
    Creates a stable hash from a list of RGB or RGBA colors.
    Ignores the alpha channel for hashing.
    """
    h = hashlib.sha256()
    for color_tuple in colors:
        r, g, b = color_tuple[:3]  # Use only the first 3 components (RGB)
    return h.hexdigest()


def _meta_path(dir_path: str) -> str:
    return os.path.join(dir_path, "meta.json")


def _write_meta(dir_path: str, meta: GlobeMeta) -> None:
    with open(_meta_path(dir_path), "w", encoding="utf-8") as f:
        json.dump(meta.__dict__, f)


def _read_meta(dir_path: str) -> Optional[GlobeMeta]:
    try:
        with open(_meta_path(dir_path), "r", encoding="utf-8") as f:
            data = json.load(f)
        return GlobeMeta(**data)
    except Exception:
        return None


def _safe_clear_dir(path: str) -> None:
    if not os.path.isdir(path):
        return
    for name in os.listdir(path):
        fp = os.path.join(path, name)
        try:
            if os.path.isfile(fp) or os.path.islink(fp):
                os.remove(fp)
        except Exception as e:
            print(f"Warning: failed to remove '{fp}': {e}")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _frame_name(idx: int) -> str:
    return f"{GLOBE_FRAME_PREFIX}{str(idx).zfill(3)}.png"


def _frames_complete(path: str, count: int) -> bool:
    if not os.path.isdir(path):
        return False
    for i in range(count):
        if not os.path.isfile(os.path.join(path, _frame_name(i))):
            return False
    return True


def _copy_frames(src: str, dst: str, count: int) -> Generator[float, None, None]:
    """Copy frames with progress, overwriting dst; yields [0..1]."""
    _ensure_dir(dst)
    _safe_clear_dir(dst)
    for i in range(count):
        filename = _frame_name(i)
        shutil.copy2(os.path.join(src, filename), os.path.join(dst, filename))
        yield (i + 1) / count


def build_numerical_grid(map_data: List[List[str]]) -> np.ndarray:
    """
    Convert map string grid into a small uint8 array using the terrain order
    in settings.TERRAIN_TYPES. Unrecognized cells fall back to index 0.
    """
    terrain_map: Dict[str, int] = {name: i for i, name in enumerate(settings.TERRAIN_TYPES)}
    h = len(map_data)
    w = 0 if h == 0 else len(map_data[0])
    out = np.zeros((h, w), dtype=np.uint8)
    for y, row in enumerate(map_data):
        for x, cell in enumerate(row):
            out[y, x] = np.uint8(terrain_map.get(cell, 0))
    return out


# ----------------------------- Public: single-frame render -----------------------------
def render_single_globe_frame(
    numerical_data: np.ndarray,
    cmap: ListedColormap,
    *,
    central_longitude: float = 0.0,
    central_latitude: float = GLOBE_TILT_LAT,
    image_pixels: int = getattr(settings, "GLOBE_IMAGE_SIZE_PIXELS", 1024),
    out_file: Optional[str] = None,
) -> Optional[str]:
    """
    NEW: Render a single globe frame to `out_file` (or return a PNG path if saved to a temp file).
    Returns the path written, or None if saving is suppressed.
    """
    try:
        try:
            plt.switch_backend("Agg")
        except Exception:
            pass

        # Lon/lat grid for equirectangular input
        map_h, map_w = numerical_data.shape
        lons = np.linspace(-180, 180, map_w)
        lats = np.linspace(90, -90, map_h)
        lons, lats = np.meshgrid(lons, lats)

        proj = ccrs.Orthographic(central_longitude=central_longitude, central_latitude=central_latitude)
        dpi = image_pixels / 5  # 5 inches @ dpi
        fig = plt.figure(figsize=(5, 5), dpi=dpi)
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        ax.set_global()

        # Base ocean (index 0 expected to be ocean color)
        # Matplotlib expects colors as floats in [0, 1] range.
        ocean_color_int = settings.GLOBE_TERRAIN_COLORS[0]
        ocean_color_float = [c / 255.0 for c in ocean_color_int]
        ax.add_feature(cfeature.OCEAN, zorder=0, facecolor=ocean_color_float)

        # Terrain texture
        ax.pcolormesh(
            lons,
            lats,
            numerical_data,
            transform=ccrs.PlateCarree(),
            cmap=cmap,
            shading="auto",
            rasterized=True,  # speed-up vector backends
            zorder=1,
        )

        # Optional overlays
        if GLOBE_DRAW_COASTLINES:
            ax.coastlines(color=GLOBE_COASTLINE_COLOR, linewidth=0.5, zorder=2)
        if GLOBE_DRAW_BORDERS:
            ax.add_feature(cfeature.BORDERS, edgecolor=GLOBE_BORDER_COLOR, linewidth=0.4, zorder=2)
        if GLOBE_DRAW_GRIDLINES:
            gl = ax.gridlines(draw_labels=False, color=GLOBE_GRIDLINE_COLOR, linewidth=0.3, alpha=0.5, zorder=2)
            # (Cartopy draws labels via gl.xlabels/etc.; we keep them off)

        # Save if requested
        if out_file:
            plt.savefig(out_file, dpi=dpi, transparent=GLOBE_USE_TRANSPARENT, bbox_inches="tight", pad_inches=0)
            return out_file
    finally:
        plt.close("all")
    return None


# ----------------------------- Public: animated frames (kept API) ----------------------
def render_map_as_globe(map_data: List[List[str]], map_seed: int) -> Generator[float, None, None]:
    """
    Generates and saves a series of PNG images of a rotating globe, textured with
    the provided map data. **Public API preserved**:
        Args:
            map_data: 2D list of terrain names (strings)
            map_seed: seed used for caching
        Yields:
            Progress float in [0.0, 1.0]
    """
    base_image_dir = "image"
    frame_dir = os.path.join(base_image_dir, GLOBE_FRAMES_DIRNAME)
    cache_root = os.path.join(base_image_dir, GLOBE_CACHE_DIRNAME)
    _ensure_dir(cache_root)

    # Prepare numerical grid & palette
    numerical_data = build_numerical_grid(map_data)
    # Matplotlib expects colors as floats in [0, 1] range.
    # Convert the RGBA integer colors from settings.
    float_colors = [[c / 255.0 for c in color] for color in settings.GLOBE_TERRAIN_COLORS]
    color_map = ListedColormap(float_colors)

    # Compute cache key
    meta = GlobeMeta(
        seed=map_seed,
        width=int(numerical_data.shape[1]),
        height=int(numerical_data.shape[0]),
        frames=int(getattr(settings, "GLOBE_NUM_FRAMES", 60)),
        colors_hash=_hash_colors(settings.GLOBE_TERRAIN_COLORS),
    )
    cache_dir = os.path.join(cache_root, f"seed_{meta.seed}_{meta.width}x{meta.height}_{meta.frames}_{meta.colors_hash[:10]}")

    force_regen = os.environ.get("WORLDOM_GLOBE_FORCE_REGENERATE") == "1"

    # If cache exists and is complete, copy to live frames dir (or skip copy if already current)
    cached_meta = _read_meta(cache_dir)
    if (not force_regen) and cached_meta == meta and _frames_complete(cache_dir, meta.frames):
        # If live dir already matches cache, skip copying
        live_meta = _read_meta(frame_dir)
        if live_meta == meta and _frames_complete(frame_dir, meta.frames):
            # Already up-to-date: just yield a complete progress ramp quickly.
            for i in range(meta.frames):
                yield (i + 1) / meta.frames
            return
        # Copy cached frames -> live
        _ensure_dir(frame_dir)
        _safe_clear_dir(frame_dir)
        for p in _copy_frames(cache_dir, frame_dir, meta.frames):
            yield p
        # Write meta to live
        _write_meta(frame_dir, meta)
        return

    # Otherwise, regenerate into live dir and refresh cache
    _ensure_dir(frame_dir)
    _safe_clear_dir(frame_dir)

    # Also prepare cache dir (freshly)
    _ensure_dir(cache_dir)
    _safe_clear_dir(cache_dir)

    # Longitude range sweep
    n_frames = meta.frames
    for i in range(n_frames):
        longitude = -180.0 + (360.0 * i / n_frames)

        # Render once, save to both live and cache
        filename = _frame_name(i)
        live_path = os.path.join(frame_dir, filename)
        cache_path = os.path.join(cache_dir, filename)

        try:
            render_single_globe_frame(
                numerical_data,
                color_map,
                central_longitude=longitude,
                central_latitude=GLOBE_TILT_LAT,
                image_pixels=getattr(settings, "GLOBE_IMAGE_SIZE_PIXELS", 1024),
                out_file=live_path,
            )
            # duplicate into cache
            shutil.copy2(live_path, cache_path)
        except Exception as e:
            print(f"Error saving frame {filename}: {e}")

        yield (i + 1) / n_frames

    # Write meta to both locations
    try:
        _write_meta(frame_dir, meta)
        _write_meta(cache_dir, meta)
    except Exception as e:
        print(f"Warning: failed to write globe metadata: {e}")

    print(f"Done! All {n_frames} frames generated for seed {map_seed} at '{frame_dir}/'.")


# --------------------------------- Optional: GIF export --------------------------------
def export_globe_gif(
    frames_dir: str = os.path.join("image", GLOBE_FRAMES_DIRNAME),
    out_path: str = os.path.join("image", "globe_preview.gif"),
    fps: int = getattr(settings, "GLOBE_GIF_FPS", 12),
) -> Optional[str]:
    """
    NEW (optional): Create a looping GIF from the current frame directory.
    Requires `imageio` to be installed. Returns output path or None on failure.
    """
    try:
        import imageio.v3 as iio  # lazy import; optional dependency
    except Exception:
        print("export_globe_gif: imageio not available; skipping GIF export.")
        return None

    try:
        files = sorted(
            [f for f in os.listdir(frames_dir) if f.lower().endswith(".png")]
        )
        if not files:
            print("export_globe_gif: no frames to export.")
            return None
        images = [iio.imread(os.path.join(frames_dir, f)) for f in files]
        iio.imwrite(out_path, images, loop=0, fps=max(1, fps))
        print(f"Saved GIF preview to '{out_path}'.")
        return out_path
    except Exception as e:
        print(f"export_globe_gif: failed to export GIF: {e}")
        return None
