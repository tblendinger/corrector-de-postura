"""UI Stylesheet and Theme Definitions."""

from posture_guard.data.models import PostureState

# Color Palette
COLOR_BG = "#1a1a2e"
COLOR_SURFACE = "#16213e"
COLOR_CARD = "#1f2b47"
COLOR_BORDER = "#2a3a5c"
COLOR_TEXT = "#e0e0e0"
COLOR_TEXT_SEC = "#8892a0"
COLOR_GOOD = "#00d4aa"
COLOR_WARNING = "#ffb347"
COLOR_BAD = "#ff6b6b"
COLOR_ACCENT = "#4fc3f7"
COLOR_PAUSED = "#6c7a89"

def get_status_color(state: PostureState) -> str:
    """Returns the hex color for a given posture state."""
    colors = {
        PostureState.GOOD: COLOR_GOOD,
        PostureState.ABSENT: COLOR_PAUSED,
        PostureState.WARNING: COLOR_WARNING,
        PostureState.ALERT_L1: COLOR_BAD,
        PostureState.ALERT_L2: COLOR_BAD,
        PostureState.PAUSED: COLOR_PAUSED,
    }
    return colors.get(state, COLOR_PAUSED)

DARK_STYLESHEET = f"""
* {{
    font-family: 'Segoe UI', sans-serif;
    color: {COLOR_TEXT};
}}

QWidget {{
    background-color: {COLOR_BG};
}}

QDialog {{
    background-color: {COLOR_BG};
}}

QLabel {{
    background-color: transparent;
}}

QPushButton {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLOR_CARD};
}}

QPushButton:pressed {{
    background-color: {COLOR_BORDER};
}}

QPushButton#primary {{
    background-color: {COLOR_ACCENT};
    color: white;
    border: none;
}}
QPushButton#primary:hover {{
    background-color: #64d1f9;
}}

QPushButton#danger {{
    background-color: {COLOR_BAD};
    color: white;
    border: none;
}}
QPushButton#danger:hover {{
    background-color: #ff8585;
}}

QPushButton#success {{
    background-color: {COLOR_GOOD};
    color: white;
    border: none;
}}
QPushButton#success:hover {{
    background-color: #22dfb9;
}}

QGroupBox {{
    background-color: transparent;
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    color: {COLOR_ACCENT};
    font-weight: bold;
}}

QSlider::groove:horizontal {{
    border: 1px solid {COLOR_BORDER};
    height: 6px;
    background: {COLOR_SURFACE};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {COLOR_ACCENT};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px;
}}

QComboBox::drop-down {{
    border: none;
}}

QCheckBox {{
    background-color: transparent;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {COLOR_BORDER};
    background-color: {COLOR_SURFACE};
}}
QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
}}

QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    background: {COLOR_BG};
}}

QTabBar::tab {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {COLOR_BG};
    border-bottom-color: {COLOR_BG};
    color: {COLOR_ACCENT};
    font-weight: bold;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QProgressBar {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    text-align: center;
    background-color: {COLOR_SURFACE};
}}
QProgressBar::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: 3px;
}}
"""
