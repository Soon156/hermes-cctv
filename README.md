# Hermes CCTV

Cross-platform motion-detecting CCTV daemon with [Hermes Agent](https://github.com/NousResearch/hermes-agent) gateway integration. Captures camera input, detects motion, records **H.264 video with AAC audio** via ffmpeg, and sends real-time alerts to Telegram, Discord, or any Hermes-supported messaging platform — with remote control (start / pause / stop / snapshot) from chat.

**macOS · Linux · Windows** — one codebase, zero cloud dependencies.

## How it works

```
┌───────────────────────────────────────────────────┐
│              Hermes Gateway                        │
│  Telegram / Discord / Slack / ...                  │
│                                                    │
│  You: "/cctv start"  → start the daemon            │
│  You: "/cctv pause"  → stop now, resume next boot  │
│  You: "/cctv stop"   → stop + remove auto-start    │
│  You: "/cctv status" → running / stopped           │
│  You: "/cctv snap"   → capture a still image       │
│                                                    │
│  Cron job (every 1m)                               │
│    reads events file → sends alert:                │
│    "Motion detected! Clip: clips/motion_....mp4"   │
└──────────────┬──────────────────▲──────────────────┘
               │ hermes-cctv CLI  │ events file
               ▼                  │
┌──────────────────────────────────────────────────┐
│            Hermes CCTV Daemon                      │
│                                                    │
│  Camera (OpenCV) → Motion Detector → Recorder     │
│                         │           (ffmpeg pipe)  │
│                    writes motion events            │
│                    to ~/.hermes/cctv/events.jsonl  │
│                                                    │
│  Encoding: H.264 video + AAC audio → .mp4         │
│  (plays on iPhone, Android, and all browsers)      │
└──────────────────────────────────────────────────┘
```

## Quick Start

### One-command setup

**Prerequisites:** Python 3.10+, [ffmpeg](https://ffmpeg.org) (for H.264 encoding + audio capture).

```bash
# macOS
brew install ffmpeg

# Linux (Debian/Ubuntu)
sudo apt install ffmpeg

# Linux (Fedora)
sudo dnf install ffmpeg-free
```

Then run the wizard:

```bash
git clone https://github.com/your-username/hermes-cctv.git
cd hermes-cctv
bash setup.sh
```

The wizard walks you through:
- Python environment (venv + dependencies)
- Camera detection and resolution
- Motion sensitivity (low / medium / high / custom)
- Recording directory and clip settings
- Hermes Gateway integration (skill + plugin + cron job for alerts)
- Auto-start on boot (macOS LaunchAgent / Linux systemd / Windows Startup)

Re-running `setup.sh` reads your existing `config.yaml`, shows it, pre-fills each
prompt with the current value (with a suggested range as a hint), and — if a
background service is already registered — asks whether to re-register it.

After setup, start it via the lifecycle CLI:
```bash
./hermes-cctv start
```

### Manual install (skip wizard)

```bash
git clone https://github.com/your-username/hermes-cctv.git
cd hermes-cctv
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### Hermes Gateway (remote control)

Already set up by the wizard. To re-run just the Hermes integration:
```bash
bash setup.sh --hermes-only
```

This installs the gateway plugin + skill (the `/cctv` commands below), the notification script, and the cron job.

### Daemon lifecycle (`hermes-cctv` CLI)

One cross-platform command manages the background service (launchd / systemd / Windows Startup):

| Command | What it does |
|---------|--------------|
| `hermes-cctv install` | Install / re-register the background service (auto-start on login). Idempotent. |
| `hermes-cctv start` | Start the daemon now. If no service is registered, runs **for this boot only**. |
| `hermes-cctv pause` | Stop the daemon now, but keep auto-start → **resumes on next boot**. |
| `hermes-cctv stop` | Stop the daemon now **and** remove auto-start → won't resume on boot. |
| `hermes-cctv restart` | Bounce the daemon (keeps auto-start). |
| `hermes-cctv status` | Report whether it's running / installed / stopped. |

`remove`, `revoke`, and `uninstall` are aliases for `stop`.

### Gateway commands (`/cctv`)

From Telegram / Discord / any Hermes platform — these mirror the CLI:

| Command | What it does |
|---------|--------------|
| `/cctv install` | Install / re-register the background service |
| `/cctv start` | Start the daemon |
| `/cctv pause` | Stop now; resumes on next boot |
| `/cctv stop` | Stop now and remove auto-start |
| `/cctv restart` | Bounce the daemon |
| `/cctv status` | Running / stopped |
| `/cctv snap` | Capture and send a still image |
| `/cctv setup` | Interactive chat-based reconfiguration |
| `/cctv update` | Pull latest and restart |
| `/cctv notify-on` · `notify-off` · `notify-status` | Toggle motion alert delivery |

## Configuration Reference

Any key omitted from `config.yaml` falls back to the default below.

| Key | Default | Description |
|-----|---------|-------------|
| `camera.device_id` | `0` | Camera index |
| `camera.width` | `640` | Frame width |
| `camera.height` | `480` | Frame height |
| `camera.fps` | `15` | Frames per second |
| `motion.threshold` | `30` | Pixel diff threshold (0-255, lower = more sensitive) |
| `motion.min_area` | `2500` | Min contour area in px to count as motion |
| `motion.blur_kernel` | `21` | Gaussian blur size (odd) |
| `motion.dilate_iterations` | `2` | Dilate the diff mask to merge fragmented blobs (0 = off) |
| `motion.confirm_frames` | `3` | Consecutive motion frames required before triggering |
| `recording.output_dir` | `~/hermes-cctv/clips` | Clip save location |
| `recording.pre_motion_buffer` | `2` | Seconds to keep before motion |
| `recording.post_motion_padding` | `15` | Seconds to keep after motion stops |
| `recording.max_clip_seconds` | `300` | Max clip duration (`0` = unlimited) |
| `recording.max_storage_mb` | `500` | Auto-delete oldest clips past this total |
| `recording.codec` | `h264` | Video codec — `h264` (H.264/AVC), `hevc` (H.265/HEVC), `vp9`, `av1` |
| `recording.audio_enabled` | `true` | Capture audio from the camera mic (AAC) |
| `recording.audio_device` | `":1"` | AVFoundation audio device (`:N` = mic index); platform-specific |

### Tuning motion sensitivity

If you get too many false triggers, the most effective knob is **`confirm_frames`** —
requiring motion across several consecutive frames suppresses single-frame sensor
noise and lighting flicker. Raising `min_area` ignores small movements, and raising
`threshold` ignores subtle pixel changes.

### Snapshots

`/cctv snap` warms up the camera (so auto-exposure/gain settle), captures several
frames and takes their median to cancel temporal noise, applies a light denoise pass,
and saves a JPEG — producing a cleaner still than a single cold-grabbed frame.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=hermes_cctv --cov-report=term
```

## License

MIT — see [LICENSE](LICENSE).
