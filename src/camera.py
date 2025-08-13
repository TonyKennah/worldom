# c:/game/worldom/camera.py
"""
Camera system for a 2D world (pygame).
- Smooth, mouse-anchored zoom with optional easing
- Inertial panning (keyboard, edge scroll, middle-mouse drag)
- Toroidal wrap *or* clamped bounds
- Follow/center helpers with soft deadzone
- Screen shake (trauma-based)
- Culling & parallax utilities
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

import math
import random
import pygame

# ---------------------------------------------------------------------
# External settings expected to exist in your project. If they don't,
# the fallback values below will be used.
# ---------------------------------------------------------------------
try:
    from settings import (
        CAMERA_SPEED,
        EDGE_SCROLL_SPEED,
        EDGE_SCROLL_BOUNDARY,
        DEBUG_PANEL_HEIGHT,
    )
except Exception:  # pragma: no cover - dev fallback
    CAMERA_SPEED = 1200.0
    EDGE_SCROLL_SPEED = 1200.0
    EDGE_SCROLL_BOUNDARY = 24
    DEBUG_PANEL_HEIGHT = 0


# ---------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------

@dataclass
class ZoomState:
    """Encapsulates the state and logic for camera zooming."""
    levels: Tuple[float, ...] = (0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
    index: int = 6  # default to 2.0x
    current: float = 2.0
    target: float = 2.0
    lerp_rate: float = 12.0  # higher = snappier zoom

    def __post_init__(self) -> None:
        # Ensure current/target align with index/levels
        self.index = max(0, min(self.index, len(self.levels) - 1))
        self.current = float(self.levels[self.index])
        self.target = self.current

    def step(self, delta: int) -> None:
        """Move zoom target by an index delta, clamped to valid levels."""
        self.index = max(0, min(self.index + delta, len(self.levels) - 1))
        self.target = float(self.levels[self.index])

    def set_to_level(self, value: float) -> None:
        """Snap to the nearest zoom level to `value`."""
        nearest = min(range(len(self.levels)), key=lambda i: abs(self.levels[i] - value))
        self.index = nearest
        self.current = float(self.levels[nearest])
        self.target = self.current

    def update(self, dt: float) -> bool:
        """
        Smoothly approach target. Returns True if zoom changed this frame.
        Smooth step: current += (target - current) * (1 - exp(-rate*dt))
        """
        if self.current == self.target:
            return False
        t = 1.0 - math.exp(-self.lerp_rate * max(dt, 0.0))
        prev = self.current
        self.current = prev + (self.target - prev) * t
        # Snap if close
        if abs(self.current - self.target) < 1e-3:
            self.current = self.target
        return self.current != prev


# ---------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------

class Camera:
    """Manages the game's viewport, handling zoom & panning with polish."""

    def __init__(self, width: int, height: int) -> None:
        """Initialize camera."""
        self.width = int(width)
        self.height = int(height)
        self.screen_center = pygame.Vector2(self.width * 0.5, self.height * 0.5)

        # World-space position of the *camera center*.
        self.position = pygame.Vector2(0.0, 0.0)

        # Movement/inertia
        self.velocity = pygame.Vector2(0.0, 0.0)
        self.accel_keyboard = float(CAMERA_SPEED)
        self.accel_edge = float(EDGE_SCROLL_SPEED)
        self.drag = 8.0  # higher = stronger deceleration
        self.inertia_enabled = True

        # Drag-panning
        self._dragging = False
        self._last_mouse = pygame.Vector2(0.0, 0.0)
        self.drag_button = pygame.BUTTON_MIDDLE  # middle mouse drag to pan

        # Zoom
        self.zoom_state = ZoomState()
        self.zoom_anchors_mouse = True   # keep mouse world point stable on zoom
        self.zoom_invert_wheel = False   # set True to invert wheel

        # Bounds / wrapping
        self.wrap_x = True
        self.wrap_y = True

        # Shake (trauma-based)
        self._trauma = 0.0         # 0..1
        self._trauma_decay = 1.6   # per second
        self._shake_freq = 42.0    # Hz-ish
        self._shake_seed = random.random() * 10_000.0

        # Optional follow behavior (soft deadzone)
        self.follow_deadzone_frac = pygame.Vector2(0.20, 0.20)  # fraction of screen
        self.follow_strength = 10.0  # smoothing toward target

    # -------------------------
    # Public utilities
    # -------------------------

    def set_window_size(self, width: int, height: int) -> None:
        """Update camera on window resize."""
        self.width = int(width)
        self.height = int(height)
        self.screen_center.update(self.width * 0.5, self.height * 0.5)

    def center_on(self, world_pos: Tuple[float, float]) -> None:
        """Instantly center the camera on a world position."""
        self.position.update(world_pos)

    def follow(self, target_world: pygame.Vector2, dt: float) -> None:
        """
        Soft-follow a target using a rectangular deadzone in *screen space*.
        The camera recenters only when target leaves the deadzone.
        """
        # Convert target's world pos into screen space
        target_screen = self.world_to_screen(target_world)

        dz_w = self.width * self.follow_deadzone_frac.x * 0.5
        dz_h = self.height * self.follow_deadzone_frac.y * 0.5
        box_min = self.screen_center - pygame.Vector2(dz_w, dz_h)
        box_max = self.screen_center + pygame.Vector2(dz_w, dz_h)

        offset = pygame.Vector2(0, 0)
        if target_screen.x < box_min.x:
            offset.x = target_screen.x - box_min.x
        elif target_screen.x > box_max.x:
            offset.x = target_screen.x - box_max.x

        if target_screen.y < box_min.y:
            offset.y = target_screen.y - box_min.y
        elif target_screen.y > box_max.y:
            offset.y = target_screen.y - box_max.y

        if offset.length_squared() > 0:
            # Translate the offset into world units and move the camera
            world_delta = offset / max(self.zoom_state.current, 1e-6)
            self.position += world_delta * min(1.0, self.follow_strength * dt)

    def add_shake(self, magnitude: float) -> None:
        """Adds camera shake 'trauma' (0..1). Magnitude is additive."""
        self._trauma = max(0.0, min(1.0, self._trauma + magnitude))

    def screen_to_world(self, screen_pos: Tuple[int, int]) -> pygame.Vector2:
        """Convert screen -> world coordinates."""
        # Remove shake from the mapping so world picks are stable
        screen_vec = pygame.Vector2(screen_pos) - self.screen_center
        world_offset = screen_vec / max(self.zoom_state.current, 1e-6)
        return self.position + world_offset

    def world_to_screen(self, world_pos: Tuple[float, float]) -> pygame.Vector2:
        """Convert world -> screen coordinates (includes shake)."""
        screen_offset = (pygame.Vector2(world_pos) - self.position) * self.zoom_state.current
        return self.screen_center + screen_offset + self._shake_offset()

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        """Transform a world-space rect to a screen-space rect."""
        tl = self.world_to_screen(rect.topleft)
        w = rect.width * self.zoom_state.current
        h = rect.height * self.zoom_state.current

        # Define a safe range for coordinates to prevent pygame errors
        # with very large or small numbers that can result from floats.
        SAFE_MIN = -2_000_000_000
        SAFE_MAX = 2_000_000_000

        # Clamp all values to the safe range before creating the Rect
        safe_x = max(SAFE_MIN, min(round(tl.x), SAFE_MAX))
        safe_y = max(SAFE_MIN, min(round(tl.y), SAFE_MAX))
        safe_w = max(0, min(round(w), SAFE_MAX))  # Width/height can't be negative
        safe_h = max(0, min(round(h), SAFE_MAX))

        return pygame.Rect(safe_x, safe_y, safe_w, safe_h)

    def apply_point(self, world_pos: Tuple[float, float]) -> Tuple[int, int]:
        """Transform a world-space point to screen-space point."""
        p = self.world_to_screen(world_pos)
        return (int(round(p.x)), int(round(p.y)))

    def get_visible_world_rect(self, margin: float = 0.0) -> pygame.Rect:
        """Returns the world-space rectangle currently visible by the camera."""
        top_left = self.screen_to_world((0 - margin, 0 - margin))
        bot_right = self.screen_to_world((self.width + margin, self.height + margin))
        x0, y0 = top_left
        x1, y1 = bot_right
        # Ensure positive width/height even if zoom flips (it shouldn't)
        return pygame.Rect(
            int(math.floor(min(x0, x1))),
            int(math.floor(min(y0, y1))),
            int(math.ceil(abs(x1 - x0))),
            int(math.ceil(abs(y1 - y0))),
        )

    def is_world_rect_visible(self, rect: pygame.Rect, margin: float = 0.0) -> bool:
        """Quick culling test in world space."""
        return self.get_visible_world_rect(margin).colliderect(rect)

    def parallax_screen_point(
        self, world_pos: Tuple[float, float], factor: float
    ) -> Tuple[int, int]:
        """
        World -> parallaxed screen point. factor < 1 = moves slower (background),
        factor > 1 = faster (foreground).
        """
        parallax_pos = self.position * (1.0 - factor) + pygame.Vector2(world_pos) * factor
        p = self.world_to_screen(parallax_pos)
        return (int(round(p.x)), int(round(p.y)))

    # -------------------------
    # Frame update
    # -------------------------

    def update(
        self,
        dt: float,
        events: Sequence[pygame.event.Event],
        map_width_pixels: int,
        map_height_pixels: int,
        follow_target: Optional[pygame.Vector2] = None,
        edge_scroll_exclusion_zone: Optional[pygame.Rect] = None,
    ) -> None:
        """
        Update camera each frame:
        - input (keyboard / edge / drag)
        - inertia & drag
        - zoom easing
        - wrapping/clamping
        - optional follow
        """
        # Zoom first so subsequent mappings are correct this frame
        self._handle_mouse_input(events)
        self.zoom_state.update(dt)

        # Movement inputs
        move_keyboard = self._keyboard_move_vector()
        move_edge = self._edge_scroll_vector(edge_scroll_exclusion_zone)

        # Mouse drag panning modifies position directly (it's not affected by inertia)
        self._handle_drag(events, dt)

        # Determine the target velocity based on inputs.
        # The speed values are in screen pixels/sec, so we divide by zoom
        # to get the correct world-space velocity.
        target_velocity = pygame.Vector2(0, 0)
        inv_zoom = 1.0 / max(self.zoom_state.current, 1e-6)
        if move_keyboard.length_squared() > 0:
            move_keyboard.normalize_ip()
            target_velocity += move_keyboard * self.accel_keyboard * inv_zoom
        if move_edge.length_squared() > 0:
            move_edge.normalize_ip()
            target_velocity += move_edge * self.accel_edge * inv_zoom

        if self.inertia_enabled:
            # With inertia, we smoothly accelerate towards the target velocity.
            # The 'drag' factor controls how quickly we reach the target speed.
            accel = (target_velocity - self.velocity) * self.drag
            self.velocity += accel * dt
            self.position += self.velocity * dt
        else:
            # Without inertia, we move directly at the target velocity.
            self.position += target_velocity * dt

        # Optional follow after inputs (soft corrective)
        if follow_target is not None:
            self.follow(follow_target, dt)

        # Apply wrapping/clamping
        self._apply_bounds(map_width_pixels, map_height_pixels)

        # Decay shake
        if self._trauma > 0.0:
            self._trauma = max(0.0, self._trauma - self._trauma_decay * dt)

    # -------------------------
    # Internal helpers
    # -------------------------

    def _keyboard_move_vector(self) -> pygame.Vector2:
        """WASD movement vector (unscaled)."""
        keys = pygame.key.get_pressed()
        v = pygame.Vector2(0, 0)
        if keys[pygame.K_w]:
            v.y -= 1
        if keys[pygame.K_s]:
            v.y += 1
        if keys[pygame.K_a]:
            v.x -= 1
        if keys[pygame.K_d]:
            v.x += 1
        return v

    def _edge_scroll_vector(self, exclusion_zone: Optional[pygame.Rect] = None) -> pygame.Vector2:
        """Edge-scroll vector (unscaled)."""
        if not pygame.mouse.get_focused():
            return pygame.Vector2(0, 0)

        mx, my = pygame.mouse.get_pos()
        mouse_pos = (mx, my)
        v = pygame.Vector2(0, 0)

        # If the mouse is inside a defined exclusion zone (like over UI buttons),
        # disable edge scrolling to prevent accidental camera movement.
        if exclusion_zone and exclusion_zone.collidepoint(mouse_pos):
            return v

        # Horizontal (outside debug panel height)
        if my >= DEBUG_PANEL_HEIGHT:
            if mx < EDGE_SCROLL_BOUNDARY:
                v.x -= 1
            elif mx > self.width - EDGE_SCROLL_BOUNDARY:
                v.x += 1

        # Vertical (top area's start is just below debug panel)
        if DEBUG_PANEL_HEIGHT <= my < DEBUG_PANEL_HEIGHT + EDGE_SCROLL_BOUNDARY:
            v.y -= 1
        elif my > self.height - EDGE_SCROLL_BOUNDARY:
            v.y += 1

        return v

    def _handle_drag(self, events: Sequence[pygame.event.Event], dt: float) -> None:
        """Middle-mouse drag panning in world units."""
        # We don't use dt here other than potential future smoothing
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == self.drag_button:
                self._dragging = True
                self._last_mouse = pygame.Vector2(pygame.mouse.get_pos())
            elif e.type == pygame.MOUSEBUTTONUP and e.button == self.drag_button:
                self._dragging = False

        if self._dragging:
            cur = pygame.Vector2(pygame.mouse.get_pos())
            delta_screen = cur - self._last_mouse
            self._last_mouse = cur
            # Convert screen delta to world delta (inverse of zoom)
            world_delta = delta_screen / max(self.zoom_state.current, 1e-6)
            self.position -= world_delta  # drag moves camera opposite to mouse

    def _handle_mouse_input(self, events: Sequence[pygame.event.Event]) -> None:
        """Zoom with mouse-wheel; keep mouse-anchored if enabled."""
        for event in events:
            if event.type == pygame.MOUSEWHEEL:
                # Pre-zoom world point under the mouse
                anchor_world = self.screen_to_world(pygame.mouse.get_pos()) if self.zoom_anchors_mouse else None

                dy = event.y
                if self.zoom_invert_wheel:
                    dy = -dy

                if dy > 0:
                    self.zoom_state.step(+1)
                elif dy < 0:
                    self.zoom_state.step(-1)

                # After setting target, we may want to *also* snap current if player is
                # flicking the wheel very fast (feel free to tweak this behavior)
                # Here we keep it smooth: no snap.

                if anchor_world is not None:
                    # Adjust position so that the world point under the mouse stays fixed
                    # wrt the screen while zoom animates. We compute the diff using the
                    # *new target* scale, which feels more immediate.
                    cur = pygame.Vector2(pygame.mouse.get_pos())
                    # Compute where the anchor would end up at target zoom, then offset.
                    # screen_to_world depends on current zoom; we need a manual mapping:
                    screen_vec = cur - self.screen_center
                    world_offset_at_target = screen_vec / self.zoom_state.target
                    desired_position = anchor_world - world_offset_at_target
                    self.position.update(desired_position)

    def _apply_bounds(self, map_w: int, map_h: int) -> None:
        """Apply wrap or clamp to camera position."""
        if self.wrap_x:
            self.position.x %= map_w
        else:
            # Clamp so you can't pan beyond edges (keep view in-bounds)
            half_w_world = (self.width * 0.5) / max(self.zoom_state.current, 1e-6)
            self.position.x = max(half_w_world, min(self.position.x, map_w - half_w_world))

        if self.wrap_y:
            self.position.y %= map_h
        else:
            half_h_world = (self.height * 0.5) / max(self.zoom_state.current, 1e-6)
            self.position.y = max(half_h_world, min(self.position.y, map_h - half_h_world))

    def _shake_offset(self) -> pygame.Vector2:
        """Compute per-frame shake offset from trauma."""
        if self._trauma <= 0.0:
            return pygame.Vector2(0, 0)

        # Use simple time-based noise (no pygame clock dependency here).
        t = pygame.time.get_ticks() * 0.001  # seconds
        mag = (self._trauma * self._trauma)  # square for nicer decay curve
        nx = math.sin((self._shake_seed + t) * self._shake_freq) * mag
        ny = math.cos((self._shake_seed * 0.5 + t * 1.3) * self._shake_freq) * mag
        # Shake amount in pixels (unscaled by zoom; screen-space shake)
        shake_px = 6.0
        return pygame.Vector2(nx * shake_px, ny * shake_px)
