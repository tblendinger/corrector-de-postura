"""PostureGuard Application Coordinator.

Central class that wires together the vision engine, alert system,
UI components, and data persistence layer.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QApplication

from posture_guard.data.models import (
    CalibrationProfile,
    PostureIssue,
    PostureState,
    PostureStatus,
    PostureEventRecord,
    AlertRecord,
    UserConfig,
)
from posture_guard.data.database import PostureDatabase
from posture_guard.data.config import ConfigManager
from posture_guard.core.engine import VisionEngine
from posture_guard.core.calibration import CalibrationManager
from posture_guard.alerts.manager import AlertManager
from posture_guard.alerts.toast import ToastNotifier
from posture_guard.alerts.sound import SoundAlert
from posture_guard.alerts.fullscreen_detector import FullscreenDetector
from posture_guard.ui.tray import SystemTrayManager
from posture_guard.ui.feed_window import FeedWindow
from posture_guard.ui.overlay_painter import OverlayPainter
from posture_guard.ui.calibration_dialog import CalibrationDialog
from posture_guard.ui.settings_dialog import SettingsDialog
from posture_guard.ui.stats_window import StatsWindow
from posture_guard.ui.styles import DARK_STYLESHEET
from posture_guard.utils.constants import (
    CALIBRATION_PATH,
    FEED_WINDOW_WIDTH,
    FEED_WINDOW_HEIGHT,
    CALIBRATION_INTERVAL_MS,
)
from posture_guard.utils.platform_win import ensure_app_data_dir, set_autostart

logger = logging.getLogger(__name__)


class PostureGuardApp(QObject):
    """Main application coordinator.

    Owns and connects:
    - VisionEngine (background QThread)
    - AlertManager (escalation logic)
    - SystemTrayManager (system tray icon)
    - FeedWindow (camera feed popup)
    - CalibrationDialog, SettingsDialog, StatsWindow
    - PostureDatabase (SQLite persistence)
    - ConfigManager (user settings)
    """

    def __init__(self, q_app: QApplication) -> None:
        super().__init__()
        self.q_app = q_app
        self.q_app.setStyleSheet(DARK_STYLESHEET)
        self.q_app.setQuitOnLastWindowClosed(False)

        # ── Data layer ──────────────────────────────
        ensure_app_data_dir()
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self.db = PostureDatabase()
        self.session_id = self.db.create_session()

        # ── Calibration ─────────────────────────────
        self.calibration_manager = CalibrationManager()
        self.calibration_profile = self._load_calibration()

        # ── Core engine ─────────────────────────────
        self.engine = VisionEngine(self.config)
        if self.calibration_profile and self.calibration_profile.is_valid:
            self.engine.set_calibration(self.calibration_profile)

        # ── Overlay painter ─────────────────────────
        self.overlay_painter = OverlayPainter()

        # ── Alert system ────────────────────────────
        self.toast_notifier = ToastNotifier()
        self.sound_alert = SoundAlert()
        self.fullscreen_detector = FullscreenDetector()
        self.alert_manager = AlertManager(
            self.toast_notifier,
            self.sound_alert,
            self.fullscreen_detector,
        )

        # ── UI components ───────────────────────────
        self.tray = SystemTrayManager()
        self.feed_window = FeedWindow()
        self.calibration_dialog: CalibrationDialog | None = None
        self.settings_dialog: SettingsDialog | None = None
        self.stats_window: StatsWindow | None = None

        # ── Posture event tracking ──────────────────
        self._last_state: PostureState = PostureState.ABSENT
        self._state_start_time: datetime = datetime.now()
        self._current_issues: list[PostureIssue] = []
        self._last_frame = None
        self._last_pose = None
        self._last_status = None

        # ── Connect signals ─────────────────────────
        self._connect_signals()

        # ── First-run calibration ───────────────────
        if not self.calibration_profile or not self.calibration_profile.is_valid:
            logger.info("No calibration found — launching calibration wizard")
            self._show_calibration()
        else:
            self._start_engine()

    # ──────────────────────────────────────────────
    # Signal wiring
    # ──────────────────────────────────────────────

    def _connect_signals(self) -> None:
        """Wire up all inter-component signals."""
        # Engine → App
        self.engine.frame_processed.connect(self._on_frame_processed)
        self.engine.state_changed.connect(self._on_state_changed)
        self.engine.alert_triggered.connect(self._on_alert_triggered)
        self.engine.break_reminder_triggered.connect(self._on_break_reminder_triggered)

        # Alert manager → Feed window
        self.alert_manager.show_feed_window.connect(self._show_feed)
        self.alert_manager.hide_feed_window.connect(self._hide_feed)

        # Tray → App
        self.tray.activated_signal.connect(self._on_tray_activated)
        self.tray.show_feed_requested.connect(self._toggle_feed)
        self.tray.pause_toggled.connect(self._on_pause_toggled)
        self.tray.recalibrate_requested.connect(self._show_calibration)
        self.tray.show_stats_requested.connect(self._show_stats)
        self.tray.show_settings_requested.connect(self._show_settings)
        self.tray.quit_requested.connect(self._quit)

        # Feed window → App
        self.feed_window.pause_requested.connect(self._pause_monitoring)
        self.feed_window.closed.connect(self._hide_feed)

    # ──────────────────────────────────────────────
    # Engine lifecycle
    # ──────────────────────────────────────────────

    def _start_engine(self) -> None:
        """Start the vision engine thread."""
        if not self.engine.isRunning():
            logger.info("Starting vision engine")
            self.engine.start()

    def _stop_engine(self) -> None:
        """Stop the vision engine thread."""
        if self.engine.isRunning():
            logger.info("Stopping vision engine")
            self.engine.stop()

    # ──────────────────────────────────────────────
    # Frame & state handlers
    # ──────────────────────────────────────────────

    @Slot(object, object, object)
    def _on_frame_processed(self, frame, pose_result, posture_status) -> None:
        """Handle each processed frame from the engine."""
        self._last_frame = frame
        self._last_pose = pose_result
        self._last_status = posture_status

        # Draw overlay and update feed window if visible
        if self.feed_window.isVisible() and frame is not None:
            if pose_result and posture_status and self.calibration_profile:
                overlaid = self.overlay_painter.draw_overlay(
                    frame, pose_result, posture_status, self.calibration_profile
                )
            else:
                overlaid = frame
            self.feed_window.update_frame(overlaid, pose_result, posture_status)

    @Slot(object)
    def _on_state_changed(self, new_state: PostureState) -> None:
        """Handle posture state transitions."""
        now = datetime.now()

        # Record the duration of the previous state
        if self._last_state in (PostureState.GOOD, PostureState.WARNING,
                                PostureState.ALERT_L1, PostureState.ALERT_L2):
            duration = (now - self._state_start_time).total_seconds()
            state_str = "good" if self._last_state == PostureState.GOOD else "bad"
            issues_csv = ",".join(i.value for i in self._current_issues)
            metrics_json = self._last_status.metrics.to_json() if self._last_status else "{}"

            event = PostureEventRecord(
                session_id=self.session_id,
                timestamp=self._state_start_time.isoformat(),
                state=state_str,
                issues=issues_csv,
                metrics_json=metrics_json,
                duration_sec=duration,
            )
            try:
                self.db.insert_posture_event(event)
            except Exception as e:
                logger.warning("Failed to record posture event: %s", e)

        self._last_state = new_state
        self._state_start_time = now

        # Update tray icon
        self.tray.update_state(new_state)

        # Handle alert escalation via AlertManager
        if new_state in (PostureState.ALERT_L1, PostureState.ALERT_L2):
            issues = self._last_status.issues if self._last_status else []
            self._current_issues = issues
            self.alert_manager.handle_state_change(new_state, issues, self.config)
        elif new_state in (PostureState.GOOD, PostureState.ABSENT, PostureState.PAUSED):
            self._current_issues = []
            self.alert_manager.handle_state_change(new_state, [], self.config)

    @Slot(int, list)
    def _on_alert_triggered(self, level: int, issues: list) -> None:
        """Record alert events to the database."""
        alert_type = "toast" if level == 1 else "feed_window"
        if self.config.gaming_mode_auto and self.fullscreen_detector.is_gaming():
            alert_type = "sound"

        record = AlertRecord(
            session_id=self.session_id,
            timestamp=datetime.now().isoformat(),
            level=level,
            alert_type=alert_type,
        )
        try:
            self.db.insert_alert(record)
        except Exception as e:
            logger.warning("Failed to record alert: %s", e)

    # ──────────────────────────────────────────────
    # Feed window
    # ──────────────────────────────────────────────

    def _show_feed(self) -> None:
        """Show the camera feed popup window."""
        if self.engine.is_paused:
            self._resume_monitoring()

        if not self.feed_window.isVisible():
            if not self.engine.isRunning():
                self._start_engine()
            issues = self._current_issues or []
            self._position_feed_window()
            self.feed_window.show_with_issues(issues)

    def _hide_feed(self) -> None:
        """Hide the camera feed popup window."""
        if self.feed_window.isVisible():
            self.feed_window.hide()

    def _position_feed_window(self) -> None:
        """Position the feed window at the configured screen corner."""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            margin = 20
            x = geom.right() - FEED_WINDOW_WIDTH - margin
            y = geom.bottom() - FEED_WINDOW_HEIGHT - margin
            self.feed_window.move(x, y)

    # ──────────────────────────────────────────────
    # Pause / Resume
    # ──────────────────────────────────────────────

    @Slot(bool)
    def _on_pause_toggled(self, paused: bool) -> None:
        if paused:
            self._pause_monitoring()
        else:
            self._resume_monitoring()

    def _pause_monitoring(self) -> None:
        """Pause posture monitoring."""
        self.engine.pause()
        self.tray.update_state(PostureState.PAUSED)
        self._hide_feed()
        logger.info("Monitoring paused")

    def _resume_monitoring(self) -> None:
        """Resume posture monitoring."""
        self.engine.resume()
        logger.info("Monitoring resumed")

    # ──────────────────────────────────────────────
    # Tray
    # ──────────────────────────────────────────────

    def _on_tray_activated(self) -> None:
        """Handle left-click on tray icon — toggle feed window."""
        self._toggle_feed()

    def _toggle_feed(self) -> None:
        """Toggle the live camera feed window."""
        if self.feed_window.isVisible():
            self._hide_feed()
        else:
            self._show_feed()

    # ──────────────────────────────────────────────
    # Calibration
    # ──────────────────────────────────────────────

    def _load_calibration(self) -> CalibrationProfile | None:
        """Load calibration profile from disk."""
        return self.calibration_manager.load_profile(CALIBRATION_PATH)

    def _show_calibration(self) -> None:
        """Show the calibration dialog."""
        if self.calibration_dialog and self.calibration_dialog.isVisible():
            self.calibration_dialog.activateWindow()
            return

        if self.engine.is_paused:
            self._resume_monitoring()

        if not self.engine.isRunning():
            self._start_engine()

        # Speed up engine for more responsive calibration preview
        self.engine.set_interval_ms(CALIBRATION_INTERVAL_MS)

        self.calibration_dialog = CalibrationDialog()
        self.calibration_dialog.calibration_started.connect(
            self.calibration_manager.start_calibration
        )
        self.calibration_dialog.calibration_complete.connect(
            self._on_calibration_complete
        )
        self.calibration_dialog.calibration_cancelled.connect(
            self._on_calibration_cancelled
        )

        # Connect engine frames for live preview + calibration capture
        self.engine.frame_processed.connect(self._on_calibration_frame)

        self.calibration_dialog.show()

    @Slot(object, object, object)
    def _on_calibration_frame(self, frame, pose_result, posture_status) -> None:
        """Feed frames to the calibration dialog preview and capture manager."""
        if not self.calibration_dialog or not self.calibration_dialog.isVisible():
            return

        # Always render live camera feed with neutral skeleton for calibration setup
        if frame is not None:
            try:
                if pose_result:
                    overlaid = self.overlay_painter.draw_skeleton_only(frame, pose_result)
                else:
                    overlaid = frame
            except Exception:
                overlaid = frame
            self.calibration_dialog.update_frame(overlaid)

        # Feed frames to calibration manager when capture is running
        if self.calibration_manager.is_calibrating and pose_result:
            is_complete, count = self.calibration_manager.add_frame(pose_result)
            total = self.calibration_manager.target_frames
            progress = int((count / total) * 100) if total > 0 else 0
            self.calibration_dialog.set_progress(progress)

            if is_complete:
                profile = self.calibration_manager.finish_calibration()
                self.calibration_dialog.set_calibration_result(profile)

    def _on_calibration_complete(self, profile: CalibrationProfile) -> None:
        """Handle successful calibration."""
        self.calibration_profile = profile

        # Apply thresholds from config before saving
        profile.head_drop_threshold = self.config.head_drop_threshold
        profile.shoulder_width_threshold = self.config.shoulder_width_threshold
        profile.shoulder_tilt_threshold = self.config.shoulder_tilt_threshold

        self.calibration_manager.save_profile(profile, CALIBRATION_PATH)
        self.engine.set_calibration(profile)

        self._cleanup_calibration()
        self.tray.show_message("PostureGuard", "Calibración exitosa ✓")
        logger.info("Calibration complete and saved")

    def _on_calibration_cancelled(self) -> None:
        """Handle calibration cancellation."""
        self._cleanup_calibration()
        logger.info("Calibration cancelled")

        # If still no valid calibration, keep running in tray so user can
        # recalibrate later via right-click > Recalibrar
        if not self.calibration_profile or not self.calibration_profile.is_valid:
            self.tray.show_message(
                "PostureGuard",
                "Sin calibración — click derecho en el ícono para calibrar cuando estés listo.",
            )
            logger.info("No calibration — app stays in tray; user can recalibrate via tray menu")

    def _cleanup_calibration(self) -> None:
        """Restore normal engine speed and disconnect calibration signal."""
        # Restore normal processing interval
        self.engine.set_interval_ms(self.config.processing_interval_ms)
        # Disconnect the calibration-specific frame handler
        try:
            self.engine.frame_processed.disconnect(self._on_calibration_frame)
        except RuntimeError:
            pass

    # ──────────────────────────────────────────────
    # Settings
    # ──────────────────────────────────────────────

    def _show_settings(self) -> None:
        """Show the settings dialog."""
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.activateWindow()
            return

        self.settings_dialog = SettingsDialog()
        self.settings_dialog.load_config(self.config)
        self.settings_dialog.config_saved.connect(self._on_config_saved)
        self.settings_dialog.show()

    @Slot(str)
    def _on_break_reminder_triggered(self, break_type: str) -> None:
        """Handle break reminder signal from engine."""
        logger.info("Break reminder triggered: %s", break_type)
        self.alert_manager.handle_break_reminder(break_type, self.config)

    @Slot(object)
    def _on_config_saved(self, new_config: UserConfig) -> None:
        """Apply new configuration settings."""
        old_auto_start = self.config.auto_start
        self.config = new_config
        self.config_manager.save(new_config)

        # Update engine timings
        self.engine.state_machine._warning_duration_sec = new_config.warning_duration_sec
        self.engine.state_machine._l1_to_l2_duration_sec = new_config.l1_to_l2_duration_sec

        # Update sitting timer intervals
        self.engine.sitting_timer.update_intervals(
            new_config.micropause_interval_min,
            new_config.active_break_interval_min,
        )

        # Update calibration thresholds
        if self.calibration_profile and self.calibration_profile.is_valid:
            self.calibration_profile.head_drop_threshold = new_config.head_drop_threshold
            self.calibration_profile.shoulder_width_threshold = new_config.shoulder_width_threshold
            self.calibration_profile.shoulder_tilt_threshold = new_config.shoulder_tilt_threshold
            self.engine.set_calibration(self.calibration_profile)

        # Handle auto-start change
        if new_config.auto_start != old_auto_start:
            set_autostart(new_config.auto_start)

        logger.info("Configuration saved and applied")

    # ──────────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────────

    def _show_stats(self) -> None:
        """Show the statistics window."""
        if self.stats_window and self.stats_window.isVisible():
            self.stats_window.activateWindow()
            return

        self.stats_window = StatsWindow()
        self.stats_window.date_changed.connect(self._on_stats_date_changed)

        # Load today's data
        today = date.today().isoformat()
        self._load_stats_data("daily", today)
        self.stats_window.show()

    @Slot(str, str)
    def _on_stats_date_changed(self, view_type: str, date_str: str) -> None:
        """Handle stats navigation."""
        self._load_stats_data(view_type, date_str)

    def _load_stats_data(self, view_type: str, date_str: str) -> None:
        """Load and display statistics data for the given view and date."""
        if not self.stats_window:
            return

        try:
            if view_type == "daily":
                stats = self.db.get_daily_stats(date_str)
                self.stats_window.set_daily_data(stats, date_str)
            elif view_type == "weekly":
                stats = self.db.get_weekly_stats(date_str)
                self.stats_window.set_weekly_data(stats, date_str)
            elif view_type == "monthly":
                parts = date_str.split("-")
                year, month = int(parts[0]), int(parts[1])
                stats = self.db.get_monthly_stats(year, month)
                self.stats_window.set_monthly_data(stats, year, month)

            summary = self.db.get_summary(date_str)
            self.stats_window.set_summary(summary)
        except Exception as e:
            logger.error("Failed to load stats data: %s", e)

    # ──────────────────────────────────────────────
    # Shutdown
    # ──────────────────────────────────────────────

    def _quit(self) -> None:
        """Graceful shutdown."""
        logger.info("PostureGuard shutting down")

        # Record final posture state duration
        self._on_state_changed(PostureState.ABSENT)

        # Stop engine
        self._stop_engine()

        # End session
        try:
            self.db.end_session(self.session_id)
            self.db.close()
        except Exception as e:
            logger.warning("Failed to close database: %s", e)

        # Hide tray
        self.tray.tray_icon.hide()

        # Quit app
        self.q_app.quit()

    def cleanup(self) -> None:
        """Called during application teardown."""
        self._stop_engine()
        try:
            self.db.end_session(self.session_id)
            self.db.close()
        except Exception:
            pass
