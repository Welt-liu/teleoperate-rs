"""Joint pose helpers. All public angles in this demo are degrees."""

from teleoperate_rs.constants import JOINT_NAMES, RS_FROM_102_DIRECTIONS


def extract_positions(payload: dict[str, object]) -> dict[str, float]:
    """Keep only ``{joint}.pos`` entries from a LeRobot action / observation."""
    positions: dict[str, float] = {}
    for key, value in payload.items():
        if not key.endswith(".pos"):
            continue
        positions[key.removesuffix(".pos")] = float(value)
    return positions


def to_action(positions: dict[str, float]) -> dict[str, float]:
    """Convert a joint-name dict to a LeRobot ``send_action`` payload."""
    return {f"{name}.pos": float(value) for name, value in positions.items()}


def copy_positions(positions: dict[str, float]) -> dict[str, float]:
    return {name: float(value) for name, value in positions.items()}


def apply_joint_scales(
    positions: dict[str, float],
    scales: dict[str, float],
) -> dict[str, float]:
    scaled = copy_positions(positions)
    for name, scale in scales.items():
        if name in scaled:
            scaled[name] = scaled[name] * float(scale)
    return scaled


def to_rs_encoder(
    positions: dict[str, float],
    leader_type: str,
) -> dict[str, float]:
    """Map a leader command into RS motorbridge encoder space.

    RS leader recordings are already encoder degrees. The 102 PyPI leader
    uses the old Seeed follower command space (elbow / wrist_flex / wrist_yaw
    inverted relative to the encoder).
    """
    if leader_type == "rebot_arm_102_leader":
        return apply_joint_scales(positions, RS_FROM_102_DIRECTIONS)
    return copy_positions(positions)


def ordered_joints(positions: dict[str, float]) -> list[str]:
    """Return known joints first, then any extra names in sorted order."""
    known = [name for name in JOINT_NAMES if name in positions]
    extra = sorted(name for name in positions if name not in JOINT_NAMES)
    return known + extra


def format_deg(positions: dict[str, float]) -> str:
    """Format joint angles for a one-line log."""
    parts = [
        f"{name}={positions[name]:+6.1f}"
        for name in ordered_joints(positions)
    ]
    return " ".join(parts)
