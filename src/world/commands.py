# c:/prj/WorldDom/src/commands.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict, replace
from typing import Optional, Tuple, Dict, Any, List, Iterable
import enum
import time
import uuid
import math
import pygame

Vec2 = pygame.math.Vector2


# --------------------------------------------------------------------------------------
# Core command types (kept + expanded)
# --------------------------------------------------------------------------------------
class CommandType(enum.Enum):
    MOVE   = "move"
    ATTACK = "attack"
    STOP   = "stop"
    HOLD   = "hold"
    PATROL = "patrol"

    # NEW
    FOLLOW   = "follow"    # follow another unit
    DEFEND   = "defend"    # hold/guard an area (pos + radius)
    RALLY    = "rally"     # regroup at a position (optionally with squad id)
    BUILD    = "build"     # build structure at a pos (meta: structure)
    GATHER   = "gather"    # gather from resource (meta: resource_id or target_pos)
    FORMATION = "formation"  # set unit/selection formation (meta: shape, spacing)


class Priority(enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DispatchPolicy(enum.Enum):
    """How to handle incoming commands when a unit already has orders."""
    QUEUE = "queue"        # append
    REPLACE = "replace"    # clear current and execute immediately
    DROP_IF_BUSY = "drop"  # ignore if unit is busy


# --------------------------------------------------------------------------------------
# Command dataclass
# --------------------------------------------------------------------------------------
@dataclass
class Command:
    """
    Lightweight, serializable order packet. Compatible with previous fields, plus:
    - command_id: unique id for cancellation/ack
    - priority: scheduling hint
    - policy: queue/replace/drop
    - source_unit_id: who issued the command (optional)
    - squad_id: logical group/rally membership
    - execute_at: schedule this command to start at/after timestamp (s)
    - expires_at: discard if not started by this timestamp (s)
    - path: optional multi-point world path (Vec2)
    - radius: optional area size (e.g., DEFEND area)
    """
    kind: CommandType
    target_pos: Optional[Vec2] = None
    target_unit_id: Optional[int] = None
    queue: bool = False
    issued_at: float = field(default_factory=lambda: time.time())
    meta: Dict[str, Any] = field(default_factory=dict)

    # NEW
    command_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    priority: Priority = Priority.NORMAL
    policy: DispatchPolicy = DispatchPolicy.QUEUE
    source_unit_id: Optional[int] = None
    squad_id: Optional[str] = None
    execute_at: Optional[float] = None
    expires_at: Optional[float] = None
    path: Optional[List[Vec2]] = None
    radius: Optional[float] = None

    # ------------------------- Serialization -------------------------
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Normalize enums & vectors
        d["kind"] = self.kind.value
        d["priority"] = self.priority.value
        d["policy"] = self.policy.value
        if self.target_pos is not None:
            d["target_pos"] = (float(self.target_pos.x), float(self.target_pos.y))
        if self.path is not None:
            d["path"] = [(float(p.x), float(p.y)) for p in self.path]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Command":
        pos = d.get("target_pos")
        path_seq = d.get("path")
        v = Vec2(pos) if pos is not None else None
        path = [Vec2(p) for p in path_seq] if path_seq else None
        return Command(
            kind=CommandType(d["kind"]),
            target_pos=v,
            target_unit_id=d.get("target_unit_id"),
            queue=bool(d.get("queue", False)),
            issued_at=float(d.get("issued_at", time.time())),
            meta=dict(d.get("meta", {})),
            command_id=d.get("command_id", uuid.uuid4().hex),
            priority=Priority(d.get("priority", Priority.NORMAL.value)),
            policy=DispatchPolicy(d.get("policy", DispatchPolicy.QUEUE.value)),
            source_unit_id=d.get("source_unit_id"),
            squad_id=d.get("squad_id"),
            execute_at=d.get("execute_at"),
            expires_at=d.get("expires_at"),
            path=path,
            radius=d.get("radius"),
        )

    # JSON alias (backwards-friendly)
    def to_json(self) -> Dict[str, Any]:
        return self.to_dict()

    @staticmethod
    def from_json(data: Dict[str, Any]) -> "Command":
        return Command.from_dict(data)

    # ------------------------- Convenience & safety -------------------------
    def age(self) -> float:
        return max(0.0, time.time() - self.issued_at)

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.expires_at is None:
            return False
        t = time.time() if now is None else now
        return t >= float(self.expires_at)

    def is_scheduled(self, now: Optional[float] = None) -> bool:
        if self.execute_at is None:
            return False
        t = time.time() if now is None else now
        return t < float(self.execute_at)

    def is_point_command(self) -> bool:
        return self.target_pos is not None or bool(self.path)

    def is_targeting_unit(self) -> bool:
        return self.target_unit_id is not None

    def clone(self, **changes: Any) -> "Command":
        """Return a shallow copy with changes (keeps same command_id unless overridden)."""
        return replace(self, **changes)

    def with_meta(self, **kvs: Any) -> "Command":
        m = dict(self.meta)
        m.update(kvs)
        return self.clone(meta=m)

    def validate(self) -> None:
        """Best-effort sanity checks; raises ValueError if invalid for its kind."""
        k = self.kind
        if k in (CommandType.MOVE,):
            if (self.target_pos is None) and not self.path:
                raise ValueError("MOVE requires target_pos or path")
        elif k in (CommandType.ATTACK,):
            if self.target_unit_id is None and self.target_pos is None:
                raise ValueError("ATTACK requires target_unit_id or target_pos (for ground-attack)")
        elif k in (CommandType.PATROL,):
            if self.target_pos is None or "b" not in self.meta:
                raise ValueError("PATROL requires target_pos (A) and meta['b'] (B)")
        elif k in (CommandType.FOLLOW,):
            if self.target_unit_id is None:
                raise ValueError("FOLLOW requires target_unit_id")
        elif k in (CommandType.DEFEND,):
            if self.target_pos is None or (self.radius is None or self.radius <= 0):
                raise ValueError("DEFEND requires target_pos and positive radius")
        elif k in (CommandType.RALLY,):
            if self.target_pos is None:
                raise ValueError("RALLY requires target_pos")
        elif k in (CommandType.BUILD,):
            if self.target_pos is None or "structure" not in self.meta:
                raise ValueError("BUILD requires target_pos and meta['structure']")
        elif k in (CommandType.GATHER,):
            if self.target_pos is None and "resource_id" not in self.meta:
                raise ValueError("GATHER requires target_pos or meta['resource_id']")
        # STOP/HOLD/FORMATION have flexible payloads

    # Scheduling sugar
    def schedule_in(self, seconds: float) -> "Command":
        return self.clone(execute_at=time.time() + max(0.0, float(seconds)))

    def expire_in(self, seconds: float) -> "Command":
        return self.clone(expires_at=time.time() + max(0.0, float(seconds)))

    def with_priority(self, pri: Priority) -> "Command":
        return self.clone(priority=pri)

    def with_policy(self, pol: DispatchPolicy) -> "Command":
        return self.clone(policy=pol)


# --------------------------------------------------------------------------------------
# Small helpers for authoring (kept + expanded)
# --------------------------------------------------------------------------------------
def move_to(pos: Tuple[float, float], *, queue: bool = False, path: Optional[Iterable[Tuple[float, float]]] = None) -> Command:
    cmd = Command(kind=CommandType.MOVE, target_pos=Vec2(pos), queue=queue)
    if path:
        cmd.path = [Vec2(p) for p in path]
    return cmd

def move_path(points: Iterable[Tuple[float, float]], *, queue: bool = False) -> Command:
    pts = [Vec2(p) for p in points]
    return Command(kind=CommandType.MOVE, path=pts, queue=queue, target_pos=pts[-1] if pts else None)

def attack_target(unit_id: int, *, queue: bool = False) -> Command:
    return Command(kind=CommandType.ATTACK, target_unit_id=unit_id, queue=queue)

def attack_ground(pos: Tuple[float, float], *, queue: bool = False, radius: Optional[float] = None) -> Command:
    return Command(kind=CommandType.ATTACK, target_pos=Vec2(pos), queue=queue, radius=radius)

def stop() -> Command:
    return Command(kind=CommandType.STOP)

def hold() -> Command:
    return Command(kind=CommandType.HOLD)

def patrol(a: Tuple[float, float], b: Tuple[float, float], *, queue: bool = False) -> Command:
    return Command(kind=CommandType.PATROL, target_pos=Vec2(a), meta={"b": tuple(b)}, queue=queue)

# NEW helpers
def follow(unit_id: int, *, queue: bool = False, distance: float = 48.0) -> Command:
    return Command(kind=CommandType.FOLLOW, target_unit_id=unit_id, queue=queue, meta={"distance": float(distance)})

def defend_area(center: Tuple[float, float], radius: float, *, queue: bool = False) -> Command:
    return Command(kind=CommandType.DEFEND, target_pos=Vec2(center), radius=float(radius), queue=queue)

def rally_at(pos: Tuple[float, float], squad_id: Optional[str] = None, *, queue: bool = False) -> Command:
    return Command(kind=CommandType.RALLY, target_pos=Vec2(pos), squad_id=squad_id, queue=queue)

def build_at(structure: str, pos: Tuple[float, float], *, queue: bool = False) -> Command:
    return Command(kind=CommandType.BUILD, target_pos=Vec2(pos), queue=queue, meta={"structure": structure})

def gather_from(pos: Optional[Tuple[float, float]] = None, resource_id: Optional[int] = None, *, queue: bool = False) -> Command:
    meta: Dict[str, Any] = {}
    if resource_id is not None:
        meta["resource_id"] = resource_id
    return Command(kind=CommandType.GATHER, target_pos=Vec2(pos) if pos else None, queue=queue, meta=meta)

def set_formation(shape: str = "line", spacing: float = 24.0, facing_deg: Optional[float] = None) -> Command:
    return Command(kind=CommandType.FORMATION, meta={"shape": shape, "spacing": float(spacing), "facing_deg": facing_deg})


# --------------------------------------------------------------------------------------
# NEW: CommandQueue helper for units/squads
# --------------------------------------------------------------------------------------
class CommandQueue:
    """Small utility to manage a per-unit command queue with compression and cancellation."""
    def __init__(self) -> None:
        self._q: List[Command] = []

    def __len__(self) -> int:
        return len(self._q)

    def __iter__(self):
        return iter(self._q)

    def to_list(self) -> List[Command]:
        return list(self._q)

    def clear(self) -> None:
        self._q.clear()

    def push(self, cmd: Command) -> None:
        self._q.append(cmd)

    def push_front(self, cmd: Command) -> None:
        self._q.insert(0, cmd)

    def pop(self) -> Optional[Command]:
        return self._q.pop(0) if self._q else None

    def peek(self) -> Optional[Command]:
        return self._q[0] if self._q else None

    def cancel(self, command_id: str) -> bool:
        """Remove a command by id; return True if found."""
        for i, c in enumerate(self._q):
            if c.command_id == command_id:
                del self._q[i]
                return True
        return False

    def drop_by_type(self, kind: CommandType) -> int:
        """Remove all commands of a given type. Returns number removed."""
        before = len(self._q)
        self._q = [c for c in self._q if c.kind != kind]
        return before - len(self._q)

    def compress_moves(self, tolerance_px: float = 6.0) -> None:
        """
        Coalesce consecutive MOVE commands with very close target positions to reduce path spam.
        """
        out: List[Command] = []
        last_move: Optional[Command] = None

        def dist(a: Vec2, b: Vec2) -> float:
            return math.hypot(a.x - b.x, a.y - b.y)

        for cmd in self._q:
            if cmd.kind == CommandType.MOVE and cmd.target_pos is not None and last_move is not None and last_move.target_pos is not None:
                if dist(cmd.target_pos, last_move.target_pos) <= tolerance_px:
                    # Merge by keeping the latter's metadata (most recent)
                    last_move = last_move.clone(
                        meta={**last_move.meta, **cmd.meta},
                        issued_at=min(last_move.issued_at, cmd.issued_at),
                        command_id=last_move.command_id,  # keep id stable
                    )
                    out[-1] = last_move
                else:
                    out.append(cmd)
                    last_move = cmd
            else:
                out.append(cmd)
                last_move = cmd if cmd.kind == CommandType.MOVE else None

        self._q = out

    def purge_expired(self) -> int:
        """Remove commands whose expires_at has passed."""
        now = time.time()
        before = len(self._q)
        self._q = [c for c in self._q if not c.is_expired(now)]
        return before - len(self._q)

    def schedule_ready(self) -> List[Command]:
        """
        Return commands that are ready to execute now (not scheduled in future),
        without removing them.
        """
        now = time.time()
        return [c for c in self._q if not c.is_scheduled(now)]


# --------------------------------------------------------------------------------------
# NOTE: The original functions (move_to, attack_target, stop, hold, patrol) are retained.
# --------------------------------------------------------------------------------------
