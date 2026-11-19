"""Jitter calculation and interruptible high-resolution waits."""

from __future__ import annotations

import random
import time
from typing import Callable

UNIFORM = "uniform"
GAUSSIAN = "gaussian"
DISTRIBUTIONS = {UNIFORM: "Uniforme", GAUSSIAN: "Gaussiana limitada"}

MIN_MS = 1.0
MAX_JITTER_RATIO = 0.5  # jitter may be at most 50% of the base value


def max_jitter(base_ms: float) -> int:
    return int(base_ms * MAX_JITTER_RATIO)


def jitter(
    base_ms: float,
    amplitude_ms: float,
    distribution: str = UNIFORM,
    rng: random.Random | None = None,
) -> float:
    """Return ``base_ms`` shifted by a random offset in ``[-amplitude, +amplitude]``.

    * uniform: every offset in the range is equally likely.
    * gaussian: normal distribution with sigma = amplitude / 2, clamped to the range
      (values cluster around the base, closer to human timing).

    The result is never below ``MIN_MS``.
    """
    rng = rng or random
    amplitude_ms = max(0.0, float(amplitude_ms))
    if amplitude_ms == 0:
        offset = 0.0
    elif distribution == GAUSSIAN:
        offset = rng.gauss(0.0, amplitude_ms / 2.0)
        offset = max(-amplitude_ms, min(amplitude_ms, offset))
    elif distribution == UNIFORM:
        offset = rng.uniform(-amplitude_ms, amplitude_ms)
    else:
        raise ValueError(f"Distribuição desconhecida: {distribution!r}")
    return max(MIN_MS, float(base_ms) + offset)


def effective_range(
    interval_ms: float, interval_jitter: float, hold_ms: float, hold_jitter: float
) -> tuple[float, float]:
    """Min/max duration of one full cycle (hold + interval), in ms."""
    lo = max(MIN_MS, hold_ms - hold_jitter) + max(MIN_MS, interval_ms - interval_jitter)
    hi = hold_ms + hold_jitter + interval_ms + interval_jitter
    return lo, hi


def interruptible_sleep(
    ms: float,
    should_stop: Callable[[], bool],
    chunk_s: float = 0.010,
    clock: Callable[[], float] = time.perf_counter,
    sleeper: Callable[[float], None] = time.sleep,
) -> bool:
    """Sleep ``ms`` milliseconds, checking ``should_stop`` at least every ``chunk_s``.

    Uses ``time.sleep`` (a high-resolution waitable timer on Windows since
    Python 3.11) against a ``perf_counter`` deadline, so precision does not
    depend on the 15.6 ms system tick. Returns ``False`` if interrupted.
    """
    deadline = clock() + ms / 1000.0
    while True:
        if should_stop():
            return False
        remaining = deadline - clock()
        if remaining <= 0:
            return True
        sleeper(min(remaining, chunk_s))
