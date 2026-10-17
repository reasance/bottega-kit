"""The implementer/reviewer loop and the judge (plan §3, the transition table).

After every dispatch, in this order:

  1. the dispatch failed or timed out          -> STOP dispatch-failed | timeout
  2. a reported model is not the requested one -> STOP identity-mismatch
  3. a reviewer or judge moved HEAD or the
     tracked diff                              -> STOP role-modified-worktree
     (dispatch.py decides 1-3; the loop maps them to state.stopped)
  4. implementer -> next is the reviewer. HEAD moved: warning
     `implementer-committed` in run.json and on stderr; continue.
  5. reviewer -> fold signal.json; replace `## Review Findings` with the
     final message; apply --uncheck.
       ready                 -> the judge if one is bound, else DONE
       blocked               -> STOP blocked (the reason is printed)
       needs-work, no signal -> round + 1 > cap ? STOP cap-reached
                                                : round + 1, next implementer
  6. judge -> replace `## Verdict` with the final message.
       ready -> DONE; anything else -> STOP judge-needs-work

A round is one implementer->reviewer pair; round 1 is the first. With cap 3
the third needs-work stops without a fourth implementer pass. state.round
never goes past the cap: the round a resume adds starts when it is granted.

The loop holds the task lock throughout. stdout gets exactly one line per
dispatch; everything else goes to stderr. Nothing is retried, nothing falls
back, no profile is substituted.
"""

import json
import re
import sys
from pathlib import Path

from . import config, dispatch, harness, prompts, receipts, state, taskdoc, worktree
from .util import (
    EXIT_OK,
    EXIT_STOPPED,
    Refused,
    atomic_write,
    bottega_executable,
    now_iso,
    read_json,
)

LOOP_ROLES = ("implementer", "reviewer", "judge")
SIGNALLING = {
    "reviewer": ("ready", "needs-work", "blocked"),
    "judge": ("ready", "needs-work"),
}
STOP_REASONS = (
    "dispatch-failed",
    "timeout",
    "identity-mismatch",
    "role-modified-worktree",
    "blocked",
    "cap-reached",
    "judge-needs-work",
    "interrupted",
)
# After these stops a resume starts a new round with the implementer; after
# any other it re-runs the role that stopped, in the same round.
NEW_ROUND_AFTER = ("cap-reached", "judge-needs-work")
NO_SIGNAL = "no-signal"
IMPLEMENTER_COMMITTED = "implementer-committed"

_HEADING = re.compile(r"^ {0,3}(#{1,2})\s+(.*)$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")


def err(message):
    print(message, file=sys.stderr)


# Checks shared by run and resume (all refuse with exit 2).


def check_plan(task_dir, st):
    """The plan region must still hash to what was approved."""
    approval = st.get("approval") or {}
    if not approval.get("plan_sha256"):
        raise Refused("task %s has no approval; run: bottega approve" % st["task"])
    text = state.task_doc(task_dir).read_text(encoding="utf-8")
    if taskdoc.plan_sha256(text) != approval["plan_sha256"]:
        raise Refused(
            "plan changed since it was approved; run: bottega approve %s" % st["task"]
        )


def check_bindings(cfg, st):
    """Every approved binding the loop dispatches must still work: the profile
    exists and is valid, its harness answers --version, its ${NAME} variables
    are set. Returns {role: profile name} for the loop roles."""
    approved = dict((st.get("approval") or {}).get("roles") or {})
    report = harness.binding_report(cfg, approved)
    problems = [
        problem
        for entry in report
        if entry["role"] in LOOP_ROLES
        for problem in entry["problems"]
    ]
    if problems:
        raise config.ConfigError(
            "the approved role bindings no longer work:\n  "
            + "\n  ".join(problems)
            + "\nfix the configuration, or bind other profiles and approve again"
        )
    return {role: approved[role] for role in LOOP_ROLES if approved.get(role)}


def check_prompts(task_dir, st, roles, test_cmd):
    """Every prompt the loop will send renders, before anything is changed."""
    for role in roles:
        template, path = prompts.load(role)
        values = prompts.values(
            st,
            task_dir,
            Path(task_dir) / state.RUNS_DIR / "check",
            role,
            st.get("rounds") or 1,
            test_cmd,
            bottega_executable(),
        )
        prompts.render(template, values, str(path))


