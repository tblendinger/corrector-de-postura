"""Tests for continuous sitting timer and break reminders."""

import pytest
from posture_guard.core.sitting_timer import SittingTimer, _RESET_ABSENT_THRESHOLD_SEC


class TestSittingTimer:
    """Test SittingTimer milestone triggers and reset behavior."""

    def test_sitting_time_accumulation(self):
        timer = SittingTimer(micropause_interval_min=30, active_break_interval_min=50)
        assert timer.sitting_sec == 0.0

        # Person sitting for 10 seconds
        res = timer.update(person_detected=True, is_paused=False, delta_sec=10.0)
        assert res is None
        assert timer.sitting_sec == 10.0

    def test_micropause_milestone_triggered(self):
        """At 30 minutes (1800s), micropause event should trigger exactly once."""
        timer = SittingTimer(micropause_interval_min=30, active_break_interval_min=50)

        # 29.5 minutes (1770s)
        res = timer.update(person_detected=True, is_paused=False, delta_sec=1770.0)
        assert res is None

        # Reach 30 minutes (1800s)
        res = timer.update(person_detected=True, is_paused=False, delta_sec=30.0)
        assert res == "micropause"

        # Subsequent updates should not re-trigger micropause
        res = timer.update(person_detected=True, is_paused=False, delta_sec=10.0)
        assert res is None

    def test_active_break_milestone_triggered(self):
        """At 50 minutes (3000s), active break event should trigger."""
        timer = SittingTimer(micropause_interval_min=30, active_break_interval_min=50)

        # Fast forward to 49 minutes (2940s)
        timer.update(person_detected=True, is_paused=False, delta_sec=2940.0)

        # Reach 50 minutes (3000s)
        res = timer.update(person_detected=True, is_paused=False, delta_sec=60.0)
        assert res == "active_break"

    def test_brief_absence_does_not_reset(self):
        """Absence under threshold (e.g. 5 seconds) should NOT reset the sitting timer."""
        timer = SittingTimer(30, 50)
        timer.update(person_detected=True, is_paused=False, delta_sec=1000.0)

        # 5 seconds absent
        timer.update(person_detected=False, is_paused=False, delta_sec=5.0)

        # Person returns
        timer.update(person_detected=True, is_paused=False, delta_sec=10.0)
        assert timer.sitting_sec >= 1010.0

    def test_extended_absence_resets_timer(self):
        """Absence over threshold (e.g. 60s) MUST reset the sitting timer."""
        timer = SittingTimer(30, 50)
        timer.update(person_detected=True, is_paused=False, delta_sec=1000.0)

        # Absent for 50 seconds (exceeds _RESET_ABSENT_THRESHOLD_SEC = 45s)
        timer.update(person_detected=False, is_paused=False, delta_sec=_RESET_ABSENT_THRESHOLD_SEC + 5.0)
        assert timer.sitting_sec == 0.0

    def test_paused_monitoring_does_not_accumulate(self):
        """While monitoring is paused, sitting time does not accumulate."""
        timer = SittingTimer(30, 50)
        timer.update(person_detected=True, is_paused=True, delta_sec=500.0)
        assert timer.sitting_sec == 0.0
