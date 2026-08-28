"""Print currently visible UART / CAN devices. Useful on macOS."""

from __future__ import annotations

import sys

from teleoperate_rs.devices.can import pcan_status
from teleoperate_rs.devices.serial import format_uart_ports, list_uart_ports


def run_ports() -> int:
    print(f"platform: {sys.platform}")
    print()
    print("USB serial (102 UART):")
    ports = list_uart_ports()
    print(format_uart_ports(ports))
    if sys.platform == "darwin" and not ports:
        print("  插上 USB 后: ls /dev/cu.usb* /dev/tty.usb*")
        print("  不要用 Linux 的 /dev/ttyUSB0")
    print()
    print("CAN (B601 RS, motorbridge):")
    if sys.platform == "darwin":
        status = pcan_status()
        print("  channel aliases: can0 -> PCAN_USBBUS1, can1 -> PCAN_USBBUS2")
        print(f"  PCBUSB (motorbridge dlopen): {status['pcbusb']}")
        print(f"  libPCBUSB.dylib (install.sh): {status['libpcbusb_dylib']}")
        print(f"  DYLD_FALLBACK_LIBRARY_PATH: {status['dyld_fallback']}")
        print(f"  runtime: {status['runtime']}")
        print(f"  PEAK USB: {status['pcan_usb']}")
        print("  macOS 不需要 sudo ip link；插上 PCAN 后直接用 can0 / can1")
        print("  不要用 ctypes.CDLL('libPCBUSB.dylib') 判断是否就绪")
        if status["pcbusb"] == "missing" or not status["runtime"].endswith("OK"):
            print("  未就绪时跑: ./scripts/setup_macos_pcan.sh")
    elif sys.platform.startswith("linux"):
        print("  先执行: sudo ip link set can0 up type can bitrate 1000000")
    else:
        print(f"  未在 {sys.platform} 上探测 CAN")
    return 0
