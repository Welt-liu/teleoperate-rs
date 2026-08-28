"""Dual-arm teleop: leader drives follower with space-pause and 3s resume blend."""

from __future__ import annotations

import logging
import time
from typing import Any

from teleoperate_rs.apps.common import (
    prepare_port,
    read_positions,
    settle_zero,
)
from teleoperate_rs.constants import (
    DEFAULT_FOLLOWER_ID,
    DEFAULT_LEADER_ID,
    DEFAULT_LOG_PERIOD_S,
)
from teleoperate_rs.control.keyboard import SpaceKeyListener
from teleoperate_rs.control.mapper import ActionMapper
from teleoperate_rs.control.pause import PauseController, TeleopMode
from teleoperate_rs.control.rate import RateLimiter
from teleoperate_rs.devices.factory import assert_teleop_ports, build_follower, build_leader
from teleoperate_rs.devices.lifecycle import connect_device, disconnect_device
from teleoperate_rs.devices.specs import DeviceSpec
from teleoperate_rs.pose import to_action, to_rs_encoder
from teleoperate_rs.settings import DemoSettings

logger = logging.getLogger(__name__)


def _banner(settings: DemoSettings) -> None:
    print("=" * 64)
    print("  teleoperate-rs  双臂遥操作")
    print(f"  leader   {settings.leader_type}  {settings.leader_port}")
    print(f"  follower {settings.follower_type}  {settings.follower_port}")
    print(
        f"  {settings.rate_hz:.0f} Hz  gripper x{settings.gripper_scale:g}  "
        f"resume {settings.resume_duration_s:.1f}s"
    )
    print("  空格: 暂停 / 恢复（恢复时 follower 3s 对齐，不跳变）")
    print("  启动时角度超差: 日志提示后按回车（或空格）3s 过渡，与空格恢复相同")
    print("  Ctrl+C: 退出（follower 回零）")
    print("=" * 64)


def run_teleop(settings: DemoSettings) -> int:
    if settings.rate_hz <= 0.0:
        raise ValueError("rate 必须大于 0")
    if settings.gripper_scale == 0.0:
        raise ValueError("gripper-scale 不能为 0")
    if settings.resume_duration_s <= 0.0:
        raise ValueError("resume-duration 必须大于 0")

    leader_spec = DeviceSpec(
        type_name=settings.leader_type,
        port=prepare_port(settings.leader_port),
        can_adapter=settings.leader_can_adapter,
        device_id=DEFAULT_LEADER_ID,
    )
    follower_spec = DeviceSpec(
        type_name=settings.follower_type,
        port=prepare_port(settings.follower_port),
        can_adapter=settings.follower_can_adapter,
        device_id=DEFAULT_FOLLOWER_ID,
    )
    assert_teleop_ports(leader_spec, follower_spec)

    _banner(settings)
    leader: Any = None
    follower: Any = None
    keyboard = SpaceKeyListener()
    try:
        leader = build_leader(leader_spec)
        follower = build_follower(follower_spec)
        connect_device(leader, "leader")
        connect_device(follower, "follower")
        leader_pose, leader_off = settle_zero(leader, "leader", "leader", settings)
        follower_pose, follower_off = settle_zero(
            follower, "follower", "follower", settings
        )
        off_zero = leader_off + follower_off

        mapper = ActionMapper(settings.gripper_scale)
        mapper.capture_reference(leader_pose, follower_pose)
        pause = PauseController(settings.resume_duration_s)
        if off_zero:
            for line in off_zero:
                logger.warning("%s", line.strip())
            logger.warning(
                "角度不在零点附近（容差 ±%g deg）。"
                "按回车继续：follower 用 %.1fs 过渡到 leader（与空格恢复相同）。"
                "空格同样可以恢复。Ctrl+C 退出。",
                settings.zero_tolerance_deg,
                settings.resume_duration_s,
            )
            pause.hold_at(follower_pose)
        rate = RateLimiter(settings.rate_hz)
        keyboard.start()
        auto_resume = bool(off_zero) and not keyboard.enabled
        if auto_resume:
            logger.warning(
                "stdin 不是终端，无法等待回车，自动开始 %.1fs 过渡",
                settings.resume_duration_s,
            )

        if off_zero and keyboard.enabled:
            logger.info(
                "Teleop holding until Enter or space. gripper scale=x%g",
                settings.gripper_scale,
            )
        else:
            logger.info("Teleop live. gripper scale=x%g", settings.gripper_scale)
        next_log = time.perf_counter() + DEFAULT_LOG_PERIOD_S
        while True:
            now = time.perf_counter()
            leader_now = read_positions(leader, "leader")
            mapped = to_rs_encoder(mapper.map(leader_now), settings.leader_type)
            space = keyboard.poll_space()
            enter = keyboard.poll_enter()
            if space or (enter and pause.mode == TeleopMode.PAUSED) or auto_resume:
                auto_resume = False
                mode = pause.toggle(mapped, now)
                if mode == TeleopMode.PAUSED:
                    logger.info("Paused. Follower holds current pose. Space to resume.")
                elif mode == TeleopMode.RESUMING:
                    logger.info(
                        "Resuming: follower eases to leader over %.1fs",
                        settings.resume_duration_s,
                    )
            command = pause.command(mapped, now)
            follower.send_action(to_action(command))
            if now >= next_log:
                logger.info("mode=%s", pause.mode.value)
                next_log = now + DEFAULT_LOG_PERIOD_S
            rate.sleep()
    except KeyboardInterrupt:
        logger.info("Stopping teleop")
    finally:
        keyboard.close()
        disconnect_device(follower, "follower")
        disconnect_device(leader, "leader")
        logger.info("Teleop done")
    return 0
