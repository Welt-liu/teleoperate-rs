"""Interactive ↑/↓ picker for recorded motion files."""

import sys
import termios
import tty
from pathlib import Path

from teleoperate_rs.exceptions import MotionFileError
from teleoperate_rs.motion.store import load_motion


def list_motion_files(directory: Path) -> list[Path]:
    directory = Path(directory)
    if not directory.is_dir():
        return []
    files = [path for path in directory.glob("*.npz") if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files


def _label(path: Path) -> tuple[str, str]:
    try:
        data = load_motion(path)
        frames = data["frames"]
        times = data["t"]
        n_frames = len(frames)
        duration = float(times[-1]) if n_frames else 0.0
        scale = float(data["gripper_scale"])
        detail = f"{duration:.1f}s · {n_frames} frames · gripper x{scale:g}"
    except Exception:
        detail = "unreadable"
    return path.name, detail


def select_motion_file(directory: Path) -> Path:
    files = list_motion_files(directory)
    if not files:
        raise MotionFileError(
            f"{directory} 中没有动作文件。请先运行: python -m teleoperate_rs record"
        )
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise MotionFileError("需要终端才能用方向键选择文件，请改用 --motion 指定路径")

    labels = [_label(path) for path in files]
    index = 0

    def _write(text: str = "") -> None:
        sys.stdout.write(text.replace("\n", "\r\n"))

    def _draw() -> None:
        _write("\033[2J\033[H")
        _write("选择要循环播放的动作\n")
        _write("↑/↓ 移动   Enter 确认   q 取消\n\n")
        for i, (title, detail) in enumerate(labels):
            marker = ">" if i == index else " "
            _write(f" {marker} {i + 1}. {title}\n")
            _write(f"      {detail}\n\n")
        sys.stdout.flush()

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        _draw()
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                chosen = files[index]
                break
            if ch in ("q", "Q", "\x03"):
                raise SystemExit("已取消选择")
            if ch == "\x1b":
                rest = sys.stdin.read(2)
                if rest == "[A":
                    index = (index - 1) % len(files)
                    _draw()
                elif rest == "[B":
                    index = (index + 1) % len(files)
                    _draw()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        sys.stdout.write("\r\n")
        sys.stdout.flush()
    return chosen
