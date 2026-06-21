#!/usr/bin/env python3
"""CCTV notification script — reads events file and delivers readable alerts.

Designed to be run by a Hermes cron job (every 1m, no_agent=true).
Output goes to stdout, which Hermes delivers as a notification.

Only delivers motion_clip events (video). Snapshots are saved to disk
but not notified — video alone is sufficient.
"""
import json
from pathlib import Path

EVENTS_FILE = Path.home() / ".hermes" / "cctv" / "events.jsonl"
STATE_FILE = Path.home() / ".hermes" / "cctv" / ".processed_count"


def main() -> None:
    if not EVENTS_FILE.exists():
        return

    lines = EVENTS_FILE.read_text().strip().split("\n")
    if not lines or lines == [""]:
        return

    processed = 0
    if STATE_FILE.exists():
        try:
            processed = int(STATE_FILE.read_text().strip())
        except ValueError:
            processed = 0

    new_events = lines[processed:]
    if not new_events:
        return

    for line in new_events:
        try:
            event = json.loads(line)
            etype = event.get("type", "")

            if etype == "motion_clip":
                clip = event.get("clip", "")
                ts = event.get("timestamp", "")
                if clip:
                    filename = Path(clip).name
                    print(f"📹 {ts} — {filename}")
                    print(f"MEDIA:{clip}")

            # motion_triggered events are silently skipped —
            # snapshots are saved to disk but not notified.

        except json.JSONDecodeError:
            pass

    STATE_FILE.write_text(str(len(lines)))


if __name__ == "__main__":
    main()
