"""Codex (`codex exec`): argv and environment, and the JSONL parser.

The final message is the file `-o <run_dir>/output.md` names. Usage comes
from the last `turn.completed`. Event names on a given Codex version are a
live-probe unknown, so unknown events are counted and kept, never fatal.

Identity: the names that say which model ran the session or the turn, the
top-level `model` and `response.model` of any event (as delegation-kit's
driver reads them), and the `session`, `payload` or `msg` model of a
session or turn event. A model named anywhere else is observed only.
"""

import re
from pathlib import Path

from ..util import bottega_executable
from . import Harness, Invocation, Parsed, base_env, matrix_argv, read_events

FAILED_EVENTS = ("turn.failed",)


NESTED = ("session", "payload", "msg")
SESSION_OR_TURN = re.compile(r"^(thread|turn|session)([._]|$)|_configured$|^turn_")


def _is_session_or_turn(event):
    kinds = [event.get("type")]
    for key in NESTED:
        inner = event.get(key)
        if isinstance(inner, dict):
            kinds.append(inner.get("type"))
    return any(isinstance(k, str) and SESSION_OR_TURN.search(k) for k in kinds)


def _models_in(event):
    """[(name, counts for identity)] for every model the event names."""
    found = [(event.get("model"), True)]
    response = event.get("response")
    if isinstance(response, dict):
        found.append((response.get("model"), True))
    session_or_turn = _is_session_or_turn(event)
    for key in NESTED:
        inner = event.get(key)
        if isinstance(inner, dict):
            found.append((inner.get("model"), session_or_turn))
    return found


class CodexHarness(Harness):
    name = "codex"

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        values = {
            "model": profile["model"],
            "effort": profile["effort"],
            "task_dir": str(task_dir),
            "run_dir": str(run_dir),
            "worktree": str(worktree),
            "bottega": bottega_executable(),
        }
        argv = matrix_argv(self.name, role, values)
        env, env_set = base_env(profile)
        stdin = Path(prompt_path).read_text(encoding="utf-8")
        return Invocation(argv, env, stdin, worktree, env_set)

    def parse(self, run_dir, stdout, stderr, rc):
        parsed = Parsed()
        events, parsed.unparsed_lines = read_events(stdout)
        parsed.events = len(events)
        for event in events:
            for name, identity in _models_in(event):
                parsed.saw_model(name, identity)
            kind = event.get("type")
            if kind == "turn.completed" and isinstance(event.get("usage"), dict):
                parsed.usage = event["usage"]
            elif kind in FAILED_EVENTS:
                parsed.is_error = True
                error = event.get("error")
                message = error.get("message") if isinstance(error, dict) else error
                parsed.error_detail = "%s: %s" % (kind, message or "no detail")
        parsed.primary_model = (
            parsed.identity_models[0] if parsed.identity_models else None
        )
        output = Path(run_dir) / "output.md"
        try:
            final = output.read_text(encoding="utf-8")
        except OSError:
            final = None
        if final is not None and final.strip():
            parsed.final = final
        return parsed
