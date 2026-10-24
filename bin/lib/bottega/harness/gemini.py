"""Gemini CLI (`gemini`, prompt on stdin): argv, policy file, parser.

Each dispatch writes `gemini-policy.toml` into the run directory and passes
it with `--admin-policy`: admin-tier rules, which outrank the user's own
policies. Every tool is denied except the role's; the shell commands a role
must not run are denied above that. Gemini CLI reads a system settings file
only from a root-owned directory and takes no effort on its command line,
so the user's settings apply, hooks included, and the effort is the CLI's
default for the model.

The stream-json output holds `init`, `message` (assistant text in deltas),
`tool_use`, `tool_result`, `error` and a final `result` event with the
status and the stats. The final message is the assistant text after the
last tool event. No event names the model that answered: `init.model` is
the requested one, and the per-model token stats also count the helper
requests Gemini CLI makes on its own. So the identity rests on the request,
and the stats' model names are recorded as observed, never checked.
"""

import json
from pathlib import Path

from . import (
    HARNESS_MATRIX,
    Harness,
    Invocation,
    Parsed,
    dispatch_values,
    fill,
    guarded_env,
    matrix_argv,
    read_events,
)

POLICY_FILE = "gemini-policy.toml"
SHELL = "run_shell_command"


def _strings(values):
    return "[%s]" % ", ".join(json.dumps(value) for value in values)


def _rule(lines, decision, priority, tools=None, prefixes=None):
    lines.append("[[rule]]")
    if prefixes is not None:
        lines.append("toolName = %s" % json.dumps(SHELL))
        lines.append("commandPrefix = %s" % _strings(prefixes))
    else:
        lines.append("toolName = %s" % (_strings(tools) if tools else '"*"'))
    lines.append("decision = %s" % json.dumps(decision))
    lines.append("priority = %d" % priority)
    lines.append("")


def policy(role, values):
    """The admin-tier policy file for `role`, as TOML text."""
    spec = HARNESS_MATRIX["gemini"]
    lines = ["# bottega-kit %s: written for one dispatch" % role, ""]
    _rule(lines, "deny", 1)
    _rule(lines, "allow", 500, tools=spec["tools"][role])
    allow = spec["shell_allow"].get(role)
    if allow:
        _rule(lines, "allow", 500, prefixes=fill(allow, values))
    deny = spec["shell_deny"].get(role)
    if deny:
        _rule(lines, "deny", 900, prefixes=fill(deny, values))
    return "\n".join(lines)


class GeminiHarness(Harness):
    name = "gemini"

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        values = dispatch_values(profile, worktree, task_dir, run_dir)
        argv = matrix_argv(self.name, role, values)
        Path(run_dir, POLICY_FILE).write_text(policy(role, values), encoding="utf-8")
        env, env_set = guarded_env(self.name, profile, values)
        stdin = Path(prompt_path).read_text(encoding="utf-8")
        return Invocation(argv, env, stdin, worktree, env_set)

    def parse(self, run_dir, stdout, stderr, rc):
        parsed = Parsed()
        events, parsed.unparsed_lines = read_events(stdout)
        parsed.events = len(events)
        text, result = [], None
        for event in events:
            kind = event.get("type")
            if kind == "message" and event.get("role") == "assistant":
                if isinstance(event.get("content"), str):
                    text.append(event["content"])
            elif kind in ("tool_use", "tool_result"):
                text = []
            elif kind == "result":
                result = event
        final = "".join(text)
        if final.strip():
            parsed.final = final
        if result is None:
            return parsed
        stats = result.get("stats")
        if isinstance(stats, dict):
            parsed.usage = stats
            if isinstance(stats.get("models"), dict):
                for name in stats["models"]:
                    parsed.saw_model(name)
            if isinstance(stats.get("duration_ms"), int):
                parsed.duration_ms = stats["duration_ms"]
        if result.get("status") != "success":
            parsed.is_error = True
            error = result.get("error")
            detail = error.get("message") if isinstance(error, dict) else None
            parsed.error_detail = "result status %s%s" % (
                result.get("status") or "missing",
                ": %s" % detail if detail else "",
            )
        return parsed
