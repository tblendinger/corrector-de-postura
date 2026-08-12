"""Data models for PostureGuard.

These dataclasses define the shared contracts between all modules:
core vision, alerts, UI, and persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class PostureIssue(Enum):
    """Types of posture problems detected."""
    FORWARD_HEAD = "forward_head"
    SLOUCH = "slouch"
    LATERAL_TILT = "lateral_tilt"

    @property
    def display_name(self) -> str:
        names = {
            PostureIssue.FORWARD_HEAD: "Cabeza adelantada",
            PostureIssue.SLOUCH: "Hombros caídos",
            PostureIssue.LATERAL_TILT: "Inclinación lateral",
        }
        return names.get(self, self.value)


class PostureState(Enum):
    """States of the posture monitoring state machine."""
    ABSENT = "absent"       # No person detected
    GOOD = "good"           # Good posture
    WARNING = "warning"     # Bad posture detected, counting time
    ALERT_L1 = "alert_l1"  # Toast notification sent
    ALERT_L2 = "alert_l2"  # Feed window shown
    PAUSED = "paused"       # User paused monitoring


class AlertType(Enum):
    """Types of alerts that can be triggered."""
    TOAST = "toast"
    FEED_WINDOW = "feed_window"
    SOUND = "sound"


# ──────────────────────────────────────────────
# Landmark Data
# ──────────────────────────────────────────────

@dataclass
class LandmarkPoint:
    """A single pose landmark from MediaPipe."""
    x: float = 0.0         # Normalized [0, 1] — horizontal position
    y: float = 0.0         # Normalized [0, 1] — vertical position
    z: float = 0.0         # Depth relative to hip midpoint
    visibility: float = 0.0  # Confidence [0, 1]


@dataclass
class PoseResult:
    """Processed pose estimation result wrapping MediaPipe output."""
    landmarks: list[LandmarkPoint] = field(default_factory=list)
    timestamp: float = 0.0

    def get(self, index: int) -> LandmarkPoint:
        """Get landmark by index, returns empty point if out of range."""
        if 0 <= index < len(self.landmarks):
            return self.landmarks[index]
        return LandmarkPoint()

    def is_visible(self, index: int, min_visibility: float = 0.5) -> bool:
        """Check if a landmark has sufficient visibility."""
        return self.get(index).visibility >= min_visibility

    @property
    def is_valid(self) -> bool:
        """Check if pose result has any landmarks."""
        return len(self.landmarks) > 0


# ──────────────────────────────────────────────
# Posture Analysis Results
# ──────────────────────────────────────────────

@dataclass
class PostureMetrics:
    """Current posture measurements computed from landmarks."""
    head_drop_ratio: float = 0.0        # nose-shoulder dist / torso height
    shoulder_width_ratio: float = 0.0    # shoulder width / torso height
    shoulder_tilt_angle: float = 0.0     # degrees from horizontal
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "head_drop_ratio": round(self.head_drop_ratio, 4),
            "shoulder_width_ratio": round(self.shoulder_width_ratio, 4),
            "shoulder_tilt_angle": round(self.shoulder_tilt_angle, 2),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> PostureMetrics:
        return cls(
            head_drop_ratio=d.get("head_drop_ratio", 0.0),
            shoulder_width_ratio=d.get("shoulder_width_ratio", 0.0),
            shoulder_tilt_angle=d.get("shoulder_tilt_angle", 0.0),
        )

    @classmethod
    def from_json(cls, s: str) -> PostureMetrics:
        return cls.from_dict(json.loads(s))


@dataclass
class PostureStatus:
    """Result of posture analysis for a single frame."""
    is_good: bool = True
    issues: list[PostureIssue] = field(default_factory=list)
    metrics: PostureMetrics = field(default_factory=PostureMetrics)
    confidence: float = 0.0  # Average visibility of key landmarks

    @property
    def issues_display(self) -> str:
        """Human-readable list of issues."""
        if not self.issues:
            return "Postura correcta"
        return ", ".join(issue.display_name for issue in self.issues)

    @property
    def issues_csv(self) -> str:
        """Comma-separated issue values for storage."""
        return ",".join(issue.value for issue in self.issues)


# ──────────────────────────────────────────────
# Calibration
# ──────────────────────────────────────────────

@dataclass
class CalibrationProfile:
    """Reference posture values captured during calibration."""
    head_drop_ratio: float = 0.0
    shoulder_width_ratio: float = 0.0
    shoulder_tilt_angle: float = 0.0
    torso_height: float = 0.0        # For normalization reference
    created_at: str = ""

    # Configurable thresholds (percentage deviation / degrees)
    head_drop_threshold: float = 0.28
    shoulder_width_threshold: float = 0.15
    shoulder_tilt_threshold: float = 15.0  # degrees — avoids tilt false positives

    def to_dict(self) -> dict:
        return {
            "head_drop_ratio": self.head_drop_ratio,
            "shoulder_width_ratio": self.shoulder_width_ratio,
            "shoulder_tilt_angle": self.shoulder_tilt_angle,
            "torso_height": self.torso_height,
            "created_at": self.created_at,
            "head_drop_threshold": self.head_drop_threshold,
            "shoulder_width_threshold": self.shoulder_width_threshold,
            "shoulder_tilt_threshold": self.shoulder_tilt_threshold,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CalibrationProfile:
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid_keys})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> CalibrationProfile:
        return cls.from_dict(json.loads(s))

    @property
    def is_valid(self) -> bool:
        """Check if profile has been calibrated (non-zero values)."""
        return self.torso_height > 0


# ──────────────────────────────────────────────
# User Configuration
# ──────────────────────────────────────────────

@dataclass
class UserConfig:
    """User-configurable settings persisted to config.json."""
    # General
    auto_start: bool = False
    camera_index: int = 0

    # Processing
    processing_interval_ms: int = 300
    camera_width: int = 640
    camera_height: int = 480

    # Sensitivity thresholds
    warning_duration_sec: int = 12
    l1_to_l2_duration_sec: int = 15
    head_drop_threshold: float = 0.28
    shoulder_width_threshold: float = 0.15
    shoulder_tilt_threshold: float = 15.0  # degrees

    # Alerts
    sound_enabled: bool = True
    toast_enabled: bool = True
    gaming_mode_auto: bool = True

    # Break Reminders (Sitting Timer)
    break_reminders_enabled: bool = True
    micropause_interval_min: int = 30
    active_break_interval_min: int = 50

    # UI
    feed_window_position: str = "bottom-right"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: dict) -> UserConfig:
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid_keys})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> UserConfig:
        return cls.from_dict(json.loads(s))


# ──────────────────────────────────────────────
# Database Records
# ──────────────────────────────────────────────

@dataclass
class SessionRecord:
    """A monitoring session (from app start to app stop)."""
    id: Optional[int] = None
    start_time: str = ""
    end_time: str = ""


@dataclass
class PostureEventRecord:
    """A recorded posture event for persistence."""
    id: Optional[int] = None
    session_id: int = 0
    timestamp: str = ""
    state: str = ""          # 'good' or 'bad'
    issues: str = ""         # comma-separated issue values
    metrics_json: str = ""   # JSON string of PostureMetrics
    duration_sec: float = 0.0


@dataclass
class AlertRecord:
    """A recorded alert event for persistence."""
    id: Optional[int] = None
    session_id: int = 0
    timestamp: str = ""
    level: int = 0
    alert_type: str = ""     # 'toast', 'feed_window', 'sound'


# ──────────────────────────────────────────────
# Statistics Aggregation
# ──────────────────────────────────────────────

@dataclass
class PostureStats:
    """Aggregated posture statistics for a time period."""
    period_label: str = ""           # e.g., "2026-08-04", "Week 31"
    total_seconds: float = 0.0
    good_seconds: float = 0.0
    bad_seconds: float = 0.0
    alert_count: int = 0
    most_common_issue: str = ""

    @property
    def good_percentage(self) -> float:
        if self.total_seconds == 0:
            return 0.0
        return (self.good_seconds / self.total_seconds) * 100

    @property
    def bad_percentage(self) -> float:
        if self.total_seconds == 0:
            return 0.0
        return (self.bad_seconds / self.total_seconds) * 100
