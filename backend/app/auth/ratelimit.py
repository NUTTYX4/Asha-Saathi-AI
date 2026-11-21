"""In-memory login failure limiter (single API process, which is our deployment).

Counts failed logins per (username, client) in a sliding window. A restart clears it; that is
acceptable for the prototype and documented in docs/v2/PROGRESS.md.
"""

import threading
import time
from collections import defaultdict, deque


class LoginRateLimiter:
    def __init__(self, max_failures: int, window_s: int) -> None:
        self.max_failures = max_failures
        self.window_s = window_s
        self._failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: tuple[str, str], now: float) -> deque[float]:
        q = self._failures[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        return q

    def blocked(self, username: str, client: str) -> bool:
        with self._lock:
            return len(self._prune((username, client), time.monotonic())) >= self.max_failures

    def record_failure(self, username: str, client: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune((username, client), now).append(now)

    def reset(self, username: str, client: str) -> None:
        with self._lock:
            self._failures.pop((username, client), None)
