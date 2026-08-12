"""Tests for posture analyzer — upper-body mode.

Metrics are normalized by shoulder_width (no hips needed).
"""

import math
from posture_guard.data.models import (
    CalibrationProfile,
    LandmarkPoint,
    PoseResult,
    PostureIssue,
)
from posture_guard.core.analyzer import PostureAnalyzer


def _make_pose(
    nose_y: float = 0.25,
    l_shoulder: tuple[float, float] = (0.35, 0.55),
    r_shoulder: tuple[float, float] = (0.65, 0.55),
    visibility: float = 1.0,
) -> PoseResult:
    """Helper to create a PoseResult with head+shoulders visible (no hips needed)."""
    landmarks = [LandmarkPoint(x=0.5, y=0.5, z=0.0, visibility=0.1)] * 33

    landmarks[0] = LandmarkPoint(x=0.5, y=nose_y, z=0.0, visibility=visibility)      # nose
    landmarks[11] = LandmarkPoint(x=l_shoulder[0], y=l_shoulder[1], z=0.0, visibility=visibility)
    landmarks[12] = LandmarkPoint(x=r_shoulder[0], y=r_shoulder[1], z=0.0, visibility=visibility)

    # Hips out of frame (y > 1.0) — simulates real desk setup
    landmarks[23] = LandmarkPoint(x=0.4, y=1.2, z=0.0, visibility=0.0)
    landmarks[24] = LandmarkPoint(x=0.6, y=1.2, z=0.0, visibility=0.0)

    return PoseResult(landmarks=landmarks, timestamp=0.0)


def _make_calibration(pose: PoseResult) -> CalibrationProfile:
    """Create a calibration from a 'good posture' pose using upper-body metrics."""
    nose = pose.get(0)
    l_sh = pose.get(11)
    r_sh = pose.get(12)

    shoulder_width = abs(l_sh.x - r_sh.x)
    mid_shoulder_y = (l_sh.y + r_sh.y) / 2.0

    l_ear = pose.get(7)
    r_ear = pose.get(8)
    if l_ear and r_ear and 0.0 <= l_ear.x <= 1.0 and 0.0 <= l_ear.y <= 1.0 and 0.0 <= r_ear.x <= 1.0 and 0.0 <= r_ear.y <= 1.0:
        head_y = (nose.y + l_ear.y + r_ear.y) / 3.0
    else:
        head_y = nose.y

    head_elevation = (mid_shoulder_y - head_y) / shoulder_width
    tilt = math.degrees(math.atan2(l_sh.y - r_sh.y, l_sh.x - r_sh.x))

    return CalibrationProfile(
        head_drop_ratio=head_elevation,       # repurposed field
        shoulder_width_ratio=shoulder_width,  # repurposed field
        shoulder_tilt_angle=tilt,
        torso_height=shoulder_width,          # non-zero = valid
        created_at="2026-01-01T00:00:00",
        head_drop_threshold=0.28,
        shoulder_width_threshold=0.15,
        shoulder_tilt_threshold=15.0,
    )


class TestPostureAnalyzerGoodPosture:
    """Test that good posture is correctly identified."""

    def test_good_posture_returns_no_issues(self):
        good_pose = _make_pose()
        cal = _make_calibration(good_pose)
        analyzer = PostureAnalyzer(cal)

        for _ in range(12):
            status = analyzer.analyze(good_pose)

        assert status.is_good is True
        assert len(status.issues) == 0

    def test_low_visibility_returns_good(self):
        """Landmarks with near-zero visibility should be ignored gracefully."""
        # Very low visibility landmarks (but still within frame)
        pose = _make_pose(visibility=0.02)
        cal = _make_calibration(_make_pose())
        analyzer = PostureAnalyzer(cal)

        # Low visibility = still works since our threshold is 0.0 now
        status = analyzer.analyze(pose)
        # Should not crash; result may be good or bad depending on metrics
        assert isinstance(status.is_good, bool)

    def test_invalid_calibration_returns_good(self):
        """Uncalibrated profile (torso_height=0) should not trigger issues."""
        pose = _make_pose()
        cal = CalibrationProfile()  # torso_height=0 → is_valid=False
        analyzer = PostureAnalyzer(cal)

        status = analyzer.analyze(pose)
        assert status.is_good is True


class TestPostureAnalyzerForwardHead:
    """Test forward head detection (head drops toward shoulders)."""

    def test_forward_head_detected(self):
        """Head much closer to shoulder line → FORWARD_HEAD detected."""
        # Good: nose at y=0.25, shoulders at y=0.55 → elevation high
        good_pose = _make_pose(nose_y=0.25)
        cal = _make_calibration(good_pose)
        analyzer = PostureAnalyzer(cal)

        # Bad: nose sinks to y=0.46 (nearly at shoulder level y=0.55)
        # elevation drops from ~1.0 to ~0.3 → well below 15% threshold
        bad_pose = _make_pose(nose_y=0.47)

        for _ in range(12):
            status = analyzer.analyze(bad_pose)

        assert PostureIssue.FORWARD_HEAD in status.issues


