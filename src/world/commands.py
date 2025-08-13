# c:/prj/WorldDom/src/commands.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple, Dict, Any
import enum
import time
import pygame

Vec2 = pygame.math.Vector2

class CommandType(enum.Enum):
    MOVE   = "move"
    ATTACK = "attack"
    STOP   = "stop"
    HOLD   = "hold"
    PATROL = "patrol"

@dataclass
class Command:
    """Lightweight order packet you can pass to units or queue in WorldState."""
    kind: CommandType
    target_pos: Optional[Vec2] = None
    target_unit_id: Optional[int] = None
    queue: bool = False
    issued_at: float = field(default_factory=lambda: time.time())
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.target_pos is not None:
            d["target_pos"] = (float(self.target_pos.x), float(self.target_pos.y))
        d["kind"] = self.kind.value
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Command":
        pos = d.get("target_pos")
        v = Vec2(pos) if pos is not None else None
        return Command(
            kind=CommandType(d["kind"]),
            target_pos=v,
            target_unit_id=d.get("target_unit_id"),
            queue=bool(d.get("queue", False)),
            issued_at=float(d.get("issued_at", time.time())),
            meta=dict(d.get("meta", {})),
        )

# Small helpers for authoring
def move_to(pos: Tuple[float, float], *, queue: bool = False) -> Command:
    return Command(kind=CommandType.MOVE, target_pos=Vec2(pos), queue=queue)

def attack_target(unit_id: int, *, queue: bool = False) -> Command:
    return Command(kind=CommandType.ATTACK, target_unit_id=unit_id, queue=queue)

def stop() -> Command:
    return Command(kind=CommandType.STOP)

def hold() -> Command:
    return Command(kind=CommandType.HOLD)

def patrol(a: Tuple[float, float], b: Tuple[float, float], *, queue: bool = False) -> Command:
    return Command(kind=CommandType.PATROL, target_pos=Vec2(a), meta={"b": tuple(b)}, queue=queue)
