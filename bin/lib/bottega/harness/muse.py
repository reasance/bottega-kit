"""Muse Code (`muse exec`): argv and environment, and the JSONL parser.

The prompt is read from the run directory's prompt.md (`--prompt-file`).
Each line of `--json` output is a record whose `.payload.kind` says what it
is. The final message is the `run_terminal` payload's `.text` when its
`.terminal` is `completed`; any other terminal is an error. The
`run_usage` payload lists, per model that served the run, the model name
and the tokens: those names are the identity, checked against the request,
as delegation-kit's Muse runner checks them.
"""

from . import Harness, Invocation, Parsed, dispatch_values, guarded_env
from . import matrix_argv, read_events

TOKEN_KEYS = ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens")


class MuseHarness(Harness):
    name = "muse"

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        values = dispatch_values(profile, worktree, task_dir, run_dir)
        argv = matrix_argv(self.name, role, values)
        env, env_set = guarded_env(self.name, profile, values)
        return Invocation(argv, env, "", worktree, env_set)

    def parse(self, run_dir, stdout, stderr, rc):
        parsed = Parsed()
        events, parsed.unparsed_lines = read_events(stdout)
        parsed.events = len(events)
        terminal, usage, session = None, None, None
        for event in events:
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            stream = event.get("stream")
            if session is None and isinstance(stream, dict):
                if stream.get("kind") == "session":
                    session = stream.get("id")
            if payload.get("kind") == "run_terminal":
                terminal = payload
            elif payload.get("kind") == "run_usage":
                usage = payload
        if usage is not None:
            models = [m for m in usage.get("models") or [] if isinstance(m, dict)]
            for entry in models:
                parsed.saw_model(entry.get("model"), identity=True)
            tokens = dict.fromkeys(TOKEN_KEYS, 0)
            for entry in models:
                for key in TOKEN_KEYS:
                    value = entry.get(key)
                    if isinstance(value, int) and not isinstance(value, bool):
                        tokens[key] += value
            parsed.usage = {
                "session_id": session,
                "models": models,
                "calls": usage.get("calls"),
                "tokens": tokens,
            }
        parsed.primary_model = (
            parsed.identity_models[0] if parsed.identity_models else None
        )
        if terminal is not None:
            if terminal.get("terminal") == "completed":
                text = terminal.get("text")
                if isinstance(text, str) and text.strip():
                    parsed.final = text
            else:
                parsed.is_error = True
                parsed.error_detail = "run ended %s%s" % (
                    terminal.get("terminal") or "without a terminal state",
                    ": %s" % terminal["reason"] if terminal.get("reason") else "",
                )
        return parsed
