"""Tests for control_reader — state reading, change detection."""
from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cctv.control_reader import ControlReader


class TestControlReader:
    """Tests for the control file reader used by the daemon."""

    def test_reads_on_state(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("on")
        reader = ControlReader(str(control_file))
        assert reader.read() == "on"

    def test_reads_off_state(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("off")
        reader = ControlReader(str(control_file))
        assert reader.read() == "off"

    def test_defaults_to_on_when_file_missing(self, tmp_path: Path) -> None:
        control_file = tmp_path / "nonexistent" / "control"
        reader = ControlReader(str(control_file))
        assert reader.read() == "on"

    def test_defaults_to_on_when_empty(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("")
        reader = ControlReader(str(control_file))
        assert reader.read() == "on"

    def test_defaults_to_on_when_garbage(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("garbage")
        reader = ControlReader(str(control_file))
        assert reader.read() == "on"

    def test_case_insensitive(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("ON")
        reader = ControlReader(str(control_file))
        assert reader.read() == "on"


class TestChangeDetection:
    """has_changed() tracks state transitions."""

    def test_no_change_on_first_read(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("on")
        reader = ControlReader(str(control_file))
        # First read always reports changed (initializes state)
        assert reader.has_changed() is True

    def test_no_change_when_same(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("on")
        reader = ControlReader(str(control_file))
        reader.has_changed()  # initialize
        assert reader.has_changed() is False

    def test_detects_change(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("on")
        reader = ControlReader(str(control_file))
        reader.has_changed()  # initialize: on

        control_file.write_text("off")
        assert reader.has_changed() is True  # changed to off

    def test_detects_change_back(self, tmp_path: Path) -> None:
        control_file = tmp_path / "control"
        control_file.write_text("on")
        reader = ControlReader(str(control_file))
        reader.has_changed()  # initialize: on

        control_file.write_text("off")
        reader.has_changed()  # changed to off

        control_file.write_text("on")
        assert reader.has_changed() is True  # changed back to on
