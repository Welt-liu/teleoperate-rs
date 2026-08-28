"""CLI entry: python -m teleoperate_rs {teleop,record,play,ports}."""

from __future__ import annotations

import argparse
import logging
import sys

from teleoperate_rs.apps.common import (
    add_play_flags,
    add_record_flags,
    add_teleop_flags,
    settings_from_args,
)
from teleoperate_rs.exceptions import TeleoperateRsError, ZeroPoseError
from teleoperate_rs.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def _run_teleop(args: argparse.Namespace) -> int:
    from teleoperate_rs.apps.teleop import run_teleop

    return run_teleop(settings_from_args(args))


def _run_record(args: argparse.Namespace) -> int:
    from teleoperate_rs.apps.record import run_record

    return run_record(settings_from_args(args))


def _run_play(args: argparse.Namespace) -> int:
    from teleoperate_rs.apps.play import run_play

    return run_play(settings_from_args(args))


def _run_ports(_args: argparse.Namespace) -> int:
    from teleoperate_rs.apps.ports import run_ports

    return run_ports()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="teleoperate-rs",
        description="B601-RS 最简遥操作 / 录制 / 回放 demo（motorbridge RS + PyPI 102）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    teleop = sub.add_parser("teleop", help="双臂遥操作（空格暂停，恢复 3s 对齐）")
    add_teleop_flags(teleop)
    teleop.set_defaults(func=_run_teleop)

    record = sub.add_parser("record", help="单臂录制 leader 轨迹")
    add_record_flags(record)
    record.set_defaults(func=_run_record)

    play = sub.add_parser("play", help="单臂循环回放 follower")
    add_play_flags(play)
    play.set_defaults(func=_run_play)

    ports = sub.add_parser("ports", help="列出本机 USB 串口 / CAN 适配器（macOS 换口时先跑这个）")
    ports.set_defaults(func=_run_ports)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ZeroPoseError as exc:
        logger.error("%s", exc)
        return 2
    except TeleoperateRsError as exc:
        logger.error("%s", exc)
        return 1
    except ValueError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
