"""Tests for posture state machine."""

import time
from unittest.mock import patch
from posture_guard.data.models import PostureState, PostureStatus, PostureIssue, PostureMetrics
from posture_guard.core.state_machine import PostureStateMachine


def _good_status():
    return PostureStatus(is_good=True, issues=[])


def _bad_status():
    return PostureStatus(
        is_good=False,
        issues=[PostureIssue.FORWARD_HEAD],
        metrics=PostureMetrics(head_drop_ratio=0.5),
    )


class TestStateMachineTransitions:
    """Test state machine transitions."""

    def test_initial_state_is_absent(self):
        sm = PostureStateMachine(
            warning_duration_sec=10,
            l1_to_l2_duration_sec=10,
            good_reset_sec=3,
        )
        assert sm.state == PostureState.ABSENT

    def test_absent_to_good_on_person_detected(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(_good_status(), person_detected=True)
        assert sm.state == PostureState.GOOD

    def test_good_to_warning_on_bad_posture(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(_good_status(), True)
        sm.update(_bad_status(), True)
        assert sm.state == PostureState.WARNING

    def test_warning_stays_before_timeout(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(_good_status(), True)
        sm.update(_bad_status(), True)
        # Still under 10s threshold
        sm.update(_bad_status(), True)
        assert sm.state == PostureState.WARNING

    def test_warning_to_alert_l1_after_timeout(self):
        sm = PostureStateMachine(
            warning_duration_sec=0,  # 0 seconds → immediate transition
            l1_to_l2_duration_sec=10,
            good_reset_sec=3,
        )
        sm.update(_good_status(), True)  # → GOOD
        sm.update(_bad_status(), True)   # → WARNING
        sm.update(_bad_status(), True)   # → ALERT_L1 (0s threshold)
        assert sm.state == PostureState.ALERT_L1

    def test_alert_l1_to_l2_after_timeout(self):
        sm = PostureStateMachine(
            warning_duration_sec=0,
            l1_to_l2_duration_sec=0,  # immediate
            good_reset_sec=3,
        )
        sm.update(_good_status(), True)  # → GOOD
        sm.update(_bad_status(), True)   # → WARNING
        sm.update(_bad_status(), True)   # → ALERT_L1
        sm.update(_bad_status(), True)   # → ALERT_L2
        assert sm.state == PostureState.ALERT_L2

    def test_no_person_goes_to_absent(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(_good_status(), True)
        assert sm.state == PostureState.GOOD
        sm.update(_good_status(), False)
        assert sm.state == PostureState.ABSENT

    def test_pause_and_resume(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(_good_status(), True)
        sm.pause()
        assert sm.state == PostureState.PAUSED

        # While paused, updates should keep PAUSED (even when person is absent/detected)
        sm.update(_bad_status(), True)
        assert sm.state == PostureState.PAUSED
        sm.update(None, False)
        assert sm.state == PostureState.PAUSED

        sm.resume()
        assert sm.state == PostureState.ABSENT

    def test_person_return_from_absent_starts_in_good_state(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(None, False)
        assert sm.state == PostureState.ABSENT

        # When person appears, starts fresh in GOOD
        sm.update(_good_status(), True)
        assert sm.state == PostureState.GOOD

    def test_good_posture_resets_from_warning(self):
        sm = PostureStateMachine(
            warning_duration_sec=10,
            l1_to_l2_duration_sec=10,
            good_reset_sec=0,  # immediate reset
        )
        sm.update(_good_status(), True)   # → GOOD
        sm.update(_bad_status(), True)    # → WARNING

        # Good posture should reset to GOOD
        sm.update(_good_status(), True)   # starts good timer
        sm.update(_good_status(), True)   # good_reset_sec=0, should reset
        assert sm.state == PostureState.GOOD


class TestStateMachineProperties:
    """Test state machine properties."""

    def test_bad_posture_duration(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(_good_status(), True)
        assert sm.bad_posture_duration == 0.0

        sm.update(_bad_status(), True)
        assert sm.bad_posture_duration >= 0.0

    def test_time_in_current_state(self):
        sm = PostureStateMachine(10, 10, 3)
        sm.update(_good_status(), True)
        assert sm.time_in_current_state >= 0.0
