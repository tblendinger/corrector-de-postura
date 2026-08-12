"""Mathematical utility functions for angle and distance calculations.

Provides geometric computations for posture analysis and a
moving-average smoother for reducing landmark jitter.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Sequence


def midpoint(
    a: tuple[float, float],
    b: tuple[float, float],
) -> tuple[float, float]:
    """Calculate the midpoint between two 2D points."""
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def midpoint_3d(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Calculate the midpoint between two 3D points."""
    return (
        (a[0] + b[0]) / 2.0,
        (a[1] + b[1]) / 2.0,
        (a[2] + b[2]) / 2.0,
    )


def euclidean_distance(
    a: tuple[float, ...],
    b: tuple[float, ...],
) -> float:
    """Calculate euclidean distance between two points of any dimension."""
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


def calculate_angle(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    """Calculate the angle at point b formed by points a-b-c.

    Returns:
        Angle in degrees [0, 180].
    """
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])

    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2)
    mag_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2)

    if mag_ba * mag_bc == 0:
        return 0.0

    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def angle_from_horizontal(
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Calculate the angle of line a→b relative to horizontal.

    Returns:
        Angle in degrees, positive if b is below a.
        Range: [-180, 180].
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return math.degrees(math.atan2(dy, dx))


def angle_from_vertical(
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Calculate the angle of line a→b relative to vertical (straight down).

    Returns:
        Angle in degrees. 0 means perfectly vertical.
        Range: [-180, 180].
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    # Vertical is 90° in standard math coords
    return math.degrees(math.atan2(dx, dy))


def normalize_angle(angle: float) -> float:
    """Normalize an angle to the range [-180, 180]."""
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


class MovingAverage:
    """Simple moving average filter for signal smoothing.

    Used to reduce jitter in MediaPipe landmark positions
    and computed posture metrics.
    """

    def __init__(self, window_size: int = 5) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._window_size = window_size

    def update(self, value: float) -> float:
        """Add a new value and return the updated average."""
        self._window.append(value)
        return self.average

    @property
    def average(self) -> float:
        """Current moving average value."""
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    @property
    def is_full(self) -> bool:
        """Whether the window has enough samples for a stable average."""
        return len(self._window) >= self._window_size

    def reset(self) -> None:
        """Clear all values from the window."""
        self._window.clear()


class MetricsSmoother:
    """Smooths multiple posture metrics simultaneously.

    Manages a MovingAverage for each metric key, keeping them
    in sync and providing a convenient interface.
    """

    def __init__(self, keys: Sequence[str], window_size: int = 5) -> None:
        self._smoothers: dict[str, MovingAverage] = {
            key: MovingAverage(window_size) for key in keys
        }

    def update(self, values: dict[str, float]) -> dict[str, float]:
        """Update all metrics and return smoothed values."""
        result = {}
        for key, smoother in self._smoothers.items():
            if key in values:
                result[key] = smoother.update(values[key])
            else:
                result[key] = smoother.average
        return result

    def reset(self) -> None:
        """Reset all smoothers."""
        for smoother in self._smoothers.values():
            smoother.reset()

    @property
    def is_stable(self) -> bool:
        """Whether all smoothers have full windows."""
        return all(s.is_full for s in self._smoothers.values())
