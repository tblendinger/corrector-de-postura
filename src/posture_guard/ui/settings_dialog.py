"""Settings Configuration Dialog — PostureGuard."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QCheckBox, QSlider, QGroupBox,
    QComboBox, QFrame, QSpacerItem, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap

from posture_guard.utils.constants import SETTINGS_WINDOW_WIDTH, SETTINGS_WINDOW_HEIGHT, LOGO_PATH
from posture_guard.data.models import UserConfig
from posture_guard.ui.styles import (
    DARK_STYLESHEET, COLOR_ACCENT, COLOR_BORDER, COLOR_SURFACE,
    COLOR_CARD, COLOR_TEXT, COLOR_TEXT_SEC, COLOR_GOOD, COLOR_WARNING, COLOR_BAD,
)


class SettingsDialog(QDialog):
    config_saved = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostureGuard — Configuración")
        self.setFixedSize(SETTINGS_WINDOW_WIDTH, SETTINGS_WINDOW_HEIGHT)
        self.setStyleSheet(DARK_STYLESHEET)
        self.setModal(True)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"background-color: {COLOR_SURFACE}; border-bottom: 1px solid {COLOR_BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 12, 20, 12)
        hl.setSpacing(10)

        if LOGO_PATH.exists():
            logo_lbl = QLabel()
            pix = QPixmap(str(LOGO_PATH)).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            hl.addWidget(logo_lbl)

        title = QLabel("Configuración")
        title.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(header)

        # ── Tabs ─────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: transparent; }}
            QTabBar::tab {{ padding: 10px 20px; font-size: 13px; }}
        """)

        self.tabs.addTab(self._build_alerts_tab(),       "🔔  Alertas")
        self.tabs.addTab(self._build_sensitivity_tab(),  "🎯  Sensibilidad")
        self.tabs.addTab(self._build_general_tab(),      "⚙️  General")

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLOR_SURFACE};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.addWidget(self.tabs)
        root.addWidget(content, stretch=1)

        # ── Footer / buttons ─────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(f"background-color: {COLOR_SURFACE}; border-top: 1px solid {COLOR_BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 12, 20, 12)
        fl.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setFixedHeight(36)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Guardar cambios")
        btn_save.setObjectName("primary")
        btn_save.setFixedHeight(36)
        btn_save.setMinimumWidth(140)
        btn_save.clicked.connect(self._save)

        fl.addWidget(btn_cancel)
        fl.addSpacing(8)
        fl.addWidget(btn_save)
        root.addWidget(footer)

    # ──────────────────────────────────────────────────────────────
    # Tab builders
    # ──────────────────────────────────────────────────────────────

    def _build_alerts_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(4, 12, 4, 4)

        # Notification types
        gb_notif = QGroupBox("Tipos de notificación")
        gb_l = QVBoxLayout(gb_notif)
        gb_l.setSpacing(10)

        self.chk_toast = QCheckBox("Notificaciones del sistema (globo en el tray)")
        self.chk_sound = QCheckBox("Alertas sonoras (beep)")
        self.chk_feed  = QCheckBox("Ventana emergente con cámara en vivo (Alerta L2)")

        for chk in (self.chk_toast, self.chk_sound, self.chk_feed):
            gb_l.addWidget(chk)

        gb_l.addSpacing(6)
        info = QLabel(
            "💡  La Alerta L2 se activa si mantenés mala postura continuada.\n"
            "     Podés ajustar los tiempos en la pestaña Sensibilidad."
        )
        info.setStyleSheet(f"color: {COLOR_TEXT_SEC}; font-size: 12px;")
        info.setWordWrap(True)
        gb_l.addWidget(info)

        layout.addWidget(gb_notif)

        # Timing
        gb_time = QGroupBox("Cuándo alertar")
        gb_tl = QVBoxLayout(gb_time)
        gb_tl.setSpacing(12)

        self.sl_warn, self.lbl_warn = self._slider_row(
            gb_tl, "Tiempo hasta 1ª alerta", 5, 60, "s",
            tip="Segundos de mala postura antes de la primera notificación"
        )
        self.sl_l2, self.lbl_l2 = self._slider_row(
            gb_tl, "Tiempo hasta alerta crítica", 5, 60, "s",
            tip="Segundos adicionales antes de mostrar la cámara en vivo"
        )

        layout.addWidget(gb_time)

        # Break Reminders (Sitting Timer)
        gb_breaks = QGroupBox("Recordatorios de pausa activa (Tiempo sentado)")
        gb_bl = QVBoxLayout(gb_breaks)
        gb_bl.setSpacing(10)

        self.chk_breaks = QCheckBox("Activar recordatorios para levantarse de la silla")
        gb_bl.addWidget(self.chk_breaks)

        self.sl_micro, self.lbl_micro = self._slider_row(
            gb_bl, "Micropausa (1-2 min)", 15, 45, " min",
            tip="Tiempo sentado antes de recordar una micropausa (Ideal: 30 min)"
        )
        self.sl_active_break, self.lbl_active_break = self._slider_row(
            gb_bl, "Descanso activo (5-10 min)", 45, 90, " min",
            tip="Tiempo máximo sentado antes de recomendar descanso activo (Límite columna: 50-60 min)"
        )

        layout.addWidget(gb_breaks)

        # Gaming mode
        gb_game = QGroupBox("Modo gaming")
        gb_gl = QVBoxLayout(gb_game)
        self.chk_gaming = QCheckBox("Cambiar a beep silencioso cuando hay pantalla completa")
        self.chk_gaming.setToolTip("Detecta automáticamente juegos / video fullscreen y evita ventanas emergentes")
        gb_gl.addWidget(self.chk_gaming)

        layout.addWidget(gb_game)
        layout.addStretch()
        return tab

    def _build_sensitivity_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(4, 12, 4, 4)

        # Detection thresholds
        gb_thresh = QGroupBox("Umbrales de detección de mala postura")
        gb_tl = QVBoxLayout(gb_thresh)
        gb_tl.setSpacing(12)

        self.sl_head, self.lbl_head = self._slider_row(
            gb_tl, "Caída de cabeza", 10, 50, "%",
            tip="Qué tanto debe bajar la cabeza para considerarse mala postura (% del ancho de hombros)"
        )
        self.sl_shoulder, self.lbl_shoulder = self._slider_row(
            gb_tl, "Caída de hombros", 5, 25, "%",
            tip="Reducción del ancho de hombros para detectar encorvamiento"
        )
        self.sl_tilt, self.lbl_tilt = self._slider_row(
            gb_tl, "Inclinación lateral", 5, 30, "°",
            tip="Ángulo de inclinación lateral de hombros para detectar asimetría"
        )

        gb_tl.addSpacing(4)
        hint = QLabel("💡  Valores más bajos = más sensible. Si hay falsos positivos, aumentalos.")
        hint.setStyleSheet(f"color: {COLOR_TEXT_SEC}; font-size: 11px;")
        hint.setWordWrap(True)
        gb_tl.addWidget(hint)

        layout.addWidget(gb_thresh)
        layout.addStretch()
        return tab

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)
        layout.setContentsMargins(4, 12, 4, 4)

        # Startup
        gb_start = QGroupBox("Inicio")
        gb_sl = QVBoxLayout(gb_start)
        self.chk_auto_start = QCheckBox("Iniciar automáticamente con Windows")
        gb_sl.addWidget(self.chk_auto_start)
        layout.addWidget(gb_start)

        # Camera
        gb_cam = QGroupBox("Cámara")
        gb_cl = QHBoxLayout(gb_cam)
        gb_cl.addWidget(QLabel("Dispositivo de cámara:"))
        self.combo_camera = QComboBox()
        self.combo_camera.setMinimumWidth(120)
        for i in range(4):
            self.combo_camera.addItem(f"Cámara {i}", i)
        gb_cl.addWidget(self.combo_camera)
        gb_cl.addStretch()
        layout.addWidget(gb_cam)

        # Recalibrate shortcut
        gb_cal = QGroupBox("Calibración")
        gb_cal_l = QVBoxLayout(gb_cal)
        cal_info = QLabel(
            "La calibración guarda tu postura de referencia (buena postura sentado).\n"
            "Si cambiás de silla, cámara o escritorio, recalibrá desde el menú del tray."
        )
        cal_info.setWordWrap(True)
        cal_info.setStyleSheet(f"color: {COLOR_TEXT_SEC}; font-size: 12px;")
        gb_cal_l.addWidget(cal_info)
        layout.addWidget(gb_cal)

        layout.addStretch()
        return tab

    # ──────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────

    def _slider_row(
        self,
        parent_layout: QVBoxLayout,
        label: str,
        min_val: int,
        max_val: int,
        unit: str,
        tip: str = "",
    ) -> tuple[QSlider, QLabel]:
        """Add a labeled slider row to parent_layout. Returns (slider, value_label)."""
        row = QVBoxLayout()
        row.setSpacing(4)

        top = QHBoxLayout()
        lbl_title = QLabel(label)
        lbl_title.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 13px;")
        if tip:
            lbl_title.setToolTip(tip)

        lbl_val = QLabel(f"{min_val}{unit}")
        lbl_val.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: bold; min-width: 40px;")
        lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top.addWidget(lbl_title)
        top.addStretch()
        top.addWidget(lbl_val)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(min_val)
        slider.setFixedHeight(20)
        slider.valueChanged.connect(lambda v: lbl_val.setText(f"{v}{unit}"))

        row.addLayout(top)
        row.addWidget(slider)
        parent_layout.addLayout(row)

        return slider, lbl_val

    # ──────────────────────────────────────────────────────────────
    # Load / Save
    # ──────────────────────────────────────────────────────────────

    def load_config(self, config: UserConfig) -> None:
        """Populate all controls from the given config."""
        self.chk_auto_start.setChecked(config.auto_start)
        idx = self.combo_camera.findData(config.camera_index)
        if idx >= 0:
            self.combo_camera.setCurrentIndex(idx)

        # Sensitivity
        self.sl_head.setValue(int(config.head_drop_threshold * 100))
        self.sl_shoulder.setValue(int(config.shoulder_width_threshold * 100))
        self.sl_tilt.setValue(int(config.shoulder_tilt_threshold))

        # Alert timing
        self.sl_warn.setValue(config.warning_duration_sec)
        self.sl_l2.setValue(config.l1_to_l2_duration_sec)

        # Notification types
        self.chk_toast.setChecked(getattr(config, "toast_enabled", True))
        self.chk_sound.setChecked(getattr(config, "sound_enabled", True))
        self.chk_feed.setChecked(getattr(config, "feed_window_enabled", True))
        self.chk_gaming.setChecked(getattr(config, "gaming_mode_auto", False))

        # Break Reminders
        self.chk_breaks.setChecked(getattr(config, "break_reminders_enabled", True))
        self.sl_micro.setValue(getattr(config, "micropause_interval_min", 30))
        self.sl_active_break.setValue(getattr(config, "active_break_interval_min", 50))

    def _save(self) -> None:
        config = UserConfig()
        config.auto_start      = self.chk_auto_start.isChecked()
        config.camera_index    = self.combo_camera.currentData()

        config.head_drop_threshold      = self.sl_head.value() / 100.0
        config.shoulder_width_threshold = self.sl_shoulder.value() / 100.0
        config.shoulder_tilt_threshold  = float(self.sl_tilt.value())

        config.warning_duration_sec   = self.sl_warn.value()
        config.l1_to_l2_duration_sec  = self.sl_l2.value()

        config.toast_enabled      = self.chk_toast.isChecked()
        config.sound_enabled      = self.chk_sound.isChecked()
        config.gaming_mode_auto   = self.chk_gaming.isChecked()

        config.break_reminders_enabled   = self.chk_breaks.isChecked()
        config.micropause_interval_min   = self.sl_micro.value()
        config.active_break_interval_min = self.sl_active_break.value()

        # feed_window_enabled stored if UserConfig supports it
        if hasattr(config, "feed_window_enabled"):
            config.feed_window_enabled = self.chk_feed.isChecked()

        self.config_saved.emit(config)
        self.accept()
