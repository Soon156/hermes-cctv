"""Write motion events for Hermes notification delivery."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class EventWriter:
    """Appends motion-detected events to a JSONL file.

    Two event types:
      motion_triggered — written immediately when motion is confirmed.
          {"type": "motion_triggered", "timestamp": "…", "snapshot": "/path/to/snap.jpg"}
      motion_clip — written when a recording clip is finalized
          (cap split or motion-end).
          {"type": "motion_clip", "timestamp": "…", "clip": "/path/to/clip.mp4"}

    Timestamps use the machine's local timezone.
    """

    def __init__(self, events_file: str) -> None:
        self._path = Path(events_file)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _local_ts() -> str:
        """Return a human-readable local-time timestamp."""
        return datetime.now().astimezone().strftime("%Y-%m-%d %I:%M:%S %p")

    def write_motion_trigger(
        self, snapshot_path: str = "", timestamp: str | None = None
    ) -> None:
        """Write a motion-triggered event (motion just started)."""
        ts = timestamp or self._local_ts()
        event = {"type": "motion_triggered", "timestamp": ts}
        if snapshot_path:
            event["snapshot"] = snapshot_path
        with open(self._path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def write_motion_clip(
        self, clip_path: str, timestamp: str | None = None
    ) -> None:
        """Write a motion-clip event (recording finalized)."""
        ts = timestamp or self._local_ts()
        event = {
            "type": "motion_clip",
            "timestamp": ts,
            "clip": clip_path,
        }
        with open(self._path, "a") as f:
            f.write(json.dumps(event) + "\n")

    # Backward-compatible alias used by the daemon for clip-finalized events.
    write_motion_event = write_motion_clip
