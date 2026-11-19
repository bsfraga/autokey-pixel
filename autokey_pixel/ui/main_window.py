"""Main application window."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config.profile import DEFAULT_PROFILE, LIMITS, Profile, ProfileStore
from ..core import pixel, timing, win32
from ..core.hotkeys import HotkeyManager
from ..core.pixel import PixelSample
from ..core.repeater import Repeater, RepeatSettings
from .widgets import HotkeyField, KeyCaptureButton

HISTORY_SIZE = 10
HOTKEY_FIELDS = ("capture", "toggle", "stop")


class Bridge(QObject):
    """Carries events from worker / hook threads to the GUI thread."""

    captured = Signal(object)
    capture_failed = Signal(str)
    toggle_requested = Signal()
    stop_requested = Signal()
    count_changed = Signal(int)
    repeater_stopped = Signal(int, object)
    hotkey_recorded = Signal(str, object)


def _ms_spin(lo: int, hi: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setSuffix(" ms")
    s.setSingleStep(5)
    s.setAccelerated(True)
    return s


class MainWindow(QMainWindow):
    def __init__(self, store: ProfileStore | None = None) -> None:
        super().__init__()
        self.setWindowTitle("AutoKey Pixel")
        self.store = store or ProfileStore()
        self.bridge = Bridge()
        self.hotkeys = HotkeyManager()
        self.repeater = Repeater(
            send_key=win32.send_key,
            on_count=self.bridge.count_changed.emit,
            on_stopped=self.bridge.repeater_stopped.emit,
        )
        self.key_vk = 0
        self.key_name = ""
        self.profile_name = DEFAULT_PROFILE
        self._hotkeys_ok = True

        self._build_ui()
        self._connect()
        self._load_profile(self.store.last_used())

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        main = QVBoxLayout(root)
        main.addWidget(self._build_capture_box())
        main.addWidget(self._build_key_box())

        row = QHBoxLayout()
        row.addWidget(self._build_times_box(), 1)
        row.addWidget(self._build_jitter_box(), 1)
        main.addLayout(row)

        main.addWidget(self._build_control_box())
        main.addLayout(self._build_footer())
        self.setCentralWidget(root)
        self._set_running(False)
        self.statusBar().showMessage("Pronto.")
        self.resize(640, 0)

    def _build_capture_box(self) -> QGroupBox:
        box = QGroupBox("Captura de pixel")
        lay = QVBoxLayout(box)

        form = QFormLayout()
        self.capture_field = HotkeyField()
        form.addRow("Hotkey de captura:", self.capture_field)
        lay.addLayout(form)

        info = QHBoxLayout()
        self.swatch = QFrame()
        self.swatch.setFixedSize(64, 64)
        self.swatch.setFrameShape(QFrame.Box)
        self._set_swatch(None)
        info.addWidget(self.swatch)

        grid = QGridLayout()
        self.lbl_x = QLabel("—")
        self.lbl_y = QLabel("—")
        self.lbl_rgb = QLabel("—")
        self.lbl_hex = QLabel("—")
        self.lbl_time = QLabel("Nenhuma captura ainda")
        for lbl in (self.lbl_x, self.lbl_y, self.lbl_rgb, self.lbl_hex):
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            f = lbl.font()
            f.setBold(True)
            lbl.setFont(f)
        self.copy_btn = QPushButton("Copiar HEX")
        self.copy_btn.setEnabled(False)
        grid.addWidget(QLabel("X:"), 0, 0)
        grid.addWidget(self.lbl_x, 0, 1)
        grid.addWidget(QLabel("Y:"), 0, 2)
        grid.addWidget(self.lbl_y, 0, 3)
        grid.addWidget(QLabel("RGB:"), 1, 0)
        grid.addWidget(self.lbl_rgb, 1, 1)
        grid.addWidget(QLabel("HEX:"), 1, 2)
        grid.addWidget(self.lbl_hex, 1, 3)
        grid.addWidget(self.copy_btn, 1, 4)
        grid.addWidget(self.lbl_time, 2, 0, 1, 5)
        grid.setColumnStretch(5, 1)
        info.addLayout(grid, 1)
        lay.addLayout(info)

        lay.addWidget(QLabel("Histórico (duplo clique copia o HEX):"))
        self.history = QListWidget()
        self.history.setMaximumHeight(90)
        lay.addWidget(self.history)
        return box

    def _build_key_box(self) -> QGroupBox:
        box = QGroupBox("Tecla a repetir")
        lay = QHBoxLayout(box)
        lay.addWidget(QLabel("Tecla:"))
        self.key_label = QLabel("—")
        f = self.key_label.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 2)
        self.key_label.setFont(f)
        self.key_label.setMinimumWidth(80)
        self.key_label.setAlignment(Qt.AlignCenter)
        self.key_label.setFrameShape(QFrame.StyledPanel)
        lay.addWidget(self.key_label)
        self.key_btn = KeyCaptureButton()
        lay.addWidget(self.key_btn)
        lay.addStretch(1)

        lay.addWidget(QLabel("Modo de envio:"))
        self.mode_scan = QRadioButton("Scan code")
        self.mode_scan.setToolTip("Recomendado: funciona na maioria dos jogos (DirectInput).")
        self.mode_vk = QRadioButton("Virtual key")
        self.mode_vk.setToolTip("Para apps comuns que não reagem a scan code.")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_scan)
        self.mode_group.addButton(self.mode_vk)
        lay.addWidget(self.mode_scan)
        lay.addWidget(self.mode_vk)
        return box

    def _build_times_box(self) -> QGroupBox:
        box = QGroupBox("Tempos")
        form = QFormLayout(box)
        self.interval_spin = _ms_spin(*LIMITS["interval_ms"])
        self.hold_spin = _ms_spin(*LIMITS["hold_ms"])
        form.addRow("Intervalo entre envios:", self.interval_spin)
        form.addRow("Tempo pressionada:", self.hold_spin)
        self.cycle_label = QLabel()
        form.addRow("Ciclo efetivo:", self.cycle_label)
        return box

    def _build_jitter_box(self) -> QGroupBox:
        box = QGroupBox("Jitter (variação aleatória ±)")
        form = QFormLayout(box)
        self.interval_jit_spin = _ms_spin(0, 0)
        self.hold_jit_spin = _ms_spin(0, 0)
        self.interval_jit_spin.setToolTip("Máximo: 50% do intervalo.")
        self.hold_jit_spin.setToolTip("Máximo: 50% do tempo pressionada.")
        self.dist_combo = QComboBox()
        for key, label in timing.DISTRIBUTIONS.items():
            self.dist_combo.addItem(label, key)
        self.dist_combo.setToolTip(
            "Uniforme: qualquer valor na faixa.\n"
            "Gaussiana: valores concentrados perto do base (mais 'humano')."
        )
        self.defaults_btn = QPushButton("Restaurar padrões")
        form.addRow("Intervalo ±", self.interval_jit_spin)
        form.addRow("Pressionada ±", self.hold_jit_spin)
        form.addRow("Distribuição:", self.dist_combo)
        form.addRow(self.defaults_btn)
        return box

    def _build_control_box(self) -> QGroupBox:
        box = QGroupBox("Controle")
        lay = QVBoxLayout(box)
        form = QFormLayout()
        self.toggle_field = HotkeyField()
        self.stop_field = HotkeyField()
        form.addRow("Hotkey iniciar/parar:", self.toggle_field)
        form.addRow("Parada de emergência:", self.stop_field)
        lay.addLayout(form)

        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel("Limite:"))
        self.limit_inf = QRadioButton("Infinito")
        self.limit_n = QRadioButton("Parar após")
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, LIMITS["repeat_limit"][1])
        self.limit_spin.setSuffix(" repetições")
        limit_row.addWidget(self.limit_inf)
        limit_row.addWidget(self.limit_n)
        limit_row.addWidget(self.limit_spin)
        limit_row.addStretch(1)
        lay.addLayout(limit_row)

        run_row = QHBoxLayout()
        self.start_btn = QPushButton("▶  INICIAR")
        self.start_btn.setMinimumHeight(40)
        f = self.start_btn.font()
        f.setBold(True)
        self.start_btn.setFont(f)
        run_row.addWidget(self.start_btn, 1)
        self.status_label = QLabel()
        self.count_label = QLabel("Enviadas: 0")
        run_row.addSpacing(16)
        run_row.addWidget(self.status_label)
        run_row.addSpacing(16)
        run_row.addWidget(self.count_label)
        lay.addLayout(run_row)
        return box

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Perfil:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(140)
        row.addWidget(self.profile_combo)
        self.save_btn = QPushButton("Salvar")
        self.save_as_btn = QPushButton("Salvar como…")
        self.delete_btn = QPushButton("Excluir")
        row.addWidget(self.save_btn)
        row.addWidget(self.save_as_btn)
        row.addWidget(self.delete_btn)
        row.addStretch(1)
        self.on_top_check = QCheckBox("Sempre no topo")
        row.addWidget(self.on_top_check)
        self.admin_btn = QPushButton("Reiniciar como admin")
        self.admin_btn.setToolTip(
            "Necessário apenas se a janela alvo (ex.: o jogo) roda como administrador."
        )
        self.admin_btn.setVisible(win32.IS_WINDOWS and not win32.is_admin())
        row.addWidget(self.admin_btn)
        row.addWidget(QLabel(f"v{__version__}"))
        return row

    # ------------------------------------------------------------- wiring
    def _connect(self) -> None:
        b = self.bridge
        b.captured.connect(self._show_sample)
        b.capture_failed.connect(lambda msg: self.statusBar().showMessage(f"Falha na captura: {msg}", 5000))
        b.toggle_requested.connect(self._toggle)
        b.stop_requested.connect(self._stop)
        b.count_changed.connect(lambda n: self.count_label.setText(f"Enviadas: {n}"))
        b.repeater_stopped.connect(self._on_repeater_stopped)
        b.hotkey_recorded.connect(self._on_hotkey_recorded)

        for name, field in self._hotkey_fields().items():
            field.record_requested.connect(lambda n=name: self._record_hotkey(n))
            field.cleared.connect(self._apply_hotkeys)

        self.copy_btn.clicked.connect(lambda: self._copy(self.lbl_hex.text()))
        self.history.itemDoubleClicked.connect(lambda it: self._copy(it.data(Qt.UserRole)))
        self.key_btn.key_captured.connect(self._set_key)

        self.interval_spin.valueChanged.connect(self._update_jitter_limits)
        self.hold_spin.valueChanged.connect(self._update_jitter_limits)
        self.interval_jit_spin.valueChanged.connect(self._update_cycle)
        self.hold_jit_spin.valueChanged.connect(self._update_cycle)
        self.defaults_btn.clicked.connect(self._restore_timing_defaults)

        self.limit_inf.toggled.connect(lambda on: self.limit_spin.setEnabled(not on))
        self.start_btn.clicked.connect(self._toggle)

        self.profile_combo.activated.connect(
            lambda i: self._load_profile(self.profile_combo.itemText(i))
        )
        self.save_btn.clicked.connect(self._save)
        self.save_as_btn.clicked.connect(self._save_as)
        self.delete_btn.clicked.connect(self._delete)
        self.on_top_check.toggled.connect(self._set_on_top)
        self.admin_btn.clicked.connect(self._relaunch_admin)

    def _hotkey_fields(self) -> dict[str, HotkeyField]:
        return {"capture": self.capture_field, "toggle": self.toggle_field, "stop": self.stop_field}

    # ------------------------------------------------------------ profile
    def _profile_from_ui(self) -> Profile:
        return Profile(
            capture_hotkey=self.capture_field.combo(),
            toggle_hotkey=self.toggle_field.combo(),
            stop_hotkey=self.stop_field.combo(),
            key_vk=self.key_vk,
            key_name=self.key_name,
            send_mode="scancode" if self.mode_scan.isChecked() else "vk",
            interval_ms=self.interval_spin.value(),
            hold_ms=self.hold_spin.value(),
            interval_jitter_ms=self.interval_jit_spin.value(),
            hold_jitter_ms=self.hold_jit_spin.value(),
            distribution=self.dist_combo.currentData(),
            repeat_limit=0 if self.limit_inf.isChecked() else self.limit_spin.value(),
            always_on_top=self.on_top_check.isChecked(),
        ).normalized()

    def _apply_profile(self, p: Profile) -> None:
        self.capture_field.set_combo(p.capture_hotkey)
        self.toggle_field.set_combo(p.toggle_hotkey)
        self.stop_field.set_combo(p.stop_hotkey)
        self._set_key(p.key_vk, p.key_name)
        (self.mode_scan if p.send_mode == "scancode" else self.mode_vk).setChecked(True)
        self.interval_spin.setValue(p.interval_ms)
        self.hold_spin.setValue(p.hold_ms)
        self._update_jitter_limits()
        self.interval_jit_spin.setValue(p.interval_jitter_ms)
        self.hold_jit_spin.setValue(p.hold_jitter_ms)
        self.dist_combo.setCurrentIndex(max(0, self.dist_combo.findData(p.distribution)))
        if p.repeat_limit:
            self.limit_n.setChecked(True)
            self.limit_spin.setValue(p.repeat_limit)
        else:
            self.limit_inf.setChecked(True)
            self.limit_spin.setValue(100)
        self.limit_spin.setEnabled(bool(p.repeat_limit))
        self.on_top_check.setChecked(p.always_on_top)
        self._update_cycle()
        self._apply_hotkeys()

    def _refresh_profile_combo(self) -> None:
        self.profile_combo.clear()
        self.profile_combo.addItems(self.store.names())
        self.profile_combo.setCurrentText(self.profile_name)

    def _load_profile(self, name: str) -> None:
        if self.repeater.running:
            self._stop()
        self.profile_name = name
        self._apply_profile(self.store.load(name))
        self._refresh_profile_combo()
        self._remember_profile()

    def _save(self) -> None:
        self.profile_name = self.store.save(self.profile_name, self._profile_from_ui())
        self._remember_profile()
        self.statusBar().showMessage(f"Perfil “{self.profile_name}” salvo.", 3000)

    def _save_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Salvar perfil como", "Nome do perfil:")
        if ok and name.strip():
            self.profile_name = name.strip()
            self._save()
            self._refresh_profile_combo()

    def _delete(self) -> None:
        if self.profile_name == DEFAULT_PROFILE:
            self.store.delete(DEFAULT_PROFILE)
            self._load_profile(DEFAULT_PROFILE)
            self.statusBar().showMessage("Perfil padrão restaurado.", 3000)
            return
        if QMessageBox.question(self, "Excluir perfil", f"Excluir o perfil “{self.profile_name}”?") \
                == QMessageBox.Yes:
            self.store.delete(self.profile_name)
            self._load_profile(DEFAULT_PROFILE)

    def _remember_profile(self) -> None:
        try:
            self.store.set_last_used(self.profile_name)
        except OSError:
            pass

    # ------------------------------------------------------------ hotkeys
    def _apply_hotkeys(self) -> None:
        combos = {n: f.combo() for n, f in self._hotkey_fields().items()}
        set_combos = [c for c in combos.values() if c]
        if len(set_combos) != len(set(set_combos)):
            self.statusBar().showMessage("Atenção: há hotkeys repetidas.", 5000)
        callbacks = {
            "capture": self._capture_from_hook,
            "toggle": self.bridge.toggle_requested.emit,
            "stop": self.bridge.stop_requested.emit,
        }
        try:
            for name, combo in combos.items():
                self.hotkeys.set(name, combo, callbacks[name])
            self._hotkeys_ok = True
        except Exception as exc:  # noqa: BLE001 - e.g. unsupported platform
            self._hotkeys_ok = False
            self.statusBar().showMessage(f"Hotkeys globais indisponíveis: {exc or type(exc).__name__}")

    def _record_hotkey(self, name: str) -> None:
        if not self._hotkeys_ok:
            self.statusBar().showMessage("Hotkeys globais indisponíveis neste sistema.", 5000)
            return
        for f in self._hotkey_fields().values():
            f.record_btn.setEnabled(False)
        self._hotkey_fields()[name].set_recording(True)
        self.hotkeys.record(lambda combo: self.bridge.hotkey_recorded.emit(name, combo))

    def _on_hotkey_recorded(self, name: str, combo: str | None) -> None:
        field = self._hotkey_fields()[name]
        field.set_recording(False)
        for f in self._hotkey_fields().values():
            f.record_btn.setEnabled(True)
        if combo:
            field.set_combo(combo)
        else:
            self._apply_profile_field_back(name)
        self._apply_hotkeys()

    def _apply_profile_field_back(self, name: str) -> None:
        stored = self.store.load(self.profile_name)
        self._hotkey_fields()[name].set_combo(getattr(stored, f"{name}_hotkey"))

    def _capture_from_hook(self) -> None:
        # runs on the keyboard hook thread; capture is fast, UI update is marshalled
        try:
            self.bridge.captured.emit(pixel.capture())
        except Exception as exc:  # noqa: BLE001
            self.bridge.capture_failed.emit(str(exc))

    # ------------------------------------------------------------ capture
    def _set_swatch(self, color: QColor | None) -> None:
        css = color.name() if color else "transparent"
        self.swatch.setStyleSheet(f"background-color: {css};")

    def _show_sample(self, s: PixelSample) -> None:
        self._set_swatch(QColor(s.r, s.g, s.b))
        self.lbl_x.setText(str(s.x))
        self.lbl_y.setText(str(s.y))
        self.lbl_rgb.setText(s.rgb)
        self.lbl_hex.setText(s.hex)
        self.lbl_time.setText(f"Capturado às {s.at:%H:%M:%S}")
        self.copy_btn.setEnabled(True)

        icon = QPixmap(14, 14)
        icon.fill(QColor(s.r, s.g, s.b))
        item = QListWidgetItem(QIcon(icon), s.summary())
        item.setData(Qt.UserRole, s.hex)
        self.history.insertItem(0, item)
        while self.history.count() > HISTORY_SIZE:
            self.history.takeItem(self.history.count() - 1)

    def _copy(self, text: str) -> None:
        if text and text != "—":
            QGuiApplication.clipboard().setText(text)
            self.statusBar().showMessage(f"{text} copiado.", 2000)

    # ------------------------------------------------------------- timing
    def _update_jitter_limits(self) -> None:
        self.interval_jit_spin.setMaximum(timing.max_jitter(self.interval_spin.value()))
        self.hold_jit_spin.setMaximum(timing.max_jitter(self.hold_spin.value()))
        self._update_cycle()

    def _update_cycle(self) -> None:
        lo, hi = timing.effective_range(
            self.interval_spin.value(),
            self.interval_jit_spin.value(),
            self.hold_spin.value(),
            self.hold_jit_spin.value(),
        )
        rate = 1000.0 / ((lo + hi) / 2)
        self.cycle_label.setText(f"{lo:.0f}–{hi:.0f} ms  (~{rate:.1f}/s)")

    def _restore_timing_defaults(self) -> None:
        d = Profile()
        self.interval_spin.setValue(d.interval_ms)
        self.hold_spin.setValue(d.hold_ms)
        self._update_jitter_limits()
        self.interval_jit_spin.setValue(d.interval_jitter_ms)
        self.hold_jit_spin.setValue(d.hold_jitter_ms)
        self.dist_combo.setCurrentIndex(self.dist_combo.findData(d.distribution))

    # ------------------------------------------------------------ repeat
    def _set_key(self, vk: int, name: str) -> None:
        self.key_vk, self.key_name = vk, name
        self.key_label.setText(name or "—")
        self.key_label.setToolTip(f"Virtual key 0x{vk:02X}" if vk else "")

    def _conflicts_with_hotkey(self) -> str | None:
        key = self.key_name.lower()
        for label, field in (("iniciar/parar", self.toggle_field), ("emergência", self.stop_field)):
            if key and key == field.combo():
                return label
        return None

    def _toggle(self) -> None:
        if self.repeater.running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        if not self.key_vk:
            QMessageBox.warning(self, "Tecla não definida", "Grave a tecla a ser repetida primeiro.")
            return
        conflict = self._conflicts_with_hotkey()
        if conflict:
            QMessageBox.warning(
                self, "Conflito de tecla",
                f"A tecla repetida é igual à hotkey de {conflict}. Escolha outra.",
            )
            return
        p = self._profile_from_ui()
        settings = RepeatSettings(
            vk=p.key_vk,
            use_scancode=p.send_mode == "scancode",
            interval_ms=p.interval_ms,
            hold_ms=p.hold_ms,
            interval_jitter_ms=p.interval_jitter_ms,
            hold_jitter_ms=p.hold_jitter_ms,
            distribution=p.distribution,
            limit=p.repeat_limit,
        )
        if self.repeater.start(settings):
            self.count_label.setText("Enviadas: 0")
            self._set_running(True)

    def _stop(self) -> None:
        self.repeater.stop()

    def _on_repeater_stopped(self, count: int, error: object) -> None:
        self._set_running(False)
        if error:
            self.statusBar().showMessage(f"Repetição interrompida: {error}")
            QMessageBox.warning(self, "Erro ao enviar tecla", str(error))
        else:
            self.statusBar().showMessage(f"Parado após {count} envio(s).", 4000)

    def _set_running(self, running: bool) -> None:
        if running:
            self.start_btn.setText("■  PARAR")
            self.status_label.setText('<span style="color:#2e9d4e">●</span> Executando')
        else:
            self.start_btn.setText("▶  INICIAR")
            self.status_label.setText('<span style="color:#c0392b">●</span> Parado')
        for w in (self.key_btn, self.profile_combo, self.save_as_btn, self.delete_btn):
            w.setEnabled(not running)

    # -------------------------------------------------------------- misc
    def _set_on_top(self, on: bool) -> None:
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()

    def _relaunch_admin(self) -> None:
        self._save()
        if win32.relaunch_as_admin():
            self.close()
        else:
            self.statusBar().showMessage("Elevação cancelada.", 3000)

    def closeEvent(self, e) -> None:  # noqa: N802
        self.repeater.stop(wait=True)
        try:
            self.hotkeys.clear()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.store.save(self.profile_name, self._profile_from_ui())
        except OSError:
            pass
        super().closeEvent(e)
