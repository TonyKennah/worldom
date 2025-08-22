"""
Lightweight camera type hints and helpers.

- Uses `from __future__ import annotations` so pygame types in annotations
  don't need pygame at import-time (helps headless CI).
- Imports pygame only under TYPE_CHECKING to keep runtime import optional.
- Provides a `CameraLike` Protocol that your camera implementation can satisfy.
- Includes data-driven zoom steps and a `snap_zoom` helper.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import Protocol, Sequence, Tuple, TYPE_CHECKING

# Import pygame for type checking only; avoids runtime dependency on a display.
if TYPE_CHECKING:  # pragma: no cover
    import pygame  # noqa: F401

# ---- Zoom helpers -----------------------------------------------------------

DEFAULT_ZOOM_STEPS: Sequence[float] = (
    0.25,
    0.33,
    0.5,
    0.66,
    0.75,
    1.0,
    1.25,
    1.5,
    2.0,
    3.0,
    4.0,
)


def snap_zoom(z: float, steps: Sequence[float] = DEFAULT_ZOOM_STEPS) -> float:
    """
    Snap an arbitrary zoom value to the nearest allowed step.

    Example:
        snap_zoom(0.92) -> 1.0
        snap_zoom(1.38) -> 1.25 or 1.5 (nearest)

    Args:
        z: Current zoom.
        steps: Allowed zoom steps (must be sorted ascending).

    Returns:
        Nearest value from `steps`.
    """
    i = bisect_left(steps, z)
    if i == 0:
        return steps[0]
    if i == len(steps):
        return steps[-1]
    after = steps[i]
    before = steps[i - 1]
    return after if abs(after - z) < abs(z - before) else before


# ---- Camera protocol --------------------------------------------------------

class CameraLike(Protocol):
    """
    Minimal requirements for objects treated as a camera in the codebase.
    Any class implementing these attributes/methods will satisfy the protocol.
    """

    zoom: float
    position: "pygame.Vector2"

    def get_visible_world_rect(self, margin: float = 0.0) -> "pygame.Rect": ...
    def apply(self, rect: "pygame.Rect") -> "pygame.Rect": ...
    def world_to_screen(self, world_pos: Tuple[float, float]) -> "pygame.Vector2": ...
    def screen_to_world(self, screen_pos: Tuple[int, int]) -> "pygame.Vector2": ...


__all__ = [
    "CameraLike",
    "DEFAULT_ZOOM_STEPS",
    "snap_zoom",
]
