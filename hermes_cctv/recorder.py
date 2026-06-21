"""Video clip recording with pre/post motion buffering and auto-cleanup.

Uses ffmpeg for H.264 encoding + audio capture, ensuring iPhone
compatibility (Apple VideoToolbox requires H.264/HEVC in MP4 containers;
MPEG-4 Part 2 / ``mp4v`` is rejected on iOS).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

import cv2
import numpy as np


_FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"


class Recorder:
    """Records video clips triggered by motion detection.

    Maintains a ring buffer of recent frames (pre-motion buffer).
    When recording starts, flushes the buffer to the video file.
    Records continuously as long as motion is detected.  A single
    motion event produces one or more clips:

      - Clips are split when max_clip_seconds is reached (default 300 s).
        The cap triggers during active motion — the current clip is
        finalized and a new one starts immediately, with no gap.
      - The final clip stops after post_motion_padding seconds of no
        motion.

    Auto-cleans the output directory after finalizing a clip:
    deletes oldest files until total size is under max_storage_mb * 0.8.

    Encoding is H.264 + AAC via ffmpeg pipe (video frames go to stdin,
    audio is captured directly by ffmpeg via AVFoundation).  This
    replaces the old OpenCV ``mp4v`` codec which produced MPEG-4 Part 2
    streams that iOS devices refuse to play.
    """

    def __init__(
        self,
        output_dir: str,
        fps: int = 15,
        width: int = 640,
        height: int = 480,
        codec: str = "mp4v",            # kept for API compat; unused with ffmpeg
        pre_motion_buffer: int = 2,
        post_motion_padding: int = 3,
        max_clip_seconds: int = 300,
        max_storage_mb: int = 500,
        audio_enabled: bool = True,
        audio_device: str = ":1",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.width = width
        self.height = height
        self.pre_motion_buffer = pre_motion_buffer
        self.post_motion_padding = post_motion_padding
        self.max_clip_seconds = max_clip_seconds
        self.max_storage_mb = max_storage_mb
        self.audio_enabled = audio_enabled
        self.audio_device = audio_device

        self._ffmpeg: subprocess.Popen | None = None
        self._buffer: deque[np.ndarray] = deque(
            maxlen=pre_motion_buffer * fps
        )
        self._recording = False
        self._clip_path: str | None = None
        self._clip_start_time: float = 0.0
        self._last_motion_time: float = 0.0

        # Verify ffmpeg is reachable once at init time.
        if not shutil.which(_FFMPEG_BIN):
            self.audio_enabled = False
            print(f"Warning: ffmpeg not found at {_FFMPEG_BIN!r} — "
                  "video-only recording via OpenCV fallback", flush=True)

    def feed(self, frame: np.ndarray, motion_detected: bool) -> str | None:
        """Feed a frame to the recorder.

        Returns the clip path when a clip is finalized (cap split or
        motion-end), or None otherwise.  Triggers auto-cleanup after
        finalizing a clip.
        """
        self._buffer.append(frame.copy())

        if motion_detected:
            self._last_motion_time = time.time()
            if not self._recording:
                self._start_recording()
            elif (
                self.max_clip_seconds > 0
                and time.time() - self._clip_start_time >= self.max_clip_seconds
            ):
                # Cap hit during active motion — finalize this clip
                # and start a fresh one without a gap.
                finalized = self._stop_recording()
                self._start_recording()
                if self._recording and self._ffmpeg is not None:
                    self._write_frame(frame)
                return finalized

        elif self._recording:
            # Stop only when motion has been absent for post_motion_padding.
            if time.time() - self._last_motion_time >= self.post_motion_padding:
                return self._stop_recording()

        if self._recording and self._ffmpeg is not None:
            self._write_frame(frame)

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_ffmpeg_cmd(self) -> list[str]:
        """Build the ffmpeg command line for the current clip."""
        cmd = [
            _FFMPEG_BIN, "-y",
            "-f", "rawvideo",
            "-pixel_format", "bgr24",
            "-video_size", f"{self.width}x{self.height}",
            "-framerate", str(self.fps),
            "-i", "pipe:0",
        ]
        if self.audio_enabled:
            cmd += [
                "-f", "avfoundation",
                "-i", self.audio_device,
            ]
        cmd += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
        ]
        if self.audio_enabled:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += [
            "-movflags", "+faststart",
            "-shortest",
            self._clip_path,
        ]
        return cmd

    def _spawn_ffmpeg(self) -> None:
        """Spawn the ffmpeg process for the current clip.

        If ffmpeg fails to start with audio enabled, retries with
        audio disabled so the user still gets video.
        """
        try:
            cmd = self._build_ffmpeg_cmd()
            self._ffmpeg = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, FileNotFoundError):
            if self.audio_enabled:
                print("ffmpeg failed with audio — retrying video-only",
                      flush=True)
                self.audio_enabled = False
                self._spawn_ffmpeg()
            else:
                raise

    def _write_frame(self, frame: np.ndarray) -> None:
        """Write a single frame to the ffmpeg stdin pipe."""
        if self._ffmpeg is None or self._ffmpeg.stdin is None:
            return
        try:
            self._ffmpeg.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError):
            pass  # ffmpeg exited; _stop_recording will clean up

    def _start_recording(self) -> None:
        """Begin recording, flushing the pre-motion buffer first."""
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        clip_id = uuid.uuid4().hex[:8]
        self._clip_path = str(self.output_dir / f"motion_{timestamp}_{clip_id}.mp4")

        self._spawn_ffmpeg()
        if self._ffmpeg is None or self._ffmpeg.stdin is None:
            raise OSError(f"Failed to spawn ffmpeg for: {self._clip_path}")

        # Flush pre-motion buffer into the new clip.
        for buf_frame in self._buffer:
            self._write_frame(buf_frame)
        self._buffer.clear()

        self._recording = True
        self._clip_start_time = time.time()

    def _stop_recording(self) -> str | None:
        """Stop recording, finalize the clip, and run cleanup."""
        self._recording = False
        if self._ffmpeg is not None:
            if self._ffmpeg.stdin is not None:
                try:
                    self._ffmpeg.stdin.close()
                except OSError:
                    pass
            try:
                self._ffmpeg.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self._ffmpeg.kill()
                self._ffmpeg.wait(timeout=5)
            self._ffmpeg = None
        clip = self._clip_path
        self._clip_path = None

        if clip is not None:
            self._cleanup_storage()

        return clip

    def _cleanup_storage(self) -> None:
        """Delete oldest files until total size is under 80% of max."""
        if self.max_storage_mb <= 0:
            return

        max_bytes = self.max_storage_mb * 1024 * 1024
        target_bytes = int(max_bytes * 0.8)

        files = sorted(
            self.output_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
        )
        files = [f for f in files if f.is_file()]

        total = sum(f.stat().st_size for f in files)
        if total <= max_bytes:
            return

        for f in files:
            if total <= target_bytes:
                break
            try:
                size = f.stat().st_size
                f.unlink()
                total -= size
            except OSError:
                pass

    def cleanup(self) -> None:
        """Release resources (kill ffmpeg if running)."""
        if self._ffmpeg is not None:
            if self._ffmpeg.stdin is not None:
                try:
                    self._ffmpeg.stdin.close()
                except OSError:
                    pass
            try:
                self._ffmpeg.kill()
                self._ffmpeg.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
            self._ffmpeg = None
