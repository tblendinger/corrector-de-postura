"""Tests for angle calculation utilities."""

import math
import pytest
from posture_guard.utils.angles import (
    midpoint,
    midpoint_3d,
    euclidean_distance,
    calculate_angle,
    angle_from_horizontal,
    angle_from_vertical,
    normalize_angle,
    MovingAverage,
    MetricsSmoother,
)


class TestMidpoint:
    def test_midpoint_basic(self):
        assert midpoint((0, 0), (2, 2)) == (1.0, 1.0)

    def test_midpoint_negative(self):
        assert midpoint((-1, -1), (1, 1)) == (0.0, 0.0)

    def test_midpoint_same_point(self):
        assert midpoint((5, 5), (5, 5)) == (5.0, 5.0)


class TestMidpoint3D:
    def test_midpoint_3d_basic(self):
        assert midpoint_3d((0, 0, 0), (2, 2, 2)) == (1.0, 1.0, 1.0)


class TestEuclideanDistance:
    def test_zero_distance(self):
        assert euclidean_distance((0, 0), (0, 0)) == 0.0

    def test_unit_distance(self):
        assert euclidean_distance((0, 0), (1, 0)) == 1.0

    def test_diagonal(self):
        assert euclidean_distance((0, 0), (3, 4)) == pytest.approx(5.0)


class TestCalculateAngle:
    def test_right_angle(self):
        angle = calculate_angle((1, 0), (0, 0), (0, 1))
        assert angle == pytest.approx(90.0, abs=0.1)

    def test_straight_line(self):
        angle = calculate_angle((-1, 0), (0, 0), (1, 0))
        assert angle == pytest.approx(180.0, abs=0.1)

    def test_zero_length_returns_zero(self):
        angle = calculate_angle((0, 0), (0, 0), (1, 1))
        assert angle == 0.0


class TestAngleFromHorizontal:
    def test_horizontal_right(self):
        angle = angle_from_horizontal((0, 0), (1, 0))
        assert angle == pytest.approx(0.0, abs=0.1)

    def test_vertical_down(self):
        angle = angle_from_horizontal((0, 0), (0, 1))
        assert angle == pytest.approx(90.0, abs=0.1)

    def test_diagonal_45(self):
        angle = angle_from_horizontal((0, 0), (1, 1))
        assert angle == pytest.approx(45.0, abs=0.1)


class TestAngleFromVertical:
    def test_vertical_down(self):
        angle = angle_from_vertical((0, 0), (0, 1))
        assert angle == pytest.approx(0.0, abs=0.1)


class TestNormalizeAngle:
    def test_within_range(self):
        assert normalize_angle(45) == 45

    def test_over_180(self):
        assert normalize_angle(270) == -90

    def test_under_minus_180(self):
        assert normalize_angle(-270) == 90


class TestMovingAverage:
    def test_single_value(self):
        ma = MovingAverage(3)
        result = ma.update(10.0)
        assert result == 10.0

    def test_average_computation(self):
        ma = MovingAverage(3)
        ma.update(1.0)
        ma.update(2.0)
        result = ma.update(3.0)
        assert result == pytest.approx(2.0)

    def test_window_sliding(self):
        ma = MovingAverage(2)
        ma.update(1.0)
        ma.update(2.0)
        result = ma.update(4.0)  # window now has [2.0, 4.0]
        assert result == pytest.approx(3.0)

    def test_is_full(self):
        ma = MovingAverage(3)
        assert ma.is_full is False
        ma.update(1)
        ma.update(2)
        assert ma.is_full is False
        ma.update(3)
        assert ma.is_full is True

    def test_reset(self):
        ma = MovingAverage(3)
        ma.update(100)
        ma.reset()
        assert ma.average == 0.0
        assert ma.is_full is False


class TestMetricsSmoother:
    def test_smoothing(self):
        smoother = MetricsSmoother(["a", "b"], window_size=2)
        smoother.update({"a": 1.0, "b": 10.0})
        result = smoother.update({"a": 3.0, "b": 20.0})
        assert result["a"] == pytest.approx(2.0)
        assert result["b"] == pytest.approx(15.0)

    def test_is_stable(self):
        smoother = MetricsSmoother(["x"], window_size=2)
        assert smoother.is_stable is False
        smoother.update({"x": 1.0})
        assert smoother.is_stable is False
        smoother.update({"x": 2.0})
        assert smoother.is_stable is True
