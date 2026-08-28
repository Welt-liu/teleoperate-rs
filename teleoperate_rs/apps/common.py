"""Shared CLI flags and startup helpers for teleop / record / play."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any

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
    DEFAULT_SETTLE_S,
    DEFAULT_ZERO_TOLERANCE_DEG,
    FOLLOWER_TYPES,
    LEADER_TYPES,
    UART_LEADER_TYPES,
)
from teleoperate_rs.devices.can import looks_like_can_port, require_can_interface
from teleoperate_rs.devices.serial import (
    require_uart_port,
    resolve_default_uart_port,
)
from teleoperate_rs.pose import extract_positions
from teleoperate_rs.safety import assert_near_zero, collect_violations
from teleoperate_rs.settings import DemoSettings

logger = logging.getLogger(__name__)


def add_common_flags(
    parser: argparse.ArgumentParser,
    *,
    rate_default: float = DEFAULT_RATE_HZ,
) -> None:
    parser.add_argument(
        "--rate",
        type=float,
        default=rate_default,
        help=f"控制频率 Hz（默认 {rate_default:g}）",
    )
    parser.add_argument(
        "--gripper-scale",
        type=float,
        default=DEFAULT_GRIPPER_SCALE,
        help=f"follower 夹爪增量 / leader 夹爪增量（默认 {DEFAULT_GRIPPER_SCALE:g}）",
    )
    parser.add_argument(
        "--zero-tolerance-deg",
        type=float,
        default=DEFAULT_ZERO_TOLERANCE_DEG,
        help=f"启动前关节相对零点的最大偏差（默认 {DEFAULT_ZERO_TOLERANCE_DEG:g} deg）",
    )
    parser.add_argument(
        "--skip-zero-check",
        action="store_true",
        help="跳过零点核对（仅调试用）",
    )


def add_leader_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--leader-type",
        choices=LEADER_TYPES,
        default=DEFAULT_LEADER_TYPE,
        help="Leader 类型：RS 走 motorbridge，102 走 PyPI",
    )
    parser.add_argument(
        "--leader-port",
        default=None,
        help="Leader 端口。B601 CAN 默认 can0；102 UART 未指定时自动探测（macOS 为 /dev/cu.usb*）",
    )
    parser.add_argument(
        "--leader-can-adapter",
        default=DEFAULT_CAN_ADAPTER,
        help="保留参数（RS 固定 motorbridge / SocketCAN·PCAN）",
    )


def add_follower_flags(
    parser: argparse.ArgumentParser,
    *,
    port_default: str = DEFAULT_FOLLOWER_PORT,
) -> None:
    parser.add_argument(
        "--follower-type",
        choices=FOLLOWER_TYPES,
        default=DEFAULT_FOLLOWER_TYPE,
        help="Follower 类型（motorbridge RS）",
    )
    parser.add_argument(
        "--follower-port",
        default=port_default,
        help=f"Follower 端口（默认 {port_default}）",
    )
    parser.add_argument(
        "--follower-can-adapter",
        default=DEFAULT_CAN_ADAPTER,
        help="保留参数（RS 固定 motorbridge / SocketCAN·PCAN）",
    )


def add_teleop_flags(parser: argparse.ArgumentParser) -> None:
    add_common_flags(parser)
    add_leader_flags(parser)
    add_follower_flags(parser)
    parser.add_argument(
        "--resume-duration",
        type=float,
        default=DEFAULT_RESUME_DURATION_S,
        help=f"空格恢复时 follower 对齐 leader 的过渡秒数（默认 {DEFAULT_RESUME_DURATION_S:g}）",
    )


def add_record_flags(parser: argparse.ArgumentParser) -> None:
    add_common_flags(parser)
    add_leader_flags(parser)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_MOTION_DIR,
        help="时间戳 npz 的保存目录",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="直接指定保存路径",
    )
    parser.add_argument("--name", default="", help="文件名前缀，例如 pick")
    parser.add_argument(
        "--gravity-compensation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="RS leader 使用 demo9 MIT + Pinocchio g(q)（默认开；102 忽略）",
    )
    parser.add_argument(
        "--meshcat",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="浏览器 MeshCat 显示 URDF（默认开）",
    )


def add_play_flags(parser: argparse.ArgumentParser) -> None:
    add_common_flags(parser, rate_default=0.0)
    add_follower_flags(parser, port_default=DEFAULT_LEADER_PORT)
    parser.add_argument(
        "--motion",
        type=Path,
        default=None,
        help="要播放的 npz。省略则用方向键在目录里选择",
    )
    parser.add_argument(
        "--motion-dir",
        type=Path,
        default=DEFAULT_MOTION_DIR,
        help="方向键选择时扫描的目录",
    )
    parser.add_argument(
        "--approach-duration",
        type=float,
        default=DEFAULT_APPROACH_DURATION_S,
        help=f"每圈开始前过渡到起点的秒数（默认 {DEFAULT_APPROACH_DURATION_S:g}）",
    )
    parser.add_argument(
        "--meshcat",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="浏览器 MeshCat 显示 URDF（默认开）",
    )


def default_leader_port(leader_type: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    if leader_type in UART_LEADER_TYPES:
        return resolve_default_uart_port()
    return DEFAULT_LEADER_PORT


def settings_from_args(args: argparse.Namespace) -> DemoSettings:
    leader_type = getattr(args, "leader_type", DEFAULT_LEADER_TYPE)
    leader_port = default_leader_port(leader_type, getattr(args, "leader_port", None))
    return DemoSettings(
        leader_type=leader_type,
        leader_port=leader_port,
        leader_can_adapter=getattr(args, "leader_can_adapter", DEFAULT_CAN_ADAPTER),
        follower_type=getattr(args, "follower_type", DEFAULT_FOLLOWER_TYPE),
        follower_port=getattr(args, "follower_port", DEFAULT_FOLLOWER_PORT),
        follower_can_adapter=getattr(
            args, "follower_can_adapter", DEFAULT_CAN_ADAPTER
        ),
        rate_hz=float(args.rate),
        gripper_scale=float(args.gripper_scale),
        zero_tolerance_deg=float(args.zero_tolerance_deg),
        skip_zero_check=bool(args.skip_zero_check),
        gravity_compensation=bool(getattr(args, "gravity_compensation", False)),
        meshcat=bool(getattr(args, "meshcat", False)),
        resume_duration_s=float(getattr(args, "resume_duration", DEFAULT_RESUME_DURATION_S)),
        approach_duration_s=float(
            getattr(args, "approach_duration", DEFAULT_APPROACH_DURATION_S)
        ),
        motion_dir=Path(getattr(args, "motion_dir", getattr(args, "output_dir", DEFAULT_MOTION_DIR))),
        motion_path=getattr(args, "motion", None) or getattr(args, "output", None),
        name=str(getattr(args, "name", "")),
    )


def prepare_port(port: str) -> str:
    if looks_like_can_port(port):
        return require_can_interface(port)
    if str(port).startswith("/dev/"):
        return require_uart_port(port)
    return port


def read_positions(device: Any, kind: str) -> dict[str, float]:
    """Return joint degrees in the space that ``send_action`` expects.

    RS motorbridge leader/follower and the 102 PyPI leader all expose
    that space via ``get_action`` / ``get_observation`` (encoder degrees
    for RS, 102 command degrees for the UART leader).
    """
    if kind == "leader":
        return extract_positions(device.get_action())
    return extract_positions(device.get_observation())


def settle_zero(
    device: Any,
    role: str,
    kind: str,
    settings: DemoSettings,
) -> tuple[dict[str, float], list[str]]:
    """Read joints after a short settle. Return (positions, zero-check lines).

    Empty violation list means the pose is within tolerance, or the check
    was skipped.
    """
    time.sleep(DEFAULT_SETTLE_S)
    positions = read_positions(device, kind)
    if settings.skip_zero_check:
        logger.warning("Skip zero-check for %s", role)
        return positions, []
    violations = collect_violations(positions, settings.zero_tolerance_deg)
    if not violations:
        logger.info("%s zero-check passed (±%g deg)", role, settings.zero_tolerance_deg)
    return positions, violations


def settle_and_check_zero(
    device: Any,
    role: str,
    kind: str,
    settings: DemoSettings,
) -> dict[str, float]:
    positions, violations = settle_zero(device, role, kind, settings)
    if violations:
        assert_near_zero(positions, role, settings.zero_tolerance_deg)
    return positions
