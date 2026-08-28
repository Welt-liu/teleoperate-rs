"""CAN channel checks for Linux SocketCAN and macOS PCAN (PCBUSB)."""

from __future__ import annotations

import ctypes
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from teleoperate_rs.constants import CAN_PORT_PREFIX
from teleoperate_rs.exceptions import DeviceConfigError

logger = logging.getLogger(__name__)

DEFAULT_CAN_BITRATE = 1_000_000
_PCAN_USB_VENDOR = 3186
_PCAN_CHANNEL_RE = re.compile(r"^(?:can(\d+)|PCAN_USBBUS(\d+))$", re.IGNORECASE)

# install.sh 只安装这个文件。ctypes.CDLL(这个名字) 不能当运行时检查。
_INSTALL_DYLIB = "libPCBUSB.dylib"
# motorbridge 原生加载器 dlopen 的裸名。缺这个就会报 load PCBUSB failed。
_MOTORBRIDGE_SONAME = "PCBUSB"


def looks_like_can_port(port: str) -> bool:
    name = str(port or "").split("@", 1)[0].strip()
    return _PCAN_CHANNEL_RE.fullmatch(name) is not None or (
        name.lower().startswith(CAN_PORT_PREFIX)
        and name[len(CAN_PORT_PREFIX) :].isdigit()
    )


def _split_can_channel(port: str) -> tuple[str, int | None]:
    raw = str(port or "").strip() or "can0"
    if "@" not in raw:
        return raw, None
    name, bitrate_s = raw.split("@", 1)
    name = name.strip() or "can0"
    try:
        bitrate = int(bitrate_s.strip())
    except ValueError as exc:
        raise DeviceConfigError(
            f"CAN 波特率无效: {port!r}。请用 can0@{DEFAULT_CAN_BITRATE}"
        ) from exc
    if bitrate <= 0:
        raise DeviceConfigError(f"CAN 波特率必须为正，得到 {port!r}")
    return name, bitrate


def _pcbusb_lib_dirs() -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        resolved = str(path.expanduser())
        if resolved in seen:
            return
        seen.add(resolved)
        dirs.append(Path(resolved))

    conda = os.environ.get("CONDA_PREFIX")
    if conda:
        add(Path(conda) / "lib")
    add(Path(sys.prefix) / "lib")
    fallback = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    for part in fallback.split(":"):
        if part.strip():
            add(Path(part.strip()))
    add(Path("/usr/local/lib"))
    add(Path("/opt/homebrew/lib"))
    add(Path.home() / ".local/lib")
    return dirs


def _find_named_library(name: str) -> Path | None:
    for directory in _pcbusb_lib_dirs():
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def _preferred_lib_dir() -> Path:
    soname = _find_named_library(_MOTORBRIDGE_SONAME)
    if soname is not None:
        return soname.parent
    dylib = _find_named_library(_INSTALL_DYLIB)
    if dylib is not None:
        return dylib.parent
    local = Path.home() / ".local/lib" / _INSTALL_DYLIB
    if local.exists():
        return local.parent
    return Path("/usr/local/lib")


def pcbusb_install_help(*, lib_dir: Path | None = None) -> str:
    lib_dir = lib_dir or _preferred_lib_dir()
    system = lib_dir == Path("/usr/local/lib")
    ln = (
        f"sudo ln -sf {lib_dir / _INSTALL_DYLIB} {lib_dir / _MOTORBRIDGE_SONAME}"
        if system
        else f"ln -sf {lib_dir / _INSTALL_DYLIB} {lib_dir / _MOTORBRIDGE_SONAME}"
    )
    fallback = str(lib_dir)
    return (
        "macOS CAN 需要 MacCAN PCBUSB。install.sh 只会安装 "
        f"{_INSTALL_DYLIB}；motorbridge 实际 dlopen 的是裸名 "
        f"{_MOTORBRIDGE_SONAME}。\n"
        "请先插入 PCAN 适配器，再按下面做。\n"
        "\n"
        "1) 安装 PCBUSB（系统级）:\n"
        "  curl -L -o macOS_Library_for_PCANUSB_v0.13.tar.gz \\\n"
        "    https://raw.githubusercontent.com/tianrking/motorbridge/main/"
        "third_party/pcan/macos/macOS_Library_for_PCANUSB_v0.13.tar.gz\n"
        "  tar -xzf macOS_Library_for_PCANUSB_v0.13.tar.gz\n"
        "  cd PCBUSB\n"
        "  sudo ./install.sh\n"
        "\n"
        f"2) 补 motorbridge 需要的符号链接:\n"
        f"  {ln}\n"
        "\n"
        "3) conda 激活时设置 DYLD_FALLBACK_LIBRARY_PATH"
        "（不要用 DYLD_LIBRARY_PATH）:\n"
        "  mkdir -p \"$CONDA_PREFIX/etc/conda/activate.d\"\n"
        "  cat > \"$CONDA_PREFIX/etc/conda/activate.d/pcbusb_dyld.sh\" << 'EOF'\n"
        f'export DYLD_FALLBACK_LIBRARY_PATH="'
        f"{fallback}"
        '${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"\n'
        "EOF\n"
        "  conda deactivate && conda activate teleoperate-rs\n"
        "\n"
        "或直接跑: ./scripts/setup_macos_pcan.sh\n"
        "不要用 ctypes.CDLL('libPCBUSB.dylib') 判断是否就绪。"
    )


