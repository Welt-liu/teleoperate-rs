"""Discover UART serial devices. Names differ on macOS vs Linux."""

from __future__ import annotations

import sys
from pathlib import Path

from teleoperate_rs.constants import DEFAULT_UART_LEADER_PORT
from teleoperate_rs.exceptions import DeviceConfigError

# macOS: call-out (cu.*) is preferred; tty.* waits for carrier.
_MACOS_UART_GLOBS = (
    "/dev/cu.usbserial*",
    "/dev/cu.usbmodem*",
    "/dev/cu.wchusbserial*",
    "/dev/cu.wchusb*",
    "/dev/cu.SLAB_USBtoUART*",
    "/dev/tty.usbserial*",
    "/dev/tty.usbmodem*",
    "/dev/tty.wchusbserial*",
    "/dev/tty.wchusb*",
    "/dev/tty.SLAB_USBtoUART*",
)

_LINUX_UART_GLOBS = (
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
)


def _glob_ports(patterns: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        glob_path = Path(pattern)
        parent = glob_path.parent
        if not parent.is_dir():
            continue
        for path in sorted(parent.glob(glob_path.name)):
            resolved = str(path)
            if resolved in seen or not path.exists():
                continue
            seen.add(resolved)
            found.append(path)
    return found


def _prefer_cu(paths: list[Path]) -> list[Path]:
    """Drop /dev/tty.X when /dev/cu.X exists for the same adapter."""
    names = {path.name for path in paths}
    kept: list[Path] = []
    for path in paths:
        name = path.name
        if name.startswith("tty.") and f"cu.{name[4:]}" in names:
            continue
        kept.append(path)
    return kept


def list_uart_ports() -> list[Path]:
    """Return currently visible USB-serial devices for this OS."""
    if sys.platform == "darwin":
        return _prefer_cu(_glob_ports(_MACOS_UART_GLOBS))
    if sys.platform.startswith("linux"):
        return _glob_ports(_LINUX_UART_GLOBS)
    return []


def format_uart_ports(ports: list[Path] | None = None) -> str:
    if ports is None:
        ports = list_uart_ports()
    if not ports:
        return "  （当前没有 USB 串口）"
    return "\n".join(f"  {path}" for path in ports)


def macos_serial_hint() -> str:
    return (
        "macOS 上 102 / Damiao 串口一般是 /dev/cu.usbserial-* 或 "
        "/dev/cu.usbmodem*，不是 Linux 的 /dev/ttyUSB0。\n"
        "插上 USB 后执行:\n"
        "  ls /dev/cu.usb* /dev/tty.usb*\n"
        "  python -m teleoperate_rs ports"
    )


def resolve_default_uart_port() -> str:
    """Pick a UART default. One device: use it. Several: ask. None: explain."""
    ports = list_uart_ports()
    if len(ports) == 1:
        return str(ports[0])
    if len(ports) > 1:
        listed = format_uart_ports(ports)
        raise DeviceConfigError(
            "检测到多个 USB 串口，请用 --leader-port 指定其中一个:\n"
            f"{listed}"
        )
    if sys.platform == "darwin":
        raise DeviceConfigError(
            "未找到 USB 串口。\n" + macos_serial_hint()
        )
    linux_default = Path(DEFAULT_UART_LEADER_PORT)
    if linux_default.exists():
        return str(linux_default)
    listed = format_uart_ports(ports)
    raise DeviceConfigError(
        f"未找到 USB 串口（默认 {DEFAULT_UART_LEADER_PORT} 不存在）。当前可见:\n"
        f"{listed}\n"
        "请用 --leader-port 指定，例如 /dev/ttyUSB0 或 /dev/ttyACM0。"
    )


def require_uart_port(port: str) -> str:
    """Ensure an explicit UART path exists; on miss, list current devices."""
    raw = str(port or "").strip()
    path = Path(raw)
    if path.exists():
        return raw
    listed = format_uart_ports()
    extra = ""
    if sys.platform == "darwin" and raw.startswith("/dev/ttyUSB"):
        extra = "\n" + macos_serial_hint()
    raise DeviceConfigError(
        f"串口 {raw!r} 不存在。当前可见 USB 串口:\n{listed}{extra}"
    )
