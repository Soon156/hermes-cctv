#!/usr/bin/env python3
"""Hermes CCTV — cross-platform motion-detecting camera daemon.

Reads control state from Hermes (on/off), captures camera frames,
detects motion, records clips, and writes events for Hermes notifications.
"""
from __future__ import annotations

import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from .camera import Camera
from .config_loader import load_config
from .control_reader import ControlReader
from .event_writer import EventWriter
from .motion import MotionDetector
from .recorder import Recorder


class CCTVDaemon:
    """Main CCTV daemon that ties camera, motion detection, and recording."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config = load_config(config_path)
        self.running = True
        self.monitoring = True  # Current on/off state
        self._in_motion_event = False  # Suppress duplicate triggers
        self._last_notify_time = 0.0   # Cooldown tracker

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, frame: object) -> None:
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False

    def _save_snapshot(self, frame, snapshot_dir: Path) -> str:
        """Save a JPEG snapshot of *frame* and return the absolute path."""
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        path = str(snapshot_dir / f"snap_{ts}.jpg")
        cv2.imwrite(path, frame)
        return path

    def run(self) -> None:
        """Main daemon loop."""
        camera = Camera(
            device_id=self.config.camera.device_id,
            width=self.config.camera.width,
            height=self.config.camera.height,
            fps=self.config.camera.fps,
        )
        detector = MotionDetector(
            threshold=self.config.motion.threshold,
            min_area=self.config.motion.min_area,
            blur_kernel=self.config.motion.blur_kernel,
            dilate_iterations=self.config.motion.dilate_iterations,
            confirm_frames=self.config.motion.confirm_frames,
        )
        recorder = Recorder(
            output_dir=self.config.recording.output_dir,
            fps=self.config.camera.fps,
            width=self.config.camera.width,
            height=self.config.camera.height,
            codec=self.config.recording.codec,
            pre_motion_buffer=self.config.recording.pre_motion_buffer,
            post_motion_padding=self.config.recording.post_motion_padding,
            max_clip_seconds=self.config.recording.max_clip_seconds,
            max_storage_mb=self.config.recording.max_storage_mb,
            audio_enabled=self.config.recording.audio_enabled,
            audio_device=self.config.recording.audio_device,
        )
        control = ControlReader(self.config.hermes.control_file)
        events = EventWriter(self.config.hermes.events_file)
        snapshot_dir = Path(self.config.recording.snapshot_dir).expanduser()

        print(f"Hermes CCTV starting...")
        print(f"  Camera: device {self.config.camera.device_id}, "
              f"{self.config.camera.width}x{self.config.camera.height} @ {self.config.camera.fps}fps")
        print(f"  Output: {self.config.recording.output_dir}")
        print(f"  Snapshots: {snapshot_dir}")
        print(f"  Max clip: {self.config.recording.max_clip_seconds}s")
        print(f"  Control file: {self.config.hermes.control_file}")
        print(f"  Events file: {self.config.hermes.events_file}")

        try:
            camera.open()
            print("Camera opened. Monitoring for motion...")
            print("(Send /cctv off via gateway to pause, /cctv on to resume)")

            for frame in camera.frames():
                if not self.running:
                    break

                # Check control state from Hermes
                if control.has_changed():
                    self.monitoring = control.state == "on"
                    if self.monitoring:
                        print("Resumed monitoring")
                        detector.reset()
                        self._in_motion_event = False
                        self._last_notify_time = 0.0
                    else:
                        print("Paused monitoring")
                        recorder.cleanup()
                        self._in_motion_event = False
                        self._last_notify_time = 0.0

                if not self.monitoring:
                    time.sleep(0.5)
                    continue

                # Motion detection
                motion = detector.detect(frame)

                # Fire motion_triggered on false→true transition
                if motion and not self._in_motion_event:
                    self._in_motion_event = True
                    # Snapshot saved to disk for reference, no notification sent.
                    # Only the motion_clip (video) event is delivered.
                    try:
                        snapshot_path = self._save_snapshot(frame, snapshot_dir)
                        print(f"Motion triggered — snapshot: {snapshot_path}")
                    except OSError as e:
                        print(f"Warning: snapshot failed: {e}", file=sys.stderr)
                    self._last_notify_time = 0.0  # unused, kept for future re-enable

                # Feed to recorder
                clip_path = recorder.feed(frame, motion)

                if clip_path:
                    if motion:
                        # Cap split — clip finalized but motion continues.
                        # Write the clip event; _in_motion_event stays True.
                        print(f"Clip split (cap): {clip_path}")
                    else:
                        # Motion ended — clip finalized and motion event done.
                        # Write the clip event and allow next trigger.
                        print(f"Motion ended — clip: {clip_path}")
                        self._in_motion_event = False

                    try:
                        events.write_motion_clip(clip_path)
                    except OSError as e:
                        print(f"Warning: failed to write event: {e}", file=sys.stderr)

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            raise
        finally:
            camera.close()
            recorder.cleanup()
            print("CCTV daemon stopped.")


def main() -> None:
    daemon = CCTVDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
