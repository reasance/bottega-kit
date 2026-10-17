"""state.json, the task directory, and the per-task lock (plan §4.2).

Layout: <data>/tasks/<project>/<task-id>/{task.md, state.json, lock, runs/}.
Every write is temp file + rename. The orchestrator owns state.json; agents
only ever write runs/<current>/signal.json through `bottega signal`.
"""

import contextlib
import os
import sys
from pathlib import Path

from . import xdg
from .util import Refused, UsageError, atomic_write_json, now_iso, pid_alive, read_json

SCHEMA_VERSION = 1
PHASES = (
    "new",
    "planning",
    "questions",
    "planned",
    "approved",
    "running",
    "done",
    "stopped",
    "removed",
)
STATE_FILE = "state.json"
TASK_DOC = "task.md"
LOCK_FILE = "lock"
RUNS_DIR = "runs"


def new_state(task, project, title, repo, worktree, branch, base, roles):
    """A fresh state for `bottega new`. `roles` holds per-task overrides only."""
    return {
        "schema_version": SCHEMA_VERSION,
        "task": task,
        "project": project,
        "title": title,
        "repo": str(repo),
        "worktree": str(worktree),
        "branch": branch,
        "base": base,
        "roles": dict(roles),
        "rounds": None,
        "phase": "new",
        "approval": None,
        "round": 0,
        "next_role": None,
        "current_run": None,
        "runs": [],
        "last_signal": None,
        "stopped": None,
        "pr": None,
        "created": now_iso(),
    }


def task_doc(task_dir):
    return Path(task_dir) / TASK_DOC


def run_dir(task_dir, run_name):
    return Path(task_dir) / RUNS_DIR / run_name


def run_name(seq, role):
    return "%03d-%s" % (seq, role)


def load(task_dir):
    path = Path(task_dir) / STATE_FILE
    try:
        state = read_json(path)
    except FileNotFoundError:
        raise Refused("no state.json in %s" % task_dir) from None
    except ValueError as error:
        raise Refused("%s is not valid JSON: %s" % (path, error)) from None
    if state.get("schema_version") != SCHEMA_VERSION:
        raise Refused(
            "%s has schema_version %r; this bottega reads %d"
            % (path, state.get("schema_version"), SCHEMA_VERSION)
        )
    if state.get("phase") not in PHASES:
        raise Refused("%s has an unknown phase %r" % (path, state.get("phase")))
    return state


def save(task_dir, state):
    if state.get("phase") not in PHASES:
        raise ValueError("unknown phase %r" % state.get("phase"))
    atomic_write_json(Path(task_dir) / STATE_FILE, state)


def all_tasks(root=None):
    """[(task_id, task_dir)] for every task on disk, sorted by id."""
    root = Path(root or xdg.tasks_dir())
    found = []
    if not root.is_dir():
        return found
    for project in sorted(root.iterdir()):
        if not project.is_dir():
            continue
        for task_dir in sorted(project.iterdir()):
            if (task_dir / STATE_FILE).is_file():
                found.append((task_dir.name, task_dir))
    found.sort(key=lambda pair: (pair[0], str(pair[1])))
    return found


def resolve(ref, root=None):
    """The task directory for a full id, or a unique prefix or suffix."""
    ref = (ref or "").strip()
    if not ref:
        raise UsageError("a task id is required")
    tasks = all_tasks(root)
    exact = [d for task_id, d in tasks if task_id == ref]
    matches = exact or [
        d for task_id, d in tasks if task_id.startswith(ref) or task_id.endswith(ref)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise UsageError("no task matches %r (see: bottega list)" % ref)
    raise UsageError(
        "%r matches several tasks: %s"
        % (ref, ", ".join(sorted(d.name for d in matches)))
    )


class LockHeld(Refused):
    pass


def _read_pid(path):
    try:
        return int(Path(path).read_text().strip().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def acquire_lock(task_dir, out=None):
    """Create the lock file with O_EXCL and our pid.

    A lock whose pid is no longer running is stale: it is reclaimed with a
    message on `out` (stderr by default). A live holder means LockHeld (exit 2).
    """
    out = out or sys.stderr
    path = Path(task_dir) / LOCK_FILE
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            pid = _read_pid(path)
            if pid is not None and pid_alive(pid):
                raise LockHeld(
                    "task %s is locked by pid %d (another bottega is working on it)"
                    % (Path(task_dir).name, pid)
                ) from None
            print(
                "bottega: reclaimed a stale lock on %s (pid %s is not running)"
                % (Path(task_dir).name, pid if pid is not None else "unknown"),
                file=out,
            )
            with contextlib.suppress(FileNotFoundError):
                os.unlink(str(path))
            continue
        with os.fdopen(fd, "w") as stream:
            stream.write("%d\n" % os.getpid())
        return path
    raise LockHeld("could not take the lock on %s" % Path(task_dir).name)


def release_lock(task_dir):
    path = Path(task_dir) / LOCK_FILE
    if _read_pid(path) == os.getpid():
        with contextlib.suppress(FileNotFoundError):
            os.unlink(str(path))


@contextlib.contextmanager
def locked(task_dir, out=None):
    acquire_lock(task_dir, out)
    try:
        yield
    finally:
        release_lock(task_dir)


def current_role(state):
    """The role of state.current_run, from the runs list."""
    name = state.get("current_run")
    if not name:
        return None
    for entry in state.get("runs") or []:
        if run_name(entry.get("seq", 0), entry.get("role", "")) == name:
            return entry.get("role")
    return None
