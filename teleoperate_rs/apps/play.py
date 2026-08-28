"""Loop-play a recorded motion on the follower arm."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from teleoperate_rs.apps.common import (
    prepare_port,
    settle_and_check_zero,
)
from teleoperate_rs.constants import DEFAULT_FOLLOWER_ID, DEFAULT_LOG_PERIOD_S, MIN_MOTION_SPAN_DEG
from teleoperate_rs.control.mapper import ActionMapper
from teleoperate_rs.control.rate import RateLimiter
from teleoperate_rs.devices.factory import build_follower
from teleoperate_rs.devices.lifecycle import connect_device, disconnect_device
from teleoperate_rs.devices.specs import DeviceSpec
from teleoperate_rs.motion.picker import select_motion_file
from teleoperate_rs.motion.player import LoopingPlayer
from teleoperate_rs.motion.store import load_motion, motion_range_deg
from teleoperate_rs.pose import to_action, to_rs_encoder
from teleoperate_rs.settings import DemoSettings
from teleoperate_rs.viz import open_meshcat

logger = logging.getLogger(__name__)


def run_play(settings: DemoSettings) -> int:
    if settings.approach_duration_s <= 0.0:
        raise ValueError("approach-duration 必须大于 0")

    if settings.motion_path is not None:
        motion_path = Path(settings.motion_path)
    else:
        motion_path = select_motion_file(settings.motion_dir)
    motion = load_motion(motion_path)
    leader_type = str(motion.get("leader_type") or "")
    frames = [to_rs_encoder(frame, leader_type) for frame in motion["frames"]]
    span = motion_range_deg(frames)
    if span < MIN_MOTION_SPAN_DEG:
        logger.warning(
            "动作文件关节几乎静止（最大峰峰值 %.1f deg），回放不会有可见运动。请重新录制。",
            span,
        )
    stored_rate = float(motion["rate_hz"])
    rate_hz = settings.rate_hz if settings.rate_hz > 0 else stored_rate
    if settings.gripper_scale != 0.0:
        gripper_scale = settings.gripper_scale
    else:
        gripper_scale = float(motion["gripper_scale"])
    if rate_hz <= 0.0:
        raise ValueError("播放频率必须大于 0")

    follower_spec = DeviceSpec(
        type_name=settings.follower_type,
        port=prepare_port(settings.follower_port),
        can_adapter=settings.follower_can_adapter,
        device_id=DEFAULT_FOLLOWER_ID,
    )
    n_frames = len(frames)
    motion_s = n_frames / rate_hz if rate_hz else 0.0

    print("=" * 64)
    print("  teleoperate-rs  单臂回放")
    print(f"  follower {settings.follower_type}  {settings.follower_port}")
    print(
        f"  {motion_path}  {n_frames} frames  "
        f"approach {settings.approach_duration_s:.1f}s + "
        f"motion {motion_s:.2f}s @ {rate_hz:.0f} Hz  "
        f"gripper x{gripper_scale:g}  meshcat={'on' if settings.meshcat else 'off'}"
    )
    print("  Ctrl+C: 回零并退出")
    print("=" * 64)

    follower: Any = None
    viz = None
    try:
        viz = open_meshcat(enabled=settings.meshcat)
        follower = build_follower(follower_spec)
        connect_device(follower, "follower")
        follower_pose = settle_and_check_zero(
            follower, "follower", "follower", settings
        )
        mapper = ActionMapper(gripper_scale)
        mapper.capture_reference(frames[0], follower_pose)
        mapped_frames = [mapper.map(frame) for frame in frames]
        player = LoopingPlayer(
            mapped_frames, rate_hz, settings.approach_duration_s
        )
        now = time.perf_counter()
        # follower_pose is encoder degrees (same space as send_action).
        player.start_clock(now, follower_pose)
        rate = RateLimiter(rate_hz)
        next_log = now + DEFAULT_LOG_PERIOD_S
        logger.info("Playback looping. %s", player.describe())
        while True:
            now = time.perf_counter()
            command = player.sample(now)
            follower.send_action(to_action(command))
            if viz is not None:
                viz.display_positions(command)
            if now >= next_log:
                logger.info(
                    "loop=%d %s frame=%d/%d",
                    player.cycle,
                    player.phase,
                    player.frame_index + 1,
                    player.n_frames,
                )
                next_log = now + DEFAULT_LOG_PERIOD_S
            rate.sleep()
    except KeyboardInterrupt:
        logger.info("Stopping playback")
    finally:
        disconnect_device(follower, "follower")
        logger.info("Play done")
    return 0
