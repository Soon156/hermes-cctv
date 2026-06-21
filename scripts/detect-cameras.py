#!/usr/bin/env python3
"""Camera detection helper — lists available cameras with per-device timeout."""
import sys
import threading
from typing import Optional, Tuple


TIMEOUT = 2  # seconds per device


def probe(device_id: int) -> Optional[Tuple[int, int]]:
    """Try to open a camera device. Returns (width, height) or None."""
    import cv2

    cap = cv2.VideoCapture(device_id)
    try:
        if not cap.isOpened():
            return None
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if w <= 0 or h <= 0:
            return None
        return (w, h)
    except Exception:
        return None
    finally:
        cap.release()


def main() -> None:
    found: list[Tuple[int, int, int]] = []

    for i in range(4):
        result: list[Optional[Tuple[int, int]]] = [None]
        done = threading.Event()

        def worker(dev: int = i) -> None:
            result[0] = probe(dev)
            done.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        done.wait(timeout=TIMEOUT)

        if result[0] is not None:
            w, h = result[0]
            found.append((i, w, h))
            print(f"    Device {i}: {w}x{h}")
        # Non-existent devices timeout silently

    if not found:
        print("NONE")
        sys.exit(1)


if __name__ == "__main__":
    main()
