"""Immutable connection spec for one arm."""

from dataclasses import dataclass

from teleoperate_rs.constants import DEFAULT_CAN_ADAPTER


@dataclass(frozen=True)
class DeviceSpec:
    type_name: str
    port: str
    can_adapter: str = DEFAULT_CAN_ADAPTER
    device_id: str = ""
    gravity_compensation: bool = False
    home_on_disconnect: bool | None = None
