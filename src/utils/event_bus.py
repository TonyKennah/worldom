# c:/prj/WorldDom/src/utils/event_bus.py
from __future__ import annotations
from typing import Any, Callable, DefaultDict, Dict, List
from collections import defaultdict


class EventBus:
    """
    Ultra-light pub/sub bus:
        off = bus.on("toast", lambda payload: ...)
        bus.emit("toast", text="Hello")
        off()  # unsubscribe
    """
    def __init__(self) -> None:
        self._subs: DefaultDict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)

    def on(self, event: str, handler: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        self._subs[event].append(handler)
        def off() -> None:
            try:
                self._subs[event].remove(handler)
            except ValueError:
                pass
        return off

    def emit(self, event: str, **payload: Any) -> None:
        for h in list(self._subs.get(event, ())):
            h(payload)


# shared instance
bus = EventBus()
