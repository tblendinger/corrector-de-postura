"""Fullscreen application detection for gaming mode."""

import time
import logging
from posture_guard.utils import platform_win

logger = logging.getLogger(__name__)

class FullscreenDetector:
    """Detects if a fullscreen application (like a game) is running."""
    
    def __init__(self):
        self._last_check_time = 0.0
        self._last_result = False
        self._cache_duration = 2.0

    @property
    def last_check_time(self) -> float:
        """Returns the time of the last check."""
        return self._last_check_time

    def is_gaming(self) -> bool:
        """Returns True if a fullscreen app (game) is running. Caches result for 2 seconds."""
        current_time = time.time()
        
        if current_time - self._last_check_time < self._cache_duration:
            return self._last_result
            
        try:
            self._last_result = platform_win.is_fullscreen_app_running()
        except Exception as e:
            logger.error("Error checking fullscreen state: %s", e)
            self._last_result = False
            
        self._last_check_time = current_time
        return self._last_result
