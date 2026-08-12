"""Vision Engine QThread.

Runs camera capture + pose estimation in a background thread.
Emits Qt signals for each processed frame, state changes, and alerts.

Performance notes:
- Uses grab()+retrieve() to avoid buffer lag
- Supports dynamic FPS adjustment (for calibration mode)
- State machine only emits on transitions to reduce signal noise
"""

from __future__ import annotations

import logging
import time
from PySide6.QtCore import QThread, Signal

from posture_guard.data.models import UserConfig, CalibrationProfile, PostureState
from posture_guard.utils.constants import (
    POSE_MODEL_COMPLEXITY,
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    DEFAULT_GOOD_POSTURE_RESET_SEC,
    CALIBRATION_INTERVAL_MS,
)
from posture_guard.core.camera import CameraCapture
from posture_guard.core.pose import PoseEstimator
from posture_guard.core.analyzer import PostureAnalyzer
from posture_guard.core.state_machine import PostureStateMachine
from posture_guard.core.sitting_timer import SittingTimer

logger = logging.getLogger(__name__)


class VisionEngine(QThread):
    """Main processing loop for vision and posture analysis (runs in QThread)."""

    # Emitted every processed frame: (frame_ndarray, PoseResult|None, PostureStatus|None)
    frame_processed = Signal(object, object, object)
    # Emitted on posture state transitions
    state_changed = Signal(object)
    # Emitted when person detection changes
    person_detected = Signal(bool)
    # Emitted when escalation triggers: (level: int, issues: list)
    alert_triggered = Signal(int, list)
    # Emitted when break milestone is reached: (break_type: str "micropause" | "active_break")
    break_reminder_triggered = Signal(str)

    def __init__(self, config: UserConfig) -> None:
        super().__init__()
        self.config = config
        self._running = False
        self._interval_ms = config.processing_interval_ms  # runtime-adjustable

        self.camera = CameraCapture()
        self.pose_estimator = PoseEstimator(
            model_complexity=POSE_MODEL_COMPLEXITY,
            min_detection_confidence=MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
        )
        self.analyzer = PostureAnalyzer(CalibrationProfile())
        self.state_machine = PostureStateMachine(
            warning_duration_sec=config.warning_duration_sec,
            l1_to_l2_duration_sec=config.l1_to_l2_duration_sec,
            good_reset_sec=DEFAULT_GOOD_POSTURE_RESET_SEC,
        )
        self.sitting_timer = SittingTimer(
            micropause_interval_min=config.micropause_interval_min,
            active_break_interval_min=config.active_break_interval_min,
        )

        self._prev_state: PostureState | None = None
        self._prev_person_detected: bool | None = None

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    @property
    def is_paused(self) -> bool:
        return self.state_machine.state == PostureState.PAUSED

    def set_calibration(self, profile: CalibrationProfile) -> None:
        """Update calibration profile used by the analyzer."""
        self.analyzer.update_calibration(profile)

    def set_interval_ms(self, ms: int) -> None:
        """Dynamically adjust processing interval (FPS control).

        Lower = more FPS. Useful to speed up during calibration.
        """
        self._interval_ms = max(50, ms)
        logger.info("Engine interval set to %d ms (~%.1f FPS)", ms, 1000 / ms)

    def stop(self) -> None:
        """Signal the run loop to stop and wait for it."""
        self._running = False
        self.wait(5000)  # 5s timeout

    def pause(self) -> None:
        """Pause the state machine (engine keeps running)."""
        self.state_machine.pause()
        self._emit_state_if_changed()

    def resume(self) -> None:
        """Resume the state machine."""
        self.state_machine.resume()
        self._emit_state_if_changed()

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _emit_state_if_changed(self) -> None:
        current = self.state_machine.state
        if current != self._prev_state:
            self.state_changed.emit(current)
            self._prev_state = current

    # ──────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────

    def run(self) -> None:
        """Processing loop — runs in background thread."""
        self._running = True
        logger.info("Vision engine thread started")

        while self._running:
            loop_start = time.perf_counter()

            # ── 1. If PAUSED manually by user ──
            if self.state_machine.state == PostureState.PAUSED:
                # Close camera device to turn off webcam LED and release hardware
                if self.camera.is_opened():
                    logger.info("Monitoring paused — releasing camera device (LED OFF)")
                    self.camera.close()

                # Sleep 200ms without reading camera
                time.sleep(0.2)
                continue

            # ── 2. If NOT paused, ensure camera is open ──
            if not self.camera.is_opened():
                logger.info("Opening camera device index %d...", self.config.camera_index)
                if not self.camera.open(self.config.camera_index):
                    logger.warning("Camera open failed. Retrying in 1s...")
                    time.sleep(1.0)
                    continue
                logger.info("Camera device opened successfully")

            # ── 3. Capture frame ──
            ret, frame = self.camera.read_frame()
            if not ret or frame is None:
                time.sleep(0.1)
                continue

            # ── 4. Pose estimation ──
            try:
                pose = self.pose_estimator.estimate(frame)
            except Exception as exc:
                logger.warning("Pose estimation error: %s", exc)
                pose = None

            is_person = pose is not None

            # Emit person_detected only on change
            if is_person != self._prev_person_detected:
                self.person_detected.emit(is_person)
                self._prev_person_detected = is_person

            if not is_person:
                self.state_machine.update(None, False)
                self._emit_state_if_changed()
                self.frame_processed.emit(frame, None, None)
                # Auto-idle sleep when no person is detected (saves CPU)
                time.sleep(0.3)
            else:
                # ── Posture analysis ──
                try:
                    status = self.analyzer.analyze(pose)
                except Exception as exc:
                    logger.warning("Analyzer error: %s", exc)
                    self.frame_processed.emit(frame, pose, None)
                    continue

                prev_state = self.state_machine.state
                self.state_machine.update(status, True)
                current_state = self.state_machine.state

                if current_state != prev_state:
                    self.state_changed.emit(current_state)
                    self._prev_state = current_state

                    if current_state == PostureState.ALERT_L1:
                        self.alert_triggered.emit(1, status.issues)
                    elif current_state == PostureState.ALERT_L2:
                        self.alert_triggered.emit(2, status.issues)

                self.frame_processed.emit(frame, pose, status)

            # ── 5. Continuous Sitting Timer (Break Reminders) ──
            elapsed_ms = (time.perf_counter() - loop_start) * 1000.0
            delta_sec = max(0.001, elapsed_ms / 1000.0)

            break_event = self.sitting_timer.update(
                person_detected=is_person,
                is_paused=self.state_machine.state == PostureState.PAUSED,
                delta_sec=delta_sec,
            )
            if break_event:
                self.break_reminder_triggered.emit(break_event)

            # ── 6. Sleep remaining interval time ──
            sleep_ms = self._interval_ms - elapsed_ms
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

        # ── Cleanup ──
        self.camera.close()
        self.pose_estimator.close()
        logger.info("Vision engine stopped")
