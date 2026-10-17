"""Run directories and their receipts (plan §4.2).

runs/NNN-<role>/
  prompt.md      the rendered prompt, as sent on stdin
  output.md      the final message
  events.jsonl   the harness's stdout, raw
  stderr.log     the harness's stderr, raw
  run.json       what ran and how it ended
  error.json     only when the run failed: phase, reason, exit code, stderr tail
  scratch/       writable scratch named in the prompt

Environment values never appear in a receipt, only variable names.
"""

from pathlib import Path

from . import state
from .util import atomic_write, atomic_write_json

PROMPT = "prompt.md"
OUTPUT = "output.md"
EVENTS = "events.jsonl"
STDERR = "stderr.log"
RUN = "run.json"
ERROR = "error.json"
SCRATCH = "scratch"

ERROR_PHASES = ("spawn", "run", "parse", "identity", "rails")
TAIL_LINES = 40


def next_seq(st, task_dir):
    """The next run number: one past every run in the state and on disk."""
    seqs = [entry.get("seq", 0) for entry in st.get("runs") or []]
    runs = Path(task_dir) / state.RUNS_DIR
    if runs.is_dir():
        for child in runs.iterdir():
            head = child.name.split("-", 1)[0]
            if head.isdigit():
                seqs.append(int(head))
    return max(seqs, default=0) + 1


def create(task_dir, seq, role):
    """Make runs/NNN-<role>/ and its scratch/; return (run name, path)."""
    name = state.run_name(seq, role)
    path = state.run_dir(task_dir, name)
    path.mkdir(parents=True)
    (path / SCRATCH).mkdir()
    return name, path


def write_prompt(run_dir, text):
    atomic_write(Path(run_dir) / PROMPT, text)


def write_output(run_dir, text):
    atomic_write(Path(run_dir) / OUTPUT, text)


def tail(text, lines=TAIL_LINES):
    return "\n".join((text or "").rstrip("\n").splitlines()[-lines:])


def write_run(run_dir, record):
    atomic_write_json(Path(run_dir) / RUN, record)


def write_error(run_dir, phase, reason, exit_code, stderr_text, detail=""):
    if phase not in ERROR_PHASES:
        raise ValueError("unknown error phase %r" % phase)
    record = {
        "phase": phase,
        "reason": reason,
        "exit_code": exit_code,
        "stderr_tail": tail(stderr_text),
        "detail": detail,
    }
    atomic_write_json(Path(run_dir) / ERROR, record)
    return record
