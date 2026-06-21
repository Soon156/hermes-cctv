"""Read CCTV control state set by Hermes skill commands."""
from __future__ import annotations

import os
from pathlib import Path


class ControlReader:
    """Reads the control file written by Hermes gateway commands.

    The control file contains a single word: 'on' or 'off'.
    Defaults to 'on' if the file doesn't exist yet.
    """

    def __init__(self, control_file: str) -> None:
        self._path = Path(control_file)
        self._last_state: str | None = None

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> str:
        """Read current control state ('on' or 'off')."""
        self._ensure_dir()
        try:
            state = self._path.read_text().strip().lower()
            if state in ("on", "off"):
                return state
        except (FileNotFoundError, OSError):
            pass
        return "on"  # Default: monitor on startup

    def has_changed(self) -> bool:
        """Return True if state changed since last read."""
        current = self.read()
        if current != self._last_state:
            self._last_state = current
            return True
        return False

    @property
    def state(self) -> str:
        return self._last_state or self.read()
