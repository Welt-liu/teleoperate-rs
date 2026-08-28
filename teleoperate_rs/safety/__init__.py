"""Safety checks that must pass before motion starts."""

from .zero_check import assert_near_zero, collect_violations

__all__ = ["assert_near_zero", "collect_violations"]
