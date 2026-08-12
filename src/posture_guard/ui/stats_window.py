"""Statistics Dashboard — PostureGuard."""

from __future__ import annotations

import math
from datetime import date, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QIcon

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from posture_guard.utils.constants import STATS_WINDOW_WIDTH, STATS_WINDOW_HEIGHT, LOGO_PATH
from posture_guard.data.models import PostureStats
from posture_guard.ui.styles import (
    DARK_STYLESHEET, COLOR_BG, COLOR_SURFACE, COLOR_CARD,
    COLOR_BORDER, COLOR_GOOD, COLOR_BAD, COLOR_ACCENT,
    COLOR_TEXT, COLOR_TEXT_SEC, COLOR_WARNING,
)

# Matplotlib hex → RGB float helpers
def _hex(s: str) -> str:
    return s  # matplotlib accepts hex strings directly


class StatsWindow(QWidget):
    date_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PostureGuard — Estadísticas")
        self.setMinimumSize(STATS_WINDOW_WIDTH, STATS_WINDOW_HEIGHT)
        self.setStyleSheet(DARK_STYLESHEET)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self._current_view = "daily"
        self._current_date = date.today().isoformat()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        # ── Summary cards ────────────────────────────────────────
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.lbl_pct    = self._card(cards, "Postura correcta", COLOR_GOOD)
        self.lbl_time   = self._card(cards, "Tiempo total",     COLOR_ACCENT)
        self.lbl_alerts = self._card(cards, "Alertas hoy",      COLOR_WARNING)
        self.lbl_streak = self._card(cards, "Racha",            COLOR_GOOD)
        root.addLayout(cards)

        # ── Matplotlib chart ─────────────────────────────────────
        self.fig = Figure(figsize=(9, 3.8), dpi=100)
        self.fig.patch.set_facecolor(COLOR_BG)
        self.ax = self.fig.add_subplot(111)
        self._style_axes()

        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.canvas, stretch=1)

        # ── Bottom nav bar ───────────────────────────────────────
        nav = QHBoxLayout()
        nav.setSpacing(8)

        self.btn_daily   = self._nav_btn("Diario",   lambda: self._switch("daily"))
        self.btn_weekly  = self._nav_btn("Semanal",  lambda: self._switch("weekly"))
        self.btn_monthly = self._nav_btn("Mensual",  lambda: self._switch("monthly"))
        for b in (self.btn_daily, self.btn_weekly, self.btn_monthly):
            nav.addWidget(b)
        self.btn_daily.setChecked(True)

        nav.addStretch()

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(32, 32)
        self.btn_prev.clicked.connect(self._go_prev)

        self.lbl_date = QLabel("Hoy")
        self.lbl_date.setAlignment(Qt.AlignCenter)
        self.lbl_date.setMinimumWidth(110)
        self.lbl_date.setStyleSheet(f"color: {COLOR_TEXT}; font-weight: 600;")

        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(32, 32)
        self.btn_next.clicked.connect(self._go_next)

        nav.addWidget(self.btn_prev)
        nav.addWidget(self.lbl_date)
        nav.addWidget(self.btn_next)
        root.addLayout(nav)

        # Legend
        legend = QHBoxLayout()
        legend.addStretch()
        for color, text in [(COLOR_GOOD, "Buena postura"), (COLOR_BAD, "Mala postura")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 16px;")
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {COLOR_TEXT_SEC}; font-size: 12px;")
            legend.addWidget(dot)
            legend.addWidget(lbl)
            legend.addSpacing(12)
        root.addLayout(legend)

    # ── Widget helpers ────────────────────────────────────────────

    def _card(self, layout: QHBoxLayout, title: str, value_color: str) -> QLabel:
        frame = QFrame()
        frame.setStyleSheet(
            f"background-color: {COLOR_CARD}; border: 1px solid {COLOR_BORDER}; border-radius: 10px;"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 10, 12, 10)

        t = QLabel(title)
        t.setStyleSheet(f"color: {COLOR_TEXT_SEC}; font-size: 12px; border: none;")
        t.setAlignment(Qt.AlignCenter)

        v = QLabel("—")
        v.setStyleSheet(f"color: {value_color}; font-size: 26px; font-weight: bold; border: none;")
        v.setAlignment(Qt.AlignCenter)

        fl.addWidget(t)
        fl.addWidget(v)
        layout.addWidget(frame)
        return v

    def _nav_btn(self, text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedHeight(30)
        btn.clicked.connect(slot)
        return btn

    def _style_axes(self):
        ax = self.ax
        ax.set_facecolor(COLOR_SURFACE)
        ax.tick_params(colors=COLOR_TEXT_SEC, labelsize=9)
        ax.yaxis.label.set_color(COLOR_TEXT_SEC)
        ax.xaxis.label.set_color(COLOR_TEXT_SEC)
        for spine in ax.spines.values():
            spine.set_color(COLOR_BORDER)
        ax.grid(axis="y", color=COLOR_BORDER, linewidth=0.5, alpha=0.6)

    # ── Navigation ────────────────────────────────────────────────

    def _switch(self, view: str):
        self._current_view = view
        self._current_date = date.today().isoformat()
        for btn, v in [(self.btn_daily, "daily"), (self.btn_weekly, "weekly"), (self.btn_monthly, "monthly")]:
            btn.setChecked(v == view)
        self.date_changed.emit(view, self._current_date)

    def _go_prev(self):
        d = date.fromisoformat(self._current_date)
        delta = {"daily": 1, "weekly": 7, "monthly": 30}.get(self._current_view, 1)
        self._current_date = (d - timedelta(days=delta)).isoformat()
        self.date_changed.emit(self._current_view, self._current_date)

    def _go_next(self):
        d = date.fromisoformat(self._current_date)
        delta = {"daily": 1, "weekly": 7, "monthly": 30}.get(self._current_view, 1)
        next_d = d + timedelta(days=delta)
        if next_d <= date.today():
            self._current_date = next_d.isoformat()
            self.date_changed.emit(self._current_view, self._current_date)

    # ── Plotting ──────────────────────────────────────────────────

    def _plot(self, labels: list[str], good_sec: list[float], bad_sec: list[float], y_label: str = "minutos"):
        """Render the stacked bar chart.

        Automatically hides zero-only bars and rotates x-axis labels
        when there are many of them.
        """
        self.ax.clear()
        self._style_axes()

        x = list(range(len(labels)))
        good_m = [s / 60.0 for s in good_sec]
        bad_m  = [s / 60.0 for s in bad_sec]

        # Only show bars with data (avoid 23 empty bars dominating the chart)
        has_data = [g + b > 0 for g, b in zip(good_m, bad_m)]
        any_data = any(has_data)

        if any_data:
            # Build display positions skipping all-zero hours for daily view
            if y_label == "minutos" and len(labels) == 24:
                # Daily: only show bars for hours with data + neighbours
                display_idx = sorted({
                    i for i, h in enumerate(has_data) if h
                } | {
                    i for i, h in enumerate(has_data) if h
                    for d in (-1, 0, 1) if 0 <= i + d < len(labels)
                })
                disp_labels = [labels[i] for i in display_idx]
                disp_good   = [good_m[i]  for i in display_idx]
                disp_bad    = [bad_m[i]   for i in display_idx]
            else:
                display_idx = list(range(len(labels)))
                disp_labels = labels
                disp_good   = good_m
                disp_bad    = bad_m

            disp_x = list(range(len(disp_labels)))
            bar_w  = 0.55 if len(disp_labels) > 5 else 0.4

            self.ax.bar(disp_x, disp_good, width=bar_w, color=COLOR_GOOD, label="Buena", zorder=3)
            self.ax.bar(disp_x, disp_bad,  width=bar_w, bottom=disp_good, color=COLOR_BAD, label="Mala", zorder=3)

            self.ax.set_xticks(disp_x)
            self.ax.set_xticklabels(
                disp_labels,
                rotation=45 if len(disp_labels) > 8 else 0,
                ha="right" if len(disp_labels) > 8 else "center",
                fontsize=9,
            )
        else:
            # No data yet — show placeholder
            self.ax.text(
                0.5, 0.5, "Sin datos para este período",
                transform=self.ax.transAxes,
                ha="center", va="center",
                color=COLOR_TEXT_SEC, fontsize=13,
            )
            self.ax.set_xticks([])

        self.ax.set_ylabel(y_label, color=COLOR_TEXT_SEC, fontsize=10)
        self.ax.tick_params(colors=COLOR_TEXT_SEC, labelsize=9)
        self.fig.tight_layout(pad=1.5)
        self.canvas.draw()

    # ── Data setters (called from app.py) ────────────────────────

    def set_daily_data(self, stats: list[PostureStats], date_str: str):
        self.lbl_date.setText(date_str)
        self._plot(
            [s.period_label for s in stats],
            [s.good_seconds for s in stats],
            [s.bad_seconds  for s in stats],
            y_label="minutos",
        )

    def set_weekly_data(self, stats: list[PostureStats], date_str: str):
        self.lbl_date.setText(date_str)
        self._plot(
            [s.period_label for s in stats],
            [s.good_seconds for s in stats],
            [s.bad_seconds  for s in stats],
            y_label="minutos",
        )

    def set_monthly_data(self, stats: list[PostureStats], year: int, month: int):
        self.lbl_date.setText(f"{month:02d}/{year}")
        self._plot(
            [s.period_label for s in stats],
            [s.good_seconds for s in stats],
            [s.bad_seconds  for s in stats],
            y_label="minutos",
        )

    def set_summary(self, summary: dict):
        self.lbl_pct.setText(f"{summary.get('pct', 0)}%")
        self.lbl_time.setText(summary.get("time", "0m"))
        self.lbl_alerts.setText(str(summary.get("alerts", 0)))
        streak = summary.get("streak", 0)
        self.lbl_streak.setText(f"{streak} día{'s' if streak != 1 else ''}")
