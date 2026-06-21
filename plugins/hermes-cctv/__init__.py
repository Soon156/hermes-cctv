"""Hermes CCTV Plugin — gateway slash commands for /cctv."""

from pathlib import Path

CCTV_PROJECT = Path.home() / "hermes-cctv"


def register(ctx):
    """Register /cctv slash commands with the gateway."""
    ctx.register_command(
        name="cctv",
        handler=_handle_cctv,
        description="CCTV motion detection control",
        args_hint="install|start|pause|stop|status|snap|restart|update|setup|notify-on|notify-off|notify-status",
    )


def _handle_cctv(raw_args: str) -> str | None:
    """Dispatch /cctv subcommands."""
    sub = raw_args.strip().lower()

    if sub in ("", None):
        return _cctv_status()

    if sub == "install":
        return _cctv_daemon("install")
    elif sub == "start":
        return _cctv_daemon("start")
    elif sub == "pause":
        return _cctv_daemon("pause")
    elif sub == "stop":
        return _cctv_daemon("stop")
    elif sub == "status":
        return _cctv_status()
    elif sub == "snap":
        return _cctv_snap()
    elif sub == "restart":
        return _cctv_restart()
    elif sub == "update":
        return _cctv_update()
    elif sub == "setup":
        return _cctv_setup()
    elif sub in ("notify-off", "notify_on_off", "notify_off"):
        return _cctv_notify("off")
    elif sub in ("notify-on", "notify_on_on", "notify_on"):
        return _cctv_notify("on")
    elif sub in ("notify-status", "notify_status"):
        return _cctv_notify("status")
    else:
        return (
            f"Unknown /cctv subcommand: {sub}\n"
            "Try: install | start | pause | stop | status | snap | restart | update | setup | "
            "notify-on | notify-off | notify-status"
        )


