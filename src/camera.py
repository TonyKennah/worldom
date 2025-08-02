# c:/game/worldom/camera.py
import pygame
from settings import CAMERA_SPEED

class Camera:
    """Manages the game's viewport, handling zoom and panning."""
    def __init__(self, width, height):
        """Initializes the camera."""
        self.width = width
        self.height = height
        self.position = pygame.math.Vector2(0, 0)
        self.screen_center = pygame.math.Vector2(width / 2, height / 2)

        # Stepped zoom implementation
        self.zoom_levels = [0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
        self.zoom_index = self.zoom_levels.index(1.0)
        self.zoom = self.zoom_levels[self.zoom_index]
        
        # Mouse panning state
        self.dragging = False
        self.drag_pos = None

    def screen_to_world(self, screen_pos):
        """Converts screen coordinates to world coordinates."""
        return (pygame.math.Vector2(screen_pos) - self.screen_center) / self.zoom + self.position

    def world_to_screen(self, world_pos):
        """Converts world coordinates to screen coordinates."""
        return (pygame.math.Vector2(world_pos) - self.position) * self.zoom + self.screen_center

    def apply(self, rect):
        """Applies camera transformation to a pygame.Rect."""
        top_left = self.world_to_screen(rect.topleft)
        w = rect.width * self.zoom
        h = rect.height * self.zoom
        # Rounding all values to prevent gaps/jitter from float truncation.
        return pygame.Rect(round(top_left.x), round(top_left.y), round(w), round(h))

    def update(self, dt, events):
        """Updates camera position based on user input."""
        keys = pygame.key.get_pressed()

        # --- WASD Movement ---
        move_vec = pygame.math.Vector2(0, 0)
        if keys[pygame.K_w]:
            move_vec.y -= 1
        if keys[pygame.K_s]:
            move_vec.y += 1
        if keys[pygame.K_a]:
            move_vec.x -= 1
        if keys[pygame.K_d]:
            move_vec.x += 1

        if move_vec.length_squared() > 0:
            move_vec.normalize_ip()
            # Scale movement by zoom level to feel consistent
            self.position += move_vec * CAMERA_SPEED / self.zoom * dt

        # --- Mouse Panning and Zooming ---
        for event in events:
            # Zooming (centered on mouse)
            if event.type == pygame.MOUSEWHEEL:
                mouse_pos_before_zoom = self.screen_to_world(pygame.mouse.get_pos())

                # Increment/decrement the zoom index
                if event.y > 0: # Zoom in
                    self.zoom_index = min(len(self.zoom_levels) - 1, self.zoom_index + 1)
                elif event.y < 0: # Zoom out
                    self.zoom_index = max(0, self.zoom_index - 1)
                
                self.zoom = self.zoom_levels[self.zoom_index]
                
                mouse_pos_after_zoom = self.screen_to_world(pygame.mouse.get_pos())
                self.position += mouse_pos_before_zoom - mouse_pos_after_zoom

            # Panning (drag with left mouse button)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.dragging = True
                self.drag_pos = pygame.math.Vector2(event.pos)

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.dragging = False
                self.drag_pos = None

            if event.type == pygame.MOUSEMOTION and self.dragging:
                drag_vec = pygame.math.Vector2(event.pos) - self.drag_pos
                self.position -= drag_vec / self.zoom
                self.drag_pos = pygame.math.Vector2(event.pos)