# c:/game/worldom/camera.py
"""
Camera system for a 2D world (pygame).

- Smooth, mouse‑anchored zoom with easing (anchor held stable during tween)
- Inertial panning (WASD/Arrows, edge scroll, middle‑mouse / Alt+LMB drag)
- Toroidal wrap *or* clamped bounds (per‑axis), robust for tiny worlds
- Follow/center helpers with soft deadzone & optional lookahead
- Screen shake (trauma‑based), configurable
- Culling & parallax utilities
- Tweened pan_to() with easing; speed modifiers (Shift/Alt)
- Fit/frame a rect (zoom_to_fit), batch point transforms, debug overlay hook
- Feature toggles: keyboard/edge/drag/zoom enable flags
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence, Tuple, List

import math
import random
import pygame

# ---------------------------------------------------------------------
# External settings (fallbacks if not present in your project).
# ---------------------------------------------------------------------
try:
    from src.utils.settings import (
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
# Constants
# ---------------------------------------------------------------------
_EPS = 1e-6
_SAFE_MIN = -2_000_000_000
_SAFE_MAX = 2_000_000_000


# ---------------------------------------------------------------------
# Easing
# ---------------------------------------------------------------------
def _ease_smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


@dataclass
class ZoomState:
    """Encapsulates the state and logic for camera zooming."""
    levels: Tuple[float, ...] = (0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
    index: int = 6  # default to 2.0x
    current: float = 2.0
    target: float = 2.0
    lerp_rate: float = 12.0  # higher = snappier zoom

    def __post_init__(self) -> None:
        self._sanitize_levels()
        self.index = max(0, min(self.index, len(self.levels) - 1))
        self.current = float(self.levels[self.index])
        self.target = self.current

    @property
    def at_target(self) -> bool:
        return abs(self.current - self.target) < 1e-3

    def step(self, delta: int) -> None:
        """Move zoom target by an index delta, clamped to valid levels."""
        if not delta:
            return
        self.index = max(0, min(self.index + delta, len(self.levels) - 1))
        self.target = float(self.levels[self.index])

    def set_to_level(self, value: float) -> None:
        """Snap to the nearest zoom level to `value`."""
        nearest = min(range(len(self.levels)), key=lambda i: abs(self.levels[i] - value))
        self.index = nearest
        self.current = float(self.levels[nearest])
        self.target = self.current

    def set_levels(self, levels: Sequence[float], *, keep_value: bool = True) -> None:
        """Replace zoom levels at runtime (non‑zero, deduped, ascending)."""
        if not levels:
            return
        cleaned = sorted({float(v) for v in levels if v > _EPS})
        if not cleaned:
            return
        self.levels = tuple(cleaned)
        if keep_value:
            self.set_to_level(self.current)
        else:
            self.index = max(0, min(self.index, len(self.levels) - 1))
            self.current = float(self.levels[self.index])
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
        if abs(self.current - self.target) < 1e-3:
            self.current = self.target
        return self.current != prev

    def _sanitize_levels(self) -> None:
        self.levels = tuple(sorted({float(v) for v in self.levels if v > _EPS}))


class Camera:
    """Manages the game's viewport, handling zoom & panning with polish."""

    __slots__ = (
        "width", "height", "screen_center",
        "position", "velocity",
        "accel_keyboard", "accel_edge", "drag",
        "inertia_enabled", "max_speed",
        "shift_speed_mult", "alt_speed_mult",
        "_dragging", "_last_mouse", "drag_button", "drag_with_alt_left",
        "zoom_state", "zoom_enabled", "zoom_anchors_mouse", "zoom_invert_wheel",
        "_zoom_anchor_world", "_zoom_anchor_screen_vec",
        "wrap_x", "wrap_y",
        "_trauma", "_trauma_decay", "_shake_freq", "_shake_seed", "_shake_px",
        "follow_deadzone_frac", "follow_strength", "follow_lookahead",
        "_pan_active", "_pan_time", "_pan_dur", "_pan_start", "_pan_end", "_pan_ease",
        "_visible_world_rect",
        "keyboard_enabled", "edge_scroll_enabled", "drag_enabled",
    )

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
        self.max_speed = 10_000.0  # hard clamp on camera speed

        # Speed modifiers (keyboard)
        self.shift_speed_mult = 1.6
        self.alt_speed_mult = 0.55

        # Input toggles
        self.keyboard_enabled = True
        self.edge_scroll_enabled = True
        self.drag_enabled = True
        self.zoom_enabled = True

        # Drag-panning
        self._dragging = False
        self._last_mouse = pygame.Vector2(0.0, 0.0)
        self.drag_button = pygame.BUTTON_MIDDLE  # middle mouse drag to pan
        self.drag_with_alt_left = True          # hold ALT + LMB to drag

        # Zoom
        self.zoom_state = ZoomState()
        self.zoom_anchors_mouse = True   # keep mouse world point stable on zoom
        self.zoom_invert_wheel = False   # set True to invert wheel
        self._zoom_anchor_world: Optional[pygame.Vector2] = None
        self._zoom_anchor_screen_vec: Optional[pygame.Vector2] = None

        # Bounds / wrapping
        self.wrap_x = True
        self.wrap_y = True

        # Shake (trauma-based)
        self._trauma = 0.0         # 0..1
        self._trauma_decay = 1.6   # per second
        self._shake_freq = 42.0    # Hz-ish
        self._shake_seed = random.random() * 10_000.0
        self._shake_px = 6.0       # screen-space shake amplitude

        # Optional follow behavior (soft deadzone + lookahead)
        self.follow_deadzone_frac = pygame.Vector2(0.20, 0.20)  # fraction of screen
        self.follow_strength = 10.0  # smoothing toward target
        self.follow_lookahead = pygame.Vector2(0.0, 0.0)  # in screen px, offset by velocity

        # Tweened pan_to()
        self._pan_active = False
        self._pan_time = 0.0
        self._pan_dur = 0.0
        self._pan_start = pygame.Vector2()
        self._pan_end = pygame.Vector2()
        self._pan_ease: Callable[[float], float] = _ease_smoothstep

        # Cached visible rect (world space)
        self._visible_world_rect = pygame.Rect(0, 0, 0, 0)

    # -------------------------
    # Public utilities
    # -------------------------

    @property
    def zoom(self) -> float:
        return self.zoom_state.current

    def set_window_size(self, width: int, height: int) -> None:
        """Update camera on window resize."""
        self.width = int(width)
        self.height = int(height)
        self.screen_center.update(self.width * 0.5, self.height * 0.5)

    def center_on(self, world_pos: Tuple[float, float]) -> None:
        """Instantly center the camera on a world position."""
        self.position.update(world_pos)

    def pan_to(self, world_pos: Tuple[float, float], duration: float = 0.35,
               ease: Optional[Callable[[float], float]] = None) -> None:
        """
        Smoothly pan the camera to a world position over `duration` seconds.
        Cancels inertia for the duration of the tween.
        """
        self._pan_active = True
        self._pan_time = 0.0
        self._pan_dur = max(1e-4, float(duration))
        self._pan_start.update(self.position)
        self._pan_end.update(world_pos)
        self._pan_ease = ease or _ease_smoothstep
        self.velocity.update(0, 0)  # prevent overshoot from inertia

    def cancel_pan(self) -> None:
        self._pan_active = False
        self._pan_time = 0.0
        self._pan_dur = 0.0

    def follow(self, target_world: pygame.Vector2, dt: float,
               target_velocity: Optional[pygame.Vector2] = None) -> None:
        """
        Soft-follow a target using a rectangular deadzone in *screen space*.
        The camera recenters only when target leaves the deadzone.
        Includes optional lookahead (in screen px), projected from velocity.
        """
        # Convert target's world pos into screen space (ignore shake for stability)
        target_screen = self.world_to_screen(target_world, include_shake=False)

        # Lookahead (screen space) based on camera's or target's velocity
        lookahead = pygame.Vector2(0, 0)
        vel = target_velocity if (target_velocity and target_velocity.length_squared() > 0) else self.velocity
        if self.follow_lookahead.length_squared() > 0 and vel.length_squared() > 0:
            vdir = vel.normalize()
            lookahead = pygame.Vector2(
                vdir.x * self.follow_lookahead.x,
                vdir.y * self.follow_lookahead.y
            )
            target_screen += lookahead

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
            world_delta = offset / max(self.zoom_state.current, _EPS)
            self.position += world_delta * min(1.0, self.follow_strength * dt)

    def add_shake(self, magnitude: float) -> None:
        """Adds camera shake 'trauma' (0..1). Magnitude is additive."""
        self._trauma = max(0.0, min(1.0, self._trauma + magnitude))

    def set_shake_params(self, *, amplitude_px: Optional[float] = None,
                         frequency_hz: Optional[float] = None,
                         decay_per_sec: Optional[float] = None) -> None:
        """Configure trauma-based shake behavior."""
        if amplitude_px is not None:
            self._shake_px = float(max(0.0, amplitude_px))
        if frequency_hz is not None:
            self._shake_freq = float(max(0.0, frequency_hz))
        if decay_per_sec is not None:
            self._trauma_decay = float(max(0.0, decay_per_sec))

    def frame_rect(self, rect: pygame.Rect, *, margin_px: int = 0, snap_to_level: bool = True) -> None:
        """
        Center and zoom so that `rect` is fully visible, with optional pixel margin.
        If snap_to_level is True, snap to the nearest discrete zoom level; otherwise set target zoom.
        """
        if rect.width <= 0 or rect.height <= 0 or self.width <= 0 or self.height <= 0:
            return
        usable_w = max(1, rect.width + margin_px * 2)
        usable_h = max(1, rect.height + margin_px * 2)
        scale_x = self.width / usable_w
        scale_y = self.height / usable_h
        desired = max(_EPS, min(scale_x, scale_y))
        if snap_to_level:
            self.zoom_state.set_to_level(desired)
        else:
            # set target without snapping; easing will handle approach
            self.zoom_state.target = desired
        self.center_on(rect.center)

    def screen_to_world(self, screen_pos: Tuple[int, int], *, include_shake: bool = False) -> pygame.Vector2:
        """Convert screen -> world coordinates."""
        # For stability, default ignores shake; pass include_shake=True if you truly want it
        screen_vec = pygame.Vector2(screen_pos) - self.screen_center
        if include_shake:
            screen_vec -= self._shake_offset()
        world_offset = screen_vec / max(self.zoom_state.current, _EPS)
        return self.position + world_offset

    def world_to_screen(self, world_pos: Tuple[float, float], *, include_shake: bool = True) -> pygame.Vector2:
        """Convert world -> screen coordinates."""
        screen_offset = (pygame.Vector2(world_pos) - self.position) * self.zoom_state.current
        p = self.screen_center + screen_offset
        if include_shake:
            p += self._shake_offset()
        return p

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        """Transform a world-space rect to a screen-space rect."""
        tl = self.world_to_screen(rect.topleft)  # include shake for the whole scene
        z = self.zoom_state.current
        w = rect.width * z
        h = rect.height * z

        # Clamp all values to the safe range before creating the Rect
        safe_x = max(_SAFE_MIN, min(round(tl.x), _SAFE_MAX))
        safe_y = max(_SAFE_MIN, min(round(tl.y), _SAFE_MAX))
        safe_w = max(0, min(round(w), _SAFE_MAX))  # Width/height can't be negative
        safe_h = max(0, min(round(h), _SAFE_MAX))

        return pygame.Rect(safe_x, safe_y, safe_w, safe_h)

    def apply_point(self, world_pos: Tuple[float, float]) -> Tuple[int, int]:
        """Transform a world-space point to screen-space point."""
        p = self.world_to_screen(world_pos)
        return (int(round(p.x)), int(round(p.y)))

    def apply_points(self, points: Iterable[Tuple[float, float]]) -> List[Tuple[int, int]]:
        """Batch-transform world-space points to screen-space points."""
        out: List[Tuple[int, int]] = []
        z = self.zoom_state.current
        shake = self._shake_offset()
        cx, cy = self.screen_center
        px, py = self.position
        for x, y in points:
            sx = cx + (x - px) * z + shake.x
            sy = cy + (y - py) * z + shake.y
            out.append((int(round(sx)), int(round(sy))))
        return out

    def apply_line(self, p0: Tuple[float, float], p1: Tuple[float, float]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Transform a world-space line to a screen-space line."""
        a = self.apply_point(p0)
        b = self.apply_point(p1)
        return a, b

    def get_visible_world_rect(self, margin: float = 0.0) -> pygame.Rect:
        """Returns the world-space rectangle currently visible by the camera (cached each call)."""
        top_left = self.screen_to_world((0 - margin, 0 - margin))
        bot_right = self.screen_to_world((self.width + margin, self.height + margin))
        x0, y0 = top_left
        x1, y1 = bot_right
        self._visible_world_rect.update(
            int(math.floor(min(x0, x1))),
            int(math.floor(min(y0, y1))),
            int(math.ceil(abs(x1 - x0))),
            int(math.ceil(abs(y1 - y0))),
        )
        return self._visible_world_rect

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

    def set_bounds_mode(self, *, wrap_x: Optional[bool] = None, wrap_y: Optional[bool] = None) -> None:
        """Toggle per-axis wrapping/clamping."""
        if wrap_x is not None:
            self.wrap_x = bool(wrap_x)
        if wrap_y is not None:
            self.wrap_y = bool(wrap_y)

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
        - zoom easing (+ anchor correction)
        - wrapping/clamping
        - optional follow
        - optional pan_to tween
        """
        # Handle zoom inputs first so mappings are correct this frame
        self._handle_mouse_input(events)

        # Update zoom value
        zoom_changed = self.zoom_state.update(dt)

        # If we are mouse-anchoring zoom, keep the anchor world point stationary during easing
        if self._zoom_anchor_world is not None and self._zoom_anchor_screen_vec is not None:
            desired_position = self._zoom_anchor_world - (self._zoom_anchor_screen_vec / max(self.zoom_state.current, _EPS))
            self.position.update(desired_position)
            if not zoom_changed or self.zoom_state.at_target:
                # Clear the anchor once we've reached the target
                self._zoom_anchor_world = None
                self._zoom_anchor_screen_vec = None

        # Movement inputs
        keys = pygame.key.get_pressed()
        move_keyboard = self._keyboard_move_vector(keys) if self.keyboard_enabled else pygame.Vector2()
        move_edge = self._edge_scroll_vector(edge_scroll_exclusion_zone) if self.edge_scroll_enabled else pygame.Vector2()

        # Mouse drag panning modifies position directly (not affected by inertia)
        if self.drag_enabled:
            self._handle_drag(events)

        # Determine the target velocity based on inputs.
        inv_zoom = 1.0 / max(self.zoom_state.current, _EPS)
        speed_mult = self._speed_modifier(keys)
        target_velocity = pygame.Vector2(0, 0)

        if move_keyboard.length_squared() > 0:
            move_keyboard.normalize_ip()
            target_velocity += move_keyboard * self.accel_keyboard * inv_zoom * speed_mult
        if move_edge.length_squared() > 0:
            move_edge.normalize_ip()
            target_velocity += move_edge * self.accel_edge * inv_zoom * speed_mult

        # Clamp max speed (safety)
        if target_velocity.length() > self.max_speed:
            target_velocity.scale_to_length(self.max_speed)

        # Apply tween pan if active (overrides velocity)
        if self._pan_active:
            self._update_pan(dt)
            target_velocity.update(0, 0)

        # Integrate
        if self.inertia_enabled:
            accel = (target_velocity - self.velocity) * self.drag
            self.velocity += accel * dt
            if self.velocity.length() > self.max_speed:
                self.velocity.scale_to_length(self.max_speed)
            self.position += self.velocity * dt
        else:
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

    def _speed_modifier(self, keys: Sequence[bool]) -> float:
        mult = 1.0
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            mult *= self.shift_speed_mult
        if keys[pygame.K_LALT] or keys[pygame.K_RALT]:
            mult *= self.alt_speed_mult
        return mult

    def _keyboard_move_vector(self, keys: Sequence[bool]) -> pygame.Vector2:
        """WASD/Arrows movement vector (unscaled)."""
        v = pygame.Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            v.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            v.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            v.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            v.x += 1
        return v

    def _edge_scroll_vector(self, exclusion_zone: Optional[pygame.Rect] = None) -> pygame.Vector2:
        """
        Edge-scroll vector (unscaled).
        Gated off while dragging or while a mouse button is held (to avoid fighting with selection/drag).
        """
        if not pygame.mouse.get_focused():
            return pygame.Vector2(0, 0)

        pressed = pygame.mouse.get_pressed(num_buttons=5)
        if self._dragging or any(pressed):
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

    def _handle_drag(self, events: Sequence[pygame.event.Event]) -> None:
        """Middle-mouse drag panning, or ALT + LMB if enabled."""
        alt_held = bool(pygame.key.get_mods() & pygame.KMOD_ALT)
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == self.drag_button or (self.drag_with_alt_left and e.button == pygame.BUTTON_LEFT and alt_held):
                    self._dragging = True
                    self._last_mouse = pygame.Vector2(pygame.mouse.get_pos())
                    self.velocity.update(0, 0)  # freeze inertia while dragging
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == self.drag_button or e.button == pygame.BUTTON_LEFT:
                    self._dragging = False

        if self._dragging:
            cur = pygame.Vector2(pygame.mouse.get_pos())
            delta_screen = cur - self._last_mouse
            self._last_mouse = cur
            # Convert screen delta to world delta (inverse of zoom)
            world_delta = delta_screen / max(self.zoom_state.current, _EPS)
            self.position -= world_delta  # drag moves camera opposite to mouse

    def _handle_mouse_input(self, events: Sequence[pygame.event.Event]) -> None:
        """Zoom with mouse-wheel; keep mouse-anchored if enabled."""
        if not self.zoom_enabled:
            return
        for event in events:
            if event.type == pygame.MOUSEWHEEL:
                dy = event.y
                if self.zoom_invert_wheel:
                    dy = -dy
                if dy == 0:
                    continue

                if self.zoom_anchors_mouse:
                    # Cache the anchor so it stays put during the easing tween
                    mouse = pygame.Vector2(pygame.mouse.get_pos())
                    self._zoom_anchor_world = self.screen_to_world(mouse)  # default ignores shake
                    self._zoom_anchor_screen_vec = mouse - self.screen_center

                self.zoom_state.step(+1 if dy > 0 else -1)

    def _apply_bounds(self, map_w: int, map_h: int) -> None:
        """Apply wrap or clamp to camera position. Robust when map < viewport."""
        z = max(self.zoom_state.current, _EPS)
        half_w_world = (self.width * 0.5) / z
        half_h_world = (self.height * 0.5) / z

        # X axis
        if self.wrap_x and map_w > 0:
            self.position.x %= map_w
        else:
            if map_w <= 0:
                self.position.x = 0.0
            elif map_w < 2 * half_w_world:
                # Viewport wider than world: lock to center
                self.position.x = map_w * 0.5
            else:
                self.position.x = max(half_w_world, min(self.position.x, map_w - half_w_world))

        # Y axis
        if self.wrap_y and map_h > 0:
            self.position.y %= map_h
        else:
            if map_h <= 0:
                self.position.y = 0.0
            elif map_h < 2 * half_h_world:
                # Viewport taller than world: lock to center
                self.position.y = map_h * 0.5
            else:
                self.position.y = max(half_h_world, min(self.position.y, map_h - half_h_world))

    def _shake_offset(self) -> pygame.Vector2:
        """Compute per-frame shake offset from trauma."""
        if self._trauma <= 0.0 or self._shake_px <= 0.0:
            return pygame.Vector2(0, 0)
        t = pygame.time.get_ticks() * 0.001  # seconds
        mag = (self._trauma * self._trauma)  # square for nicer decay curve
        nx = math.sin((self._shake_seed + t) * self._shake_freq) * mag
        ny = math.cos((self._shake_seed * 0.5 + t * 1.3) * self._shake_freq) * mag
        return pygame.Vector2(nx * self._shake_px, ny * self._shake_px)

    def _update_pan(self, dt: float) -> None:
        """Advance a pan_to() tween."""
        if not self._pan_active:
            return
        self._pan_time += dt
        t = min(1.0, self._pan_time / self._pan_dur)
        t = self._pan_ease(t)
        self.position = self._pan_start.lerp(self._pan_end, t)
        if self._pan_time >= self._pan_dur:
            self._pan_active = False

    # -------------------------
    # Debug overlay (optional)
    # -------------------------
    def debug_draw_overlay(self, screen: pygame.Surface) -> None:
        """Draws a simple overlay: center cross, deadzone box, zoom/pos text."""
        try:
            from src.core.camera_debug import draw_camera_debug_overlay
        except Exception:
            return
        draw_camera_debug_overlay(screen, self)
