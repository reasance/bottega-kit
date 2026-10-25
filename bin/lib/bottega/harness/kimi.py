"""Kimi Code (`kimi -p`): argv, agent file and environment, and the parser.

Each dispatch writes an agent file into the run directory and selects it with
`--agent-file`: its `tools:` list is the role's tool set, which the CLI
enforces before every call, and its body keeps Kimi Code's own system prompt
(`${base_prompt}`). `--skills-dir` points at an empty directory, so no user
or project skill is loaded. Effort goes through KIMI_MODEL_THINKING_EFFORT;
the CLI has no flag for it.

The stream-json output holds `assistant`, `tool` and `meta` messages. The
final message is the last assistant message with text content. No event
names the model, so the identity rests on the request. The session's own
log (`$KIMI_CODE_HOME/sessions/*/<session id>/agents/main/wire.jsonl`, found
through the `session.resume_hint` event) records the model the CLI asked
for, the effort it sent and the tokens per request; they are read into the
receipt as observed, never checked, and a missing or unreadable log is not
an error.
"""

import re
from pathlib import Path

from ..util import bottega_executable
from . import HARNESS_MATRIX, Harness, Invocation, Parsed, base_env, fill
from . import git_config_env, matrix_argv, read_events

AGENT_FILE = "kimi-agent.md"
SKILLS_DIR = "kimi-skills"
RECORDED_PROMPT = "<prompt.md>"
USAGE_KEYS = ("inputOther", "inputCacheRead", "inputCacheCreation", "output")
# A session id goes into a glob pattern: letters, digits, `_` and `-` only.
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def agent_file(role):
    """The agent file for `role`: a name, the role's tools, the default prompt."""
    tools = HARNESS_MATRIX["kimi"]["tools"][role]
    lines = [
        "---",
        "name: bottega-%s" % role,
        "description: bottega-kit %s; one dispatch, run by bottega-kit" % role,
        "tools:",
    ]
    lines += ["  - %s" % tool for tool in tools]
    lines += ["subagents: []", "---", "", "${base_prompt}", ""]
    return "\n".join(lines)


def _session_id(events):
    for event in events:
        if event.get("type") == "session.resume_hint":
            value = event.get("session_id")
            if isinstance(value, str) and SESSION_ID.match(value):
                return value
    return None


def _wire(home, session_id):
    matches = sorted(
        Path(home).glob("sessions/*/%s/agents/main/wire.jsonl" % session_id)
    )
    return matches[0] if matches else None


def _text(content):
    """The text of an assistant message's content: a string or text parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "".join(parts)
    return ""


class KimiHarness(Harness):
    name = "kimi"

    def __init__(self):
        # Set by command(), read by parse(): where Kimi Code keeps sessions.
        self.home = None

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        spec = HARNESS_MATRIX[self.name]
        prompt = Path(prompt_path).read_text(encoding="utf-8")
        values = {
            "model": profile["model"],
            "effort": profile["effort"],
            "task_dir": str(task_dir),
            "run_dir": str(run_dir),
            "worktree": str(worktree),
            "bottega": bottega_executable(),
        }
        argv = matrix_argv(self.name, role, dict(values, prompt=prompt))
        recorded = matrix_argv(self.name, role, dict(values, prompt=RECORDED_PROMPT))
        Path(run_dir, AGENT_FILE).write_text(agent_file(role), encoding="utf-8")
        Path(run_dir, SKILLS_DIR).mkdir(exist_ok=True)
        env, env_set = base_env(profile)
        harness_env = {
            name: fill([value], values)[0] for name, value in spec["env"].items()
        }
        harness_env.update(git_config_env(env, spec["git_config"]))
        env.update(harness_env)
        home = env.get("KIMI_CODE_HOME")
        if home:
            self.home = Path(home).expanduser()
        elif env.get("HOME"):
            self.home = Path(env["HOME"]) / ".kimi-code"
        names = set(env_set) | set(harness_env)
        return Invocation(argv, env, "", worktree, names, recorded_argv=recorded)

    def parse(self, run_dir, stdout, stderr, rc):
        parsed = Parsed()
        events, parsed.unparsed_lines = read_events(stdout)
        parsed.events = len(events)
        for event in events:
            if event.get("role") == "assistant":
                text = _text(event.get("content"))
                if text.strip():
                    parsed.final = text
        session_id = _session_id(events)
        if session_id:
            parsed.usage = {"session_id": session_id}
            self._read_session(session_id, parsed)
        return parsed

    def _read_session(self, session_id, parsed):
        """Fill usage, duration and turns from the session log; never raises."""
        try:
            wire = _wire(self.home, session_id) if self.home else None
            text = wire.read_text(encoding="utf-8", errors="replace") if wire else ""
        except OSError:
            text = ""
        if not text:
            return
        totals = dict.fromkeys(USAGE_KEYS, 0)
        requests, efforts, models, endings = 0, [], [], []
        duration_ms = 0
        for event in read_events(text)[0]:
            if event.get("agentId", "main") != "main":
                continue
            kind = event.get("type")
            if kind == "llm.request":
                requests += 1
                for key in ("modelAlias", "model"):
                    _add(models, event.get(key))
                _add(efforts, event.get("thinkingEffort"))
            elif kind == "usage.record" and isinstance(event.get("usage"), dict):
                for key in USAGE_KEYS:
                    value = event["usage"].get(key)
                    if isinstance(value, int) and not isinstance(value, bool):
                        totals[key] += value
            elif kind == "turn.ended":
                endings.append(event.get("reason"))
                if isinstance(event.get("durationMs"), int):
                    duration_ms += event["durationMs"]
        parsed.usage.update(
            requests=requests,
            requested_models=models,
            thinking_effort=efforts,
            turn_endings=endings,
            tokens=totals,
        )
        if endings:
            parsed.num_turns = len(endings)
            parsed.duration_ms = duration_ms


def _add(found, value):
    if isinstance(value, str) and value not in found:
        found.append(value)
