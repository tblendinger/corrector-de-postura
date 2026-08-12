"""Global constants for PostureGuard."""

from pathlib import Path
import os

# ──────────────────────────────────────────────
# Application
# ──────────────────────────────────────────────
APP_NAME = "PostureGuard"
APP_VERSION = "1.0.0"
APP_AUTHOR = "PostureGuard"

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PACKAGE_DIR / "resources"
LOGO_PATH = RESOURCES_DIR / "logo.png"

APP_DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
DB_PATH = APP_DATA_DIR / "posture_data.db"
CONFIG_PATH = APP_DATA_DIR / "config.json"
CALIBRATION_PATH = APP_DATA_DIR / "calibration.json"
LOG_PATH = APP_DATA_DIR / "posture_guard.log"

# ──────────────────────────────────────────────
# Camera
# ──────────────────────────────────────────────
DEFAULT_CAMERA_INDEX = 0
DEFAULT_CAMERA_WIDTH = 640
DEFAULT_CAMERA_HEIGHT = 480

# ──────────────────────────────────────────────
# Processing
# ──────────────────────────────────────────────
DEFAULT_PROCESSING_INTERVAL_MS = 300   # ~3 FPS
CALIBRATION_INTERVAL_MS = 100          # 10 FPS during calibration
MIN_PROCESSING_INTERVAL_MS = 200       # 5 FPS max
MAX_PROCESSING_INTERVAL_MS = 2000      # 0.5 FPS min

# ──────────────────────────────────────────────
# MediaPipe Configuration
# ──────────────────────────────────────────────
POSE_MODEL_COMPLEXITY = 1
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5
MIN_LANDMARK_VISIBILITY = 0.05  # Tasks API visibility semantics differ from legacy

# ──────────────────────────────────────────────
# MediaPipe Landmark Indices (of 33 total)
# ──────────────────────────────────────────────
LM_NOSE = 0
LM_LEFT_EYE_INNER = 1
LM_LEFT_EYE = 2
LM_LEFT_EYE_OUTER = 3
LM_RIGHT_EYE_INNER = 4
LM_RIGHT_EYE = 5
LM_RIGHT_EYE_OUTER = 6
LM_LEFT_EAR = 7
LM_RIGHT_EAR = 8
LM_MOUTH_LEFT = 9
LM_MOUTH_RIGHT = 10
LM_LEFT_SHOULDER = 11
LM_RIGHT_SHOULDER = 12
LM_LEFT_HIP = 23
LM_RIGHT_HIP = 24

# Landmark connections for skeleton drawing (upper body only)
SKELETON_CONNECTIONS = [
    (LM_LEFT_EAR, LM_LEFT_EYE_OUTER),
    (LM_RIGHT_EAR, LM_RIGHT_EYE_OUTER),
    (LM_LEFT_EYE_OUTER, LM_LEFT_EYE),
    (LM_LEFT_EYE, LM_LEFT_EYE_INNER),
    (LM_RIGHT_EYE_INNER, LM_RIGHT_EYE),
    (LM_RIGHT_EYE, LM_RIGHT_EYE_OUTER),
    (LM_LEFT_EYE_INNER, LM_NOSE),
    (LM_NOSE, LM_RIGHT_EYE_INNER),
    (LM_MOUTH_LEFT, LM_MOUTH_RIGHT),
    (LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER),
    (LM_LEFT_SHOULDER, LM_LEFT_HIP),
    (LM_RIGHT_SHOULDER, LM_RIGHT_HIP),
    (LM_LEFT_HIP, LM_RIGHT_HIP),
]

# Key landmarks used for posture analysis
POSTURE_LANDMARKS = [
    LM_NOSE, LM_LEFT_EAR, LM_RIGHT_EAR,
    LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER,
    LM_LEFT_HIP, LM_RIGHT_HIP,
]

# ──────────────────────────────────────────────
# Posture Analysis Defaults
# ──────────────────────────────────────────────
DEFAULT_HEAD_DROP_THRESHOLD = 0.28       # 28% deviation (prevents false positives when looking at screen)
DEFAULT_SHOULDER_WIDTH_THRESHOLD = 0.15  # 15% deviation from calibrated ratio
DEFAULT_SHOULDER_TILT_THRESHOLD = 15.0   # degrees — 15° lateral tilt allowed

# ──────────────────────────────────────────────
# State Machine Timing
# ──────────────────────────────────────────────
DEFAULT_WARNING_DURATION_SEC = 12    # seconds of bad posture before L1 alert
DEFAULT_L1_TO_L2_DURATION_SEC = 15   # additional seconds before L2 alert
DEFAULT_GOOD_POSTURE_RESET_SEC = 3   # seconds of good posture to reset state

# ──────────────────────────────────────────────
# Smoothing
# ──────────────────────────────────────────────
SMOOTHING_WINDOW_SIZE = 5  # frames for moving average

# ──────────────────────────────────────────────
# Calibration
# ──────────────────────────────────────────────
CALIBRATION_CAPTURE_FRAMES = 15
CALIBRATION_CAPTURE_DURATION_SEC = 3

# ──────────────────────────────────────────────
# UI Dimensions
# ──────────────────────────────────────────────
FEED_WINDOW_WIDTH = 480
FEED_WINDOW_HEIGHT = 360
STATS_WINDOW_WIDTH = 900
STATS_WINDOW_HEIGHT = 600
SETTINGS_WINDOW_WIDTH = 520
SETTINGS_WINDOW_HEIGHT = 580
CALIBRATION_WINDOW_WIDTH = 560
CALIBRATION_WINDOW_HEIGHT = 540

# ──────────────────────────────────────────────
# Alert Sound
# ──────────────────────────────────────────────
BEEP_FREQUENCY_HZ = 800
BEEP_DURATION_MS = 300

# ──────────────────────────────────────────────
# Windows Registry (Auto-start)
# ──────────────────────────────────────────────
REGISTRY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_APP_NAME = APP_NAME
