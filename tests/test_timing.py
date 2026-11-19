import random

import pytest

from autokey_pixel.core import timing


@pytest.mark.parametrize("dist", [timing.UNIFORM, timing.GAUSSIAN])
def test_jitter_stays_within_range(dist):
    rng = random.Random(42)
    values = [timing.jitter(100, 15, dist, rng) for _ in range(5000)]
    assert min(values) >= 85
    assert max(values) <= 115
    assert 98 < sum(values) / len(values) < 102


def test_jitter_zero_amplitude_is_exact():
    assert timing.jitter(100, 0) == 100


def test_jitter_never_below_minimum():
    rng = random.Random(1)
    assert all(timing.jitter(2, 50, timing.UNIFORM, rng) >= timing.MIN_MS for _ in range(1000))


def test_unknown_distribution():
    with pytest.raises(ValueError):
        timing.jitter(100, 10, "nope")


def test_effective_range():
    assert timing.effective_range(100, 15, 50, 10) == (125, 175)


def test_max_jitter_is_half():
    assert timing.max_jitter(100) == 50


def test_interruptible_sleep_completes_and_interrupts():
    now = [0.0]

    def clock():
        return now[0]

    def sleeper(s):
        now[0] += s

    assert timing.interruptible_sleep(50, lambda: False, clock=clock, sleeper=sleeper)
    assert now[0] == pytest.approx(0.05)

    calls = {"n": 0}

    def stop_after_two():
        calls["n"] += 1
        return calls["n"] > 2

    now[0] = 0.0
    assert not timing.interruptible_sleep(1000, stop_after_two, clock=clock, sleeper=sleeper)
    assert now[0] < 1.0
