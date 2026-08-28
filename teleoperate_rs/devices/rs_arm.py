"""B601-RS arm over motorbridge, matching isaacsim ``rs_can_*`` (no PyPI follower).

Public angles are degrees so the rest of this demo and the 102 PyPI leader
stay in the same units. motorbridge ``send_mit`` / encoder state are radians.
There is no ``joint_directions`` multiply: commands are encoder space.

Leader: MIT ``kp=kd=tau=0`` so loc frames keep streaming while the arm is
dragged. Follower: YAML MIT gains on the arm; gripper uses the same
torque-limited MIT as isaacsim / the old Seeed follower.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

from motorbridge import CallError, Controller, Mode

from teleoperate_rs.constants import (
    GRIPPER_HOLD_TORQUE_LIMIT,
    GRIPPER_HOLD_VEL_THRESH,
    GRIPPER_JOINT,
    GRIPPER_MIT_CMD_KD,
    GRIPPER_MIT_KD,
    GRIPPER_MIT_KP,
    GRIPPER_TARGET_VEL_MAX,
    GRIPPER_TORQUE_LIMIT,
    GRIPPER_VEL_LPF_ALPHA,
    HOME_DURATION_S,
    HOME_RATE_HZ,
    JOINT_NAMES,
    RS_FOLLOWER_MOTOR_MODELS,
    RS_MIT_KD,
    RS_MIT_KP,
    RS_MOTOR_CAN_IDS,
    RS_ROBSTRIDE_HOST_ID,
)
from teleoperate_rs.exceptions import DeviceConfigError

logger = logging.getLogger(__name__)

_ARM_JOINTS = tuple(name for name in JOINT_NAMES if name != GRIPPER_JOINT)


class GripperTorqueLimiter:
    """Impedance tau with move/hold clips, same as isaacsim ``rs_can_common``."""

    def __init__(self) -> None:
        self._prev_target: float | None = None
        self._prev_filt_vel: float | None = None
        self._prev_pos: float | None = None

    def command(self, pos_target: float, pos_now: float, dt: float) -> float:
        dt_s = float(dt) if dt > 1e-4 else 1.0 / HOME_RATE_HZ
        if self._prev_target is None:
            target_vel = 0.0
        else:
            target_vel = (pos_target - self._prev_target) / dt_s
        self._prev_target = pos_target
        if self._prev_filt_vel is None:
            filtered = target_vel
        else:
            filtered = (
                GRIPPER_VEL_LPF_ALPHA * target_vel
                + (1.0 - GRIPPER_VEL_LPF_ALPHA) * self._prev_filt_vel
            )
        target_vel = max(
            -GRIPPER_TARGET_VEL_MAX,
            min(GRIPPER_TARGET_VEL_MAX, filtered),
        )
        self._prev_filt_vel = target_vel

        if self._prev_pos is None:
            state_vel = 0.0
        else:
            state_vel = (pos_now - self._prev_pos) / dt_s
        self._prev_pos = pos_now

        tau = GRIPPER_MIT_KP * (pos_target - pos_now) + GRIPPER_MIT_KD * (
            target_vel - state_vel
        )
        max_torque = (
            GRIPPER_TORQUE_LIMIT
            if abs(state_vel) > GRIPPER_HOLD_VEL_THRESH
            else GRIPPER_HOLD_TORQUE_LIMIT
        )
        return float(max(-max_torque, min(max_torque, tau)))


class RsArm:
    """LeRobot-shaped wrapper around a motorbridge RobStride bus."""

    def __init__(
        self,
        port: str,
        role: str,
        *,
        home_on_disconnect: bool | None = None,
    ) -> None:
        if role not in {"leader", "follower"}:
            raise DeviceConfigError(f"RsArm role 必须是 leader 或 follower，收到 {role!r}")
        self.port = str(port)
        self.role = role
        self._ctrl: Controller | None = None
        self._motors: dict[str, Any] = {}
        self._connected = False
        self._gripper = GripperTorqueLimiter()
        self._last_send_t: float | None = None
        self._home_on_disconnect = (
            role == "follower" if home_on_disconnect is None else bool(home_on_disconnect)
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self, calibrate: bool = False) -> None:
        del calibrate
        if self._connected:
            return
        logger.info("RS %s motorbridge connect %s", self.role, self.port)
        ctrl = Controller(self.port)
        motors: dict[str, Any] = {}
        try:
            for name in JOINT_NAMES:
                send_id, recv_id = RS_MOTOR_CAN_IDS[name]
                model = RS_FOLLOWER_MOTOR_MODELS[name]
                motor = ctrl.add_robstride_motor(send_id, recv_id, model)
                motor.ensure_mode(Mode.MIT, 1000)
                motor.enable()
                motors[name] = motor
                time.sleep(0.05)
        except Exception:
            try:
                ctrl.close()
            except Exception:
                pass
            raise
        self._ctrl = ctrl
        self._motors = motors
        self._connected = True
        self._gripper = GripperTorqueLimiter()
        self._last_send_t = None
        if self.role == "leader":
            self._stream_leader()
        logger.info(
            "RS %s ready (host 0x%02X, MIT, models rs-06/rs-00)",
            self.role,
            RS_ROBSTRIDE_HOST_ID,
        )

    def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            if self._home_on_disconnect:
                self._go_home()
        finally:
            self._disable_and_close()

    def get_action(self) -> dict[str, float]:
        self._require_connected()
        if self.role == "leader":
            self._stream_leader()
        return self._read_action()

    def get_observation(self) -> dict[str, float]:
        self._require_connected()
        if self.role == "leader":
            self._stream_leader()
        return self._read_action()

    def send_action(self, action: dict[str, float]) -> dict[str, float]:
        self._require_connected()
        if self.role != "follower":
            raise DeviceConfigError("RS leader 不接受 send_action")
        now = time.perf_counter()
        dt = (
            now - self._last_send_t
            if self._last_send_t is not None
            else 1.0 / HOME_RATE_HZ
        )
        self._last_send_t = now
        goal = {
            key.removesuffix(".pos"): float(val)
            for key, val in action.items()
            if key.endswith(".pos")
        }
        goal.setdefault("wrist_yaw", 0.0)
        self._send_follower(goal, dt)
        return {f"{name}.pos": goal[name] for name in goal}

    def _require_connected(self) -> None:
        if not self._connected or self._ctrl is None:
            raise DeviceConfigError(f"RS {self.role} 未连接")

    def _stream_leader(self) -> None:
        for motor in self._motors.values():
            try:
                motor.send_mit(0.0, 0.0, 0.0, 0.0, 0.0)
            except CallError:
                pass

    def _poll(self) -> None:
        for motor in self._motors.values():
            try:
                motor.request_feedback()
            except CallError:
                pass
        if self._ctrl is not None:
            try:
                self._ctrl.poll_feedback_once()
            except CallError:
                pass

    def _position_rad(self, name: str) -> float:
        motor = self._motors.get(name)
        if motor is None:
            return 0.0
        state = motor.get_state()
        if state is None:
            return 0.0
        return float(state.pos)

    def _read_action(self) -> dict[str, float]:
        self._poll()
        return {
            f"{name}.pos": math.degrees(self._position_rad(name))
            for name in JOINT_NAMES
        }

    def _send_follower(self, goal_deg: dict[str, float], dt: float) -> None:
        for name in _ARM_JOINTS:
            if name not in goal_deg:
                continue
            motor = self._motors.get(name)
            if motor is None:
                continue
            try:
                motor.send_mit(
                    math.radians(goal_deg[name]),
                    0.0,
                    RS_MIT_KP[name],
                    RS_MIT_KD[name],
                    0.0,
                )
            except CallError:
                pass
        if GRIPPER_JOINT not in goal_deg:
            return
        motor = self._motors.get(GRIPPER_JOINT)
        if motor is None:
            return
        target = math.radians(goal_deg[GRIPPER_JOINT])
        pos_now = self._position_rad(GRIPPER_JOINT)
        tau = self._gripper.command(target, pos_now, dt)
        try:
            motor.send_mit(0.0, 0.0, 0.0, GRIPPER_MIT_CMD_KD, tau)
        except CallError:
            pass

    def _go_home(self) -> None:
        logger.info("RS %s homing to encoder zero over %.1fs", self.role, HOME_DURATION_S)
        self._poll()
        start = {name: self._position_rad(name) for name in JOINT_NAMES}
        self._gripper = GripperTorqueLimiter()
        dt = 1.0 / HOME_RATE_HZ
        n_steps = max(1, int(round(HOME_DURATION_S * HOME_RATE_HZ)))
        t0 = time.perf_counter()
        for i in range(n_steps):
            alpha = (i + 1) / n_steps
            ease = 0.5 * (1.0 - math.cos(math.pi * alpha))
            goal_deg = {
                name: math.degrees((1.0 - ease) * start[name])
                for name in JOINT_NAMES
            }
            self._poll()
            self._send_follower(goal_deg, dt)
            sleep = (i + 1) * dt - (time.perf_counter() - t0)
            if sleep > 0:
                time.sleep(sleep)
        logger.info("RS %s at encoder zero", self.role)

    def _disable_and_close(self) -> None:
        for motor in self._motors.values():
            try:
                motor.disable()
            except CallError:
                pass
        if self._ctrl is not None:
            try:
                self._ctrl.close()
            except Exception:
                logger.exception("RS %s controller close failed", self.role)
            self._ctrl = None
        self._motors = {}
        self._connected = False
        self._last_send_t = None
