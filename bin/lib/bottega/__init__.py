"""bottega-kit: a planner, an implementer, a reviewer and a judge in a git worktree."""

from pathlib import Path

# bin/lib/bottega/__init__.py -> the kit root (a checkout, or the install dir).
KIT_ROOT = Path(__file__).resolve().parents[3]
