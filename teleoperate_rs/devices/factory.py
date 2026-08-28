"""Build leader / follower instances.

RS follower and teleop RS leader use motorbridge. Record RS leader uses
reBotArm_control_py demo 9 gravity compensation when enabled. The 102
leader still comes from the published PyPI teleoperator.
"""

from collections.abc import Callable
from typing import Any

from teleoperate_rs.constants import FOLLOWER_TYPES, LEADER_TYPES, UART_LEADER_TYPES
from teleoperate_rs.devices.specs import DeviceSpec
from teleoperate_rs.exceptions import DeviceConfigError

LeaderFactory = Callable[[DeviceSpec], Any]
FollowerFactory = Callable[[DeviceSpec], Any]


def _missing_pypi(package: str) -> DeviceConfigError:
    return DeviceConfigError(
        f"未安装 PyPI 包 {package}。请先执行: pip install {package}"
    )


def _build_rs_arm(spec: DeviceSpec, role: str) -> Any:
    try:
        import motorbridge  # noqa: F401
    except ImportError as exc:
        raise DeviceConfigError(
            "未安装 motorbridge。请先执行: pip install motorbridge"
        ) from exc
    from teleoperate_rs.devices.rs_arm import RsArm
    return RsArm(
        port=spec.port,
        role=role,
        home_on_disconnect=spec.home_on_disconnect,
    )


def _build_rs_leader(spec: DeviceSpec) -> Any:
    if spec.gravity_compensation:
        from teleoperate_rs.devices.gravity_leader import RsGravityLeader

        return RsGravityLeader(
            port=spec.port,
            home_on_disconnect=spec.home_on_disconnect,
        )
    return _build_rs_arm(spec, "leader")


def _build_rs_follower(spec: DeviceSpec) -> Any:
    return _build_rs_arm(spec, "follower")


def _build_rebot_102_leader(spec: DeviceSpec) -> Any:
    try:
        from lerobot_teleoperator_rebot_arm_102 import (
            RebotArm102Leader,
            RebotArm102LeaderConfig,
        )
    except ImportError as exc:
        raise _missing_pypi("lerobot-teleoperator-rebot-arm-102") from exc

    config = RebotArm102LeaderConfig(port=spec.port, id=spec.device_id)
    return RebotArm102Leader(config)


_LEADER_BUILDERS: dict[str, LeaderFactory] = {
    "seeed_b601_rs_leader": _build_rs_leader,
    "rebot_arm_102_leader": _build_rebot_102_leader,
}

_FOLLOWER_BUILDERS: dict[str, FollowerFactory] = {
    "seeed_b601_rs_follower": _build_rs_follower,
}


def _ensure_ports_differ(leader: DeviceSpec, follower: DeviceSpec) -> None:
    if leader.port == follower.port and leader.type_name not in UART_LEADER_TYPES:
        raise DeviceConfigError(
            f"Leader 与 follower 不能共用同一 CAN 口 {leader.port!r}。"
            "请分别指定例如 can0 / can1。"
        )
    if (
        leader.type_name in UART_LEADER_TYPES
        and leader.port == follower.port
    ):
        raise DeviceConfigError(
            f"Leader 与 follower 不能共用同一端口 {leader.port!r}。"
        )


def build_leader(spec: DeviceSpec) -> Any:
    builder = _LEADER_BUILDERS.get(spec.type_name)
    if builder is None:
        raise DeviceConfigError(
            f"未知 leader 类型 {spec.type_name!r}。可选: {', '.join(LEADER_TYPES)}"
        )
    return builder(spec)


def build_follower(spec: DeviceSpec) -> Any:
    builder = _FOLLOWER_BUILDERS.get(spec.type_name)
    if builder is None:
        raise DeviceConfigError(
            f"未知 follower 类型 {spec.type_name!r}。可选: {', '.join(FOLLOWER_TYPES)}"
        )
    return builder(spec)


def assert_teleop_ports(leader: DeviceSpec, follower: DeviceSpec) -> None:
    _ensure_ports_differ(leader, follower)
