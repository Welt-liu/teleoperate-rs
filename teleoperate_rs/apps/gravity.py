"""Hold the RS leader in demo 9 gravity compensation without recording."""

from __future__ import annotations

import logging
import time
from typing import Any

from teleoperate_rs.apps.common import (
    prepare_port,
    read_positions,
    settle_and_check_zero,
)
from teleoperate_rs.constants import (
    DEFAULT_LEADER_ID,
    DEFAULT_LOG_PERIOD_S,
    UART_LEADER_TYPES,
)
from teleoperate_rs.control.rate import RateLimiter
from teleoperate_rs.devices.factory import build_leader
from teleoperate_rs.devices.lifecycle import connect_device, disconnect_device
from teleoperate_rs.devices.specs import DeviceSpec
from teleoperate_rs.settings import DemoSettings
from teleoperate_rs.viz import open_meshcat

logger = logging.getLogger(__name__)


def run_gravity(settings: DemoSettings) -> int:
    if settings.rate_hz <= 0.0:
        raise ValueError("rate 必须大于 0")
    if settings.leader_type in UART_LEADER_TYPES:
        raise ValueError("gravity demo 只支持 RS leader（demo 9 重力补偿）")

    leader_spec = DeviceSpec(
        type_name=settings.leader_type,
        port=prepare_port(settings.leader_port),
        can_adapter=settings.leader_can_adapter,
        device_id=DEFAULT_LEADER_ID,
        gravity_compensation=True,
        home_on_disconnect=True,
    )

    print("=" * 64)
    print("  teleoperate-rs  单臂重力补偿（不录制）")
    print(f"  leader {settings.leader_type}  {settings.leader_port}")
    print(
        f"  {settings.rate_hz:.0f} Hz  gripper x{settings.gripper_scale:g}  "
        f"gravity=on  meshcat={'on' if settings.meshcat else 'off'}"
    )
    print("  手拖 leader；不保存轨迹。Ctrl+C 回零退出")
    print("=" * 64)

    leader: Any = None
    viz = None
    try:
        viz = open_meshcat(enabled=settings.meshcat)
        leader = build_leader(leader_spec)
        connect_device(leader, "leader")
        settle_and_check_zero(leader, "leader", "leader", settings)
        rate = RateLimiter(settings.rate_hz)
        t0 = time.perf_counter()
        next_log = t0 + DEFAULT_LOG_PERIOD_S
        logger.info("Gravity compensation. Move the leader; Ctrl+C to home and exit.")
        while True:
            now = time.perf_counter()
            pose = read_positions(leader, "leader")
            if viz is not None:
                viz.display_positions(pose)
            if now >= next_log:
                logger.info("t=%.2fs", now - t0)
                next_log = now + DEFAULT_LOG_PERIOD_S
            rate.sleep()
    except KeyboardInterrupt:
        logger.info("Stopping gravity compensation")
    finally:
        disconnect_device(leader, "leader")
        logger.info("Gravity done")
    return 0
