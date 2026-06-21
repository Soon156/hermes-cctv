"""Tests for config_loader — YAML loading, defaults, path expansion."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hermes_cctv.config_loader import Config, CameraConfig, load_config


class TestDefaults:
    """Config returns sensible defaults when no file exists."""

    def test_loads_defaults_with_no_file(self) -> None:
        config = load_config("/nonexistent/path/config.yaml")
        assert config.camera.device_id == 0
        assert config.camera.width == 640
        assert config.camera.height == 480
        assert config.camera.fps == 15
        assert config.motion.threshold == 30
        assert config.motion.min_area == 2500
        assert config.motion.blur_kernel == 21
        assert config.motion.dilate_iterations == 2
        assert config.motion.confirm_frames == 3
        assert config.recording.pre_motion_buffer == 2
        assert config.recording.post_motion_padding == 15
        assert config.recording.codec == "h264"
        assert config.recording.max_clip_seconds == 300
        assert config.recording.snapshot_dir.endswith("snapshots")

    def test_default_config_is_usable(self) -> None:
        config = Config()
        assert isinstance(config.camera, CameraConfig)
        assert config.camera.device_id == 0


class TestPathExpansion:
    """Tilde paths are expanded to absolute paths."""

    def test_expands_output_dir(self, tmp_path: Path) -> None:
        yaml_content = f"recording:\n  output_dir: {tmp_path}/clips\n"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        config = load_config(str(config_file))
        assert config.recording.output_dir == str(tmp_path / "clips")

    def test_expands_hermes_paths(self, tmp_path: Path) -> None:
        yaml_content = (
            f"hermes:\n"
            f"  control_file: {tmp_path}/control\n"
            f"  events_file: {tmp_path}/events.jsonl\n"
        )
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        config = load_config(str(config_file))
        assert config.hermes.control_file == str(tmp_path / "control")
        assert config.hermes.events_file == str(tmp_path / "events.jsonl")


class TestPartialConfig:
    """Missing keys fall back to defaults."""

    def test_partial_camera_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("camera:\n  device_id: 2\n")

        config = load_config(str(config_file))
        assert config.camera.device_id == 2
        # Other camera values stay at defaults
        assert config.camera.width == 640
        assert config.camera.fps == 15

    def test_partial_motion_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("motion:\n  threshold: 50\n")

        config = load_config(str(config_file))
        assert config.motion.threshold == 50
        assert config.motion.min_area == 2500  # default

    def test_empty_yaml_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        config = load_config(str(config_file))
        assert config.camera.device_id == 0
