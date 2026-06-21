"""Motion detection via frame differencing."""
from __future__ import annotations

import cv2
import numpy as np


class MotionDetector:
    """Detects motion between consecutive frames using frame differencing.

    Algorithm:
    1. Convert frame to grayscale
    2. Apply Gaussian blur to reduce noise
    3. Compute absolute difference from previous frame
    4. Threshold the difference image
    5. Dilate the mask to merge fragmented blobs
    6. Find contours; if any contour exceeds min_area, the frame is "active"
    7. Report motion only after confirm_frames consecutive active frames

    The dilation and consecutive-frame confirmation suppress single-frame
    sensor noise spikes and lighting flicker, which are the main causes of
    false triggers with raw frame differencing.
    """

    def __init__(
        self,
        threshold: int = 30,
        min_area: int = 2500,
        blur_kernel: int = 21,
        dilate_iterations: int = 2,
        confirm_frames: int = 3,
    ) -> None:
        if blur_kernel % 2 == 0:
            raise ValueError("blur_kernel must be odd")
        self.threshold = threshold
        self.min_area = min_area
        self.blur_kernel = (blur_kernel, blur_kernel)
        self.dilate_iterations = max(0, dilate_iterations)
        self.confirm_frames = max(1, confirm_frames)
        self._prev_gray: np.ndarray | None = None
        self._active_streak = 0
        self._inactive_streak = 0

    def detect(self, frame: np.ndarray) -> bool:
        """Analyze a frame. Returns True once motion is confirmed."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self.blur_kernel, 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return False

        # Frame differencing
        diff = cv2.absdiff(self._prev_gray, gray)
        _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
        if self.dilate_iterations > 0:
            thresh = cv2.dilate(thresh, None, iterations=self.dilate_iterations)
        self._prev_gray = gray

        # Find contours
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Is this frame "active" (any contour large enough)?
        frame_active = any(
            cv2.contourArea(contour) >= self.min_area for contour in contours
        )

        if frame_active:
            self._active_streak += 1
            self._inactive_streak = 0
        else:
            self._inactive_streak += 1
            if self._inactive_streak >= self.confirm_frames:
                self._active_streak = 0

        # Confirm motion only after enough consecutive active frames
        return self._active_streak >= self.confirm_frames

    def reset(self) -> None:
        """Reset internal state (for when camera re-opens)."""
        self._prev_gray = None
        self._active_streak = 0
        self._inactive_streak = 0
