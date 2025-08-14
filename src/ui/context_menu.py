# c:/prj/WorldDom/src/context_menu.py
"""
Context menu state & model.

- Strongly-typed MenuItem model (supports submenus, disabled, checked, shortcuts).
- Backward-compatible defaults for existing code that used `.options`.
- Pure state module (no pygame font creation here) so it can be imported safely
  before pygame.init().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pygame


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass
class MenuItem:
    """
    A single menu item.

    label       : the displayed text. Use "-" or "—" as a separator line item.
    id          : optional command identifier for game logic.
    enabled     : False renders greyed-out and prevents activation.
    checked     : show a checkmark indicator.
    shortcut    : optional display text, e.g. "A" or "Ctrl+M".
    tooltip     : optional string shown in a tooltip area (renderer optional).
    sub_items   : optional submenu items.
    icon        : optional pygame.Surface (16–20px recommended).
    payload     : arbitrary data to attach for callbacks.
    """
    label: str
    id: Optional[str] = None
    enabled: bool = True
    checked: bool = False
    shortcut: Optional[str] = None
    tooltip: Optional[str] = None
    sub_items: List["MenuItem"] = field(default_factory=list)
    icon: Optional[pygame.Surface] = None
    payload: Optional[Dict[str, Any]] = None

    @property
    def is_separator(self) -> bool:
        return self.label.strip() in {"-", "—"}

    @classmethod
    def from_legacy(cls, d: Dict[str, Any]) -> "MenuItem":
        """
        Convert legacy dicts like: {"label": "Build", "sub_options": ["Shelter", ...]}
        """
        label: str = d.get("label", "")
        enabled: bool = d.get("enabled", True)
        checked: bool = d.get("checked", False)
        shortcut: Optional[str] = d.get("shortcut")
        tooltip: Optional[str] = d.get("tooltip")
        payload: Optional[Dict[str, Any]] = d.get("payload")
        id_value: Optional[str] = d.get("id")

        sub_items: List[MenuItem] = []
        # "sub_options" can be list[str] or list[dict]
        if "sub_options" in d and isinstance(d["sub_options"], list):
            for el in d["sub_options"]:
                if isinstance(el, str):
                    sub_items.append(MenuItem(label=el))
                elif isinstance(el, dict):
                    sub_items.append(MenuItem.from_legacy(el))

        return cls(
            label=label,
            id=id_value,
            enabled=enabled,
            checked=checked,
            shortcut=shortcut,
            tooltip=tooltip,
            sub_items=sub_items,
            payload=payload,
        )


@dataclass
class SubMenuState:
    """State of an open submenu (positioning, hover, rects)."""
    active: bool = False
    rects: List[pygame.Rect] = field(default_factory=list)
    parent_rect: Optional[pygame.Rect] = None
    pos: Optional[Tuple[int, int]] = None
    hover_index: Optional[int] = None
    open_side: str = "right"  # "right" or "left"


@dataclass
class ContextMenuState:
    """
    Encapsulates the state of a context menu & user interaction.

    - `items`   : the MenuItems to show (replaces `options`).
    - `rects`   : calculated by the renderer for each item.
    - `hover_index`: which item the mouse is over (-like).
    - `sub_menu`: state for the currently open submenu, if any.
    """
    active: bool = False
    pos: Optional[Tuple[int, int]] = None  # top-left of main menu
    items: List[MenuItem] = field(default_factory=list)
    rects: List[pygame.Rect] = field(default_factory=list)
    hover_index: Optional[int] = None
    target_tile: Optional[Tuple[int, int]] = None
    sub_menu: SubMenuState = field(default_factory=SubMenuState)
    last_selected: Optional[MenuItem] = None

    # ---- Backward compatibility shim ----
    # Old code referenced state.options as list[dict].
    # Here we keep a property bridging to `items` with automatic conversion.
    @property
    def options(self) -> List[Dict[str, Any]]:
        # Return a lightweight dict view (label + nested sub_options) for old call sites.
        def to_dict(mi: MenuItem) -> Dict[str, Any]:
            d: Dict[str, Any] = {"label": mi.label}
            if mi.sub_items:
                d["sub_options"] = [to_dict(s) for s in mi.sub_items]
            if not mi.enabled:
                d["enabled"] = False
            if mi.checked:
                d["checked"] = True
            if mi.shortcut:
                d["shortcut"] = mi.shortcut
            if mi.tooltip:
                d["tooltip"] = mi.tooltip
            if mi.id:
                d["id"] = mi.id
            if mi.payload:
                d["payload"] = mi.payload
            return d

        return [to_dict(mi) for mi in self.items]

    @options.setter
    def options(self, value: List[Dict[str, Any]]) -> None:
        # Accept legacy input and convert to MenuItem.
        self.items = [MenuItem.from_legacy(v) if isinstance(v, dict) else MenuItem(str(v)) for v in value]


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def default_context_menu() -> ContextMenuState:
    """
    Provide the classic default menu structure with richer MenuItems.
    """
    state = ContextMenuState(active=False)
    state.items = [
        MenuItem(label="Attack", id="attack", shortcut="A"),
        MenuItem(
            label="Build",
            id="build",
            sub_items=[
                MenuItem("Shelter", id="build_shelter"),
                MenuItem("Workshop", id="build_workshop"),
                MenuItem("Farm", id="build_farm"),
                MenuItem("Barracks", id="build_barracks"),
            ],
        ),
        MenuItem(label="MoveTo", id="move", shortcut="M"),
        MenuItem(label="-"),  # separator
        MenuItem(label="Cancel", id="cancel", shortcut="Esc"),
    ]
    return state
