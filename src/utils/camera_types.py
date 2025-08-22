# camera_types.py
+from __future__ import annotations
+
+# Fix F821 by importing missing typing names and making pygame annotations lazy.
+from typing import Protocol, Tuple, TYPE_CHECKING
+
+# Import pygame for type checking only; this keeps CI/headless runs safe.
+if TYPE_CHECKING:  # pragma: no cover
+    import pygame  # noqa: F401

+class CameraLike(Protocol):
+    zoom: float
+    position: "pygame.Vector2"
+    def get_visible_world_rect(self, margin: float = 0.0) -> "pygame.Rect": ...
+    def apply(self, rect: "pygame.Rect") -> "pygame.Rect": ...
+    def world_to_screen(self, world_pos: Tuple[float, float]) -> "pygame.Vector2": ...
+    def screen_to_world(self, screen_pos: Tuple[int, int]) -> "pygame.Vector2": ...
