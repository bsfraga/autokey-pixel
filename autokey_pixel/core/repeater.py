"""Background thread that presses and releases a key repeatedly."""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass
from typing import Callable

from . import timing


@dataclass(frozen=True)
class RepeatSettings:
    vk: int
    use_scancode: bool
    interval_ms: float
    hold_ms: float
    interval_jitter_ms: float
    hold_jitter_ms: float
    distribution: str
    limit: int = 0  # 0 = infinite


KeyFn = Callable[[int, bool, bool], None]  # (vk, up, use_scancode)


class Repeater:
    """Runs the press/hold/release/wait loop in a daemon thread.

    Callbacks are invoked from the worker thread; the GUI must marshal them
    to its own thread (the Qt bridge does this with signals).
    """

    def __init__(
        self,
        send_key: KeyFn,
        on_count: Callable[[int], None] | None = None,
        on_stopped: Callable[[int, str | None], None] | None = None,
        rng: random.Random | None = None,
        sleep: Callable[..., bool] = timing.interruptible_sleep,
    ) -> None:
        self._send_key = send_key
        self._on_count = on_count or (lambda n: None)
        self._on_stopped = on_stopped or (lambda n, err: None)
        self._rng = rng or random.Random()
        self._sleep = sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive()

    def start(self, settings: RepeatSettings) -> bool:
        with self._lock:
            if self.running:
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, args=(settings,), name="repeater", daemon=True
            )
            self._thread.start()
            return True

    def stop(self, wait: bool = False, timeout: float = 1.0) -> None:
        self._stop.set()
        t = self._thread
        if wait and t is not None and t is not threading.current_thread():
            t.join(timeout)

    def _run(self, s: RepeatSettings) -> None:
        count = 0
        error: str | None = None
        should_stop = self._stop.is_set
        try:
            while not should_stop():
                hold = timing.jitter(s.hold_ms, s.hold_jitter_ms, s.distribution, self._rng)
                self._send_key(s.vk, False, s.use_scancode)
                try:
                    self._sleep(hold, should_stop)
                finally:
                    # always release, even when interrupted mid-hold
                    self._send_key(s.vk, True, s.use_scancode)
                count += 1
                self._on_count(count)
                if s.limit and count >= s.limit:
                    break
                gap = timing.jitter(
                    s.interval_ms, s.interval_jitter_ms, s.distribution, self._rng
                )
                if not self._sleep(gap, should_stop):
                    break
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            error = str(exc)
        finally:
            self._on_stopped(count, error)
