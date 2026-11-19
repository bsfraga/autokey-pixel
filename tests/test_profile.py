import json

from autokey_pixel.config.profile import DEFAULT_PROFILE, Profile, ProfileStore


def test_defaults():
    p = Profile()
    assert (p.interval_ms, p.hold_ms, p.interval_jitter_ms, p.hold_jitter_ms) == (100, 50, 15, 10)


def test_normalize_clamps():
    p = Profile(interval_ms=1, hold_ms=99999, interval_jitter_ms=500, hold_jitter_ms=-3,
                distribution="x", send_mode="y").normalized()
    assert p.interval_ms == 10
    assert p.hold_ms == 5000
    assert p.interval_jitter_ms == 5
    assert p.hold_jitter_ms == 0
    assert p.distribution == "uniform"
    assert p.send_mode == "scancode"


def test_store_roundtrip(tmp_path):
    store = ProfileStore(tmp_path)
    assert store.names() == [DEFAULT_PROFILE]
    name = store.save("Jogo: teste/1", Profile(interval_ms=250, key_name="F"))
    assert name == "Jogo_ teste_1"
    assert store.load(name).interval_ms == 250
    assert name in store.names()
    store.set_last_used(name)
    assert store.last_used() == name
    store.delete(name)
    assert store.load(name) == Profile()


def test_load_ignores_unknown_and_bad_files(tmp_path):
    store = ProfileStore(tmp_path)
    store.profiles_dir.mkdir(parents=True)
    (store.profiles_dir / "a.json").write_text(json.dumps({"hold_ms": 70, "extra": 1}))
    (store.profiles_dir / "b.json").write_text("{not json")
    assert store.load("a").hold_ms == 70
    assert store.load("b") == Profile()
