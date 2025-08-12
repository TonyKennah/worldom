from __future__ import annotations
from typing import Tuple, TYPE_CHECKING



if TYPE_CHECKING:
    from game import Game

class SelectionManager:
    """Processes selections and delegates actions to the game."""

    def __init__(self, game: Game) -> None:
        """Initializes the game."""
        self.game = game

    def handle_left_click_selection(self, mouse_pos: Tuple[int, int]) -> None:
        """Handles unit selection logic for a left click."""
        world_pos = self.game.camera.screen_to_world(mouse_pos)

        # Deselect all units first
        for unit in self.game.world_state.selected_units:
            unit.selected = False
        self.game.world_state.selected_units.clear()

        # Find and select the clicked unit
        for unit in self.game.world_state.units:
            if unit.get_world_rect().collidepoint(world_pos):
                unit.selected = True
                self.game.world_state.selected_units.append(unit)
                break  # Stop after selecting one unit

    def handle_drag_selection(self, selection_rect_screen: pygame.Rect) -> None:
        """Selects units within a given rectangle in screen coordinates."""
        # Deselect all units first, unless holding shift (extension for later)
        for unit in self.game.world_state.selected_units:
            unit.selected = False
        self.game.world_state.selected_units.clear()

        # Convert screen rect to world rect to check for collisions with units
        world_topleft = self.game.camera.screen_to_world(selection_rect_screen.topleft)
        world_bottomright = self.game.camera.screen_to_world(selection_rect_screen.bottomright)
        selection_rect_world = pygame.Rect(
            world_topleft,
            (world_bottomright.x - world_topleft.x, world_bottomright.y - world_topleft.y)
        )
        selection_rect_world.normalize()

        for unit in self.game.world_state.units:
            if selection_rect_world.colliderect(unit.get_world_rect()):
                unit.selected = True
                self.game.world_state.selected_units.append(unit)