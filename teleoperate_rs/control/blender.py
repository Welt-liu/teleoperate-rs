"""Cosine-ease pose interpolation. Used for resume and playback approach."""

from __future__ import annotations

import math

from teleoperate_rs.pose import copy_positions


def cosine_ease(alpha: float) -> float:
    """Map linear 0..1 progress to a cosine ease-in-out factor."""
    clamped = max(0.0, min(1.0, float(alpha)))
    return 0.5 * (1.0 - math.cos(math.pi * clamped))


def blend_positions(
    start: dict[str, float],
    end: dict[str, float],
    alpha: float,
) -> dict[str, float]:
    """Blend two joint dicts. Missing keys fall back to the other side."""
    ease = cosine_ease(alpha)
    names = set(start) | set(end)
    blended: dict[str, float] = {}
    for name in names:
        start_value = float(start.get(name, end.get(name, 0.0)))
        end_value = float(end.get(name, start_value))
        blended[name] = (1.0 - ease) * start_value + ease * end_value
    return blended


class PoseBlender:
    """Blend from a frozen start pose toward a (possibly moving) target."""

    def __init__(self, duration_s: float) -> None:
        if duration_s <= 0.0:
            raise ValueError("duration_s must be greater than zero")
        self.duration_s = float(duration_s)
        self._t0: float | None = None
        self._start: dict[str, float] | None = None

    def begin(self, start: dict[str, float], now: float) -> None:
        self._t0 = float(now)
        self._start = copy_positions(start)

    def step(self, target: dict[str, float], now: float) -> tuple[dict[str, float], bool]:
        if self._t0 is None or self._start is None:
            return copy_positions(target), True
        alpha = (float(now) - self._t0) / self.duration_s
        done = alpha >= 1.0
        blended = blend_positions(self._start, target, min(1.0, alpha))
        return blended, done
