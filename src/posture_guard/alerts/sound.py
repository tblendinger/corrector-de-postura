"""Sound alerts for PostureGuard (Windows winsound)."""

from __future__ import annotations

import logging
import threading
import time

from posture_guard.utils import constants

logger = logging.getLogger(__name__)

try:
    import winsound
    _WINSOUND_AVAILABLE = True
except ImportError:
    winsound = None
    _WINSOUND_AVAILABLE = False
    logger.warning("winsound not available. Sound alerts disabled.")


class SoundAlert:
    """Plays alert beeps using the Windows winsound module."""

    def play_beep(self) -> None:
        """Single short beep (Alert L1)."""
        if not _WINSOUND_AVAILABLE:
            return
        try:
            winsound.Beep(constants.BEEP_FREQUENCY_HZ, constants.BEEP_DURATION_MS)
        except Exception as e:
            logger.error("Failed to play beep: %s", e)

    def play_alert_pattern(self) -> None:
        """Two-beep escalation pattern (Alert L2) — distinct from L1 single beep."""
        if not _WINSOUND_AVAILABLE:
            return
        try:
            winsound.Beep(constants.BEEP_FREQUENCY_HZ, constants.BEEP_DURATION_MS)
            time.sleep(0.15)
            winsound.Beep(constants.BEEP_FREQUENCY_HZ + 200, constants.BEEP_DURATION_MS)
        except Exception as e:
            logger.error("Failed to play alert pattern: %s", e)

    def play_beep_async(self) -> None:
        """Play single beep in background thread (non-blocking)."""
        if not _WINSOUND_AVAILABLE:
            return
        threading.Thread(target=self.play_beep, daemon=True).start()

    def play_alert_pattern_async(self) -> None:
        """Play two-beep pattern in background thread (non-blocking)."""
        if not _WINSOUND_AVAILABLE:
            return
        threading.Thread(target=self.play_alert_pattern, daemon=True).start()
