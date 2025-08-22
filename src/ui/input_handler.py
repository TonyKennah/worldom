# src/ui/input_handler.py
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    # Type-only import to avoid circular imports at runtime
    from src.core.game import Game


__all__ = ["InputHandler", "handle_keydown", "handle_event"]


class InputHandler:
    """
    Small helper for UI-related keyboard handling.

    - F1 or Shift+/ : toggle the help overlay (if present)
    - ESC           : close the help overlay (if visible)
    """

    def __init__(self, game: "Game") -> None:
        self.game = game

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Entry point; return True if the event was consumed."""
        if event.type == pygame.KEYDOWN:
            return self._handle_keydown(event)
        return False

    # ---- internals ---------------------------------------------------------

    def _toggle_help_overlay(self) -> bool:
        """
        Try to toggle the help overlay via ui_manager.
        Returns True if we successfully toggled/changed visibility.
        """
        ui = getattr(self.game, "ui_manager", None)
        if ui is None:
            return False

        # Preferred: dedicated method if the UIManager provides it
        if hasattr(ui, "toggle_help_overlay"):
            try:
                ui.toggle_help_overlay()  # type: ignore[attr-defined]
                return True
            except Exception:
                # fall back to flipping a visible flag
                pass

        # Fallback: flip a known 'visible' flag on a help_overlay object
        overlay = getattr(ui, "help_overlay", None)
        if overlay is not None and hasattr(overlay, "visible"):
            try:
                overlay.visible = not bool(overlay.visible)  # type: ignore[attr-defined]
                return True
            except Exception:
                return False

        return False

    def _hide_help_overlay_if_visible(self) -> bool:
        """If a help overlay exists and is visible, hide it and return True."""
        ui = getattr(self.game, "ui_manager", None)
        if ui is None:
            return False

        overlay = getattr(ui, "help_overlay", None)
        is_visible = bool(getattr(overlay, "visible", False))
        if not is_visible:
            return False

        if hasattr(ui, "toggle_help_overlay"):
            try:
                # Use provided toggle to maintain any side effects
                ui.toggle_help_overlay()  # type: ignore[attr-defined]
                return True
            except Exception:
                # fall back to force-hide
                pass

        if overlay is not None and hasattr(overlay, "visible"):
            try:
                overlay.visible = False  # type: ignore[attr-defined]
                return True
            except Exception:
                return False

        return False

    def _handle_keydown(self, event: pygame.event.Event) -> bool:
        mods = pygame.key.get_mods()

        # Toggle help overlay on F1 or Shift + /
        if event.key == pygame.K_F1 or (event.key == pygame.K_SLASH and (mods & pygame.KMOD_SHIFT)):
            # Return True if we consumed it by changing overlay state
            return self._toggle_help_overlay()

        # Close help overlay on ESC (if visible)
        if event.key == pygame.K_ESCAPE:
            if self._hide_help_overlay_if_visible():
                return True

        # Not consumed
        return False


# -----------------------------------------------------------------------------
# Module-level convenience functions (for existing code calling functions)
# -----------------------------------------------------------------------------

def handle_event(game: "Game", event: pygame.event.Event) -> bool:
    """
    Functional wrapper for callers not using the InputHandler class.
    Returns True if the event was consumed.
    """
    return InputHandler(game).handle_event(event)


def handle_keydown(game: "Game", event: pygame.event.Event) -> bool:
    """
    Functional wrapper specifically for KEYDOWN events.
    Returns True if the event was consumed.
    """
    if event.type != pygame.KEYDOWN:
        return False
    return InputHandler(game)._handle_keydown(event)
