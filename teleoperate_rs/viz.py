"""MeshCat URDF viewer, same stack as reBotArm_control_py ``example/sim``."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np

from teleoperate_rs.constants import GRIPPER_JOINT, JOINT_NAMES
from teleoperate_rs.devices.control_py import ensure_control_py
from teleoperate_rs.exceptions import DeviceConfigError

logger = logging.getLogger(__name__)

_ARM_JOINTS = tuple(name for name in JOINT_NAMES if name != GRIPPER_JOINT)


class MeshcatArm:
    """Display encoder-space joint degrees on the RS URDF in a browser."""

    def __init__(self, *, open_browser: bool = True) -> None:
        ensure_control_py()
        try:
            import pinocchio as pin
            from pinocchio.visualize import MeshcatVisualizer
        except ImportError as exc:
            raise DeviceConfigError(
                "MeshCat 需要 pinocchio。请在 conda 环境中安装: conda install -c conda-forge pinocchio"
            ) from exc
        try:
            import meshcat
        except ImportError as exc:
            raise DeviceConfigError(
                "未安装 meshcat。请执行: pip install meshcat"
            ) from exc

        from reBotArm_control_py.kinematics import _resolve_urdf, pad_q_for_model

        urdf_path, pkg_dir = _resolve_urdf()
        urdf_dir = str(Path(urdf_path).parent)
        package_dirs = [urdf_dir]
        if pkg_dir and pkg_dir not in package_dirs:
            package_dirs.append(pkg_dir)
        self._pad_q = pad_q_for_model
        self._model = pin.buildModelFromUrdf(urdf_path)
        self._data = self._model.createData()
        self._visual_model = pin.buildGeomFromUrdf(
            self._model, urdf_path, pin.GeometryType.VISUAL, package_dirs=package_dirs
        )
        self._visual_data = self._visual_model.createData()
        viewer = meshcat.Visualizer(zmq_url=None)
        self._viz = MeshcatVisualizer(
            self._model,
            collision_model=None,
            visual_model=self._visual_model,
            data=self._data,
            visual_data=self._visual_data,
        )
        self._viz.initViewer(viewer, loadModel=False)
        self._viz.loadViewerModel()
        if open_browser:
            logger.info("MeshCat %s  urdf=%s", viewer.url(), urdf_path)

    def display_positions(self, positions: dict[str, float]) -> None:
        q_arm = np.array(
            [math.radians(float(positions.get(name, 0.0))) for name in _ARM_JOINTS],
            dtype=np.float64,
        )
        q = self._pad_q(self._model, q_arm, controlled_joints=len(_ARM_JOINTS))
        self._viz.display(q)


def open_meshcat(*, enabled: bool) -> MeshcatArm | None:
    if not enabled:
        return None
    return MeshcatArm()
