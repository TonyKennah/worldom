from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import pygame
 
# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Binding:
    """A single input binding."""
    kind: str                          # "keyboard" | "mouse" | "wheel"
    key: Optional[int] = None          # pygame keycode (if keyboard)
    mouse_button: Optional[int] = None # 1..5 supported
    wheel_dir: Optional[str] = None    # "up" | "down" | "left" | "right"
    # Modifiers
    mod_ctrl: bool = False
    mod_shift: bool = False
    mod_alt: bool = False
    mod_gui: bool = False              # NEW: Cmd/Win/Super

    def requires_mods(self) -> Tuple[bool, bool, bool, bool]:
        return self.mod_ctrl, self.mod_shift, self.mod_alt, self.mod_gui

class Keymap:
    def __init__(self, bindings: Dict[str, Iterable[str]]) -> None:
        self._warnings: List[str] = []
        parsed: Dict[str, List[Binding]] = {}
        for action, exprs in bindings.items():
            blist: List[Binding] = []
            for e in exprs:
                b = _parse_binding(e)
                if b:
                    blist.append(b)
                else:
                    self._warnings.append(f"Unrecognized binding '{e}' for action '{action}'")
            parsed[action] = blist
        self._map: Dict[str, List[Binding]] = parsed
        self._rebuild_buckets()

    # ---------------- Public diagnostics / info ----------------
    @property
    def warnings(self) -> List[str]:
        """Any parse warnings collected at construction or after set_bindings/add_binding."""
        return list(self._warnings)
 
    def is_action_down(self, action: str) -> bool:
        """Polling: returns True if any binding for the action is 'down' now."""
        """
        Polling: returns True if any *keyboard or mouse button* binding
        for the action is 'down' now. Wheel bindings are event‑only and
        never report as pressed here.
        """
        binds = self._map.get(action)
        if not binds:
          return False
        keys = pygame.key.get_pressed()
        mouse = pygame.mouse.get_pressed(3)
        mods = pygame.key.get_mods()
        for b in binds:
            if b.kind == "keyboard" and b.key is not None:
                if not _mods_ok(b, mods):  # type: ignore
                    continue
                if keys[b.key]:
                    return True
            elif b.kind == "mouse" and b.mouse_button:
                if not _mods_ok(b, mods):  # type: ignore
                    continue
                idx = b.mouse_button - 1
                if 0 <= idx < len(mouse) and mouse[idx]:
                    return True
        return False
        mods = pygame.key.get_mods()
        kstate = pygame.key.get_pressed()
        # Ask for 5 buttons to include MOUSE4/5; pygame clamps if unsupported
        mstate = pygame.mouse.get_pressed(5)

        for b in binds:
            if b.kind == "keyboard" and b.key is not None:
                if not _mods_ok_for_state(b, mods):
                    continue
                try:
                    if kstate[b.key]:
                        return True
                except IndexError:
                    continue
            elif b.kind == "mouse" and b.mouse_button:
                if not _mods_ok_for_state(b, mods):
                    continue
                idx = b.mouse_button - 1
                if 0 <= idx < len(mstate) and mstate[idx]:
                    return True
        return False

    def match_event(self, action: str, ev: pygame.event.Event) -> bool:
        """
        Returns True if this event matches any binding for the action.
        Matches KEYDOWN/KEYUP, MOUSEBUTTONDOWN/MOUSEBUTTONUP, and MOUSEWHEEL.
        """
        binds = self._map.get(action)
        if not binds:
            return False
        return any(self._binding_matches_event(b, ev) for b in binds)

    def event_to_actions(self, ev: pygame.event.Event) -> List[str]:
        """Return all actions matched by this event."""
        out: List[str] = []
        for action, binds in self._map.items():
            for b in binds:
                if _binding_matches_event(b, ev):
                    out.append(action)
                    break
        return out
        """
        Return all actions matched by this event. Uses buckets to avoid
        scanning unrelated bindings.
        """
        kind = _event_kind(ev)
        src = self._by_kind.get(kind, self._map)
        out: List[str] = []
        for action, binds in src.items():
            for b in binds:
                if self._binding_matches_event(b, ev):
                    out.append(action)
                    break
        return out

    def first_action_for_event(self, ev: pygame.event.Event) -> Optional[str]:
        """Convenience: return the first matching action for an event."""
        kind = _event_kind(ev)
        src = self._by_kind.get(kind, self._map)
        for action, binds in src.items():
            if any(self._binding_matches_event(b, ev) for b in binds):
                return action
        return None

    def pressed_actions(self) -> List[str]:
        """All actions currently considered 'down' using polling."""
        return [a for a in self._map.keys() if self.is_action_down(a)]

    def bindings_for(self, action: str) -> List[Binding]:
        """Get the list of bindings for an action (for UI/tooltips)."""
        return list(self._map.get(action, ()))

    def known_actions(self) -> List[str]:
        """List actions known to this keymap."""
        return sorted(self._map.keys())

    # ---------------- Dynamic rebinding APIs ----------------
    def set_bindings(self, action: str, exprs: Iterable[str]) -> None:
        """Replace bindings for an action using expressions."""
        blist: List[Binding] = []
        for e in exprs:
            b = _parse_binding(e)
            if b:
                blist.append(b)
            else:
                self._warnings.append(f"Unrecognized binding '{e}' for action '{action}'")
        self._map[action] = blist
        self._rebuild_buckets()

    def add_binding(self, action: str, expr: str) -> bool:
        """Append a single binding from expression. Returns True on success."""
        b = _parse_binding(expr)
        if not b:
            self._warnings.append(f"Unrecognized binding '{expr}' for action '{action}'")
            return False
        self._map.setdefault(action, []).append(b)
        self._rebuild_buckets()
        return True

    def remove_bindings(self, action: str) -> None:
        """Remove all bindings for an action."""
        self._map.pop(action, None)
        self._rebuild_buckets()

    # ---------------- Internals ----------------
    def _rebuild_buckets(self) -> None:
        """Bucket bindings by kind (keyboard/mouse/wheel) for faster event scans."""
        self._by_kind: Dict[str, Dict[str, List[Binding]]] = {
            "keyboard": {},
            "mouse": {},
            "wheel": {},
        }
        for action, binds in self._map.items():
            kb = [b for b in binds if b.kind == "keyboard"]
            ms = [b for b in binds if b.kind == "mouse"]
            wh = [b for b in binds if b.kind == "wheel"]
            if kb: self._by_kind["keyboard"][action] = kb
            if ms: self._by_kind["mouse"][action] = ms
            if wh: self._by_kind["wheel"][action] = wh

    def _binding_matches_event(self, b: Binding, ev: pygame.event.Event) -> bool:
        """Event matcher that supports DOWN/UP and wheel x/y."""
        mods = getattr(ev, "mod", None)
        if mods is None:
            mods = pygame.key.get_mods()

        # Keyboard
        if b.kind == "keyboard" and b.key is not None and ev.type in (pygame.KEYDOWN, pygame.KEYUP):
            if not _mods_ok_for_state(b, mods):
                return False
            return getattr(ev, "key", None) == b.key

        # Mouse button
        if b.kind == "mouse" and b.mouse_button and ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if not _mods_ok_for_state(b, mods):
                return False
            return getattr(ev, "button", None) == b.mouse_button

        # Mouse wheel
        if b.kind == "wheel" and ev.type == pygame.MOUSEWHEEL and b.wheel_dir:
            # vertical y, horizontal x
            if b.wheel_dir == "up":
                return getattr(ev, "y", 0) > 0
            if b.wheel_dir == "down":
                return getattr(ev, "y", 0) < 0
            if b.wheel_dir == "left":
                return getattr(ev, "x", 0) < 0
            if b.wheel_dir == "right":
                return getattr(ev, "x", 0) > 0

        return False


