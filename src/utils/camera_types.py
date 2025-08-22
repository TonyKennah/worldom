# camera_types.py
from __future__ import annotations
from bisect import bisect_left
from typing import Sequence

DEFAULT_ZOOM_STEPS: Sequence[float] = (0.25, 0.33, 0.5, 0.66, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)

def snap_zoom(z: float, steps: Sequence[float] = DEFAULT_ZOOM_STEPS) -> float:
    i = bisect_left(steps, z)
    if i == 0:   return steps[0]
    if i == len(steps): return steps[-1]
    return steps[i] if abs(steps[i]-z) < abs(z-steps[i-1]) else steps[i-1]

class CameraLike(Protocol):
    """
    Structural protocol for camera utilities.
    Your Camera class doesn't need to inherit this; it just needs to match it.

    Expected attributes/methods:
      - position: pygame.Vector2               # world-space center
      - width: int; height: int                # screen size in pixels (for scissor helpers)
      - get_visible_world_rect(margin=0.0) -> pygame.Rect
      - apply(pygame.Rect) -> pygame.Rect      # world rect -> screen rect
      - world_to_screen((x, y)) -> pygame.Vector2
      - screen_to_world((sx, sy)) -> pygame.Vector2
    """
    position: pygame.Vector2
    width: int
    height: int

    def get_visible_world_rect(self, margin: float = 0.0) -> pygame.Rect: ...
    def apply(self, rect: pygame.Rect) -> pygame.Rect: ...
    def world_to_screen(self, world_pos: Tuple[float, float]) -> pygame.Vector2: ...
    def screen_to_world(self, screen_pos: Tuple[int, int]) -> pygame.Vector2: ...
