#!/usr/bin/env python3
"""Capture a single snapshot from the camera and save as JPEG.

Reads the same config.yaml as the daemon for camera settings.
To keep snapshots clean rather than grainy:
  1. Warm up ~2s so auto-exposure / auto-gain settle (high gain = noise).
  2. Capture several frames and take the per-pixel median, which cancels
     random sensor/temporal noise on a static scene.
  3. Apply a light NL-means denoise and write JPEG at quality 90.
Prints the output path so Hermes can attach it to a gateway message.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Snapshot tuning
WARMUP_SECONDS = 2.0   # let auto-exposure / auto-gain settle
MEDIAN_FRAMES = 5      # frames combined via median to cancel temporal noise
JPEG_QUALITY = 90


def main() -> None:
    # Find project root (parent of scripts/)
    project_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_dir))

    from hermes_cctv.config_loader import load_config

    config = load_config(str(project_dir / "config.yaml"))
    cam_cfg = config.camera
    rec_cfg = config.recording

    import cv2
    import numpy as np

    cap = cv2.VideoCapture(cam_cfg.device_id)
    if not cap.isOpened():
        print(f"ERROR: cannot open camera device {cam_cfg.device_id}", file=sys.stderr)
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg.height)

    # Warm up: read frames for ~WARMUP_SECONDS so auto-exposure/auto-gain
    # settle. A camera grabbed cold runs at high gain → grainy frames.
    warmup_deadline = time.time() + WARMUP_SECONDS
    while time.time() < warmup_deadline:
        cap.read()

    # Capture several frames and take the per-pixel median to cancel
    # random temporal (sensor) noise. Median is robust to the odd frame
    # that catches a transient.
    frames = []
    for _ in range(MEDIAN_FRAMES):
        ret, f = cap.read()
        if ret and f is not None:
            frames.append(f)
    cap.release()

    if not frames:
        print("ERROR: failed to capture frame", file=sys.stderr)
        sys.exit(1)

    if len(frames) >= 3:
        frame = np.median(np.stack(frames), axis=0).astype(np.uint8)
    else:
        frame = frames[-1]

    # Light NL-means denoise to smooth residual chroma/luma noise.
    frame = cv2.fastNlMeansDenoisingColored(frame, None, 5, 5, 7, 21)

    output_dir = Path(rec_cfg.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    out_path = output_dir / f"snap_{ts}.jpg"
    cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

    if not out_path.exists():
        print(f"ERROR: failed to write {out_path}", file=sys.stderr)
        sys.exit(1)

    print(str(out_path))


if __name__ == "__main__":
    main()
