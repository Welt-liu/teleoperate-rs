"""Record a leader trajectory to a timestamped npz file."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from teleoperate_rs.apps.common import (
    prepare_port,
    read_positions,
    settle_and_check_zero,
)
from teleoperate_rs.constants import (
    DEFAULT_LEADER_ID,
    DEFAULT_LOG_PERIOD_S,
    MIN_MOTION_SPAN_DEG,
    UART_LEADER_TYPES,
)
from teleoperate_rs.control.rate import RateLimiter
from teleoperate_rs.devices.factory import build_leader
from teleoperate_rs.devices.lifecycle import connect_device, disconnect_device
from teleoperate_rs.devices.specs import DeviceSpec
from teleoperate_rs.motion.store import motion_range_deg, save_motion, unique_motion_path
from teleoperate_rs.settings import DemoSettings
from teleoperate_rs.viz import open_meshcat

logger = logging.getLogger(__name__)


def run_record(settings: DemoSettings) -> int:
    if settings.rate_hz <= 0.0:
        raise ValueError("rate 必须大于 0")
    if settings.gripper_scale == 0.0:
        raise ValueError("gripper-scale 不能为 0")

    use_gravity = bool(settings.gravity_compensation) and (
        settings.leader_type not in UART_LEADER_TYPES
    )
    leader_spec = DeviceSpec(
        type_name=settings.leader_type,
        port=prepare_port(settings.leader_port),
        can_adapter=settings.leader_can_adapter,
        device_id=DEFAULT_LEADER_ID,
        gravity_compensation=use_gravity,
        home_on_disconnect=True,
    )
    output = settings.motion_path
    if output is None:
        output = unique_motion_path(settings.motion_dir, settings.name)
    else:
        output = Path(output)

    print("=" * 64)
    print("  teleoperate-rs  单臂录制")
    print(f"  leader {settings.leader_type}  {settings.leader_port}")
    print(
        f"  {settings.rate_hz:.0f} Hz  gripper x{settings.gripper_scale:g}  "
        f"gravity={'on' if use_gravity else 'off'}  "
        f"meshcat={'on' if settings.meshcat else 'off'}"
    )
    print(f"  保存到 {output}")
    print("  手拖 leader，Ctrl+C 保存并回零退出")
    print("=" * 64)

    leader: Any = None
    viz = None
    times: list[float] = []
    frames: list[dict[str, float]] = []
    try:
        viz = open_meshcat(enabled=settings.meshcat)
        leader = build_leader(leader_spec)
        connect_device(leader, "leader")
        settle_and_check_zero(leader, "leader", "leader", settings)
        rate = RateLimiter(settings.rate_hz)
        t0 = time.perf_counter()
        next_log = t0 + DEFAULT_LOG_PERIOD_S
        logger.info("Recording. Move the leader; Ctrl+C to save.")
        while True:
            now = time.perf_counter()
            pose = read_positions(leader, "leader")
            times.append(now - t0)
            frames.append(pose)
            if viz is not None:
                viz.display_positions(pose)
            if now >= next_log:
                logger.info("t=%.2fs frames=%d", times[-1], len(times))
                next_log = now + DEFAULT_LOG_PERIOD_S
            rate.sleep()
    except KeyboardInterrupt:
        logger.info("Stopping record")
    finally:
        if times and frames:
            saved = save_motion(
                output,
                rate_hz=settings.rate_hz,
                gripper_scale=settings.gripper_scale,
                leader_type=settings.leader_type,
                times=times,
                frames=frames,
            )
            logger.info(
                "Saved %d frames (%.2fs) -> %s",
                len(frames),
                times[-1],
                saved,
            )
            span = motion_range_deg(frames)
            if span < MIN_MOTION_SPAN_DEG:
                logger.warning(
                    "录制关节几乎没动（最大峰峰值 %.1f deg）。回放会停在原地。"
                    "请手拖手臂并确认 MeshCat 在动后再保存。",
                    span,
                )
        else:
            logger.warning("No frames captured; nothing saved")
        disconnect_device(leader, "leader")
        logger.info("Record done")
    return 0
