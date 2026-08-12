"""Calibration Manager — Upper-Body Mode.

Designed for the typical webcam-at-desk setup where hips are out of frame.
Metrics are normalized by shoulder_width instead of torso_height, which is
always measurable with just head + shoulders visible.

Posture metrics:
  head_elevation_ratio  = (mid_shoulder_y - nose_y) / shoulder_width
                          Positive = head above shoulders (good).
                          Drops when head sinks forward / toward screen.

  shoulder_width_norm   = shoulder_width (raw normalized [0,1]).
                          Drops when shoulders roll forward / collapse.

  shoulder_tilt_angle   = degrees from horizontal.
                          Non-zero = lateral lean.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from posture_guard.data.models import CalibrationProfile, PoseResult
from posture_guard.utils.angles import midpoint
from posture_guard.utils.constants import CALIBRATION_CAPTURE_FRAMES

logger = logging.getLogger(__name__)

# Minimum shoulder width (normalized) to accept a frame.
# Avoids division-by-zero when person is too far or camera very wide.
_MIN_SHOULDER_WIDTH = 0.05


class CalibrationManager:
    """Manages the calibration capture process."""

    def __init__(self) -> None:
        self._frames: list[dict] = []
        self._is_calibrating = False

    @property
    def is_calibrating(self) -> bool:
        return self._is_calibrating

    @property
    def target_frames(self) -> int:
        return CALIBRATION_CAPTURE_FRAMES

    def start_calibration(self) -> None:
        """Begin collecting calibration frames."""
        self._frames = []
        self._is_calibrating = True
        logger.info("Calibration started — collecting %d frames (upper-body mode)", CALIBRATION_CAPTURE_FRAMES)

    def add_frame(self, pose: PoseResult) -> Tuple[bool, int]:
        """Add one pose frame. Works with only head+shoulders visible (no hips needed).

        Returns:
            (is_complete, frames_collected)
        """
        if not self._is_calibrating:
            return False, len(self._frames)

        if not pose or not pose.is_valid or len(pose.landmarks) < 13:
            return False, len(self._frames)

        nose = pose.get(0)
        l_shoulder = pose.get(11)
        r_shoulder = pose.get(12)

        # Basic sanity: key points inside frame [0,1]
        for lm, name in [(nose, "nose"), (l_shoulder, "l_shoulder"), (r_shoulder, "r_shoulder")]:
            if not (0.0 <= lm.x <= 1.0 and 0.0 <= lm.y <= 1.0):
                logger.debug("Calibration frame skipped: %s out of frame (%.2f, %.2f)", name, lm.x, lm.y)
                return False, len(self._frames)

        shoulder_width = abs(l_shoulder.x - r_shoulder.x)
        if shoulder_width < _MIN_SHOULDER_WIDTH:
            logger.debug("Calibration frame skipped: shoulder_width too small (%.3f)", shoulder_width)
            return False, len(self._frames)

        mid_shoulder_y = (l_shoulder.y + r_shoulder.y) / 2.0

        # Head elevation: head midpoint (nose + ears) above shoulder midpoint, normalized by shoulder_width
        l_ear = pose.get(7)
        r_ear = pose.get(8)
        if l_ear and r_ear and 0.0 <= l_ear.x <= 1.0 and 0.0 <= l_ear.y <= 1.0 and 0.0 <= r_ear.x <= 1.0 and 0.0 <= r_ear.y <= 1.0:
            head_y = (nose.y + l_ear.y + r_ear.y) / 3.0
        else:
            head_y = nose.y

        head_elevation = (mid_shoulder_y - head_y) / shoulder_width

        # Lateral tilt: angle of shoulder line from horizontal (0° = level)
        tilt = math.degrees(math.atan2(
            l_shoulder.y - r_shoulder.y,
            l_shoulder.x - r_shoulder.x,
        ))

        self._frames.append({
            "head_elevation_ratio": head_elevation,
            "shoulder_width": shoulder_width,
            "shoulder_tilt_angle": tilt,
        })

        count = len(self._frames)
        logger.debug("Calibration frame %d/%d (head_elev=%.3f, sw=%.3f, tilt=%.1f°)",
                     count, CALIBRATION_CAPTURE_FRAMES, head_elevation, shoulder_width, tilt)

        is_complete = count >= CALIBRATION_CAPTURE_FRAMES
        if is_complete:
            self._is_calibrating = False

        return is_complete, count

    def finish_calibration(self) -> Optional[CalibrationProfile]:
        """Average collected frames into a CalibrationProfile."""
        if not self._frames:
            logger.warning("finish_calibration() called with no frames")
            return None

        n = len(self._frames)
        avg_head_elev = sum(f["head_elevation_ratio"] for f in self._frames) / n
        avg_sw = sum(f["shoulder_width"] for f in self._frames) / n
        avg_tilt = sum(f["shoulder_tilt_angle"] for f in self._frames) / n

        logger.info(
            "Calibration complete: head_elevation=%.3f, shoulder_width=%.3f, tilt=%.1f°",
            avg_head_elev, avg_sw, avg_tilt,
        )

        # Store in CalibrationProfile fields:
        #   head_drop_ratio      → head_elevation_ratio (repurposed)
        #   shoulder_width_ratio → shoulder_width       (repurposed)
        #   shoulder_tilt_angle  → same
        #   torso_height         → avg_sw (used as validity marker > 0)
        profile = CalibrationProfile(
            head_drop_ratio=avg_head_elev,
            shoulder_width_ratio=avg_sw,
            shoulder_tilt_angle=avg_tilt,
            torso_height=avg_sw,        # non-zero = valid profile
            created_at=datetime.now().isoformat(),
        )

        self._frames = []
        return profile

    def save_profile(self, profile: CalibrationProfile, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(profile.to_json())
            logger.info("Calibration profile saved to %s", path)
        except Exception as e:
            logger.error("Failed to save calibration profile: %s", e)

    def load_profile(self, path: Path) -> Optional[CalibrationProfile]:
        try:
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                profile = CalibrationProfile.from_json(f.read())
            logger.info("Calibration profile loaded from %s", path)
            return profile
        except Exception as e:
            logger.error("Failed to load calibration profile: %s", e)
            return None
