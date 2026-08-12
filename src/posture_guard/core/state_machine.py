"""Posture State Machine."""

import logging
import time
from posture_guard.data.models import PostureState, PostureStatus

logger = logging.getLogger(__name__)

class PostureStateMachine:
    """Manages transitions between posture states."""
    
    def __init__(self, warning_duration_sec: int, l1_to_l2_duration_sec: int, good_reset_sec: int) -> None:
        self._warning_duration_sec = warning_duration_sec
        self._l1_to_l2_duration_sec = l1_to_l2_duration_sec
        self._good_reset_sec = good_reset_sec
        
        self._state = PostureState.ABSENT
        self._state_start_time = time.time()
        
        self._bad_posture_start = 0.0
        self._good_posture_start = 0.0
        self._l1_alert_time = 0.0
        
    @property
    def state(self) -> PostureState:
        return self._state
        
    @property
    def time_in_current_state(self) -> float:
        return time.time() - self._state_start_time
        
    @property
    def bad_posture_duration(self) -> float:
        if self._state in (PostureState.WARNING, PostureState.ALERT_L1, PostureState.ALERT_L2):
            return time.time() - self._bad_posture_start
        return 0.0
        
    def _change_state(self, new_state: PostureState) -> None:
        if self._state != new_state:
            self._state = new_state
            self._state_start_time = time.time()
            
    def update(self, posture_status: PostureStatus | None, person_detected: bool) -> PostureState:
        """Update the state based on posture status and person detection."""
        now = time.time()

        # 1. PAUSED state MUST be checked first (never unpause automatically)
        if self._state == PostureState.PAUSED:
            return self._state

        # 2. No person detected -> ABSENT (auto-pause / idle)
        if not person_detected:
            if self._state != PostureState.ABSENT:
                self._change_state(PostureState.ABSENT)
                self._good_posture_start = 0.0
                self._bad_posture_start = 0.0
                self._l1_alert_time = 0.0
            return self._state

        # 3. Person detected! If coming from ABSENT, start fresh in GOOD state
        if self._state == PostureState.ABSENT:
            self._change_state(PostureState.GOOD)
            self._good_posture_start = 0.0
            self._bad_posture_start = 0.0
            self._l1_alert_time = 0.0

        if posture_status is None:
            return self._state

        # 4. Posture analysis tracking
        if posture_status.is_good:
            if self._state in (PostureState.WARNING, PostureState.ALERT_L1, PostureState.ALERT_L2):
                if self._good_posture_start == 0.0:
                    self._good_posture_start = now
                elif now - self._good_posture_start >= self._good_reset_sec:
                    self._change_state(PostureState.GOOD)
                    self._good_posture_start = 0.0
                    self._bad_posture_start = 0.0
                    self._l1_alert_time = 0.0
            else:
                self._change_state(PostureState.GOOD)
                self._good_posture_start = 0.0
        else:
            self._good_posture_start = 0.0

            if self._state == PostureState.GOOD or self._state == PostureState.ABSENT:
                self._change_state(PostureState.WARNING)
                self._bad_posture_start = now
            elif self._state == PostureState.WARNING:
                if now - self._bad_posture_start >= self._warning_duration_sec:
                    self._change_state(PostureState.ALERT_L1)
                    self._l1_alert_time = now
            elif self._state == PostureState.ALERT_L1:
                if now - self._l1_alert_time >= self._l1_to_l2_duration_sec:
                    self._change_state(PostureState.ALERT_L2)

        return self._state
        
    def pause(self) -> None:
        """Pause the state machine."""
        self._change_state(PostureState.PAUSED)
        
    def resume(self) -> None:
        """Resume the state machine."""
        self._change_state(PostureState.ABSENT)
        self._good_posture_start = 0.0
        self._bad_posture_start = 0.0
        self._l1_alert_time = 0.0
        
    def reset(self) -> None:
        """Reset the state machine."""
        self.resume()
