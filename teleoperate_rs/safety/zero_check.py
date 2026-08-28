"""Refuse to start unless every reported joint is near mechanical zero."""

from teleoperate_rs.constants import DEFAULT_ZERO_TOLERANCE_DEG
from teleoperate_rs.exceptions import ZeroPoseError
from teleoperate_rs.pose import ordered_joints


def collect_violations(
    positions: dict[str, float],
    tolerance_deg: float = DEFAULT_ZERO_TOLERANCE_DEG,
) -> list[str]:
    """Return human-readable lines for joints outside ±tolerance_deg."""
    violations: list[str] = []
    for name in ordered_joints(positions):
        angle = float(positions[name])
        if abs(angle) > float(tolerance_deg):
            violations.append(
                f"  {name:16s} {angle:+7.1f} deg  (limit ±{tolerance_deg:g})"
            )
    return violations


def assert_near_zero(
    positions: dict[str, float],
    role: str,
    tolerance_deg: float = DEFAULT_ZERO_TOLERANCE_DEG,
) -> None:
    """Raise ZeroPoseError if any joint of *role* is not near zero."""
    violations = collect_violations(positions, tolerance_deg)
    if not violations:
        return
    detail = "\n".join(violations)
    message = (
        f"[zero-check] {role} 不在零点附近（容差 ±{tolerance_deg:g} deg）:\n"
        f"{detail}\n"
        "请将机械臂放到机械零位后再启动。"
    )
    raise ZeroPoseError(message, violations)
