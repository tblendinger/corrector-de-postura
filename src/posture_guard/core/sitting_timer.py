"""Continuous Sitting Timer & Break Reminder Tracker.

Tracks total continuous time the user has spent sitting in front of the computer.
Triggers milestone alerts for:
  - 30 min (Ideal): Micropause of 1-2 min (stand up, stretch, venous return).
  - 50-60 min (Max): Active break of 5-10 min (prevent lumbar/cervical stiffness).

Resets automatically when the user stands up and leaves the desk for >= 45s.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum seconds away from camera to reset continuous sitting timer
_RESET_ABSENT_THRESHOLD_SEC = 45.0


class SittingTimer:
    """Tracks continuous sitting duration and triggers break milestones."""

    def __init__(
        self,
        micropause_interval_min: int = 30,
        active_break_interval_min: int = 50,
    ) -> None:
        self.micropause_interval_sec = micropause_interval_min * 60.0
        self.active_break_interval_sec = active_break_interval_min * 60.0

        self._sitting_sec = 0.0
        self._absent_sec = 0.0
        self._micropause_fired = False
        self._active_break_fired = False

    def update_intervals(self, micropause_min: int, active_break_min: int) -> None:
        """Update milestone thresholds from config."""
        self.micropause_interval_sec = micropause_min * 60.0
        self.active_break_interval_sec = active_break_min * 60.0

    @property
    def sitting_sec(self) -> float:
        return self._sitting_sec

    @property
    def sitting_min(self) -> float:
        return self._sitting_sec / 60.0

    @property
    def formatted_sitting_time(self) -> str:
        total_m = int(self._sitting_sec // 60)
        h = total_m // 60
        m = total_m % 60
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m"

    def reset(self) -> None:
        """Reset continuous sitting timer to zero."""
        self._sitting_sec = 0.0
        self._absent_sec = 0.0
        self._micropause_fired = False
        self._active_break_fired = False

    def update(self, person_detected: bool, is_paused: bool, delta_sec: float) -> Optional[str]:
        """Update timer state with elapsed delta_sec.

        Returns:
            "micropause" when 30-min milestone is reached
            "active_break" when 50-60 min milestone is reached
            None otherwise
        """
        if is_paused:
            return None

        if not person_detected:
            self._absent_sec += delta_sec
            if self._absent_sec >= _RESET_ABSENT_THRESHOLD_SEC:
                if self._sitting_sec > 0:
                    logger.info(
                        "User away for >%.0fs. Continuous sitting timer reset (was %.1fm)",
                        _RESET_ABSENT_THRESHOLD_SEC, self.sitting_min,
                    )
                self.reset()
            return None

        # Person IS detected -> user is sitting
        self._absent_sec = 0.0
        self._sitting_sec += delta_sec

        # Check Active Break milestone (e.g. 50-60 min)
        if (
            self._sitting_sec >= self.active_break_interval_sec
            and not self._active_break_fired
        ):
            self._active_break_fired = True
            logger.info("Active break milestone reached (%.1fm sitting)", self.sitting_min)
            return "active_break"

        # Check Micropause milestone (e.g. 30 min)
        if (
            self._sitting_sec >= self.micropause_interval_sec
            and not self._micropause_fired
        ):
            self._micropause_fired = True
            logger.info("Micropause milestone reached (%.1fm sitting)", self.sitting_min)
            return "micropause"

        return None
