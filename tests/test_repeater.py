import threading

from autokey_pixel.core.repeater import Repeater, RepeatSettings


def _settings(limit):
    return RepeatSettings(
        vk=0x45, use_scancode=True, interval_ms=1, hold_ms=1,
        interval_jitter_ms=0, hold_jitter_ms=0, distribution="uniform", limit=limit,
    )


def test_limit_and_press_release_pairs():
    events = []
    done = threading.Event()
    result = {}

    def on_stopped(n, err):
        result.update(n=n, err=err)
        done.set()

    r = Repeater(lambda vk, up, sc: events.append((vk, up)), on_stopped=on_stopped)
    assert r.start(_settings(5))
    assert done.wait(5)
    assert result == {"n": 5, "err": None}
    assert events == [(0x45, False), (0x45, True)] * 5


def test_stop_releases_key():
    events = []
    done = threading.Event()
    r = Repeater(lambda vk, up, sc: events.append(up), on_stopped=lambda n, e: done.set())
    s = RepeatSettings(0x45, True, 1000, 1000, 0, 0, "uniform", 0)
    r.start(s)
    r.stop(wait=True)
    assert done.wait(5)
    assert events[-1] is True  # last event is a key-up
    assert events.count(False) == events.count(True)


def test_send_error_is_reported():
    done = threading.Event()
    result = {}

    def boom(*a):
        raise OSError("bloqueado")

    def on_stopped(n, err):
        result.update(n=n, err=err)
        done.set()

    Repeater(boom, on_stopped=on_stopped).start(_settings(3))
    assert done.wait(5)
    assert result["err"] == "bloqueado"


def test_cannot_start_twice():
    r = Repeater(lambda *a: None)
    s = RepeatSettings(0x45, True, 1000, 1000, 0, 0, "uniform", 0)
    assert r.start(s)
    assert not r.start(s)
    r.stop(wait=True)
