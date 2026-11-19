from __future__ import annotations

import threading
import time
from typing import Any


class InMemoryRunTileCache:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str, *, max_age_seconds: int = 1800) -> dict[str, str | None] | None:
        with self._lock:
            item = self._items.get(run_id)
        if not item:
            return None
        if time.time() - float(item.get("timestamp", 0)) > max_age_seconds:
            with self._lock:
                self._items.pop(run_id, None)
            return None
        return dict(item.get("tiles") or {})

    def set(self, run_id: str, tiles: dict[str, str | None]) -> None:
        with self._lock:
            self._items[run_id] = {"timestamp": time.time(), "tiles": dict(tiles)}
