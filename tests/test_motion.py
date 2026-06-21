"""Tests for motion detector — frame differencing logic."""
from __future__ import annotations

import numpy as np
import pytest

from hermes_cctv.motion import MotionDetector


def _make_frame(width: int = 640, height: int = 480, value: int = 0) -> np.ndarray:
    """Create a synthetic BGR frame filled with a single value."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = value
    return frame


class TestMotionDetector:
    """Tests for the frame-differencing motion detector."""

    def test_no_motion_on_first_frame(self) -> None:
        detector = MotionDetector(threshold=25, min_area=500, blur_kernel=21)
        frame = _make_frame(value=100)
        assert detector.detect(frame) is False  # first frame initializes

    def test_no_motion_on_identical_frames(self) -> None:
        detector = MotionDetector(threshold=25, min_area=500, blur_kernel=21)
        frame = _make_frame(value=100)
        detector.detect(frame)  # initialize
        assert detector.detect(frame) is False  # same frame

    def test_detects_motion_with_large_change(self) -> None:
        detector = MotionDetector(
            threshold=10, min_area=100, blur_kernel=21, confirm_frames=1
        )
        frame1 = _make_frame(value=0)
        frame2 = _make_frame(value=200)  # big change
        detector.detect(frame1)  # initialize
        assert detector.detect(frame2) is True

    def test_no_motion_with_small_change_below_threshold(self) -> None:
        detector = MotionDetector(threshold=50, min_area=500, blur_kernel=21)
        frame1 = _make_frame(value=100)
        frame2 = _make_frame(value=105)  # tiny change, below threshold
        detector.detect(frame1)
        assert detector.detect(frame2) is False

    def test_detects_motion_with_region_change(self) -> None:
        detector = MotionDetector(
            threshold=25, min_area=100, blur_kernel=21, confirm_frames=1
        )
        frame1 = _make_frame(value=50)
        detector.detect(frame1)

        # Change a large region
        frame2 = frame1.copy()
        frame2[100:300, 100:300] = 200  # 200x200 pixel block changed
        assert detector.detect(frame2) is True

    def test_ignores_tiny_region_below_min_area(self) -> None:
        detector = MotionDetector(
            threshold=25, min_area=5000, blur_kernel=21, confirm_frames=1
        )
        frame1 = _make_frame(value=50)
        detector.detect(frame1)

        # Change a tiny region (10x10 = 100px, well below min_area=5000)
        frame2 = frame1.copy()
        frame2[100:110, 100:110] = 200
        assert detector.detect(frame2) is False

    def test_requires_consecutive_frames_before_confirming(self) -> None:
        # confirm_frames=3 — a single active frame must NOT trigger
        detector = MotionDetector(
            threshold=25, min_area=100, blur_kernel=21, confirm_frames=3
        )
        base = _make_frame(value=50)
        moved = base.copy()
        moved[100:300, 100:300] = 200

        detector.detect(base)  # initialize

        # Alternating frames keep producing diffs, building the streak.
        assert detector.detect(moved) is False  # streak 1
        assert detector.detect(base) is False   # streak 2 (reverse change)
        assert detector.detect(moved) is True    # streak 3 -> confirmed

    def test_single_frame_spike_does_not_trigger(self) -> None:
        # One noisy frame surrounded by stillness should be ignored.
        detector = MotionDetector(
            threshold=25, min_area=100, blur_kernel=21, confirm_frames=3
        )
        still = _make_frame(value=50)
        spike = still.copy()
        spike[100:300, 100:300] = 200

        detector.detect(still)        # initialize
        assert detector.detect(spike) is False  # streak 1
        assert detector.detect(still) is False  # back to still — diff again, streak 2
        assert detector.detect(still) is False  # identical — no diff, streak resets

    def test_reset_clears_state(self) -> None:
        detector = MotionDetector(
            threshold=25, min_area=100, blur_kernel=21, confirm_frames=1
        )
        frame = _make_frame(value=100)
        detector.detect(frame)
        detector.reset()

        # After reset, next frame should be initialization again
        frame2 = _make_frame(value=200)
        assert detector.detect(frame2) is False  # first frame after reset

    def test_rejects_even_blur_kernel(self) -> None:
        with pytest.raises(ValueError, match="blur_kernel must be odd"):
            MotionDetector(blur_kernel=20)

    def test_accepts_odd_blur_kernel(self) -> None:
        detector = MotionDetector(blur_kernel=21)
        assert detector.blur_kernel == (21, 21)
