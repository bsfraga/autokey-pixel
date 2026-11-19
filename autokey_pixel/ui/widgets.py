"""Small reusable widgets."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

_MODIFIER_NAMES = {
    Qt.Key_Shift: "Shift",
    Qt.Key_Control: "Ctrl",
    Qt.Key_Alt: "Alt",
    Qt.Key_Meta: "Win",
    Qt.Key_CapsLock: "Caps Lock",
}


def _fallback_vk(key: int) -> int:
    """Best-effort Qt key -> Windows VK, used when no native VK is available."""
    if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
        return int(key)
    if Qt.Key_F1 <= key <= Qt.Key_F24:
        return 0x70 + (key - Qt.Key_F1)
    return {
        Qt.Key_Space: 0x20,
        Qt.Key_Return: 0x0D,
        Qt.Key_Enter: 0x0D,
        Qt.Key_Tab: 0x09,
        Qt.Key_Backspace: 0x08,
        Qt.Key_Left: 0x25,
        Qt.Key_Up: 0x26,
        Qt.Key_Right: 0x27,
        Qt.Key_Down: 0x28,
        Qt.Key_Shift: 0x10,
        Qt.Key_Control: 0x11,
        Qt.Key_Alt: 0x12,
    }.get(key, 0)


class HotkeyField(QWidget):
    """Read-only display of a global hotkey + Record / Clear buttons."""

    record_requested = Signal()
    cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit(readOnly=True)
        self.edit.setPlaceholderText("(nenhuma)")
        self.record_btn = QPushButton("● Gravar")
        self.clear_btn = QPushButton("Limpar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.record_btn)
        lay.addWidget(self.clear_btn)
        self.record_btn.clicked.connect(self.record_requested)
        self.clear_btn.clicked.connect(self._clear)

    def _clear(self) -> None:
        self.set_combo("")
        self.cleared.emit()

    def combo(self) -> str:
        return self.edit.text().replace(" + ", "+").lower()

    def set_combo(self, combo: str) -> None:
        self.edit.setText(" + ".join(p.capitalize() if len(p) > 1 else p.upper() for p in combo.split("+") if p))

    def set_recording(self, on: bool) -> None:
        self.record_btn.setEnabled(not on)
        self.clear_btn.setEnabled(not on)
        if on:
            self.edit.setText("Pressione a combinação… (Esc cancela)")


class KeyCaptureButton(QPushButton):
    """Click, then press a key: emits ``key_captured(vk, display_name)``."""

    key_captured = Signal(int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("● Gravar", parent)
        self._capturing = False
        self.clicked.connect(self._begin)

    def _begin(self) -> None:
        self._capturing = True
        self.setText("Pressione uma tecla… (Esc cancela)")
        self.setFocus()
        self.grabKeyboard()

    def _end(self) -> None:
        self._capturing = False
        self.releaseKeyboard()
        self.setText("● Gravar")

    def event(self, e: QEvent) -> bool:  # catch Tab before focus navigation
        if self._capturing and e.type() == QEvent.KeyPress:
            self.keyPressEvent(e)  # type: ignore[arg-type]
            return True
        return super().event(e)

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if not self._capturing:
            super().keyPressEvent(e)
            return
        key = e.key()
        if key == Qt.Key_Escape:
            self._end()
            return
        vk = e.nativeVirtualKey() or _fallback_vk(key)
        if not vk:
            self.setText("Tecla não suportada — tente outra")
            return
        name = _MODIFIER_NAMES.get(key) or QKeySequence(key).toString() or f"VK 0x{vk:02X}"
        self._end()
        self.key_captured.emit(int(vk), name)

    def focusOutEvent(self, e) -> None:  # noqa: N802
        if self._capturing:
            self._end()
        super().focusOutEvent(e)
