"""Global hotkeys (work with any window focused) via the ``keyboard`` package.

The package is imported lazily so the rest of the app can be imported on
systems where it is unavailable (e.g. CI test runners).
"""

from __future__ import annotations

import threading
from typing import Callable


def _kb():
    import keyboard  # noqa: PLC0415 - lazy on purpose

    return keyboard


def normalize(combo: str) -> str:
    return "+".join(p.strip().lower() for p in combo.split("+") if p.strip())


class HotkeyManager:
    def __init__(self) -> None:
        self._bindings: dict[str, tuple[str, Callable[[], None]]] = {}
        self._handles: dict[str, object] = {}
        self._paused = False

    def set(self, name: str, combo: str, callback: Callable[[], None]) -> None:
        """Bind (or rebind) ``name`` to ``combo``. An empty combo just unbinds."""
        self._remove(name)
        combo = normalize(combo)
        if combo:
            self._bindings[name] = (combo, callback)
            if not self._paused:
                self._add(name)
        else:
            self._bindings.pop(name, None)

    def pause(self) -> None:
        self._paused = True
        for name in list(self._handles):
            self._remove(name)

    def resume(self) -> None:
        self._paused = False
        for name in self._bindings:
            if name not in self._handles:
                self._add(name)

    def clear(self) -> None:
        for name in list(self._handles):
            self._remove(name)
        self._bindings.clear()

    def _add(self, name: str) -> None:
        combo, cb = self._bindings[name]
        self._handles[name] = _kb().add_hotkey(combo, cb, suppress=False)

    def _remove(self, name: str) -> None:
        handle = self._handles.pop(name, None)
        if handle is not None:
            try:
                _kb().remove_hotkey(handle)
            except (KeyError, ValueError):
                pass

    def record(self, on_done: Callable[[str | None], None]) -> None:
        """Wait (in a thread) for the user to press a combination.

        Calls ``on_done(combo)`` from that thread, or ``on_done(None)`` when
        Esc is pressed. Existing hotkeys are paused while recording.
        """
        self.pause()

        def worker() -> None:
            combo: str | None = None
            try:
                combo = normalize(_kb().read_hotkey(suppress=False))
                if combo in ("esc", "escape"):
                    combo = None
            finally:
                self.resume()
                on_done(combo)

        threading.Thread(target=worker, name="hotkey-record", daemon=True).start()
