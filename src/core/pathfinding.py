from __future__ import annotations
from typing import Iterable, Tuple

SQRT2 = 2 ** 0.5

def octile(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    dx, dy = abs(a[0]-b[0]), abs(a[1]-b[1])
    return (dx + dy) + (SQRT2 - 2.0) * min(dx, dy)

def heuristic(a, b, start) -> float:
    # Standard octile + tiny cross-product tie-breaker to prefer straight paths
    h = octile(a, b)
    cross = abs((a[0]-b[0]) * (start[1]-b[1]) - (a[1]-b[1]) * (start[0]-b[0]))
    return h + cross * 0.001

def iter_neighbors(x: int, y: int, walkable) -> Iterable[Tuple[int,int]]:
    # 8-way neighbors with corner-cutting prevention
    # walkable(nx, ny) -> bool
    card = [(1,0),(-1,0),(0,1),(0,-1)]
    diag = [(1,1),(1,-1),(-1,1),(-1,-1)]
    for dx, dy in card:
        nx, ny = x+dx, y+dy
        if walkable(nx, ny):
            yield (nx, ny)
    for dx, dy in diag:
        nx, ny = x+dx, y+dy
        # prevent cutting corners: both adjacent cards must be walkable
        if walkable(nx, ny) and walkable(x+dx, y) and walkable(x, y+dy):
            yield (nx, ny)