# ---------------------------------------------------------------------------
# Parsing helpers and lookup tables
# ---------------------------------------------------------------------------

# Mod names (expanded with GUI/CMD/META/SUPER aliases)
_MOD_TOKENS = {
    "CTRL", "CONTROL",
    "SHIFT",
    "ALT",
    "GUI", "META", "SUPER", "CMD",
}

_MOUSE_BUTTON_ALIASES: Dict[str, int] = {
    "MOUSE1": 1, "LMB": 1, "LEFTMOUSE": 1, "MOUSE_LEFT": 1,
    "MOUSE2": 2, "RMB": 2, "RIGHTMOUSE": 2, "MOUSE_RIGHT": 2,
    "MOUSE3": 3, "MMB": 3, "MOUSE_MIDDLE": 3,
    "MOUSE4": 4, "M4": 4,                        # NEW
    "MOUSE5": 5, "M5": 5,                        # NEW
}

_WHEEL_ALIASES: Dict[str, str] = {
    "WHEEL_UP": "up",
    "WHEEL_DOWN": "down",
    "WHEEL_LEFT": "left",                        # NEW
    "WHEEL_RIGHT": "right",                      # NEW
}

# Common punctuation & special keys
_SPECIAL_KEYCODES: Dict[str, int] = {
    # function keys
    **{f"F{i}": getattr(pygame, f"K_F{i}") for i in range(1, 13)},
    # arrows & navigation
    "LEFT": pygame.K_LEFT, "RIGHT": pygame.K_RIGHT, "UP": pygame.K_UP, "DOWN": pygame.K_DOWN,
    "HOME": pygame.K_HOME, "END": pygame.K_END, "PGUP": pygame.K_PAGEUP, "PAGEUP": pygame.K_PAGEUP,
    "PGDN": pygame.K_PAGEDOWN, "PAGEDOWN": pygame.K_PAGEDOWN,
    "INS": pygame.K_INSERT, "INSERT": pygame.K_INSERT, "DEL": pygame.K_DELETE, "DELETE": pygame.K_DELETE,
    # system keys
    "ESC": pygame.K_ESCAPE, "ESCAPE": pygame.K_ESCAPE,
    "TAB": pygame.K_TAB, "BACKSPACE": pygame.K_BACKSPACE, "ENTER": pygame.K_RETURN, "RETURN": pygame.K_RETURN,
    "SPACE": pygame.K_SPACE,
    # numpad
    "KP0": pygame.K_KP0, "KP1": pygame.K_KP1, "KP2": pygame.K_KP2, "KP3": pygame.K_KP3, "KP4": pygame.K_KP4,
    "KP5": pygame.K_KP5, "KP6": pygame.K_KP6, "KP7": pygame.K_KP7, "KP8": pygame.K_KP8, "KP9": pygame.K_KP9,
    "KPMINUS": pygame.K_KP_MINUS, "KPPLUS": pygame.K_KP_PLUS,
    "KPMULTIPLY": pygame.K_KP_MULTIPLY, "KPDIVIDE": pygame.K_KP_DIVIDE, "KPENTER": pygame.K_KP_ENTER,
    # punctuation aliases (map upper/lower and shifted variants to same key)
    ";": pygame.K_SEMICOLON, ":": pygame.K_SEMICOLON,
    "[": pygame.K_LEFTBRACKET, "{": pygame.K_LEFTBRACKET,
   "]": pygame.K_RIGHTBRACKET, "}": pygame.K_RIGHTBRACKET,
    ",": pygame.K_COMMA, "<": pygame.K_COMMA,
    ".": pygame.K_PERIOD, ">": pygame.K_PERIOD,
    "/": pygame.K_SLASH, "?": pygame.K_SLASH,
    "\\": pygame.K_BACKSLASH, "|": pygame.K_BACKSLASH,
    "-": pygame.K_MINUS, "_": pygame.K_MINUS,
    "=": pygame.K_EQUALS, "+": pygame.K_EQUALS,
    "`": pygame.K_BACKQUOTE, "~": pygame.K_BACKQUOTE,
}

