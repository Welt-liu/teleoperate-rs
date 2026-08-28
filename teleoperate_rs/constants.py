"""Shared constants. Do not scatter magic numbers in business code."""

from pathlib import Path

JOINT_NAMES: tuple[str, ...] = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_yaw",
    "wrist_roll",
    "gripper",
)

GRIPPER_JOINT = "gripper"

DEFAULT_RATE_HZ = 60.0
DEFAULT_GRIPPER_SCALE = 3.0
DEFAULT_ZERO_TOLERANCE_DEG = 10.0
DEFAULT_RESUME_DURATION_S = 3.0
DEFAULT_APPROACH_DURATION_S = 2.0
DEFAULT_SETTLE_S = 0.2
DEFAULT_LOG_PERIOD_S = 1.0
DEFAULT_KEYBOARD_POLL_S = 0.05

DEFAULT_LEADER_TYPE = "seeed_b601_rs_leader"
DEFAULT_FOLLOWER_TYPE = "seeed_b601_rs_follower"
DEFAULT_LEADER_PORT = "can0"
DEFAULT_FOLLOWER_PORT = "can1"
DEFAULT_CAN_ADAPTER = "socketcan"
DEFAULT_LEADER_ID = "leader"
DEFAULT_FOLLOWER_ID = "follower"

# 102 UART: Linux 常见 /dev/ttyUSB0。macOS 在运行时探测 /dev/cu.usb*。
DEFAULT_UART_LEADER_PORT = "/dev/ttyUSB0"

DEFAULT_MOTION_DIR = Path("datasets/rs_motions")

LEADER_TYPES: tuple[str, ...] = (
    "seeed_b601_rs_leader",
    "rebot_arm_102_leader",
)

FOLLOWER_TYPES: tuple[str, ...] = (
    "seeed_b601_rs_follower",
)

UART_LEADER_TYPES = frozenset({"rebot_arm_102_leader"})
CAN_PORT_PREFIX = "can"
MIN_MOTION_SPAN_DEG = 5.0

# RobStride host/feedback id (rebotarm_rs.yaml).
RS_ROBSTRIDE_HOST_ID = 0xFD
RS_MOTOR_CAN_IDS: dict[str, tuple[int, int]] = {
    name: (index, RS_ROBSTRIDE_HOST_ID)
    for index, name in enumerate(JOINT_NAMES, start=1)
}

# Same physical B601-RS arm as rebotarm_rs.yaml (joints 1-3 rs-06, 4-7 rs-00).
RS_FOLLOWER_MOTOR_MODELS: dict[str, str] = {
    "shoulder_pan": "rs-06",
    "shoulder_lift": "rs-06",
    "elbow_flex": "rs-06",
    "wrist_flex": "rs-00",
    "wrist_yaw": "rs-00",
    "wrist_roll": "rs-00",
    "gripper": "rs-00",
}

# YAML MIT kp/kd for follower arm joints (gripper uses torque-limited MIT).
RS_MIT_KP: dict[str, float] = {
    "shoulder_pan": 50.0,
    "shoulder_lift": 150.0,
    "elbow_flex": 150.0,
    "wrist_flex": 50.0,
    "wrist_yaw": 50.0,
    "wrist_roll": 50.0,
}
RS_MIT_KD: dict[str, float] = {
    "shoulder_pan": 3.0,
    "shoulder_lift": 10.0,
    "elbow_flex": 10.0,
    "wrist_flex": 5.0,
    "wrist_yaw": 4.0,
    "wrist_roll": 4.0,
}

# isaacsim rs_can_common gripper impedance (radians).
GRIPPER_MIT_KP = 12.0
GRIPPER_MIT_KD = 0.05
GRIPPER_MIT_CMD_KD = 1.5
GRIPPER_TORQUE_LIMIT = 3.5
GRIPPER_HOLD_TORQUE_LIMIT = 1.0
GRIPPER_HOLD_VEL_THRESH = 0.25
GRIPPER_TARGET_VEL_MAX = 3.0
GRIPPER_VEL_LPF_ALPHA = 0.3

HOME_DURATION_S = 5.0
HOME_RATE_HZ = 60.0

# Official Seeed RS follower joint_directions except gripper (ActionMapper owns scale).
# Maps 102 PyPI leader command space onto RS encoder space.
RS_FROM_102_DIRECTIONS: dict[str, float] = {
    "elbow_flex": -1.0,
    "wrist_flex": -1.0,
    "wrist_yaw": -1.0,
}
