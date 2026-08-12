"""System Tray Icon Manager."""

from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PySide6.QtCore import QObject, Signal, Qt

from posture_guard.data.models import PostureState
from posture_guard.ui.styles import get_status_color
from posture_guard.utils.constants import LOGO_PATH


class SystemTrayManager(QObject):
    show_main_requested = Signal()
    show_feed_requested = Signal()      # new: "Ver cámara"
    pause_toggled = Signal(bool)
    recalibrate_requested = Signal()
    show_stats_requested = Signal()
    show_settings_requested = Signal()
    quit_requested = Signal()
    activated_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray_icon = QSystemTrayIcon(self)
        self.is_paused = False

        self.menu = QMenu()

        # ── Primary actions ──────────────────────
        self.action_feed = self.menu.addAction("📷  Ver cámara en vivo")
        self.action_feed.triggered.connect(self.show_feed_requested.emit)

        self.menu.addSeparator()

        self.action_pause = self.menu.addAction("⏸  Pausar monitoreo")
        self.action_pause.triggered.connect(self._on_pause_toggled)

        self.action_recalibrate = self.menu.addAction("🎯  Recalibrar")
        self.action_recalibrate.triggered.connect(self.recalibrate_requested.emit)

        self.menu.addSeparator()

        # ── Secondary actions ─────────────────────
        self.action_stats = self.menu.addAction("📊  Estadísticas")
        self.action_stats.triggered.connect(self.show_stats_requested.emit)

        self.action_settings = self.menu.addAction("⚙️  Configuración")
        self.action_settings.triggered.connect(self.show_settings_requested.emit)

        self.menu.addSeparator()

        self.action_quit = self.menu.addAction("✕  Salir")
        self.action_quit.triggered.connect(self.quit_requested.emit)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_activated)

        self.update_state(PostureState.ABSENT)
        self.tray_icon.show()

    def _on_pause_toggled(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.action_pause.setText("▶️  Reanudar monitoreo")
        else:
            self.action_pause.setText("⏸  Pausar monitoreo")
        self.pause_toggled.emit(self.is_paused)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click → show feed window
            self.show_feed_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double click → show stats
            self.show_stats_requested.emit()

    def _create_icon(self, color_hex: str) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(color_hex)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.drawEllipse(4, 4, 56, 56)
        painter.end()

        return QIcon(pixmap)

    def update_state(self, state: PostureState) -> None:
        if state == PostureState.PAUSED:
            self.is_paused = True
            self.action_pause.setText("▶️  Reanudar monitoreo")
        elif self.is_paused and state != PostureState.PAUSED:
            self.is_paused = False
            self.action_pause.setText("⏸  Pausar monitoreo")

        color = get_status_color(state)
        self.tray_icon.setIcon(self._create_icon(color))

        state_names = {
            PostureState.GOOD: "Postura correcta ✓",
            PostureState.ABSENT: "Sin persona detectada",
            PostureState.WARNING: "⚠ Precaución: mala postura",
            PostureState.ALERT_L1: "🔴 Alerta: corregí la postura",
            PostureState.ALERT_L2: "🚨 Alerta crítica",
            PostureState.PAUSED: "⏸ Monitoreo pausado",
        }
        self.tray_icon.setToolTip(f"PostureGuard — {state_names.get(state, '')}")

    def show_message(self, title: str, message: str) -> None:
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)
