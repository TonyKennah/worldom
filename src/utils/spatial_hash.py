# src/utils/spatial_hash.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import DefaultDict, Dict, Iterable, MutableMapping, Set, Tuple, Any
from collections import defaultdict

Coord = Tuple[int, int]
Rect  = Tuple[float, float, float, float]  # x, y, w, h

@dataclass
class SpatialHash:
    cell: int = 64
    _grid: DefaultDict[Coord, Set[Any]] = field(default_factory=lambda: defaultdict(set))
    _pos: Dict[Any, Tuple[float, float]] = field(default_factory=dict)

    def _key(self, x: float, y: float) -> Coord:
        return int(x)//self.cell, int(y)//self.cell

    def insert(self, obj: Any, x: float, y: float) -> None:
        self._pos[obj] = (x, y)
        self._grid[self._key(x, y)].add(obj)

    def move(self, obj: Any, x: float, y: float) -> None:
        ox, oy = self._pos.get(obj, (None, None))
        if ox is None:  # new
            self.insert(obj, x, y); return
        oldk = self._key(ox, oy)
        newk = self._key(x, y)
        if newk != oldk:
            self._grid[oldk].discard(obj)
            self._grid[newk].add(obj)
        self._pos[obj] = (x, y)

    def remove(self, obj: Any) -> None:
        ox, oy = self._pos.pop(obj, (None, None))
        if ox is not None:
            self._grid[self._key(ox, oy)].discard(obj)

    def query_rect(self, rect: Rect) -> Iterable[Any]:
        x, y, w, h = rect
        x0, y0 = int(x)//self.cell, int(y)//self.cell
        x1, y1 = int(x+w)//self.cell, int(y+h)//self.cell
        seen: Set[Any] = set()
        for gx in range(x0, x1+1):
            for gy in range(y0, y1+1):
                for obj in self._grid.get((gx, gy), ()):
                    if obj not in seen:
                        seen.add(obj)
                        yield obj
