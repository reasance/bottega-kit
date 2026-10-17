"""Where bottega-kit keeps its configuration and its task data."""

import os
from pathlib import Path

APP = "bottega-kit"


def _base(variable, default):
    value = os.environ.get(variable, "")
    # The XDG spec says relative values are invalid and must be ignored.
    if value and os.path.isabs(value):
        return Path(value)
    return Path.home() / default


def config_dir():
    return _base("XDG_CONFIG_HOME", ".config") / APP


def config_file():
    return config_dir() / "config.json"


def prompts_override_dir():
    return config_dir() / "prompts"


def data_dir():
    """BOTTEGA_DATA_HOME wins, so the runtime and install.sh agree on one root."""
    explicit = os.environ.get("BOTTEGA_DATA_HOME", "")
    if explicit and os.path.isabs(explicit):
        return Path(explicit)
    return _base("XDG_DATA_HOME", ".local/share") / APP


def tasks_dir():
    return data_dir() / "tasks"
