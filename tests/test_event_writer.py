"""Tests for event_writer — JSONL event writing (two event types)."""
from __future__ import annotations

import json
from pathlib import Path

from hermes_cctv.event_writer import EventWriter


class TestEventWriter:
    """Tests for writing motion events to a JSONL file."""

    # -- motion_triggered -------------------------------------------------

    def test_writes_trigger_event(self, tmp_path: Path) -> None:
        events_file = tmp_path / "events.jsonl"
        writer = EventWriter(str(events_file))
        writer.write_motion_trigger(snapshot_path="/tmp/snap.jpg")

        lines = events_file.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["type"] == "motion_triggered"
        assert event["snapshot"] == "/tmp/snap.jpg"
        assert "timestamp" in event

    def test_trigger_without_snapshot(self, tmp_path: Path) -> None:
        events_file = tmp_path / "events.jsonl"
        writer = EventWriter(str(events_file))
        writer.write_motion_trigger()

        event = json.loads(events_file.read_text().strip())
        assert event["type"] == "motion_triggered"
        assert "snapshot" not in event

    # -- motion_clip ------------------------------------------------------

    def test_writes_clip_event(self, tmp_path: Path) -> None:
        events_file = tmp_path / "events.jsonl"
        writer = EventWriter(str(events_file))
        writer.write_motion_clip("/tmp/clip.mp4")

        lines = events_file.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["type"] == "motion_clip"
        assert event["clip"] == "/tmp/clip.mp4"
        assert "timestamp" in event

    # -- backward compat --------------------------------------------------

    def test_write_motion_event_alias(self, tmp_path: Path) -> None:
        """write_motion_event is an alias for write_motion_clip."""
        events_file = tmp_path / "events.jsonl"
        writer = EventWriter(str(events_file))
        writer.write_motion_event("/tmp/clip.mp4")

        event = json.loads(events_file.read_text().strip())
        assert event["type"] == "motion_clip"
        assert event["clip"] == "/tmp/clip.mp4"

    # -- appending --------------------------------------------------------

    def test_appends_mixed_events(self, tmp_path: Path) -> None:
        events_file = tmp_path / "events.jsonl"
        writer = EventWriter(str(events_file))
        writer.write_motion_trigger(snapshot_path="/tmp/s1.jpg")
        writer.write_motion_clip("/tmp/c1.mp4")
        writer.write_motion_trigger(snapshot_path="/tmp/s2.jpg")
        writer.write_motion_clip("/tmp/c2.mp4")

        lines = events_file.read_text().strip().split("\n")
        assert len(lines) == 4

        types = [json.loads(line)["type"] for line in lines]
        assert types == [
            "motion_triggered",
            "motion_clip",
            "motion_triggered",
            "motion_clip",
        ]

    # -- directory creation -----------------------------------------------

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        events_file = tmp_path / "deeply" / "nested" / "events.jsonl"
        writer = EventWriter(str(events_file))
        writer.write_motion_trigger()

        assert events_file.exists()
        assert events_file.parent.exists()

    # -- timestamp format -------------------------------------------------

    def test_timestamps_are_local_time(self, tmp_path: Path) -> None:
        from datetime import datetime

        events_file = tmp_path / "events.jsonl"
        writer = EventWriter(str(events_file))
        writer.write_motion_trigger()
        writer.write_motion_clip("/tmp/clip.mp4")

        for line in events_file.read_text().strip().split("\n"):
            event = json.loads(line)
            ts = event["timestamp"]
            # Local time: "2026-06-23 07:54:29 PM"
            assert " " in ts
            datetime.strptime(ts, "%Y-%m-%d %I:%M:%S %p")
