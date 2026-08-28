"""Connect / disconnect wrappers. Always disconnect in a finally block."""

import logging
from typing import Any

from teleoperate_rs.exceptions import DeviceConfigError

logger = logging.getLogger(__name__)


def connect_device(device: Any, role: str) -> None:
    logger.info("Connecting %s", role)
    try:
        device.connect(calibrate=False)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        raise DeviceConfigError(f"{role} 连接失败: {exc}") from exc
    logger.info("%s connected", role)


def disconnect_device(device: Any, role: str) -> None:
    if device is None:
        return
    connected = getattr(device, "is_connected", False)
    if not connected:
        return
    try:
        device.disconnect()
        logger.info("%s disconnected", role)
    except KeyboardInterrupt:
        logger.info("%s disconnect interrupted after homing", role)
    except Exception:
        logger.exception("Failed to disconnect %s", role)
