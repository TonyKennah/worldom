# c:/game/worldom/input/keymap.py
"""
Keymap helper for parsing human-readable bindings from settings.KEY_BINDINGS.

Supports:
- Polling (is_action_down) for simple single-key/mouse bindings.
- Event matching (event_to_actions / match_event) for keys, combos with CTRL/SHIFT/ALT,
  mouse buttons, and mouse wheel.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import pygame


# ------------------ Parsing helpers ------------------

_MOD_NAMES = {"CTRL", "CONTROL", "SHIFT", "ALT"}

_SPECIAL_KEYCODES = {
    "ESC": pygame.K_ESCAPE, "ESCAPE": pygame.K_ESCAPE,
    "SPACE": pygame.K_SPACE, "TAB": pygame.K_TAB,
    "ENTER": pygame.K_RETURN, "RETURN": pygame.K_RETURN,
    "BACKSPACE": pygame.K_BACKSPACE, "DELETE": pygame.K_DELETE,
    "UP": pygame.K_UP, "DOWN": pygame.K_DOWN, "LEFT": pygame.K_LEFT, "RIGHT": pygame.K_RIGHT,
    "-": pygame.K_MINUS, "_": pygame.K_MINUS,  # shift-mod still matches
    "=": pygame.K_EQUALS, "+": pygame.K_EQUALS,
}
for i in range(1, 13):
    _SPECIAL_KEYCODES[f"F{i}"] = getattr(pygame, f"K_F{i}")

_MOUSE_ALIASES = {
    "MOUSE1": 1, "LMB": 1, "LEFTMOUSE": 1, "MOUSE_LEFT": 1,
    "MOUSE2": 2, "RMB": 2, "RIGHTMOUSE": 2, "MOUSE_RIGHT": 2,
    "MOUSE3": 3, "MMB": 3, "MOUSE_MIDDLE": 3,
}
_WHEEL_ALIASES = {"WHEEL_UP": "up", "WHEEL_DOWN": "down"}


def _keycode_from_token(token: str) -> Optional[int]:
    t = token.upper()
    if t in _SPECIAL_KEYCODES:
        return _SPECIAL_KEYCODES[t]
    # Single character (letters/numbers)
    if len(t) == 1:
        # letters/numbers map to K_a.. and K_0..K_9
        attr = f"K_{t.lower()}"
        return getattr(pygame, attr, None)
    # Named constants like PAGEUP, HOME, etc.
    attr = f"K_{t.lower()}"
    return getattr(pygame, attr, None)


@dataclass(frozen=True)
class Binding:
    kind: str  # "keyboard" | "mouse" | "wheel"
    key: Optional[int] = None   # pygame K_* or None for wheel
    mouse_button: Optional[int] = None  # 1..3
    wheel_dir: Optional[str] = None     # "up" | "down"
    mod_ctrl: bool = False
    mod_shift: bool = False
    mod_alt: bool = False


def _parse_binding(expr: str) -> Optional[Binding]:
    """
    Parse strings like:
      "W", "CTRL+F12", "MOUSE1", "MOUSE2", "MOUSE3", "WHEEL_UP", "WHEEL_DOWN", "SHIFT+=", "-".
    """
    tokens = [t.strip() for t in expr.replace("+", " + ").split() if t.strip()]
    mods = {"CTRL": False, "SHIFT": False, "ALT": False}
    main: Optional[str] = None

    for t in tokens:
        up = t.upper()
        if up in _MOD_NAMES:
            mods["CTRL"] |= (up in {"CTRL", "CONTROL"})
            mods["SHIFT"] |= (up == "SHIFT")
            mods["ALT"] |= (up == "ALT")
        else:
            main = t  # last non-mod token wins

    if main is None:
        return None

    up_main = main.upper()

    # Mouse buttons
    if up_main in _MOUSE_ALIASES:
        return Binding(
            kind="mouse",
            mouse_button=_MOUSE_ALIASES[up_main],
            mod_ctrl=mods["CTRL"],
            mod_shift=mods["SHIFT"],
            mod_alt=mods["ALT"],
        )

    # Mouse wheel
    if up_main in _WHEEL_ALIASES:
        return Binding(
            kind="wheel",
            wheel_dir=_WHEEL_ALIASES[up_main],
            mod_ctrl=mods["CTRL"],
            mod_shift=mods["SHIFT"],
            mod_alt=mods["ALT"],
        )

    # Keyboard key
    key = _keycode_from_token(main)
    if key is not None:
        return Binding(
            kind="keyboard",
            key=key,
            mod_ctrl=mods["CTRL"],
            mod_shift=mods["SHIFT"],
            mod_alt=mods["ALT"],
        )

    return None


# ------------------ Public API ------------------

class Keymap:
    def __init__(self, bindings: Dict[str, Iterable[str]]) -> None:
        """
        bindings: action -> iterable of binding expressions (strings).
        """
        parsed: Dict[str, List[Binding]] = {}
        for action, exprs in bindings.items():
            lst: List[Binding] = []
            for e in exprs:
                b = _parse_binding(e)
                if b:
                    lst.append(b)
            parsed[action] = lst
        self._map = parsed

    # ------------- Polling (good for movement/mouse buttons) -------------
    def is_action_down(self, action: str) -> bool:
        """
        Return True if any simple binding for `action` is currently pressed.

        Notes:
          - For keyboard combos (CTRL/SHIFT/ALT), polling also works by
            checking current mod state.
          - Mouse wheel cannot be polled (event-only), so this returns False
            for wheel bindings.
        """
        if action not in self._map:
            return False

        pressed = pygame.key.get_pressed()
        mods = pygame.key.get_mods()
        m_pressed = pygame.mouse.get_pressed(3)

        def _mods_ok(b: Binding) -> bool:
            if b.mod_ctrl and not (mods & pygame.KMOD_CTRL):
                return False
            if b.mod_shift and not (mods & pygame.KMOD_SHIFT):
                return False
            if b.mod_alt and not (mods & pygame.KMOD_ALT):
                return False
            return True

        for b in self._map[action]:
            if b.kind == "keyboard" and b.key is not None and _mods_ok(b):
                if pressed[b.key]:
                    return True
            elif b.kind == "mouse" and b.mouse_button is not None and _mods_ok(b):
                idx = b.mouse_button - 1
                if 0 <= idx < len(m_pressed) and m_pressed[idx]:
                    return True
        return False

    # ------------- Event matching (for wheel, combos, discrete actions) -------------
    def match_event(self, action: str, ev: pygame.event.Event) -> bool:
        """Return True if `ev` triggers any binding of `action`."""
        return any(self._binding_matches_event(b, ev) for b in self._map.get(action, []))

    def event_to_actions(self, ev: pygame.event.Event) -> List[str]:
        """Return list of actions that match `ev`."""
        out: List[str] = []
        for action, binds in self._map.items():
            if any(self._binding_matches_event(b, ev) for b in binds):
                out.append(action)
        return out

    # ------------------ Internals ------------------
    @staticmethod
    def _mods_from_event(ev: pygame.event.Event) -> Tuple[bool, bool, bool]:
        mod = 0
        if hasattr(ev, "mod"):
            mod = ev.mod
        else:
            mod = pygame.key.get_mods()
        return (
            bool(mod & pygame.KMOD_CTRL),
            bool(mod & pygame.KMOD_SHIFT),
            bool(mod & pygame.KMOD_ALT),
        )

    def _binding_matches_event(self, b: Binding, ev: pygame.event.Event) -> bool:
        ctrl, shift, alt = self._mods_from_event(ev)
        if b.mod_ctrl and not ctrl: return False
        if b.mod_shift and not shift: return False
        if b.mod_alt and not alt: return False

        if b.kind == "keyboard" and ev.type == pygame.KEYDOWN and b.key is not None:
            return ev.key == b.key

        if b.kind == "mouse" and ev.type == pygame.MOUSEBUTTONDOWN and b.mouse_button is not None:
            return ev.button == b.mouse_button

        if b.kind == "wheel" and ev.type == pygame.MOUSEWHEEL and b.wheel_dir:
            return (b.wheel_dir == "up" and ev.y > 0) or (b.wheel_dir == "down" and ev.y < 0)

        return False
