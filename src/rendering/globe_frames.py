# src/rendering/globe_frames.py
from __future__ import annotations

import os
from typing import List


__all__ = ["generate_globe_frames"]


def generate_globe_frames(
    map_data: List[List[str]],
    out_dir: str = os.path.join("image", "globe_frames"),
    *,
    seed: int = 0,
    frames: int = 60,
    size_px: int = 512,
) -> None:
    """
    Convenience wrapper that delegates to the top-level globe_renderer module.
    Heavy dependencies are imported lazily only when this function is called.
    """
    try:
        from globe_renderer import render_map_as_globe, warm_up_rendering_libraries
    except Exception as e:
        raise RuntimeError(
            "generate_globe_frames requires optional deps (numpy, matplotlib, cartopy)"
        ) from e

    warm_up_rendering_libraries()
    for _ in render_map_as_globe(
        map_data,
        map_seed=seed,
        out_dir=out_dir,
        num_frames=frames,
        image_size_px=size_px,
    ):
        # progress generator; ignore for now
        pass
