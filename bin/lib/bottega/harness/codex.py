"""Codex (`codex exec`): argv and environment, and the JSONL parser.

The final message is the file `-o <run_dir>/output.md` names. The reported
model is read from any event carrying `model`, `response.model` or session
metadata (as delegation-kit's driver does); usage from the last
`turn.completed`. Event names on a given Codex version are a live-probe
unknown, so unknown events are counted and kept, never fatal.
"""

from pathlib import Path

from ..util import bottega_executable
from . import Harness, Invocation, Parsed, base_env, matrix_argv, read_events

FAILED_EVENTS = ("turn.failed",)


def _models_in(event):
    found = [event.get("model")]
    for key in ("response", "session", "payload", "msg"):
        inner = event.get(key)
        if isinstance(inner, dict):
            found.append(inner.get("model"))
    return [name for name in found if isinstance(name, str) and name.strip()]


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
            for name in _models_in(event):
                parsed.saw_model(name)
            kind = event.get("type")
            if kind == "turn.completed" and isinstance(event.get("usage"), dict):
                parsed.usage = event["usage"]
            elif kind in FAILED_EVENTS:
                parsed.is_error = True
                error = event.get("error")
                message = error.get("message") if isinstance(error, dict) else error
                parsed.error_detail = "%s: %s" % (kind, message or "no detail")
        parsed.primary_model = parsed.models[0] if parsed.models else None
        output = Path(run_dir) / "output.md"
        try:
            final = output.read_text(encoding="utf-8")
        except OSError:
            final = None
        if final is not None and final.strip():
            parsed.final = final
        return parsed
