"""RS leader using demo 9 ``GravityCompensation`` (MIT + Pinocchio g(q))."""

from __future__ import annotations

import logging
import math
import time

import numpy as np

from teleoperate_rs.constants import (
    GRIPPER_JOINT,
    GRIPPER_MIT_CMD_KD,
    HOME_DURATION_S,
    HOME_RATE_HZ,
    JOINT_NAMES,
    RS_MIT_KD,
    RS_MIT_KP,
)
from teleoperate_rs.devices.control_py import ensure_control_py
from teleoperate_rs.devices.rs_arm import GripperTorqueLimiter
from teleoperate_rs.exceptions import DeviceConfigError

logger = logging.getLogger(__name__)

_ARM_JOINTS = tuple(name for name in JOINT_NAMES if name != GRIPPER_JOINT)


class RsGravityLeader:
    """LeRobot-shaped wrapper around ``reBotArm_control_py`` demo 9."""

    def __init__(self, port: str, *, home_on_disconnect: bool | None = None) -> None:
        ensure_control_py()
        from reBotArm_control_py.actuator import RebotArm
        from reBotArm_control_py.controllers import GravityCompensation

        robot = RebotArm(hw_yaml="rebotarm_rs.yaml")
        robot._channel = str(port)
        self.port = str(port)
        self.rebotarm = robot
        self._gc = GravityCompensation(robot, log_every=0)
        self._connected = False
        self._home_on_disconnect = True if home_on_disconnect is None else bool(
            home_on_disconnect
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self, calibrate: bool = False) -> None:
        del calibrate
        if self._connected:
            return
        logger.info("RS leader gravity compensation (demo 9) on %s", self.port)
        self._gc.start()
        self._connected = True

    def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            if self._home_on_disconnect:
                self._go_home()
        finally:
            self._gc.end()
            self._connected = False

    def get_action(self) -> dict[str, float]:
        return self._read_deg()

    def get_observation(self) -> dict[str, float]:
        return self._read_deg()

    def _read_deg(self) -> dict[str, float]:
        if not self._connected:
            raise DeviceConfigError("RS gravity leader 未连接")
        q_arm = self.rebotarm.arm.get_positions()
        action: dict[str, float] = {}
        for i, name in enumerate(_ARM_JOINTS):
            value = float(q_arm[i]) if i < len(q_arm) else 0.0
            action[f"{name}.pos"] = math.degrees(value)
        gripper_q = 0.0
        if self.rebotarm.has_gripper:
            q_g = self.rebotarm.gripper.get_positions()
            if len(q_g):
                gripper_q = float(q_g[0])
        action[f"{GRIPPER_JOINT}.pos"] = math.degrees(gripper_q)
        return action

    def send_action(self, action: dict[str, float]) -> dict[str, float]:
        del action
        raise DeviceConfigError("RS gravity leader 不接受 send_action")

    def _go_home(self) -> None:
        robot = self.rebotarm
        if robot.control_loop_active:
            robot.stop_control_loop()
        logger.info("RS leader homing to encoder zero over %.1fs", HOME_DURATION_S)
        n = robot.arm.num_joints
        q0 = np.asarray(robot.arm.get_positions(), dtype=np.float64)
        q_g0 = (
            np.asarray(robot.gripper.get_positions(), dtype=np.float64)
            if robot.has_gripper
            else None
        )
        kp = np.array(
            [RS_MIT_KP[name] for name in _ARM_JOINTS[:n]],
            dtype=np.float64,
        )
        kd = np.array(
            [RS_MIT_KD[name] for name in _ARM_JOINTS[:n]],
            dtype=np.float64,
        )
        limiter = GripperTorqueLimiter()
        dt = 1.0 / HOME_RATE_HZ
        n_steps = max(1, int(round(HOME_DURATION_S * HOME_RATE_HZ)))
        t0 = time.perf_counter()
        for i in range(n_steps):
            alpha = (i + 1) / n_steps
            ease = 0.5 * (1.0 - math.cos(math.pi * alpha))
            q = (1.0 - ease) * q0
            robot.arm.send_mit(
                pos=q,
                vel=np.zeros(n),
                kp=kp,
                kd=kd,
                tau=np.zeros(n),
            )
            if q_g0 is not None:
                target = (1.0 - ease) * q_g0
                pos_now = robot.gripper.get_positions()
                pos_now_0 = float(pos_now[0]) if len(pos_now) else 0.0
                tau = limiter.command(float(target[0]), pos_now_0, dt)
                n_g = robot.gripper.num_joints
                robot.gripper.send_mit(
                    pos=np.zeros(n_g),
                    vel=np.zeros(n_g),
                    kp=np.zeros(n_g),
                    kd=np.full(n_g, GRIPPER_MIT_CMD_KD),
                    tau=np.full(n_g, tau),
                )
            sleep = (i + 1) * dt - (time.perf_counter() - t0)
            if sleep > 0:
                time.sleep(sleep)
        logger.info("RS leader at encoder zero")
