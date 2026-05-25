"""CircuitBreaker — sliding window failure protection (Harness Module 7)."""

from enum import Enum
from time import time


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, window_seconds: int = 300, failure_threshold: float = 0.5):
        self.window = window_seconds
        self.threshold = failure_threshold
        self.state = State.CLOSED
        self.successes = 0
        self.failures = 0
        self.window_start = time()

    def check(self) -> bool:
        self._rotate_window()
        if self.state == State.OPEN:
            return False
        return True

    def record(self, success: bool):
        self._rotate_window()
        if success:
            self.successes += 1
        else:
            self.failures += 1
        self._update_state()

    def _rotate_window(self):
        if time() - self.window_start > self.window:
            self.successes = 0
            self.failures = 0
            self.window_start = time()

    def _update_state(self):
        total = self.successes + self.failures
        if total == 0:
            return
        rate = self.failures / total
        if self.state == State.CLOSED and rate > self.threshold:
            self.state = State.OPEN
        elif self.state == State.OPEN:
            self.state = State.HALF_OPEN  # will try 1 request
        elif self.state == State.HALF_OPEN:
            self.state = State.CLOSED if rate < self.threshold else State.OPEN
