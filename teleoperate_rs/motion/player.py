"""Loop a recorded trajectory with a cosine approach into the start pose."""

from __future__ import annotations

from teleoperate_rs.control.blender import blend_positions
from teleoperate_rs.constants import DEFAULT_APPROACH_DURATION_S
from teleoperate_rs.pose import copy_positions


class LoopingPlayer:
    """Each cycle: ease to frame 0, then play the recorded frames."""

    def __init__(
        self,
        frames: list[dict[str, float]],
        rate_hz: float,
        approach_duration_s: float = DEFAULT_APPROACH_DURATION_S,
    ) -> None:
        if not frames:
            raise ValueError("frames must not be empty")
        if rate_hz <= 0.0:
            raise ValueError("rate_hz must be greater than zero")
        if approach_duration_s <= 0.0:
            raise ValueError("approach_duration_s must be greater than zero")
        self.frames = [copy_positions(frame) for frame in frames]
        self.rate_hz = float(rate_hz)
        self.approach_duration_s = float(approach_duration_s)
        self.n_frames = len(self.frames)
        self.motion_s = self.n_frames / self.rate_hz
        self.cycle_s = self.approach_duration_s + self.motion_s
        self.start = copy_positions(self.frames[0])
        self.end = copy_positions(self.frames[-1])
        self._t0: float | None = None
        self._first_pose: dict[str, float] | None = None
        self.cycle = 0
        self.phase = "approach"
        self.frame_index = 0

    def start_clock(self, now: float, current: dict[str, float]) -> None:
        """``current`` must be in send_action space, not raw encoder readings."""
        self._t0 = float(now)
        self._first_pose = copy_positions(current)

    def sample(self, now: float) -> dict[str, float]:
        if self._t0 is None:
            raise RuntimeError("LoopingPlayer.start_clock() was not called")
        elapsed = max(0.0, float(now) - self._t0)
        self.cycle = int(elapsed // self.cycle_s)
        local = elapsed - self.cycle * self.cycle_s
        if local < self.approach_duration_s:
            alpha = min(1.0, local / self.approach_duration_s)
            arm_from = self._first_pose if self.cycle == 0 else self.end
            if arm_from is None:
                arm_from = self.start
            self.phase = "approach"
            self.frame_index = 0
            return blend_positions(arm_from, self.start, alpha)
        t_motion = local - self.approach_duration_s
        idx = min(int(t_motion * self.rate_hz), self.n_frames - 1)
        self.phase = "play"
        self.frame_index = idx
        return copy_positions(self.frames[idx])

    def describe(self) -> str:
        return (
            f"approach {self.approach_duration_s:.1f}s + "
            f"motion {self.motion_s:.2f}s @ {self.rate_hz:.0f} Hz"
        )
