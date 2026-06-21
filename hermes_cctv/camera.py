"""Camera capture via OpenCV."""
from __future__ import annotations

import time
from typing import Iterator

import cv2
import numpy as np


class CameraError(Exception):
    """Camera access failure."""


class Camera:
    """Cross-platform camera capture using OpenCV VideoCapture."""

    def __init__(
        self,
        device_id: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 15,
    ) -> None:
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        """Open the camera device."""
        self._cap = cv2.VideoCapture(self.device_id)
        if not self._cap.isOpened():
            raise CameraError(
                f"Cannot open camera device {self.device_id}. "
                "Check that a camera is connected and not in use."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

    def read(self) -> np.ndarray | None:
        """Read a single frame. Returns None if read fails."""
        if self._cap is None:
            raise CameraError("Camera not opened. Call open() first.")
        ret, frame = self._cap.read()
        if not ret:
            return None
        return frame

    def frames(self) -> Iterator[np.ndarray]:
        """Yield frames from the camera as a generator."""
        frame_interval = 1.0 / self.fps
        last_frame_time = 0.0
        while True:
            now = time.time()
            if now - last_frame_time < frame_interval:
                time.sleep(0.001)
                continue
            last_frame_time = now
            frame = self.read()
            if frame is None:
                break
            yield frame

    def close(self) -> None:
        """Release the camera."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> Camera:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
