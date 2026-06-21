"""Tests for recorder — clip buffering, naming, start/stop logic, cap-split."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from hermes_cctv.recorder import Recorder


def _make_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a synthetic BGR frame."""
    return np.zeros((height, width, 3), dtype=np.uint8)


class TestRecorderBuffer:
    """Tests for the pre-motion frame buffer."""

    def test_buffer_maintains_max_size(self, tmp_path: Path) -> None:
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,  # 1 second = 15 frames
            post_motion_padding=5,
        )
        # Feed 30 frames with no motion — buffer should cap at 15
        for _ in range(30):
            recorder.feed(_make_frame(), False)
        assert len(recorder._buffer) == 15

    def test_buffer_flushes_on_recording_start(self, tmp_path: Path) -> None:
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=5,
        )
        # Feed 10 frames
        for _ in range(10):
            recorder.feed(_make_frame(), False)
        assert len(recorder._buffer) == 10

        # Trigger motion — buffer should flush (become empty)
        recorder.feed(_make_frame(), True)
        assert len(recorder._buffer) == 0


class TestRecorderClipNaming:
    """Tests for clip file naming."""

    def test_clip_name_contains_timestamp(self, tmp_path: Path) -> None:
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=3,
        )
        # Trigger recording
        recorder.feed(_make_frame(), True)
        assert recorder._clip_path is not None
        assert "motion_" in recorder._clip_path
        assert recorder._clip_path.endswith(".mp4")

    def test_clip_names_unique_within_same_second(self, tmp_path: Path) -> None:
        """Each clip gets a random id, so back-to-back clips never collide."""
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=0,
        )
        names = set()
        for _ in range(5):
            recorder.feed(_make_frame(), True)   # start
            names.add(recorder._clip_path)
            recorder.feed(_make_frame(), False)  # stop (immediate)
        assert len(names) == 5

    def test_output_dir_created(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "deep" / "clips"
        Recorder(
            output_dir=str(output_dir),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=3,
        )
        assert output_dir.exists()


class TestRecorderState:
    """Tests for recorder state transitions."""

    def test_not_recording_initially(self, tmp_path: Path) -> None:
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=3,
        )
        assert recorder._recording is False

    def test_starts_recording_on_motion(self, tmp_path: Path) -> None:
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=3,
        )
        recorder.feed(_make_frame(), True)
        assert recorder._recording is True

    def test_stops_recording_after_cooldown(self, tmp_path: Path) -> None:
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=0,  # immediate stop
        )
        recorder.feed(_make_frame(), True)  # start recording
        result = recorder.feed(_make_frame(), False)  # motion stopped
        assert recorder._recording is False

    def test_cleanup_releases_writer(self, tmp_path: Path) -> None:
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=3,
        )
        recorder.feed(_make_frame(), True)
        assert recorder._ffmpeg is not None  # ffmpeg is active
        recorder.cleanup()
        assert recorder._ffmpeg is None  # ffmpeg released


class TestRecorderCapSplit:
    """Tests for the max_clip_seconds cap-split behaviour."""

    def test_cap_split_during_active_motion(self, tmp_path: Path) -> None:
        """When max_clip_seconds is hit during active motion, the current
        clip is finalized and a new one starts.  Recording continues."""
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=5,
            max_clip_seconds=10,
        )
        # Start recording the first clip.
        recorder.feed(_make_frame(), True)
        assert recorder._recording is True
        first_clip = recorder._clip_path

        # Backdate the clip start so the next motion frame trips the cap.
        recorder._clip_start_time = time.time() - 11

        # Next motion frame finalizes the first clip and starts a new one.
        result = recorder.feed(_make_frame(), True)
        assert result == first_clip          # the finalized clip path
        assert Path(result).exists()         # it was written to disk
        assert recorder._recording is True   # recording continues
        assert recorder._ffmpeg is not None  # a fresh ffmpeg is active
        assert recorder._clip_path != first_clip   # a fresh, distinct clip
        # The new clip's start time was reset to ~now, so no immediate re-split.
        assert recorder._clip_start_time > time.time() - 1

    def test_no_split_before_cap(self, tmp_path: Path) -> None:
        """No split occurs while the clip is younger than max_clip_seconds."""
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=5,
            max_clip_seconds=10,
        )
        recorder.feed(_make_frame(), True)
        clip = recorder._clip_path
        # Clip is only ~9s old — under the cap, so no split.
        recorder._clip_start_time = time.time() - 9
        result = recorder.feed(_make_frame(), True)
        assert result is None
        assert recorder._clip_path == clip

    def test_cap_disabled_with_zero(self, tmp_path: Path) -> None:
        """max_clip_seconds=0 disables the cap entirely."""
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=3,
            max_clip_seconds=0,
        )
        recorder.feed(_make_frame(), True)
        for _ in range(50):
            result = recorder.feed(_make_frame(), True)
            assert result is None
        assert recorder._recording is True

    def test_clip_start_time_set_on_recording(self, tmp_path: Path) -> None:
        """_clip_start_time is set when recording starts."""
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=5,
            max_clip_seconds=300,
        )
        assert recorder._clip_start_time == 0.0
        recorder.feed(_make_frame(), True)
        assert recorder._clip_start_time > 0.0

    def test_default_max_clip_seconds(self, tmp_path: Path) -> None:
        """Default max_clip_seconds is 300."""
        recorder = Recorder(
            output_dir=str(tmp_path),
            fps=15,
            pre_motion_buffer=1,
            post_motion_padding=3,
        )
        assert recorder.max_clip_seconds == 300
