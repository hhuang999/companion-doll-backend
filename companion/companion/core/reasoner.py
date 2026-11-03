"""Per-user serial scheduler with durable end jobs owned by the core/store."""

import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ReasonerScheduler:
    def __init__(self, workers: int, run: Callable[[str, str, tuple[str, ...]], None]) -> None:
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="reasoner")
        self.run = run
        self.condition = threading.Condition()
        self.pending: dict[str, dict[tuple[str, str], set[str]]] = defaultdict(dict)
        self.running: set[str] = set()
        self.closed = False

    def submit(self, user_key: str, session_id: str, trigger: str, kind: str = "normal") -> None:
        with self.condition:
            if self.closed:
                return
            jobs = self.pending[user_key]
            if kind == "end":
                jobs.pop((session_id, "normal"), None)
            elif (session_id, "end") in jobs:
                return
            jobs.setdefault((session_id, kind), set()).add(trigger)
            if user_key not in self.running:
                self.running.add(user_key)
                self.pool.submit(self._drain, user_key)

    def _drain(self, user_key: str) -> None:
        while True:
            with self.condition:
                jobs = self.pending[user_key]
                if not jobs:
                    self.running.discard(user_key)
                    self.pending.pop(user_key, None)
                    self.condition.notify_all()
                    return
                key = next((key for key in jobs if key[1] == "end"), next(iter(jobs)))
                reasons = tuple(sorted(jobs.pop(key)))
            try:
                self.run(key[0], key[1], reasons)
            except Exception:
                # Core records model/DB failures; this is a last-resort worker boundary.
                logger.exception("Reasoner worker failed for session %s", key[0])

    def wait_idle(self, timeout: float = 25, user_key: str | None = None) -> bool:
        deadline = time.monotonic() + timeout
        with self.condition:
            while user_key in self.running if user_key else bool(self.running):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
            return True

    def close(self) -> None:
        with self.condition:
            self.closed = True
        self.pool.shutdown(wait=True, cancel_futures=False)
