"""Device package: factory, specs, and connect / disconnect lifecycle."""

from .factory import build_follower, build_leader
from .lifecycle import connect_device, disconnect_device
from .specs import DeviceSpec

__all__ = [
    "DeviceSpec",
    "build_follower",
    "build_leader",
    "connect_device",
    "disconnect_device",
]