def _macos_pcan_usb_present() -> bool | None:
    try:
        result = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-l", "-w", "0"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    needle = f'"idVendor" = {_PCAN_USB_VENDOR}'
    return needle in result.stdout


def _try_load_motorbridge_soname() -> tuple[bool, str]:
    """Load the name motorbridge dlopens. Not libPCBUSB.dylib."""
    try:
        ctypes.CDLL(_MOTORBRIDGE_SONAME)
        return True, _MOTORBRIDGE_SONAME
    except OSError as exc:
        return False, str(exc)


def _expose_pcbusb_in_conda_lib(src: Path) -> None:
    """Put the PCBUSB soname on conda Python's lib dir as a fallback."""
    lib_dir = Path(sys.prefix) / "lib"
    if not lib_dir.is_dir():
        return
    dest = lib_dir / _MOTORBRIDGE_SONAME
    if dest.exists() or dest.is_symlink():
        return
    try:
        dest.symlink_to(src)
    except OSError:
        return


def pcan_status() -> dict[str, str]:
    """Facts for `teleoperate-rs ports` on macOS."""
    soname = _find_named_library(_MOTORBRIDGE_SONAME)
    dylib = _find_named_library(_INSTALL_DYLIB)
    loaded, load_detail = _try_load_motorbridge_soname()
    present = _macos_pcan_usb_present() if sys.platform == "darwin" else None
    if present is True:
        adapter = "detected"
    elif present is False:
        adapter = "not plugged in"
    else:
        adapter = "unknown"
    fallback = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    return {
        "pcbusb": str(soname) if soname else "missing",
        "libpcbusb_dylib": str(dylib) if dylib else "missing",
        "dyld_fallback": fallback or "unset",
        "runtime": "PCBUSB load OK" if loaded else f"load PCBUSB failed ({load_detail})",
        "pcan_usb": adapter,
    }


def require_can_interface(port: str, *, bitrate: int = DEFAULT_CAN_BITRATE) -> str:
    """Return a motorbridge CAN channel after checking the local adapter."""
    name, explicit_bitrate = _split_can_channel(port)
    use_bitrate = explicit_bitrate if explicit_bitrate is not None else int(bitrate)

    if sys.platform.startswith("linux"):
        sys_path = Path("/sys/class/net") / name
        if not sys_path.is_dir():
            raise DeviceConfigError(
                f"未找到 CAN 接口 {name!r}。请先执行: "
                f"sudo ip link set {name} up type can bitrate {use_bitrate}"
            )
        return name

    if not looks_like_can_port(name):
        raise DeviceConfigError(
            f"无法识别 CAN 通道 {port!r}。macOS/Windows 请用 can0、can1 或 PCAN_USBBUS1。"
        )

    if sys.platform == "darwin":
        present = _macos_pcan_usb_present()
        if present is False:
            raise DeviceConfigError(
                "未检测到 PEAK PCAN USB。请先插入适配器，再用 can0 "
                "（对应 PCAN_USBBUS1）。macOS 不需要 ip link。"
            )
        soname = _find_named_library(_MOTORBRIDGE_SONAME)
        dylib = _find_named_library(_INSTALL_DYLIB)
        if soname is None:
            if dylib is not None:
                raise DeviceConfigError(
                    f"找到了 {_INSTALL_DYLIB}（{dylib}），但 motorbridge "
                    f"dlopen 的是裸名 {_MOTORBRIDGE_SONAME}，连接机械臂仍会报 "
                    "load PCBUSB failed。\n"
                    f"  sudo ln -sf {dylib} {dylib.parent / _MOTORBRIDGE_SONAME}\n"
                    "然后设置 DYLD_FALLBACK_LIBRARY_PATH，见 README 或:\n"
                    "  ./scripts/setup_macos_pcan.sh"
                )
            raise DeviceConfigError(pcbusb_install_help())
        _expose_pcbusb_in_conda_lib(soname.resolve())
        loaded, detail = _try_load_motorbridge_soname()
        if not loaded:
            lib_dir = soname.parent
            raise DeviceConfigError(
                f"无法按裸名加载 {_MOTORBRIDGE_SONAME}: {detail}\n"
                "ctypes.CDLL('libPCBUSB.dylib') 通过也不算就绪。"
                "请用 DYLD_FALLBACK_LIBRARY_PATH，不要用 DYLD_LIBRARY_PATH。\n"
                f"  export DYLD_FALLBACK_LIBRARY_PATH="
                f'"{lib_dir}'
                '${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"\n'
                "或: ./scripts/setup_macos_pcan.sh\n"
                "然后 conda deactivate && conda activate teleoperate-rs"
            )
        logger.info("macOS PCAN ready: channel=%s pcbusb=%s", name, soname)
        return name

    raise DeviceConfigError(
        f"当前系统 {sys.platform!r} 未适配 CAN。Linux 用 SocketCAN，macOS 用 PEAK PCAN。"
    )