def test_command(st):
    value = worktree.project_config(st["repo"]).get("test_cmd") or ""
    if not isinstance(value, str):
        raise Refused("bottega.json: test_cmd must be a string")
    return value


# Merging a role's final message into task.md.


def section_body(message, title):
    """The final message as the body of section `title`.

    One outer code fence is removed; a leading `## <title>` heading the agent
    wrote is dropped; any other level-1 or level-2 heading becomes level 3,
    so the message can never add or end a section of task.md.
    """
    lines = taskdoc.unwrap(message).split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines:
        match = _HEADING.match(lines[0])
        if match and match.group(2).strip().rstrip("#").strip() == title:
            lines.pop(0)
    out, fenced = [], False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            match = _HEADING.match(line)
            if match:
                line = "### " + match.group(2)
        out.append(line)
    return "\n".join(out).strip("\n")


def write_section(task_dir, title, message, before=None):
    path = state.task_doc(task_dir)
    text = path.read_text(encoding="utf-8")
    body = section_body(message, title)
    atomic_write(path, taskdoc.replace_section(text, title, body, before=before))


def apply_uncheck(task_dir, ids):
    """Untick the ids the reviewer named. Ids no longer in task.md are
    reported, not fatal. Returns the ids actually unticked."""
    if not ids:
        return []
    path = state.task_doc(task_dir)
    text = path.read_text(encoding="utf-8")
    known = set(taskdoc.item_ids(text))
    missing = [i for i in ids if i not in known]
    if missing:
        err("bottega: warning: --uncheck id(s) not in task.md: " + ", ".join(missing))
    present = [i for i in ids if i in known]
    if present:
        atomic_write(path, taskdoc.set_checked(text, present, False))
    return present


def read_signal(run_dir, role, run_name):
    """The signal the agent recorded for this run, or None.

    A file that is not valid JSON, names another run, or carries a status
    the role may not emit counts as no signal (with a warning).
    """
    path = Path(run_dir) / "signal.json"
    if not path.is_file():
        return None
    try:
        record = read_json(path)
    except (OSError, ValueError) as error:
        err("bottega: warning: ignoring unreadable %s: %s" % (path, error))
        return None
    if (
        not isinstance(record, dict)
        or record.get("run") != run_name
        or record.get("status") not in SIGNALLING.get(role, ())
    ):
        err("bottega: warning: ignoring %s: not a valid %s signal" % (path, role))
        return None
    uncheck = record.get("uncheck") or []
    if not isinstance(uncheck, list):
        uncheck = []
    return {
        "status": record["status"],
        "reason": record.get("reason") or "",
        "uncheck": [i for i in uncheck if isinstance(i, str)],
        "by": role,
        "run": run_name,
        "at": record.get("at") or now_iso(),
    }


def implied_signal(role, run_name):
    """No signal from a reviewer or judge counts as needs-work (plan §2.4)."""
    return {
        "status": "needs-work",
        "reason": NO_SIGNAL,
        "uncheck": [],
        "by": role,
        "run": run_name,
        "at": now_iso(),
        "implied": True,
    }


# State transitions.


def _entry(st, run_name):
    for entry in st["runs"]:
        if state.run_name(entry["seq"], entry["role"]) == run_name:
            return entry
    return None


def stop(st, reason, detail, next_role):
    st["phase"] = "stopped"
    st["stopped"] = {"reason": reason, "detail": detail, "at": now_iso()}
    st["next_role"] = next_role
    st["current_run"] = None


def done(st):
    st["phase"] = "done"
    st["stopped"] = None
    st["next_role"] = None
    st["current_run"] = None


def start_run(st):
    """`bottega run`: round 1, the implementer first, the approved cap."""
    st["round"] = 1
    st["rounds"] = st["approval"]["rounds"]
    st["next_role"] = "implementer"
    st["stopped"] = None


