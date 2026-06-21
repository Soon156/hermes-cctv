"""Load and validate CCTV configuration from YAML."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CameraConfig:
    device_id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 15


@dataclass
class MotionConfig:
    enabled: bool = True
    threshold: int = 30
    min_area: int = 2500
    blur_kernel: int = 21
    dilate_iterations: int = 2
    confirm_frames: int = 3
    notify_cooldown_seconds: int = 30  # min gap between trigger notifications


@dataclass
class RecordingConfig:
    output_dir: str = "~/hermes-cctv/clips"
    snapshot_dir: str = "~/hermes-cctv/snapshots"
    pre_motion_buffer: int = 2
    post_motion_padding: int = 15  # seconds of no-motion before finalizing clip
    codec: str = "h264"            # h264 (H.264/AVC), hevc (H.265/HEVC), vp9, av1
    max_clip_seconds: int = 300
    max_storage_mb: int = 500
    audio_enabled: bool = True
    audio_device: str = ":1"       # AVFoundation index (":mic_idx") or name


@dataclass
class HermesConfig:
    control_file: str = "~/.hermes/cctv/control"
    events_file: str = "~/.hermes/cctv/events.jsonl"


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    hermes: HermesConfig = field(default_factory=HermesConfig)


def _expand_path(path: str) -> str:
    """Expand ~ to user home directory."""
    return str(Path(path).expanduser())


def load_config(path: str = "config.yaml") -> Config:
    """Load configuration from a YAML file, applying defaults for missing keys."""
    config = Config()
    if not os.path.exists(path):
        return config

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    if "camera" in raw:
        c = raw["camera"]
        config.camera = CameraConfig(
            device_id=c.get("device_id", 0),
            width=c.get("width", 640),
            height=c.get("height", 480),
            fps=c.get("fps", 15),
        )
    if "motion" in raw:
        m = raw["motion"]
        config.motion = MotionConfig(
            enabled=m.get("enabled", True),
            threshold=m.get("threshold", 30),
            min_area=m.get("min_area", 2500),
            blur_kernel=m.get("blur_kernel", 21),
            dilate_iterations=m.get("dilate_iterations", 2),
            confirm_frames=m.get("confirm_frames", 3),
            notify_cooldown_seconds=m.get("notify_cooldown_seconds", 30),
        )
    if "recording" in raw:
        r = raw["recording"] or {}
        config.recording = RecordingConfig(
            output_dir=_expand_path(r.get("output_dir", "~/hermes-cctv/clips")),
            snapshot_dir=_expand_path(r.get("snapshot_dir", "~/hermes-cctv/snapshots")),
            pre_motion_buffer=r.get("pre_motion_buffer", 2),
            post_motion_padding=r.get("post_motion_padding", 15),
            codec=r.get("codec", "h264"),
            max_clip_seconds=r.get("max_clip_seconds", 300),
            max_storage_mb=r.get("max_storage_mb", 500),
            audio_enabled=r.get("audio_enabled", True),
            audio_device=r.get("audio_device", ":1"),
        )
    if "hermes" in raw:
        h = raw["hermes"] or {}
        config.hermes = HermesConfig(
            control_file=_expand_path(h.get("control_file", "~/.hermes/cctv/control")),
            events_file=_expand_path(h.get("events_file", "~/.hermes/cctv/events.jsonl")),
        )

    return config
