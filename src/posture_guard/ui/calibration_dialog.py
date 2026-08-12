"""Calibration Wizard Dialog."""

import numpy as np
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QWidget,
    QProgressBar,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QImage, QPixmap, QIcon

from posture_guard.utils.constants import (
    CALIBRATION_WINDOW_WIDTH,
    CALIBRATION_WINDOW_HEIGHT,
    LOGO_PATH,
)
from posture_guard.data.models import CalibrationProfile
from posture_guard.ui.styles import DARK_STYLESHEET, COLOR_GOOD, COLOR_BAD, COLOR_SURFACE


class CalibrationDialog(QDialog):
    calibration_started = Signal()
    calibration_complete = Signal(object)
    calibration_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostureGuard — Calibración")
        self.setFixedSize(CALIBRATION_WINDOW_WIDTH, CALIBRATION_WINDOW_HEIGHT)
        self.setStyleSheet(DARK_STYLESHEET)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)

        # ── Live Camera Feed Display (Always Visible) ──
        self.feed_label = QLabel()
        self.feed_label.setFixedSize(480, 320)
        self.feed_label.setAlignment(Qt.AlignCenter)
        self.feed_label.setStyleSheet(
            f"background-color: black; border: 2px solid {COLOR_SURFACE}; border-radius: 8px;"
        )

        self.layout.addWidget(self.feed_label, 0, Qt.AlignCenter)

        # ── Stacked Steps Below Video Feed ──
        self.stacked = QStackedWidget()

        # Step 1: Instructions & Start
        step1 = QWidget()
        s1_layout = QVBoxLayout(step1)
        s1_layout.setContentsMargins(0, 0, 0, 0)
        s1_layout.setAlignment(Qt.AlignCenter)

        s1_lbl = QLabel("Sentate derecho con buena postura frente a la cámara.\nCuando estés listo, presioná Iniciar Calibración.")
        s1_lbl.setAlignment(Qt.AlignCenter)
        s1_lbl.setStyleSheet("font-size: 13px; color: #e0e0e0;")

        s1_btn = QPushButton("Iniciar Calibración")
        s1_btn.setObjectName("success")
        s1_btn.setMinimumWidth(180)
        s1_btn.clicked.connect(self._start_calibration)

        s1_layout.addWidget(s1_lbl)
        s1_layout.addWidget(s1_btn, 0, Qt.AlignCenter)

        # Step 2: Capturing Progress
        step2 = QWidget()
        s2_layout = QVBoxLayout(step2)
        s2_layout.setContentsMargins(0, 0, 0, 0)
        s2_layout.setAlignment(Qt.AlignCenter)

        s2_lbl = QLabel("Capturando postura de referencia... Mantené la posición")
        s2_lbl.setAlignment(Qt.AlignCenter)
        s2_lbl.setStyleSheet("font-size: 13px; color: #ffb347; font-weight: bold;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)

        s2_cancel_btn = QPushButton("Cancelar")
        s2_cancel_btn.clicked.connect(self._cancel_calibration)

        s2_layout.addWidget(s2_lbl)
        s2_layout.addWidget(self.progress_bar)
        s2_layout.addWidget(s2_cancel_btn, 0, Qt.AlignCenter)

        # Step 3: Result
        step3 = QWidget()
        s3_layout = QVBoxLayout(step3)
        s3_layout.setContentsMargins(0, 0, 0, 0)
        s3_layout.setAlignment(Qt.AlignCenter)

        self.result_lbl = QLabel()
        self.result_lbl.setAlignment(Qt.AlignCenter)

        self.s3_accept_btn = QPushButton("Aceptar")
        self.s3_accept_btn.setObjectName("primary")
        self.s3_accept_btn.clicked.connect(self.accept)

        self.s3_retry_btn = QPushButton("Reintentar")
        self.s3_retry_btn.clicked.connect(self._retry_calibration)

        self.s3_cancel_btn = QPushButton("Cancelar")
        self.s3_cancel_btn.clicked.connect(self._cancel_calibration)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.s3_accept_btn)
        btn_layout.addWidget(self.s3_retry_btn)
        btn_layout.addWidget(self.s3_cancel_btn)

        s3_layout.addWidget(self.result_lbl)
        s3_layout.addLayout(btn_layout)

        self.stacked.addWidget(step1)
        self.stacked.addWidget(step2)
        self.stacked.addWidget(step3)

        self.layout.addWidget(self.stacked)

        self.profile: CalibrationProfile | None = None

    def _start_calibration(self):
        self.stacked.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.calibration_started.emit()

    def _cancel_calibration(self):
        self.calibration_cancelled.emit()
        self.reject()

    def _retry_calibration(self):
        self.stacked.setCurrentIndex(0)

    def update_frame(self, frame: np.ndarray):
        """Update live camera preview label."""
        try:
            frame_rgb = frame[:, :, ::-1].copy()
            h, w, ch = frame_rgb.shape
            stride = w * ch
            qimg = QImage(frame_rgb.data, w, h, stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                self.feed_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.feed_label.setPixmap(scaled)
        except Exception:
            pass

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)

    def set_calibration_result(self, profile: CalibrationProfile | None):
        self.stacked.setCurrentIndex(2)
        if profile and profile.is_valid:
            self.profile = profile
            self.result_lbl.setText("✓ Calibración exitosa\nValores de referencia guardados.")
            self.result_lbl.setStyleSheet(f"color: {COLOR_GOOD}; font-size: 15px; font-weight: bold;")
            self.s3_accept_btn.show()
            self.s3_retry_btn.hide()
            self.calibration_complete.emit(profile)
        else:
            self.profile = None
            self.result_lbl.setText("✗ Calibración fallida\nNo se detectó una persona o la iluminación es insuficiente.")
            self.result_lbl.setStyleSheet(f"color: {COLOR_BAD}; font-size: 15px; font-weight: bold;")
            self.s3_accept_btn.hide()
            self.s3_retry_btn.show()
