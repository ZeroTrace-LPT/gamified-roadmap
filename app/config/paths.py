"""Application-owned paths, with a test/development override."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIRECTORY_NAME = "CybersecurityRoadmap"


def get_data_dir() -> Path:
    """Return the local data directory without relying on a fixed user path."""
    override = os.environ.get("CYBER_ROADMAP_HOME")
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIRECTORY_NAME
    return Path.home() / "AppData" / "Local" / APP_DIRECTORY_NAME


def get_database_path() -> Path:
    """Return the SQLite database path used by the current user."""
    return get_data_dir() / "roadmap.sqlite3"
