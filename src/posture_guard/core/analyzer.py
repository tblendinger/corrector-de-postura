"""Posture Analyzer — Upper-Body Mode with hysteresis.

Analyzes posture using only head + shoulders (no hips required).

Key improvements:
  - Hysteresis: once "good" is established, requires a larger deviation
    to trigger "bad" again. This dramatically reduces false positives
    caused by calibration imprecision or small natural movements.
  - Shoulders out of frame → SLOUCH (user leaning forward/down)
  - Window size 10 for tilt (most jittery metric)
"""

from __future__ import annotations

import logging
import math
from posture_guard.data.models import (
    CalibrationProfile,
    PoseResult,
    PostureStatus,
    PostureIssue,
    PostureMetrics,
)
from posture_guard.utils.angles import MetricsSmoother

logger = logging.getLogger(__name__)

_MIN_SHOULDER_WIDTH = 0.05

# Hysteresis multiplier: once flagged as bad, the metric must recover
# to (threshold * HYSTERESIS) before clearing to "good".
# 1.15 = must improve 15% beyond the bad threshold to clear.
_HYSTERESIS = 1.15


class PostureAnalyzer:
    """Analyzes upper-body pose results against a calibration profile."""

    def __init__(self, calibration_profile: CalibrationProfile) -> None:
        self._calibration = calibration_profile
        self._smoother = MetricsSmoother(
            keys=["head_elevation", "shoulder_width", "shoulder_tilt"],
            window_size=10,
        )
        # Hysteresis state per issue
        self._active: dict[PostureIssue, bool] = {
            PostureIssue.FORWARD_HEAD: False,
            PostureIssue.SLOUCH: False,
            PostureIssue.LATERAL_TILT: False,
        }

    def update_calibration(self, profile: CalibrationProfile) -> None:
        self._calibration = profile
        self._smoother.reset()
        self._active = {k: False for k in self._active}
        logger.info(
            "Analyzer updated: head_elev=%.3f  sw=%.3f  tilt=%.1f°",
            profile.head_drop_ratio, profile.shoulder_width_ratio, profile.shoulder_tilt_angle,
        )

    def reset(self) -> None:
        self._smoother.reset()
        self._active = {k: False for k in self._active}

    def _update_hysteresis(
        self,
        issue: PostureIssue,
        metric: float,
        bad_threshold: float,
        direction: str = "below",  # "below" = bad when metric < threshold
    ) -> bool:
        """Return True if the issue is currently active (with hysteresis).

        direction="below": bad when metric falls below bad_threshold
        direction="above": bad when metric exceeds bad_threshold (tilt)
        """
        currently_active = self._active[issue]

        if direction == "below":
            is_bad_now = metric < bad_threshold
            # Clear only if metric has recovered well past threshold
            clear_threshold = bad_threshold * _HYSTERESIS
            should_clear = metric > clear_threshold
        else:  # "above" for tilt magnitude
            is_bad_now = metric > bad_threshold
            clear_threshold = bad_threshold / _HYSTERESIS
            should_clear = metric < clear_threshold

        if is_bad_now:
            self._active[issue] = True
        elif currently_active and should_clear:
            self._active[issue] = False
        # If currently_active but not yet recovered, stay active

        return self._active[issue]

    def analyze(self, pose: PoseResult) -> PostureStatus:
        """Analyze pose and return PostureStatus."""
        if not pose or not pose.is_valid:
            return PostureStatus(is_good=True, issues=[], confidence=0.0)

        if not self._calibration.is_valid:
            return PostureStatus(is_good=True, issues=[], confidence=0.0)

        nose = pose.get(0)
        l_shoulder = pose.get(11)
        r_shoulder = pose.get(12)

        confidence = (nose.visibility + l_shoulder.visibility + r_shoulder.visibility) / 3.0

        # ── Shoulders out of frame ────────────────────────────────────
        # If either shoulder landmark is outside the frame, the user has
        # likely slouched so far forward that shoulders left the camera view.
        shoulders_in_frame = (
            0.0 <= l_shoulder.x <= 1.0 and 0.0 <= l_shoulder.y <= 1.0 and
            0.0 <= r_shoulder.x <= 1.0 and 0.0 <= r_shoulder.y <= 1.0
        )
        if not shoulders_in_frame:
            # Shoulders out of frame = slouch
            self._active[PostureIssue.SLOUCH] = True
            metrics = PostureMetrics(
                head_drop_ratio=0.0,
                shoulder_width_ratio=0.0,
                shoulder_tilt_angle=0.0,
                timestamp=pose.timestamp,
            )
            return PostureStatus(
                is_good=False,
                issues=[PostureIssue.SLOUCH],
                metrics=metrics,
                confidence=confidence,
            )

        # Nose also must be in frame for head metrics
        if not (0.0 <= nose.x <= 1.0 and 0.0 <= nose.y <= 1.0):
            # Can still check shoulders
            shoulder_width = abs(l_shoulder.x - r_shoulder.x)
            if shoulder_width < _MIN_SHOULDER_WIDTH:
                return PostureStatus(is_good=True, issues=[], confidence=confidence)
            sw_threshold = self._calibration.shoulder_width_ratio * (1.0 - self._calibration.shoulder_width_threshold)
            issues = []
            if self._update_hysteresis(PostureIssue.SLOUCH, shoulder_width, sw_threshold, "below"):
                issues.append(PostureIssue.SLOUCH)
            else:
                self._active[PostureIssue.SLOUCH] = False
            return PostureStatus(is_good=len(issues) == 0, issues=issues, confidence=confidence)

        shoulder_width = abs(l_shoulder.x - r_shoulder.x)
        if shoulder_width < _MIN_SHOULDER_WIDTH:
            return PostureStatus(is_good=True, issues=[], confidence=confidence)

        mid_shoulder_y = (l_shoulder.y + r_shoulder.y) / 2.0

        # Head elevation: head midpoint (nose + ears) above shoulder midpoint
        l_ear = pose.get(7)
        r_ear = pose.get(8)
        if l_ear and r_ear and 0.0 <= l_ear.x <= 1.0 and 0.0 <= l_ear.y <= 1.0 and 0.0 <= r_ear.x <= 1.0 and 0.0 <= r_ear.y <= 1.0:
            head_y = (nose.y + l_ear.y + r_ear.y) / 3.0
        else:
            head_y = nose.y

        head_elevation = (mid_shoulder_y - head_y) / shoulder_width

        # Lateral tilt: shoulder line angle (0° = level)
        tilt = math.degrees(math.atan2(
            l_shoulder.y - r_shoulder.y,
            l_shoulder.x - r_shoulder.x,
        ))

        # Smooth metrics
        smoothed = self._smoother.update({
            "head_elevation": head_elevation,
            "shoulder_width": shoulder_width,
            "shoulder_tilt": tilt,
        })

        s_head = smoothed["head_elevation"]
        s_sw   = smoothed["shoulder_width"]
        s_tilt = smoothed["shoulder_tilt"]

        cal = self._calibration
        issues: list[PostureIssue] = []

        # ── Forward head ──────────────────────────────────────────────
        head_bad_thr = cal.head_drop_ratio * (1.0 - cal.head_drop_threshold)
        if self._update_hysteresis(PostureIssue.FORWARD_HEAD, s_head, head_bad_thr, "below"):
            issues.append(PostureIssue.FORWARD_HEAD)

        # ── Shoulder collapse / slouch ────────────────────────────────
        sw_bad_thr = cal.shoulder_width_ratio * (1.0 - cal.shoulder_width_threshold)
        if self._update_hysteresis(PostureIssue.SLOUCH, s_sw, sw_bad_thr, "below"):
            issues.append(PostureIssue.SLOUCH)

        # ── Lateral tilt ─────────────────────────────────────────────
        tilt_deviation = abs(s_tilt - cal.shoulder_tilt_angle)
        if self._update_hysteresis(PostureIssue.LATERAL_TILT, tilt_deviation, cal.shoulder_tilt_threshold, "above"):
            issues.append(PostureIssue.LATERAL_TILT)

        metrics = PostureMetrics(
            head_drop_ratio=s_head,
            shoulder_width_ratio=s_sw,
            shoulder_tilt_angle=s_tilt,
            timestamp=pose.timestamp,
        )

        return PostureStatus(
            is_good=len(issues) == 0,
            issues=issues,
            metrics=metrics,
            confidence=confidence,
        )
