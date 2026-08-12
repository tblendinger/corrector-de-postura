"""Alert Manager — orchestrates toast, beep, and feed window alerts.

Alert escalation:
  ALERT_L1: toast notification + beep (if enabled)
  ALERT_L2: feed window popup + beep (if enabled)

Gaming mode: suppresses windows/toasts, keeps beep only.
"""

from __future__ import annotations

import logging
from PySide6.QtCore import QObject, Signal

from posture_guard.data.models import PostureState, PostureIssue, UserConfig
from posture_guard.alerts.toast import ToastNotifier
from posture_guard.alerts.sound import SoundAlert
from posture_guard.alerts.fullscreen_detector import FullscreenDetector

logger = logging.getLogger(__name__)


class AlertManager(QObject):
    """Coordinates the escalation system for posture alerts."""

    show_feed_window = Signal()
    hide_feed_window = Signal()

    def __init__(
        self,
        toast_notifier: ToastNotifier,
        sound_alert: SoundAlert,
        fullscreen_detector: FullscreenDetector,
    ):
        super().__init__()
        self.toast = toast_notifier
        self.sound = sound_alert
        self.fullscreen = fullscreen_detector

    def handle_state_change(
        self,
        new_state: PostureState,
        issues: list[PostureIssue],
        config: UserConfig,
    ) -> None:
        """Handle a posture state change and fire the appropriate alerts."""

        is_gaming = config.gaming_mode_auto and self.fullscreen.is_gaming()

        if new_state == PostureState.ALERT_L1:
            # Always play beep if enabled (regardless of gaming mode)
            if config.sound_enabled:
                self.sound.play_beep_async()

            # Show toast only outside gaming mode
            if not is_gaming and config.toast_enabled:
                self.toast.show_posture_alert(issues)

            logger.debug("Alert L1 fired — gaming=%s  sound=%s  toast=%s",
                         is_gaming, config.sound_enabled, config.toast_enabled)

        elif new_state == PostureState.ALERT_L2:
            # Always play beep (louder pattern) if enabled
            if config.sound_enabled:
                self.sound.play_alert_pattern_async()

            # Show feed window only outside gaming mode
            if not is_gaming:
                self.show_feed_window.emit()

            logger.debug("Alert L2 fired — gaming=%s  sound=%s", is_gaming, config.sound_enabled)

        elif new_state in (PostureState.GOOD, PostureState.ABSENT, PostureState.PAUSED):
            self.hide_feed_window.emit()

    def handle_alert(self, level: int, issues: list[PostureIssue], config: UserConfig) -> None:
        if level == 1:
            self.handle_state_change(PostureState.ALERT_L1, issues, config)
        elif level == 2:
            self.handle_state_change(PostureState.ALERT_L2, issues, config)

    def handle_break_reminder(self, break_type: str, config: UserConfig) -> None:
        """Handle break reminder notification (micropause or active break)."""
        if not config.break_reminders_enabled:
            return

        is_gaming = config.gaming_mode_auto and self.fullscreen.is_gaming()

        if config.sound_enabled:
            self.sound.play_alert_pattern_async()

        if not is_gaming and config.toast_enabled:
            if break_type == "micropause":
                self.toast.show_micropause_reminder(config.micropause_interval_min)
            elif break_type == "active_break":
                self.toast.show_active_break_reminder(config.active_break_interval_min)

        logger.info("Break reminder handled: break_type=%s, gaming=%s", break_type, is_gaming)
