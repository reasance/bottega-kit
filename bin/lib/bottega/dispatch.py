"""One role dispatch, end to end, with its receipt.

render the prompt -> make the run directory -> snapshot the worktree ->
spawn the harness (cwd = worktree, prompt on stdin, own process group) ->
parse -> identity check -> snapshot again -> run.json (+ error.json).

Failure reasons, checked in this order (plan §3, rules 1-3):
  dispatch-failed         could not start, exited non-zero, reported an
                          error, or produced no final message
  timeout                 the profile's timeout passed; the process group
                          was killed
  identity-mismatch       a reported model is neither the requested one nor
                          one of the profile's aliases
  role-modified-worktree  a planner, reviewer or judge moved HEAD or the
                          tracked diff
Nothing is retried and nothing falls back.
"""

import contextlib
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from . import harness as harnesses
from . import prompts, receipts, state, worktree
from .util import BottegaError, bottega_executable, format_duration, now_iso

READ_ONLY_ROLES = ("planner", "reviewer", "judge")
KILL_GRACE = 5


class Outcome:
    def __init__(self, seq, run_name, run_dir, record, final):
        self.seq = seq
        self.run_name = run_name
        self.run_dir = run_dir
        self.record = record
        self.final = final

    @property
    def ok(self):
        return self.record["status"] == "ok"

    @property
    def reason(self):
        return self.record.get("reason")


def line(seq, role, profile_name, model, result, seconds):
    """The one line a dispatch prints (plan §4.7)."""
    return "%03d %s %s %s → %s (%s)" % (
        seq,
        role,
        profile_name,
        model,
        result,
        format_duration(seconds),
    )


