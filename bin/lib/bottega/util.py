"""Small helpers shared by every command: errors, atomic writes, git, time."""

import datetime
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_STOPPED = 3
EXIT_USAGE = 64


class BottegaError(Exception):
    """An expected failure: printed as one line, exits with `code`."""

    code = EXIT_REFUSED

    def __init__(self, message, code=None):
        super().__init__(message)
        if code is not None:
            self.code = code


class Refused(BottegaError):
    code = EXIT_REFUSED


class UsageError(BottegaError):
    code = EXIT_USAGE


def atomic_write(path, text):
    """Write `text` to `path` via a temp file in the same directory + rename.

    A reader sees either the old file or the new one, never a partial write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def atomic_write_json(path, value):
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def slugify(text, limit=40):
    """Lowercase `[a-z0-9-]`, at most `limit` characters, never empty."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = slug[:limit].strip("-")
    return slug or "task"


def now_iso():
    """Local time with its UTC offset, to the second."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def run_git(args, cwd, check=True):
    """Run git in `cwd`; return stdout stripped of the trailing newline.

    With check=True a non-zero exit raises Refused carrying git's stderr.
    With check=False the CompletedProcess is returned instead.
    """
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if not check:
        return proc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise Refused(
            "git {} failed: {}".format(
                " ".join(args), detail[-1] if detail else "exit %d" % proc.returncode
            )
        )
    return proc.stdout.rstrip("\n")


def format_duration(seconds):
    """12s, 2m14s, 1h05m: the duration in a one-line dispatch report."""
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm%02ds" % divmod(seconds, 60)
    hours, rest = divmod(seconds, 3600)
    return "%dh%02dm" % (hours, rest // 60)


def bottega_executable():
    """The absolute path of the running kit's `bottega` (agents call it to signal)."""
    from . import KIT_ROOT

    return str(KIT_ROOT / "bin" / "bottega")


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