def _cctv_status() -> str:
    """Report the daemon lifecycle state via the hermes-cctv CLI."""
    import subprocess

    ctl = CCTV_PROJECT / "hermes-cctv"
    if not ctl.exists():
        return f"Status failed: hermes-cctv CLI not found at {ctl}"

    try:
        result = subprocess.run(
            ["bash", str(ctl), "status"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as e:
        return f"Status error: {e}"

    out = (result.stdout + result.stderr).strip()
    low = out.lower()
    if "running" in low:
        return "CCTV is **RUNNING** — monitoring for motion."
    if "not running" in low or "not installed" in low:
        return f"CCTV is **STOPPED**.\n```\n{out[-400:]}\n```"
    return f"CCTV status:\n```\n{out[-400:]}\n```"


def _cctv_snap() -> str:
    import subprocess
    import sys

    snap_script = CCTV_PROJECT / "scripts" / "snap.py"
    venv_python = CCTV_PROJECT / "venv" / "bin" / "python3"

    if not snap_script.exists():
        return "Snapshot failed: snap.py not found."
    if not venv_python.exists():
        return "Snapshot failed: venv python not found."

    try:
        result = subprocess.run(
            [str(venv_python), str(snap_script)],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(CCTV_PROJECT),
        )
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            if Path(path).exists():
                return f"MEDIA:{path}"
            return f"Snapshot saved but file not found: {path}"
        return f"Snapshot failed: {result.stderr or 'unknown error'}"
    except subprocess.TimeoutExpired:
        return "Snapshot timed out."
    except Exception as e:
        return f"Snapshot error: {e}"


def _cctv_restart() -> str:
    import subprocess

    ctl_script = CCTV_PROJECT / "scripts" / "daemon-ctl.sh"
    if not ctl_script.exists():
        return "Restart failed: daemon-ctl.sh not found."

    try:
        result = subprocess.run(
            ["bash", str(ctl_script), "restart"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return f"CCTV daemon restarted.\n```\n{result.stdout.strip()[-500:]}\n```"
        return f"Restart failed: {result.stderr or 'unknown error'}"
    except Exception as e:
        return f"Restart error: {e}"


def _cctv_update() -> str:
    import subprocess

    ctl_script = CCTV_PROJECT / "scripts" / "daemon-ctl.sh"
    if not ctl_script.exists():
        return "Update failed: daemon-ctl.sh not found."

    try:
        result = subprocess.run(
            ["bash", str(ctl_script), "update"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return f"CCTV updated and restarted.\n```\n{result.stdout.strip()[-500:]}\n```"
        return f"Update failed: {result.stderr or 'unknown error'}"
    except Exception as e:
        return f"Update error: {e}"


def _cctv_setup() -> str:
    """Pre-flight: detect cameras and read existing config, then trigger chat flow.

    Returns camera info + existing config values so the agent can show
    current settings as defaults when asking each question.
    """
    import subprocess

    detect = CCTV_PROJECT / "scripts" / "detect-cameras.py"
    venv_python = CCTV_PROJECT / "venv" / "bin" / "python3"

    # ── Detect cameras ──
    cameras = ""
    if detect.exists() and venv_python.exists():
        try:
            result = subprocess.run(
                [str(venv_python), str(detect)],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                cameras = result.stdout.strip()
        except Exception:
            pass

    # ── Read existing config ──
    config_file = CCTV_PROJECT / "config.yaml"
    existing = ""
    if config_file.exists():
        try:
            import yaml
            with open(config_file) as f:
                cfg = yaml.safe_load(f) or {}
            lines = []
            if cfg.get("camera"):
                c = cfg["camera"]
                lines.append(f"  Camera: device={c.get('device_id','?')}, {c.get('width','?')}x{c.get('height','?')} @ {c.get('fps','?')}fps")
            if cfg.get("motion"):
                m = cfg["motion"]
                sens = "custom"
                if m.get("threshold") == 50: sens = "low"
                elif m.get("threshold") == 25: sens = "medium"
                elif m.get("threshold") == 10: sens = "high"
                lines.append(f"  Motion: {sens} (threshold={m.get('threshold','?')}, min_area={m.get('min_area','?')})")
            if cfg.get("recording"):
                r = cfg["recording"]
                lines.append(f"  Storage max: {r.get('max_storage_mb','?')}MB")
                lines.append(f"  Clip max: {r.get('max_clip_seconds','?')}s (0=unlimited)")
            existing = "**Current config:**\n```\n" + "\n".join(lines) + "\n```\n"
        except Exception:
            existing = "⚠ Could not read existing config.\n"

    parts = ["Starting interactive CCTV setup...", ""]
    if cameras:
        parts.append("**Detected cameras:**")
        parts.append("```")
        parts.append(cameras)
        parts.append("```")
        parts.append("")
    else:
        parts.append("⚠ No cameras detected automatically.")
        parts.append("")
    parts.append(existing)
    if existing:
        parts.append(
            "Existing config found. Reconfigure all settings, "
            "or just reinstall the integration?"
        )
    else:
        parts.append("Which camera device? [0]")

    return "\n".join(parts)


def _cctv_notify(action: str) -> str:
    """Pause/resume/check the CCTV notification cron job."""
    import subprocess

    try:
        result = subprocess.run(
            ["hermes", "cron", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        return f"Failed to check cron jobs: {e}"

    output = result.stdout
    job_id = None

    for line in output.splitlines():
        if "CCTV Motion Alerts" in line:
            parts = line.split()
            if parts:
                job_id = parts[0]
            break

    if not job_id:
        return "No 'CCTV Motion Alerts' cron job found. Run `/cctv setup` first."

    if action == "status":
        if "paused" in output.lower() or "disabled" in output.lower():
            return "Notifications are **OFF** (paused)."
        return "Notifications are **ON** (enabled)."

    if action == "off":
        try:
            subprocess.run(
                ["hermes", "cron", "pause", job_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "Notifications **paused**. Recording continues silently."
        except Exception as e:
            return f"Failed to pause notifications: {e}"

    if action == "on":
        try:
            subprocess.run(
                ["hermes", "cron", "resume", job_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "Notifications **resumed**. You will receive motion alerts."
        except Exception as e:
            return f"Failed to resume notifications: {e}"

    return f"Unknown notify action: {action}"


def _cctv_daemon(action: str) -> str:
    """Start or stop the CCTV daemon via the hermes-cctv CLI."""
    import subprocess

    ctl = CCTV_PROJECT / "hermes-cctv"
    if not ctl.exists():
        return f"Daemon {action} failed: hermes-cctv CLI not found at {ctl}"

    try:
        result = subprocess.run(
            ["bash", str(ctl), action],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return f"CCTV daemon **{action}ed**.\n```\n{result.stdout.strip()[-500:]}\n```"
        return f"Daemon {action} failed: {result.stderr or result.stdout or 'unknown error'}"
    except subprocess.TimeoutExpired:
        return f"Daemon {action} timed out."
    except Exception as e:
        return f"Daemon {action} error: {e}"
