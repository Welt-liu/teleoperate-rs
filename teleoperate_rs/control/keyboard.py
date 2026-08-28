"""Non-blocking spacebar listener. Restores terminal settings on close."""

from __future__ import annotations

import logging
import os
import queue
import select
import sys
import threading

from teleoperate_rs.constants import DEFAULT_KEYBOARD_POLL_S

logger = logging.getLogger(__name__)

_SPACE = b" "
_ENTER = (b"\n", b"\r")


class SpaceKeyListener:
    """Daemon thread that enqueues spacebar presses without requiring Enter."""

    def __init__(self) -> None:
        self._events: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._fd: int | None = None
        self._saved = None
        self.enabled = False

    def start(self) -> None:
        if not sys.stdin.isatty():
            logger.warning("stdin 不是终端，空格暂停不可用")
            return
        try:
            import termios
            import tty
        except ImportError:
            logger.warning("当前系统不支持 termios，空格暂停不可用")
            return

        self._fd = sys.stdin.fileno()
        self._saved = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        self.enabled = True
        self._thread = threading.Thread(
            target=self._run,
            name="space-key-listener",
            daemon=True,
        )
        self._thread.start()
        logger.info("Space / Enter enabled (space pause/resume; Enter resumes from hold)")

    def _run(self) -> None:
        fd = self._fd
        if fd is None:
            return
        while not self._stop.is_set():
            ready, _, _ = select.select([fd], [], [], DEFAULT_KEYBOARD_POLL_S)
            if not ready:
                continue
            try:
                chunk = os.read(fd, 1)
            except OSError:
                break
            if chunk == _SPACE:
                self._events.put("space")
            elif chunk in _ENTER:
                self._events.put("enter")

    def poll_space(self) -> bool:
        return self._drain("space")

    def poll_enter(self) -> bool:
        return self._drain("enter")

    def _drain(self, kind: str) -> bool:
        hit = False
        kept: list[str] = []
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event == kind:
                hit = True
            else:
                kept.append(event)
        for event in kept:
            self._events.put(event)
        return hit

    def close(self) -> None:
        self._stop.set()
        if self._saved is None or self._fd is None:
            return
        try:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        except Exception:
            logger.exception("Failed to restore terminal settings")
        self._saved = None
        self.enabled = False
