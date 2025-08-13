# camera_types.py
from __future__ import annotations
from typing import Protocol, Tuple
import pygame


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