def start_resume(st, extra):
    """`bottega resume`: cap = current round + extra; restart at next_role.
    After cap-reached or judge-needs-work the implementer opens a new round."""
    stopped = st.get("stopped") or {}
    if stopped.get("reason") in NEW_ROUND_AFTER:
        st["round"] = st["round"] + 1
        st["next_role"] = "implementer"
        st["rounds"] = st["round"] - 1 + extra
    else:
        st["round"] = max(st.get("round") or 0, 1)
        st["next_role"] = st.get("next_role") or "implementer"
        st["rounds"] = st["round"] + extra
    st["stopped"] = None


def recover_interrupted(task_dir, st):
    """A task left `running` by a bottega that died (we now hold its lock):
    its current run failed as `interrupted` and the task is stopped there."""
    role = state.current_role(st) or st.get("next_role") or "implementer"
    name = st.get("current_run")
    entry = _entry(st, name) if name else None
    if entry and entry.get("status") == "running":
        entry.update(status="failed", reason="interrupted", finished=now_iso())
    stop(st, "interrupted", "the previous bottega process ended mid-run", role)
    state.save(task_dir, st)
    err(
        "bottega: task %s was left running; its run %s counts as interrupted"
        % (st["task"], name or "(none)")
    )


# The loop.


class Loop:
    def __init__(self, task_dir, cfg, roles, test_cmd):
        self.task_dir = Path(task_dir)
        self.cfg = cfg
        self.roles = roles
        self.test_cmd = test_cmd

    def drive(self):
        """Dispatch until DONE or STOP. Returns the exit code."""
        while True:
            st = state.load(self.task_dir)
            role = st["next_role"]
            if role not in LOOP_ROLES:
                raise Refused("task %s has no next role to run" % st["task"])
            st = self.step(st, role)
            if st["phase"] == "done":
                self.report_done(st)
                return EXIT_OK
            if st["phase"] == "stopped":
                self.report_stop(st)
                return EXIT_STOPPED

    def step(self, st, role):
        name = self.roles[role]
        profile = self.cfg["profiles"][name]
        seq = receipts.next_seq(st, self.task_dir)
        run_name = state.run_name(seq, role)
        st["phase"] = "running"
        st["current_run"] = run_name
        st["next_role"] = role
        st["stopped"] = None
        st["runs"].append(
            {
                "seq": seq,
                "role": role,
                "profile": name,
                "round": st["round"],
                "status": "running",
                "started": now_iso(),
            }
        )
        state.save(self.task_dir, st)
        try:
            outcome = dispatch.run(
                st,
                self.task_dir,
                seq,
                role,
                name,
                profile,
                st["rounds"],
                self.test_cmd,
            )
        except BaseException as error:
            self.interrupted(run_name, role, error)
            raise
        st = state.load(self.task_dir)
        result, warnings, signal = self.transition(st, role, outcome)
        entry = _entry(st, run_name)
        entry["status"] = "ok" if outcome.ok else "failed"
        entry["finished"] = now_iso()
        if not outcome.ok:
            entry["reason"] = outcome.reason
        if signal is not None:
            entry["signal"] = signal["status"]
            if signal.get("implied"):
                entry["reason"] = NO_SIGNAL
        state.save(self.task_dir, st)
        record = dict(
            outcome.record,
            round=entry["round"],
            signal=signal,
            warnings=warnings,
        )
        receipts.write_run(outcome.run_dir, record)
        outcome.record = record
        print(
            dispatch.line(
                seq,
                role,
                name,
                profile["model"],
                result,
                outcome.record["duration_s"],
            ),
            flush=True,
        )
        for warning in warnings:
            err("bottega run: warning: %s" % warning)
        new = (outcome.record.get("rails") or {}).get("new_untracked")
        if new:
            err(
                "bottega run: warning: new untracked file(s) in the worktree: "
                + ", ".join(new)
            )
        return st

    def transition(self, st, role, outcome):
        """Apply the transition table to `st` (saved by the caller).
        Returns (word for the dispatch line, warnings, signal or None)."""
        warnings = []
        if not outcome.ok:
            detail = self.error_detail(outcome)
            stop(st, outcome.reason, detail, role)
            return "failed " + outcome.reason, warnings, None
        if role == "implementer":
            rails = outcome.record.get("rails") or {}
            if rails and rails.get("head_before") != rails.get("head_after"):
                warnings.append(
                    "%s: the implementer committed (HEAD %s -> %s)"
                    % (
                        IMPLEMENTER_COMMITTED,
                        (rails.get("head_before") or "?")[:12],
                        (rails.get("head_after") or "?")[:12],
                    )
                )
            st["next_role"] = "reviewer"
            st["current_run"] = None
            return "done", warnings, None

        signal = read_signal(outcome.run_dir, role, outcome.run_name)
        word = signal["status"] if signal else NO_SIGNAL
        if signal is None:
            signal = implied_signal(role, outcome.run_name)
        st["last_signal"] = {k: v for k, v in signal.items() if k != "implied"}
        if signal.get("implied"):
            st["last_signal"]["implied"] = True
        st["current_run"] = None

        if role == "reviewer":
            write_section(
                self.task_dir, taskdoc.FINDINGS, outcome.final, before=taskdoc.VERDICT
            )
            apply_uncheck(self.task_dir, signal["uncheck"])
            status = signal["status"]
            if status == "ready":
                if self.roles.get("judge"):
                    st["next_role"] = "judge"
                else:
                    done(st)
            elif status == "blocked":
                stop(st, "blocked", signal["reason"], "reviewer")
            elif st["round"] + 1 > st["rounds"]:
                stop(
                    st,
                    "cap-reached",
                    "round %d of %d needs work" % (st["round"], st["rounds"]),
                    "implementer",
                )
            else:
                st["round"] += 1
                st["next_role"] = "implementer"
            return word, warnings, signal

        # judge
        write_section(self.task_dir, taskdoc.VERDICT, outcome.final)
        if signal["status"] == "ready":
            done(st)
        else:
            stop(st, "judge-needs-work", signal["reason"], "implementer")
        return word, warnings, signal

    def error_detail(self, outcome):
        try:
            error = read_json(outcome.run_dir / receipts.ERROR)
        except (OSError, ValueError):
            return outcome.reason
        return error.get("detail") or outcome.reason

    def interrupted(self, run_name, role, error):
        """An exception mid-dispatch: the task stops `interrupted`, resumable."""
        st = state.load(self.task_dir)
        if state.run_dir(self.task_dir, run_name).is_dir():
            entry = _entry(st, run_name)
            if entry:
                entry.update(status="failed", reason="interrupted", finished=now_iso())
        else:
            st["runs"] = [
                e for e in st["runs"] if state.run_name(e["seq"], e["role"]) != run_name
            ]
        detail = str(error) or type(error).__name__
        stop(st, "interrupted", detail, role)
        state.save(self.task_dir, st)

    def report_done(self, st):
        judged = " and the judge" if self.roles.get("judge") else ""
        err(
            "bottega run: done: the reviewer%s found it ready in round %d of %d"
            % (judged, st["round"], st["rounds"])
        )
        err(
            "next: read the branch %s, then: bottega pr %s" % (st["branch"], st["task"])
        )

    def report_stop(self, st):
        stopped = st["stopped"]
        reason = stopped["reason"]
        if reason == "blocked":
            err(
                "bottega run: stopped: blocked: %s" % (stopped["detail"] or "no reason")
            )
        else:
            err("bottega run: stopped: %s: %s" % (reason, stopped["detail"] or ""))
        last = st["runs"][-1] if st["runs"] else None
        if last:
            path = state.run_dir(
                self.task_dir, state.run_name(last["seq"], last["role"])
            )
            err("receipt: %s" % path)
        err("findings: %s" % state.task_doc(self.task_dir))
        err(
            "resume with: bottega resume %s [--rounds N] (restarts at the %s)"
            % (st["task"], st["next_role"])
        )


def records(task_dir):
    """Every run.json in the task, by sequence number."""
    found = []
    runs = Path(task_dir) / state.RUNS_DIR
    if not runs.is_dir():
        return found
    for child in sorted(runs.iterdir()):
        path = child / receipts.RUN
        if path.is_file():
            try:
                found.append(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                continue
    found.sort(key=lambda record: record.get("seq", 0))
    return found
