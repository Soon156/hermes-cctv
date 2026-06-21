---
name: hermes-cctv
description: Control the Hermes CCTV daemon via gateway commands. Provides an interactive chat-based setup flow — triggered by /cctv setup. The agent MUST follow the Chat-Based Interactive Setup flow immediately after the plugin returns camera/config info.
---

# Hermes CCTV Control

This skill handles CCTV commands and interactive chat-based setup.

## Chat-Based Interactive Setup

**IMPORTANT: When the user triggers `/cctv setup`, the plugin returns camera info and current config, then says "Continue with the setup flow from the hermes-cctv skill." You MUST immediately begin the interactive flow below. Load this skill and start at Step 0. Do NOT treat the plugin response as final — it's your cue to take over.**

Use the `clarify` tool for each question. Ask ONE question at a time, wait for the answer, then proceed. Show the current value from the existing config as the default in brackets, like `[0] (currently: 1)`.

### Step 0 — Plugin already asked
The plugin's response already asked: "Existing config found. Reconfigure all settings, or just reinstall?" (or "Which camera device?" if no config exists). Based on the user's answer:

- If they chose "reconfigure" or answered a camera device → **go to Step 1**
- If they chose "just reinstall" or "no" → **skip to Step 6**

### Step 1 — Camera device
The plugin already detected cameras and listed them. Show them and ask:
> Which camera device? [0] (currently: 1)
> Options: Device 0, Device 1

The default is the current config value if it exists, otherwise 0.

### Step 2 — Resolution
> What resolution? [1280x720] (currently: 1920x1080)
> Options: 640x480, 1280x720, 1920x1080, or type custom WxH

The default is the current config value if it exists, otherwise 1280x720.

### Step 3 — Motion sensitivity
> Motion sensitivity? [2] (currently: 3 — High)
> 1 — Low (only large movement)
> 2 — Medium (recommended)
> 3 — High (detects everything)

Map to config:
- 1 → threshold=40, min_area=5000
- 2 → threshold=30, min_area=2500  (default — matches config_loader defaults)
- 3 → threshold=20, min_area=1000

### Step 4 — Storage limit
> Max storage for clips (MB)? [500] (currently: 200)

Oldest clips are auto-deleted when exceeded. The default is the current value if it exists.

### Step 5 — Clip duration before split
> Max seconds per clip before splitting? [300] (currently: 300)
>
> When a single motion event exceeds this cap, the clip is finalized and a new
> one starts immediately (no gap).  Set to 0 to disable splitting entirely.

### Step 6 — Write config
Write the collected (or existing) settings to `~/hermes-cctv/config.yaml`. Use write_file with this format:
```yaml
camera:
  device_id: <chosen>
  width: <w>
  height: <h>
  fps: 15
motion:
  enabled: true
  threshold: <chosen>
  min_area: <chosen>
  blur_kernel: 21
  dilate_iterations: 2
  confirm_frames: 3
recording:
  output_dir: ~/hermes-cctv/clips
  snapshot_dir: ~/hermes-cctv/snapshots
  pre_motion_buffer: 2
  post_motion_padding: 3
  codec: mp4v
  max_clip_seconds: <chosen or 300>
  max_storage_mb: <chosen>
hermes:
  control_file: ~/.hermes/cctv/control
  events_file: ~/.hermes/cctv/events.jsonl
```

### Step 7 — Install Hermes integration
Run these commands (use terminal tool):
```bash
# Install skill
mkdir -p ~/.hermes/skills/hermes-cctv
cp ~/hermes-cctv/skills/hermes-cctv/SKILL.md ~/.hermes/skills/hermes-cctv/SKILL.md

# Install plugin
mkdir -p ~/.hermes/plugins/hermes-cctv
cp ~/hermes-cctv/plugins/hermes-cctv/__init__.py ~/.hermes/plugins/hermes-cctv/__init__.py

# Install notification script
mkdir -p ~/.hermes/scripts
cp ~/hermes-cctv/scripts/cctv-notify.py ~/.hermes/scripts/cctv-notify.py
chmod +x ~/.hermes/scripts/cctv-notify.py

# Create control file
mkdir -p ~/.hermes/cctv
echo "on" > ~/.hermes/cctv/control

# Create cron job (use the cronjob tool, not terminal)
```
Then use the `cronjob` tool:
```
cronjob(action='create', name='CCTV Motion Alerts', schedule='every 1m', script='cctv-notify.py', no_agent=true, deliver='origin', repeat=0)
```

### Step 8 — Done
Tell the user:
> Setup complete! Summary:
> - Camera: Device <X>, <W>x<H>
> - Motion: <Low/Medium/High>
> - Storage: <N>MB max
> - Clip split: every <N>s (or disabled)
> - Notifications: immediate snapshot on motion + video when clip ready (polled every 1m)
> 
> Run `hermes gateway restart` for the new plugin to take effect.
> Then `/cctv start` to begin monitoring.

## Gateway Commands (plugin-backed)

The plugin at `~/.hermes/plugins/hermes-cctv/__init__.py` handles these directly:

### `/cctv install`
Install / re-register the background service via `bash ~/hermes-cctv/hermes-cctv install`.

### `/cctv start`
Start the daemon via `bash ~/hermes-cctv/hermes-cctv start`.

### `/cctv pause`
Stop the daemon now but keep auto-start, via `bash ~/hermes-cctv/hermes-cctv pause`. It resumes on next boot/login.

### `/cctv stop`
Stop the daemon AND remove auto-start, via `bash ~/hermes-cctv/hermes-cctv stop`. It will NOT resume on boot — re-run `/cctv install` (or `/cctv setup`) to bring it back.

### `/cctv status`
Run `bash ~/hermes-cctv/hermes-cctv status` and report whether the daemon is running / installed / stopped.

### `/cctv snap`
Run `~/hermes-cctv/venv/bin/python3 ~/hermes-cctv/scripts/snap.py`, reply with `MEDIA:<path>`.

### `/cctv restart`
Run `bash ~/hermes-cctv/scripts/daemon-ctl.sh restart`.

### `/cctv update`
Run `bash ~/hermes-cctv/scripts/daemon-ctl.sh update`.

### `/cctv setup`
The plugin returns a prompt that triggers this skill's interactive chat-based setup flow (above). Follow the Chat-Based Interactive Setup section step-by-step.

### `/cctv notify-off`
Pause the "CCTV Motion Alerts" cron job. Use the `cronjob` tool: `cronjob(action='pause', job_id='<id>')`.

### `/cctv notify-on`
Resume the "CCTV Motion Alerts" cron job: `cronjob(action='resume', job_id='<id>')`.

### `/cctv notify-status`
List cron jobs and check if "CCTV Motion Alerts" is enabled or paused.
