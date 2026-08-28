"""Runtime settings filled from the CLI. One object is passed down the stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from teleoperate_rs.constants import (
    DEFAULT_APPROACH_DURATION_S,
    DEFAULT_CAN_ADAPTER,
    DEFAULT_FOLLOWER_PORT,
    DEFAULT_FOLLOWER_TYPE,
    DEFAULT_GRIPPER_SCALE,
    DEFAULT_LEADER_PORT,
    DEFAULT_LEADER_TYPE,
    DEFAULT_MOTION_DIR,
    DEFAULT_RATE_HZ,
    DEFAULT_RESUME_DURATION_S,
    DEFAULT_ZERO_TOLERANCE_DEG,
)


@dataclass
class DemoSettings:
    leader_type: str = DEFAULT_LEADER_TYPE
    leader_port: str = DEFAULT_LEADER_PORT
    leader_can_adapter: str = DEFAULT_CAN_ADAPTER
    follower_type: str = DEFAULT_FOLLOWER_TYPE
    follower_port: str = DEFAULT_FOLLOWER_PORT
    follower_can_adapter: str = DEFAULT_CAN_ADAPTER
    rate_hz: float = DEFAULT_RATE_HZ
    gripper_scale: float = DEFAULT_GRIPPER_SCALE
    zero_tolerance_deg: float = DEFAULT_ZERO_TOLERANCE_DEG
    skip_zero_check: bool = False
    gravity_compensation: bool = False
    meshcat: bool = True
    resume_duration_s: float = DEFAULT_RESUME_DURATION_S
    approach_duration_s: float = DEFAULT_APPROACH_DURATION_S
    motion_dir: Path = DEFAULT_MOTION_DIR
    motion_path: Path | None = None
    name: str = ""
