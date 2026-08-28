"""Domain exceptions. Callers should catch these at the application boundary."""


class TeleoperateRsError(Exception):
    """Base error for this demo."""


class DeviceConfigError(TeleoperateRsError):
    """Leader / follower type, port, or missing package is invalid."""


class ZeroPoseError(TeleoperateRsError):
    """A connected arm is not close enough to the mechanical zero pose."""

    def __init__(self, message: str, violations: list[str]) -> None:
        super().__init__(message)
        self.violations = list(violations)


class MotionFileError(TeleoperateRsError):
    """Recorded motion file is missing or unreadable."""
