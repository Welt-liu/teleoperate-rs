"""Map leader joint angles onto follower commands."""

from __future__ import annotations

from teleoperate_rs.constants import DEFAULT_GRIPPER_SCALE, GRIPPER_JOINT
from teleoperate_rs.pose import copy_positions


class ActionMapper:
    """1:1 arm copy plus relative gripper scale from the connect pose.

    Follower gripper command:
        follow0 + scale * (leader_now - leader0)
    """

    def __init__(self, gripper_scale: float = DEFAULT_GRIPPER_SCALE) -> None:
        if gripper_scale == 0.0:
            raise ValueError("gripper_scale cannot be zero")
        self.gripper_scale = float(gripper_scale)
        self._leader_grip0 = 0.0
        self._follower_grip0 = 0.0
        self._captured = False

    def capture_reference(
        self,
        leader: dict[str, float],
        follower: dict[str, float] | None = None,
    ) -> None:
        """``follower`` gripper must be in encoder / send_action space when provided."""
        self._leader_grip0 = float(leader.get(GRIPPER_JOINT, 0.0))
        if follower is None:
            self._follower_grip0 = 0.0
        else:
            self._follower_grip0 = float(follower.get(GRIPPER_JOINT, 0.0))
        self._captured = True

    def map(self, leader: dict[str, float]) -> dict[str, float]:
        mapped = copy_positions(leader)
        if GRIPPER_JOINT not in mapped:
            return mapped
        if not self._captured:
            self.capture_reference(leader)
        mapped[GRIPPER_JOINT] = self._follower_grip0 + self.gripper_scale * (
            mapped[GRIPPER_JOINT] - self._leader_grip0
        )
        return mapped
