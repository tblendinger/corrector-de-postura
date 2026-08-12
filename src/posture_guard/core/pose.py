"""MediaPipe Pose estimation wrapper — Tasks API (mediapipe >= 1.0).

MediaPipe 1.0 removed the legacy ``solutions`` API. This module uses
the new ``PoseLandmarker`` from ``mediapipe.tasks.python.vision``,
which requires a downloaded ``.task`` model file.

The model is automatically downloaded on first run to
``%APPDATA%/PostureGuard/models/``.
"""

from __future__ import annotations

import logging
import time
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np

from posture_guard.data.models import LandmarkPoint, PoseResult
from posture_guard.utils.constants import (
    APP_DATA_DIR,
    MIN_DETECTION_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Model download configuration
# ──────────────────────────────────────────────
_MODEL_DIR = APP_DATA_DIR / "models"
_MODEL_FILENAME = "pose_landmarker_lite.task"
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)


def _ensure_model() -> Path:
    """Download the PoseLandmarker model if not already present.

    Returns:
        Path to the local model file.

    Raises:
        RuntimeError: If the model cannot be downloaded.
    """
    model_path = _MODEL_DIR / _MODEL_FILENAME
    if model_path.exists():
        return model_path

    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading pose landmarker model (%s)...", _MODEL_FILENAME)
    logger.info("URL: %s", _MODEL_URL)

    try:
        urllib.request.urlretrieve(_MODEL_URL, str(model_path))
        size_mb = model_path.stat().st_size / (1024 * 1024)
        logger.info("Model downloaded successfully (%.1f MB)", size_mb)
    except Exception as exc:
        # Clean up partial download
        if model_path.exists():
            model_path.unlink()
        raise RuntimeError(
            f"Failed to download pose model from {_MODEL_URL}. "
            "Please check your internet connection and try again."
        ) from exc

    return model_path


class PoseEstimator:
    """Estimates human pose using MediaPipe PoseLandmarker (Tasks API).

    Wraps the ``mediapipe.tasks.python.vision.PoseLandmarker`` and
    converts its output into the app-internal ``PoseResult`` model.
    """

    def __init__(
        self,
        model_complexity: int = 1,  # Kept for API compat (not used in Tasks API)
        min_detection_confidence: float = MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = MIN_TRACKING_CONFIDENCE,
    ) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import (
            PoseLandmarker,
            PoseLandmarkerOptions,
            RunningMode,
        )

        model_path = _ensure_model()

        # Read model into memory to avoid Unicode path issues
        # (MediaPipe's C library can't handle non-ASCII paths on Windows)
        with open(model_path, "rb") as f:
            model_data = f.read()

        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=model_data),
            running_mode=RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        self._landmarker = PoseLandmarker.create_from_options(options)
        self._mp = mp
        self._last_timestamp_ms = 0

        logger.info("PoseEstimator initialized (Tasks API, model=%s)", _MODEL_FILENAME)

    def estimate(self, frame: np.ndarray) -> Optional[PoseResult]:
        """Estimate pose from a BGR image frame.

        Args:
            frame: OpenCV BGR image (numpy array).

        Returns:
            PoseResult with 33 landmarks, or None if no person detected.
        """
        try:
            # Convert BGR → RGB
            frame_rgb = frame[:, :, ::-1].copy()

            # Create MediaPipe Image
            mp_image = self._mp.Image(
                image_format=self._mp.ImageFormat.SRGB,
                data=frame_rgb,
            )

            # Ensure monotonically increasing timestamps
            current_ms = int(time.time() * 1000)
            if current_ms <= self._last_timestamp_ms:
                current_ms = self._last_timestamp_ms + 1
            self._last_timestamp_ms = current_ms

            # Run detection
            result = self._landmarker.detect_for_video(mp_image, current_ms)

            # Check if any poses were detected
            if not result.pose_landmarks or len(result.pose_landmarks) == 0:
                return None

            # Convert first detected person's landmarks
            landmarks: list[LandmarkPoint] = []
            for lm in result.pose_landmarks[0]:
                vis = getattr(lm, "visibility", None)
                if vis is None:
                    vis = getattr(lm, "presence", None)
                if vis is None:
                    vis = 1.0
                landmarks.append(LandmarkPoint(
                    x=lm.x,
                    y=lm.y,
                    z=lm.z,
                    visibility=float(vis),
                ))

            return PoseResult(landmarks=landmarks, timestamp=time.time())

        except Exception as exc:
            logger.warning("Pose estimation failed: %s", exc)
            return None

    def close(self) -> None:
        """Release MediaPipe resources."""
        if hasattr(self, "_landmarker") and self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
            self._landmarker = None
            logger.info("PoseEstimator closed")
