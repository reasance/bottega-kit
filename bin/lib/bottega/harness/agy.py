"""Antigravity CLI (`agy -p`): argv, a fresh HOME with the role's settings,
environment, and the stream-json parser.

`agy` reads its permission rules only from
`~/.gemini/antigravity-cli/settings.json`; no flag or variable names another
file. So each dispatch runs with HOME set to a temporary directory whose
settings file holds the role's `permissions` from HARNESS_MATRIX, and is
deleted after the run; a copy is kept in the run directory. Your own `agy`
settings, hooks, plugins, MCP servers, skills and rules stay out of the run.

The sign-in stays yours. `agy` keeps it in
`~/.gemini/antigravity-cli/antigravity-oauth-token` or in the system
keychain; the fresh HOME holds a symbolic link to that file when it exists,
and the SSH session markers, which would keep `agy` off the keychain, are
removed. bottega-kit never opens, copies or moves the file. With HOME moved,
`bottega signal` is pointed at this kit's task data. Git runs without your
global config: the terminal sandbox refuses to read it, and no role commits.

Each stream-json line is `{"event": <kind>, <kind>: {...}}`: one `init`
(the requested model, the tools), `step_update`s (assistant text in
`text_delta` on `agent_response` steps; `tool` steps) and a final `result`:
`status`, `response`, `usage`, `duration_seconds`, `num_turns`,
`conversation_id`, and `error` on failure. The model is named only in
`init`, as requested, so the identity rests on the request.
"""

import json
import os
import tempfile
from pathlib import Path

from .. import xdg
from . import HARNESS_MATRIX, Harness, Invocation, Parsed, dispatch_values, fill
from . import guarded_env, matrix_argv, read_events

SETTINGS = Path(".gemini", "antigravity-cli", "settings.json")
SETTINGS_COPY = "agy-settings.json"
SIGN_IN = Path(".gemini", "antigravity-cli", "antigravity-oauth-token")
RECORDED_PROMPT = "<prompt.md>"
# With any of these set, `agy` looks for its sign-in in the file only, never
# in the keychain.
SSH_MARKERS = ("SSH_CLIENT", "SSH_CONNECTION", "SSH_TTY")


def settings(role, values):
    """The settings file for `role`: its permission rules, sandbox on."""
    rules = HARNESS_MATRIX["agy"]["permissions"][role]
    return {
        "permissions": {kind: fill(rules[kind], values) for kind in ("allow", "deny")},
        "toolPermission": "request-review",
        "allowNonWorkspaceAccess": False,
        "enableTerminalSandbox": True,
        "disableSlashCommands": True,
    }


class AgyHarness(Harness):
    name = "agy"

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        values = dispatch_values(profile, worktree, task_dir, run_dir)
        prompt = Path(prompt_path).read_text(encoding="utf-8")
        argv = matrix_argv(self.name, role, dict(values, prompt=prompt))
        recorded = matrix_argv(self.name, role, dict(values, prompt=RECORDED_PROMPT))
        text = json.dumps(settings(role, values), indent=2) + "\n"
        Path(run_dir, SETTINGS_COPY).write_text(text, encoding="utf-8")
        home = tempfile.mkdtemp(prefix="bottega-agy-home-")
        path = Path(home, SETTINGS)
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        sign_in = Path(os.environ.get("HOME") or Path.home(), SIGN_IN)
        if sign_in.is_file():
            Path(home, SIGN_IN).symlink_to(sign_in)

        env, env_set = guarded_env(self.name, profile, values)
        removed = [name for name in SSH_MARKERS if name in env]
        for name in SSH_MARKERS:
            env.pop(name, None)
        moved = {"HOME": home, "BOTTEGA_DATA_HOME": str(xdg.data_dir())}
        env.update(moved)
        return Invocation(
            argv,
            env,
            "",
            worktree,
            set(env_set) | set(moved),
            removed,
            cleanup=[home],
            recorded_argv=recorded,
        )

    def parse(self, run_dir, stdout, stderr, rc):
        parsed = Parsed()
        events, parsed.unparsed_lines = read_events(stdout)
        parsed.events = len(events)
        text, result = [], None
        for event in events:
            kind = event.get("event")
            body = event.get(kind)
            if not isinstance(body, dict):
                continue
            if kind == "init":
                parsed.saw_model(body.get("model"))
            elif kind == "step_update":
                step = body.get("step_type")
                if step == "tool":
                    text = []
                elif step == "agent_response" and isinstance(
                    body.get("text_delta"), str
                ):
                    text.append(body["text_delta"])
            elif kind == "result":
                result = body
        final = "".join(text)
        if final.strip():
            parsed.final = final
        if result is None:
            return parsed
        response = result.get("response")
        if isinstance(response, str) and response.strip():
            parsed.final = response
        usage = result.get("usage")
        parsed.usage = {
            "conversation_id": result.get("conversation_id"),
            "tokens": usage if isinstance(usage, dict) else None,
        }
        seconds = result.get("duration_seconds")
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
            parsed.duration_ms = int(seconds * 1000)
        turns = result.get("num_turns")
        if isinstance(turns, int) and not isinstance(turns, bool):
            parsed.num_turns = turns
        if result.get("status") != "SUCCESS":
            parsed.is_error = True
            error = result.get("error")
            detail = error.get("message") if isinstance(error, dict) else error
            parsed.error_detail = "result status %s%s" % (
                result.get("status") or "missing",
                ": %s" % detail if detail else "",
            )
        return parsed