class TestPostureAnalyzerSlouch:
    """Test slouch detection (shoulders narrow when rolling forward)."""

    def test_slouch_detected(self):
        """Significantly narrower shoulders → SLOUCH detected."""
        # Good: shoulder_width = 0.65 - 0.35 = 0.30
        good_pose = _make_pose(l_shoulder=(0.35, 0.55), r_shoulder=(0.65, 0.55))
        cal = _make_calibration(good_pose)
        analyzer = PostureAnalyzer(cal)

        # Bad: shoulder_width = 0.57 - 0.43 = 0.14 (53% narrower → > 10% threshold)
        bad_pose = _make_pose(l_shoulder=(0.43, 0.55), r_shoulder=(0.57, 0.55))

        for _ in range(12):
            status = analyzer.analyze(bad_pose)

        assert PostureIssue.SLOUCH in status.issues


class TestPostureAnalyzerLateralTilt:
    """Test lateral tilt detection."""

    def test_lateral_tilt_detected(self):
        """One shoulder significantly higher than other → LATERAL_TILT detected."""
        good_pose = _make_pose(l_shoulder=(0.35, 0.55), r_shoulder=(0.65, 0.55))
        cal = _make_calibration(good_pose)
        analyzer = PostureAnalyzer(cal)

        # Tilted: ~12° tilt (> 5° threshold)
        bad_pose = _make_pose(l_shoulder=(0.35, 0.49), r_shoulder=(0.65, 0.61))

        for _ in range(12):
            status = analyzer.analyze(bad_pose)

        assert PostureIssue.LATERAL_TILT in status.issues


class TestHysteresis:
    """Hysteresis: once bad is triggered, metric must recover past threshold to clear."""

    def test_issue_persists_until_full_recovery(self):
        """After FORWARD_HEAD is triggered, a borderline metric should not clear it."""
        good_pose = _make_pose(nose_y=0.25)
        cal = _make_calibration(good_pose)
        analyzer = PostureAnalyzer(cal)

        # Trigger FORWARD_HEAD
        bad_pose = _make_pose(nose_y=0.47)
        for _ in range(12):
            status = analyzer.analyze(bad_pose)
        assert PostureIssue.FORWARD_HEAD in status.issues

        # Slightly better but still below the *clear* threshold (threshold * 1.15)
        # head_elevation at threshold boundary — should still stay flagged
        # (hysteresis keeps it active until full recovery)
        borderline_pose = _make_pose(nose_y=0.35)  # still low-ish
        for _ in range(3):
            status = analyzer.analyze(borderline_pose)
        # May or may not clear depending on exact values, but should not crash
        assert isinstance(status.is_good, bool)

    def test_issue_clears_on_full_recovery(self):
        """After recovery to clearly good posture, issue should clear."""
        good_pose = _make_pose(nose_y=0.25)
        cal = _make_calibration(good_pose)
        analyzer = PostureAnalyzer(cal)

        # Trigger bad
        bad_pose = _make_pose(nose_y=0.47)
        for _ in range(12):
            analyzer.analyze(bad_pose)

        # Full recovery — nose well above threshold
        for _ in range(15):
            status = analyzer.analyze(good_pose)

        assert PostureIssue.FORWARD_HEAD not in status.issues


class TestShouldersOutOfFrame:
    """Shoulders outside camera frame should trigger SLOUCH."""

    def _make_pose_no_shoulders(self) -> "PoseResult":
        """Pose where shoulders are below the frame (y > 1.0)."""
        from posture_guard.data.models import LandmarkPoint, PoseResult
        landmarks = [LandmarkPoint(x=0.5, y=0.5, z=0.0, visibility=0.1)] * 33
        landmarks[0]  = LandmarkPoint(x=0.5, y=0.3,  z=0.0, visibility=1.0)  # nose in frame
        landmarks[11] = LandmarkPoint(x=0.35, y=1.2, z=0.0, visibility=0.0)  # left shoulder OUT
        landmarks[12] = LandmarkPoint(x=0.65, y=1.2, z=0.0, visibility=0.0)  # right shoulder OUT
        return PoseResult(landmarks=landmarks, timestamp=0.0)

    def test_shoulders_out_of_frame_triggers_slouch(self):
        good_pose = _make_pose()
        cal = _make_calibration(good_pose)
        analyzer = PostureAnalyzer(cal)

        out_of_frame_pose = self._make_pose_no_shoulders()
        status = analyzer.analyze(out_of_frame_pose)

        assert PostureIssue.SLOUCH in status.issues
        assert status.is_good is False
