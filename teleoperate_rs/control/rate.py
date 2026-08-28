"""Sleep the remainder of a control period."""

import time


class RateLimiter:
    def __init__(self, rate_hz: float) -> None:
        if rate_hz <= 0.0:
            raise ValueError("rate_hz must be greater than zero")
        self.period_s = 1.0 / float(rate_hz)
        self._next = time.perf_counter()

    def sleep(self) -> None:
        self._next += self.period_s
        remaining = self._next - time.perf_counter()
        if remaining > 0.0:
            time.sleep(remaining)
        else:
            self._next = time.perf_counter()
