"""Space-to-pause / space-to-resume state machine for teleoperation."""

from __future__ import annotations

from enum import Enum

from teleoperate_rs.control.blender import PoseBlender
from teleoperate_rs.constants import DEFAULT_RESUME_DURATION_S
from teleoperate_rs.pose import copy_positions


class TeleopMode(str, Enum):
    LIVE = "live"
    PAUSED = "paused"
    RESUMING = "resuming"


class PauseController:
    """Hold the last *command* while paused; ease back to the live leader.

    Commands are already in RS encoder space (after 102→encoder mapping).
    Freeze the last sent command, not the follower observation.

    Resume interpolates from the frozen command toward the current leader
    command over ``resume_duration_s``.
    """

    def __init__(self, resume_duration_s: float = DEFAULT_RESUME_DURATION_S) -> None:
        if resume_duration_s <= 0.0:
            raise ValueError("resume_duration_s must be greater than zero")
        self.mode = TeleopMode.LIVE
        self._hold: dict[str, float] | None = None
        self._last: dict[str, float] | None = None
        self._blender = PoseBlender(resume_duration_s)

    def hold_at(self, positions: dict[str, float]) -> None:
        """Freeze *positions* as if the operator had just paused."""
        self._hold = copy_positions(positions)
        self._last = copy_positions(positions)
        self.mode = TeleopMode.PAUSED

    def toggle(self, live: dict[str, float], now: float) -> TeleopMode:
        frozen = self._last if self._last is not None else live
        if self.mode == TeleopMode.LIVE:
            self._hold = copy_positions(frozen)
            self.mode = TeleopMode.PAUSED
            return self.mode
        if self.mode == TeleopMode.PAUSED:
            start = self._hold if self._hold is not None else frozen
            self._blender.begin(start, now)
            self.mode = TeleopMode.RESUMING
            return self.mode
        self._hold = copy_positions(frozen)
        self.mode = TeleopMode.PAUSED
        return self.mode

    def command(self, live: dict[str, float], now: float) -> dict[str, float]:
        if self.mode == TeleopMode.PAUSED:
            if self._hold is None:
                self._hold = copy_positions(live)
            output = copy_positions(self._hold)
        elif self.mode == TeleopMode.RESUMING:
            blended, done = self._blender.step(live, now)
            if done:
                self.mode = TeleopMode.LIVE
                self._hold = None
                output = copy_positions(live)
            else:
                output = blended
        else:
            output = copy_positions(live)
        self._last = copy_positions(output)
        return output
