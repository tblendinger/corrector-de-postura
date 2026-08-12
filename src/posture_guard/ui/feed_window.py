"""Camera Feed Popup Window."""

import numpy as np
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPainterPath, QColor, QMouseEvent

from posture_guard.utils.constants import FEED_WINDOW_WIDTH, FEED_WINDOW_HEIGHT, LOGO_PATH
from posture_guard.data.models import PostureIssue
from posture_guard.ui.styles import COLOR_BG, COLOR_SURFACE, COLOR_BAD
from PySide6.QtGui import QIcon

class FeedWindow(QWidget):
    pause_requested = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(FEED_WINDOW_WIDTH, FEED_WINDOW_HEIGHT)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        
        self.old_pos = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_bar.setStyleSheet(f"background-color: rgba(22, 33, 62, 200); border-top-left-radius: 10px; border-top-right-radius: 10px;")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(10, 5, 10, 5)

        title_lbl = QLabel("PostureGuard — ¡Corregí tu postura!")
        title_lbl.setStyleSheet(f"color: {COLOR_BAD}; font-weight: bold;")
        
        close_btn = QPushButton("X")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SURFACE}; 
                border-radius: 12px; 
                color: white; 
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{ background-color: {COLOR_BAD}; }}
        """)
        close_btn.clicked.connect(self.close)

        top_bar_layout.addWidget(title_lbl)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(close_btn)
        
        # Camera feed
        self.feed_label = QLabel()
        self.feed_label.setAlignment(Qt.AlignCenter)
        self.feed_label.setStyleSheet("background-color: black;")
        
        # Bottom bar
        bottom_bar = QWidget()
        bottom_bar.setStyleSheet(f"background-color: rgba(22, 33, 62, 200); border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;")
        bottom_bar_layout = QHBoxLayout(bottom_bar)
        bottom_bar_layout.setContentsMargins(10, 5, 10, 5)

        self.issue_label = QLabel()
        self.issue_label.setStyleSheet("color: white;")
        
        pause_btn = QPushButton("Pausar")
        pause_btn.setObjectName("primary")
        pause_btn.clicked.connect(self.pause_requested.emit)

        bottom_bar_layout.addWidget(self.issue_label)
        bottom_bar_layout.addStretch()
        bottom_bar_layout.addWidget(pause_btn)

        layout.addWidget(top_bar)
        layout.addWidget(self.feed_label, 1)
        layout.addWidget(bottom_bar)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        painter.fillPath(path, QColor(COLOR_BG))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None

    def update_frame(self, frame: np.ndarray, pose_result, posture_status):
        frame_rgb = frame[:, :, ::-1].copy()
        h, w, ch = frame_rgb.shape
        stride = w * ch
        qimg = QImage(frame_rgb.data, w, h, stride, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.feed_label.setPixmap(pixmap.scaled(self.feed_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def show_with_issues(self, issues: list[PostureIssue]):
        issue_texts = [i.display_name for i in issues]
        self.issue_label.setText("Problemas: " + ", ".join(issue_texts) if issues else "Problemas detectados")
        
        self.setWindowOpacity(0.0)
        self.show()
        
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