def _kill_group(proc):
    """SIGTERM the process group, then SIGKILL whatever is left."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=KILL_GRACE)
    except subprocess.TimeoutExpired:
        pass
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def spawn(invocation, run_dir, timeout):
    """Run the harness. Returns (exit code or None, timed out, spawn error)."""
    events = Path(run_dir) / receipts.EVENTS
    errors = Path(run_dir) / receipts.STDERR
    with (
        open(events, "w", encoding="utf-8") as out,
        open(errors, "w", encoding="utf-8") as err,
    ):
        try:
            proc = subprocess.Popen(
                invocation.argv,
                cwd=invocation.cwd,
                env=invocation.env,
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                text=True,
                start_new_session=True,
            )
        except OSError as error:
            return None, False, "%s could not start: %s" % (invocation.argv[0], error)
        try:
            proc.communicate(invocation.stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            return proc.returncode, True, None
        except BaseException:
            _kill_group(proc)
            raise
        # The harness may leave children behind (a dev server, a test runner);
        # its process group goes with it.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        return proc.returncode, False, None


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _snapshot(path):
    try:
        return worktree.snapshot(path)
    except (BottegaError, OSError):
        return None


def run(st, task_dir, seq, role, profile_name, profile, rounds, test_cmd):
    """Dispatch `role` once and write its receipt. Returns an Outcome.

    A prompt or configuration problem raises before anything is spawned and
    leaves no run directory behind.
    """
    harness = harnesses.get(profile["harness"])
    planned_dir = state.run_dir(task_dir, state.run_name(seq, role))
    template, _ = prompts.load(role)
    values = prompts.values(
        st, task_dir, planned_dir, role, rounds, test_cmd, bottega_executable()
    )
    prompt_text = prompts.render(template, values, "prompt %s" % role)
    run_name, run_dir = receipts.create(task_dir, seq, role)
    receipts.write_prompt(run_dir, prompt_text)
    try:
        invocation = harness.command(
            role,
            profile,
            run_dir / receipts.PROMPT,
            st["worktree"],
            task_dir,
            run_dir,
        )
    except BaseException:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise
    try:
        return _dispatch(
            st, seq, role, profile_name, profile, harness, invocation, run_name, run_dir
        )
    finally:
        for path in invocation.cleanup:
            shutil.rmtree(path, ignore_errors=True)


def _dispatch(st, seq, role, profile_name, profile, harness, invocation, name, run_dir):
    before = _snapshot(st["worktree"])
    started = now_iso()
    clock = time.monotonic()
    timeout = profile.get("timeout")
    rc, timed_out, spawn_error = spawn(invocation, run_dir, timeout)
    duration = time.monotonic() - clock
    finished = now_iso()
    stdout = _read(run_dir / receipts.EVENTS)
    stderr = _read(run_dir / receipts.STDERR)
    parse_error = None
    try:
        parsed = harness.parse(run_dir, stdout, stderr, rc)
    except Exception as error:  # a parser must never crash the orchestrator
        parsed = harnesses.Parsed()
        parse_error = "the %s parser failed: %r" % (harness.name, error)
    if parsed.final is not None and _read(run_dir / receipts.OUTPUT) != parsed.final:
        receipts.write_output(run_dir, parsed.final)
    source, mismatched = harnesses.identity(
        profile["model"], parsed.identity_models, profile.get("aliases")
    )
    after = _snapshot(st["worktree"])
    rails = worktree.rails(before, after) if before and after else None

    failure = None  # (error phase, reason, detail)
    if spawn_error:
        failure = ("spawn", "dispatch-failed", spawn_error)
    elif timed_out:
        failure = ("run", "timeout", "no exit after %s seconds" % timeout)
    elif rc != 0:
        failure = ("run", "dispatch-failed", "%s exited %d" % (harness.binary, rc))
    elif parse_error:
        failure = ("parse", "dispatch-failed", parse_error)
    elif parsed.is_error:
        failure = ("parse", "dispatch-failed", parsed.error_detail)
    elif parsed.final is None:
        failure = ("parse", "dispatch-failed", "no final message")
    elif mismatched:
        failure = (
            "identity",
            "identity-mismatch",
            "requested %s, reported %s" % (profile["model"], ", ".join(mismatched)),
        )
    elif role in READ_ONLY_ROLES and (rails is None or worktree.changed(rails)):
        detail = (
            "the %s changed HEAD or the tracked diff" % role
            if rails
            else "the worktree could not be inspected"
        )
        failure = ("rails", "role-modified-worktree", detail)

    record = {
        "seq": seq,
        "role": role,
        "profile": profile_name,
        "harness": harness.name,
        "requested_model": profile["model"],
        "provider_reported_model": parsed.primary_model,
        "model_identity_source": source,
        "identity_models": parsed.identity_models,
        "observed_models": parsed.models,
        "effort": profile["effort"],
        "argv": invocation.argv,
        "env": {"set": invocation.env_set, "removed": invocation.env_removed},
        "cwd": invocation.cwd,
        "started": started,
        "finished": finished,
        "duration_s": round(duration, 3),
        "exit_code": rc,
        "timeout_s": timeout,
        "usage": parsed.usage,
        "cost_usd": parsed.cost_usd,
        "duration_ms": parsed.duration_ms,
        "num_turns": parsed.num_turns,
        "events": parsed.events,
        "unparsed_lines": parsed.unparsed_lines,
        "signal": None,
        "rails": rails,
        "status": "failed" if failure else "ok",
        "reason": failure[1] if failure else None,
    }
    receipts.write_run(run_dir, record)
    if failure:
        receipts.write_error(run_dir, failure[0], failure[1], rc, stderr, failure[2])
    return Outcome(seq, name, run_dir, record, parsed.final)


def fail(outcome, phase, reason, detail):
    """Turn an ok dispatch into a failed one after the fact (for instance a
    planner whose output is not a plan). The receipt is kept and updated."""
    record = dict(outcome.record, status="failed", reason=reason)
    receipts.write_run(outcome.run_dir, record)
    stderr = _read(outcome.run_dir / receipts.STDERR)
    receipts.write_error(
        outcome.run_dir, phase, reason, record["exit_code"], stderr, detail
    )
    outcome.record = record
    return outcome
