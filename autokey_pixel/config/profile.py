"""User profiles persisted as JSON under %APPDATA%\\AutoKeyPixel\\profiles."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from ..core import timing

DEFAULT_PROFILE = "Padrão"

LIMITS = {
    "interval_ms": (10, 60_000),
    "hold_ms": (1, 5_000),
    "repeat_limit": (0, 1_000_000),
}


@dataclass
class Profile:
    capture_hotkey: str = "ctrl+shift+c"
    toggle_hotkey: str = "f6"
    stop_hotkey: str = "f12"
    key_vk: int = 0x45  # 'E'
    key_name: str = "E"
    send_mode: str = "scancode"  # or "vk"
    interval_ms: int = 100
    hold_ms: int = 50
    interval_jitter_ms: int = 15
    hold_jitter_ms: int = 10
    distribution: str = timing.UNIFORM
    repeat_limit: int = 0  # 0 = infinite
    always_on_top: bool = False

    def normalized(self) -> "Profile":
        """Return a copy with every value clamped to its valid range."""
        p = Profile(**asdict(self))
        for name, (lo, hi) in LIMITS.items():
            setattr(p, name, int(min(hi, max(lo, int(getattr(p, name))))))
        p.interval_jitter_ms = int(
            min(timing.max_jitter(p.interval_ms), max(0, int(p.interval_jitter_ms)))
        )
        p.hold_jitter_ms = int(min(timing.max_jitter(p.hold_ms), max(0, int(p.hold_jitter_ms))))
        if p.distribution not in timing.DISTRIBUTIONS:
            p.distribution = timing.UNIFORM
        if p.send_mode not in ("scancode", "vk"):
            p.send_mode = "scancode"
        p.key_vk = int(p.key_vk) & 0xFF
        return p

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known}).normalized()


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / "AutoKeyPixel"


class ProfileStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or config_dir()
        self.profiles_dir = self.root / "profiles"
        self.settings_file = self.root / "settings.json"

    @staticmethod
    def _safe(name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
        return cleaned or DEFAULT_PROFILE

    def _path(self, name: str) -> Path:
        return self.profiles_dir / f"{self._safe(name)}.json"

    def names(self) -> list[str]:
        found = sorted(p.stem for p in self.profiles_dir.glob("*.json")) if self.profiles_dir.exists() else []
        if DEFAULT_PROFILE not in found:
            found.insert(0, DEFAULT_PROFILE)
        return found

    def load(self, name: str) -> Profile:
        path = self._path(name)
        try:
            return Profile.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return Profile()

    def save(self, name: str, profile: Profile) -> str:
        name = self._safe(name)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._path(name).write_text(profile.normalized().to_json(), encoding="utf-8")
        return name

    def delete(self, name: str) -> None:
        try:
            self._path(name).unlink()
        except FileNotFoundError:
            pass

    def last_used(self) -> str:
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            return str(data.get("last_profile") or DEFAULT_PROFILE)
        except (OSError, ValueError):
            return DEFAULT_PROFILE

    def set_last_used(self, name: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(
            json.dumps({"last_profile": self._safe(name)}, ensure_ascii=False), encoding="utf-8"
        )