def _tokenize(expr: str) -> List[str]:
    """
    Split an expression into tokens. Accepts either `CTRL+K`, `CTRL + K`,
    or even redundant spacing. Tokens are upper‑cased.
    """
    s = (expr or "").replace("+", " + ").strip()
    parts = [p for p in s.replace("\t", " ").split(" ") if p]
    # Remove literal plus separators
    parts = [p for p in parts if p != "+"]
    return [p.upper() for p in parts]

def _parse_binding(expr: str) -> Optional[Binding]:
    """Return a Binding or None if not understood."""
    toks = _tokenize(expr)
    if not toks:
        return None

    want_ctrl = want_shift = want_alt = want_gui = False
    keycode: Optional[int] = None
    mouse_button: Optional[int] = None
    wheel_dir: Optional[str] = None

    for tok in toks:
        # modifiers
        if tok in _MOD_TOKENS:
            if tok in {"CTRL", "CONTROL"}:
                want_ctrl = True
            elif tok == "SHIFT":
                want_shift = True
            elif tok == "ALT":
                want_alt = True
            elif tok in {"GUI", "META", "SUPER", "CMD"}:
                want_gui = True
            continue

        # mouse buttons
        if tok in _MOUSE_BUTTON_ALIASES:
            mouse_button = _MOUSE_BUTTON_ALIASES[tok]
            continue

        # wheel directions
        if tok in _WHEEL_ALIASES:
            wheel_dir = _WHEEL_ALIASES[tok]
            continue

        # special keycodes
        if tok in _SPECIAL_KEYCODES:
            keycode = _SPECIAL_KEYCODES[tok]
            continue

        # single printable letter or digit (a..z / 0..9)
        if len(tok) == 1:
            ch = tok
            if "A" <= ch <= "Z":
                keycode = getattr(pygame, f"K_{ch.lower()}", None)
                if keycode is not None:
                    continue
            if "0" <= ch <= "9":
                keycode = getattr(pygame, f"K_{ch}", None)
                if keycode is not None:
                    continue

        # fallback unknown -> None
        return None

    # Construct binding by precedence: wheel > mouse > keyboard
    if wheel_dir is not None:
        return Binding(
            kind="wheel",
            wheel_dir=wheel_dir,
            mod_ctrl=want_ctrl, mod_shift=want_shift, mod_alt=want_alt, mod_gui=want_gui,
        )
    if mouse_button is not None:
        return Binding(
            kind="mouse",
            mouse_button=mouse_button,
            mod_ctrl=want_ctrl, mod_shift=want_shift, mod_alt=want_alt, mod_gui=want_gui,
        )
    if keycode is not None:
        return Binding(
            kind="keyboard",
            key=keycode,
            mod_ctrl=want_ctrl, mod_shift=want_shift, mod_alt=want_alt, mod_gui=want_gui,
        )

    return None


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def _event_kind(ev: pygame.event.Event) -> str:
    if ev.type in (pygame.KEYDOWN, pygame.KEYUP):
        return "keyboard"
    if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        # Wheel is a different event in pygame, so this branch is pure mouse button
        return "mouse"
    if ev.type == pygame.MOUSEWHEEL:
        return "wheel"
    return "other"

def _mods_ok_for_state(b: Binding, mods: int) -> bool:
    """Check pressed modifiers against a Binding's requirements for polling or events."""
    if b.mod_ctrl  and not (mods & pygame.KMOD_CTRL):  return False
    if b.mod_shift and not (mods & pygame.KMOD_SHIFT): return False
    if b.mod_alt   and not (mods & pygame.KMOD_ALT):   return False
    if b.mod_gui   and not (mods & pygame.KMOD_GUI):   return False
    return True

