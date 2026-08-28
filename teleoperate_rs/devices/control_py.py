"""Locate a sibling / env ``reBotArm_control_py`` checkout."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from teleoperate_rs.exceptions import DeviceConfigError

_REPO_ROOT = Path(__file__).resolve().parents[2]


def ensure_control_py() -> Path:
    """Put reBotArm_control_py on ``sys.path`` and return its repo root."""
    env = os.environ.get("REBOTARM_CONTROL_PY", "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(_REPO_ROOT.parent / "reBotArm_control_py")
    candidates.append(_REPO_ROOT / "third_party" / "reBotArm_control_py")

    for root in candidates:
        if (root / "reBotArm_control_py").is_dir():
            inserted = str(root.resolve())
            if inserted not in sys.path:
                sys.path.insert(0, inserted)
            return root.resolve()

    try:
        import reBotArm_control_py as pkg
    except ImportError as exc:
        raise DeviceConfigError(
            "未找到 reBotArm_control_py。请把仓库放在 teleoperate-rs 同级目录，"
            "或设置 REBOTARM_CONTROL_PY。"
        ) from exc
    return Path(pkg.__file__).resolve().parents[1]
