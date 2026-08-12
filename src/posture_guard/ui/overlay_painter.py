"""Landmark Overlay Renderer.

Draws skeleton, posture metrics, and status text on top of camera frames.
Uses OpenCV for rendering (stays in numpy/BGR land, no Qt needed).
"""

from __future__ import annotations

import cv2
import numpy as np

from posture_guard.data.models import (
    PoseResult,
    PostureStatus,
    PostureIssue,
    CalibrationProfile,
)
from posture_guard.utils.constants import SKELETON_CONNECTIONS, POSTURE_LANDMARKS

# BGR colors
_COLOR_GOOD = (170, 212, 0)    # teal-green
_COLOR_BAD = (107, 107, 255)   # coral-red
_COLOR_NEUTRAL = (200, 200, 200)  # light grey for calibration mode
_COLOR_BG = (30, 30, 30)       # semi-transparent overlay background
_VIS_THRESHOLD = 0.01          # MediaPipe Tasks API: visibility can be near 0, still valid


class OverlayPainter:
    """Renders pose skeleton and posture metrics onto BGR frames."""

    def draw_overlay(
        self,
        frame: np.ndarray,
        pose_result: PoseResult,
        posture_status: PostureStatus | None,
        calibration: CalibrationProfile | None = None,
    ) -> np.ndarray:
        """Draw full overlay: skeleton + metrics + status.

        Safe to call with posture_status=None or calibration=None —
        falls back to neutral rendering in those cases.
        """
        res = frame.copy()
        h, w = res.shape[:2]

        if not pose_result or not pose_result.is_valid:
            return res

        is_good = posture_status.is_good if posture_status else True
        issues = posture_status.issues if posture_status else []
        color = _COLOR_GOOD if is_good else _COLOR_BAD

        self._draw_skeleton(res, pose_result, w, h, color)

        if posture_status and posture_status.metrics:
            self._draw_metrics(res, posture_status)

        # Status banner
        if calibration and calibration.is_valid and posture_status:
            status_text = "POSTURA CORRECTA ✓" if is_good else "MALA POSTURA ✗"
            (tw, _), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            self._draw_text_bg(res, status_text, (w // 2 - tw // 2, 30), color, 0.7)

        return res

    def draw_skeleton_only(
        self,
        frame: np.ndarray,
        pose_result: PoseResult,
    ) -> np.ndarray:
        """Draw just the skeleton in neutral colour (used during calibration before first profile)."""
        res = frame.copy()
        h, w = res.shape[:2]

        if not pose_result or not pose_result.is_valid:
            return res

        self._draw_skeleton(res, pose_result, w, h, _COLOR_NEUTRAL)

        # Calibration hint
        self._draw_text_bg(res, "Posicionándose... mantené buena postura", (10, 30), _COLOR_NEUTRAL, 0.5)

        return res

    # ──────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────

    def _draw_skeleton(
        self,
        frame: np.ndarray,
        pose: PoseResult,
        w: int,
        h: int,
        color: tuple,
    ) -> None:
        """Draw skeleton connections and landmark dots."""
        # Connections
        for idx1, idx2 in SKELETON_CONNECTIONS:
            pt1 = pose.get(idx1)
            pt2 = pose.get(idx2)
            if pt1.visibility > _VIS_THRESHOLD and pt2.visibility > _VIS_THRESHOLD:
                x1, y1 = int(pt1.x * w), int(pt1.y * h)
                x2, y2 = int(pt2.x * w), int(pt2.y * h)
                # Clamp to frame bounds
                if 0 <= x1 < w and 0 <= y1 < h and 0 <= x2 < w and 0 <= y2 < h:
                    cv2.line(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

        # Landmark dots
        for idx in POSTURE_LANDMARKS:
            pt = pose.get(idx)
            if pt.visibility > _VIS_THRESHOLD:
                x, y = int(pt.x * w), int(pt.y * h)
                if 0 <= x < w and 0 <= y < h:
                    cv2.circle(frame, (x, y), 5, color, -1, cv2.LINE_AA)
                    cv2.circle(frame, (x, y), 5, (255, 255, 255), 1, cv2.LINE_AA)

    def _draw_metrics(self, frame: np.ndarray, status: PostureStatus) -> None:
        """Draw posture metric values in the top-left corner."""
        metrics = status.metrics
        head_color = _COLOR_BAD if PostureIssue.FORWARD_HEAD in status.issues else _COLOR_GOOD
        shoulder_color = _COLOR_BAD if PostureIssue.SLOUCH in status.issues else _COLOR_GOOD
        tilt_color = _COLOR_BAD if PostureIssue.LATERAL_TILT in status.issues else _COLOR_GOOD

        self._draw_text_bg(frame, f"Cabeza:   {metrics.head_drop_ratio:.2f}", (10, 30), head_color)
        self._draw_text_bg(frame, f"Hombros:  {metrics.shoulder_width_ratio:.2f}", (10, 58), shoulder_color)
        self._draw_text_bg(frame, f"Inclinac: {metrics.shoulder_tilt_angle:+.1f}°", (10, 86), tilt_color)
    def _draw_text_bg(
        self,
        frame: np.ndarray,
        text: str,
        position: tuple[int, int],
        color: tuple,
        font_scale: float = 0.5,
    ) -> None:
        """Draw text with a semi-transparent dark background for readability."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 1 if font_scale <= 0.6 else 2
        x, y = position
        h_frame, w_frame = frame.shape[:2]

        (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        pad = 4
        x1, y1 = max(0, x - pad), max(0, y - th - pad)
        x2, y2 = min(w_frame - 1, x + tw + pad), min(h_frame - 1, y + baseline + pad)

        # Semi-transparent background
        sub = frame[y1:y2, x1:x2]
        if sub.size > 0:
            bg = np.full_like(sub, _COLOR_BG)
            cv2.addWeighted(bg, 0.6, sub, 0.4, 0, sub)
            frame[y1:y2, x1:x2] = sub

        cv2.putText(frame, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)
