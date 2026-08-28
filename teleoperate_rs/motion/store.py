"""Save / load joint trajectories as compressed npz files."""

from datetime import datetime
from pathlib import Path

import numpy as np

from teleoperate_rs.constants import DEFAULT_GRIPPER_SCALE, GRIPPER_JOINT, JOINT_NAMES
from teleoperate_rs.exceptions import MotionFileError
from teleoperate_rs.pose import ordered_joints


def unique_motion_path(directory: Path, name: str = "") -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = "".join(
        ch if ch.isalnum() or ch in "-_" else "_" for ch in name.strip()
    )
    stem = f"{label}_{stamp}" if label else f"motion_{stamp}"
    path = directory / f"{stem}.npz"
    suffix = 2
    while path.exists():
        path = directory / f"{stem}_{suffix}.npz"
        suffix += 1
    return path


def save_motion(
    path: Path,
    *,
    rate_hz: float,
    gripper_scale: float,
    leader_type: str,
    times: list[float],
    frames: list[dict[str, float]],
) -> Path:
    if not times or not frames:
        raise MotionFileError("没有可保存的帧")
    joint_names = ordered_joints(frames[0])
    if not joint_names:
        joint_names = list(JOINT_NAMES)
    matrix = np.zeros((len(frames), len(joint_names)), dtype=np.float64)
    for row, frame in enumerate(frames):
        for col, name in enumerate(joint_names):
            matrix[row, col] = float(frame.get(name, 0.0))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        rate=np.asarray(rate_hz, dtype=np.float64),
        gripper_scale=np.asarray(gripper_scale, dtype=np.float64),
        leader_type=np.asarray(leader_type),
        t=np.asarray(times, dtype=np.float64),
        joint_names=np.asarray(joint_names),
        q=matrix,
    )
    return path


def load_motion(path: Path) -> dict[str, object]:
    path = Path(path)
    if not path.is_file():
        raise MotionFileError(f"找不到动作文件: {path}")
    try:
        with np.load(path, allow_pickle=False) as data:
            q = np.asarray(data["q"], dtype=np.float64)
            times = np.asarray(data["t"], dtype=np.float64)
            joint_names = [str(name) for name in data["joint_names"].tolist()]
            rate_hz = float(np.asarray(data["rate"]).reshape(-1)[0])
            scale = float(np.asarray(data["gripper_scale"]).reshape(-1)[0])
            leader_type = ""
            if "leader_type" in data:
                leader_type = str(np.asarray(data["leader_type"]).reshape(-1)[0])
    except (OSError, KeyError, ValueError) as exc:
        raise MotionFileError(f"无法读取动作文件 {path}: {exc}") from exc
    if q.ndim != 2 or q.shape[0] < 1:
        raise MotionFileError(f"动作文件 {path} 没有有效帧")
    n_frames = min(q.shape[0], times.shape[0])
    frames: list[dict[str, float]] = []
    for i in range(n_frames):
        frames.append(
            {
                name: float(q[i, col])
                for col, name in enumerate(joint_names)
                if col < q.shape[1]
            }
        )
    return {
        "rate_hz": rate_hz,
        "gripper_scale": scale if scale != 0.0 else DEFAULT_GRIPPER_SCALE,
        "leader_type": leader_type,
        "t": times[:n_frames],
        "joint_names": joint_names,
        "frames": frames,
        "path": path,
    }


def motion_range_deg(frames: list[dict[str, float]]) -> float:
    """Largest peak-to-peak span among arm joints, in degrees."""
    if not frames:
        return 0.0
    names = [name for name in ordered_joints(frames[0]) if name != GRIPPER_JOINT]
    if not names:
        names = list(frames[0])
    span = 0.0
    for name in names:
        values = [float(frame.get(name, 0.0)) for frame in frames]
        span = max(span, max(values) - min(values))
    return span
