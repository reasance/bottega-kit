"""Claude Code (`claude -p`): argv and environment, and the stream-json parser.

Field names mirror delegation-kit's reader of the same stream: the
`system/init` event's `.model`, each assistant event's `.message.model`, and
the `result` event's `.result`, `.is_error`, `.usage`, `.modelUsage`,
`.total_cost_usd`, `.duration_ms`, `.num_turns`.

Identity: only the content model counts, the init event's `.model` and each
assistant event's `.message.model`. The `modelUsage` keys also list helper
models (Claude Code runs a small model for background tasks), so they are
recorded as observed and never compared with the request.
"""

import os
import tempfile
from pathlib import Path

from .. import config
from ..util import bottega_executable
from . import (
    PROXY_STRIPPED,
    Harness,
    Invocation,
    Parsed,
    base_env,
    matrix_argv,
    read_events,
)

PROXY_KEY = "ANTHROPIC_BASE_URL"


def is_proxied(profile):
    """A claude profile pointed at another Anthropic-compatible endpoint."""
    return PROXY_KEY in (profile.get("env") or {})


def proxied_env(profile, config_dir, environ=None):
    """The environment for a proxied Claude profile (plan §4.4).

    Anthropic credentials (and the routing variables in PROXY_STRIPPED) are
    removed from the inherited environment before the profile's env is
    applied, so they can never reach a third-party
    endpoint, and CLAUDE_CONFIG_DIR points at a fresh directory so the user's
    own login and settings are not used either. `${NAME}` references in the
    profile expand from the original environment.

    Returns (env, names set, names removed).
    """
    environ = dict(os.environ if environ is None else environ)
    extra = config.expand_env(profile, environ)
    env = dict(environ)
    removed = [name for name in PROXY_STRIPPED if name in env]
    for name in PROXY_STRIPPED:
        env.pop(name, None)
    env.update(extra)
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    return env, sorted(set(extra) | {"CLAUDE_CONFIG_DIR"}), removed


class ClaudeHarness(Harness):
    name = "claude"

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        values = {
            "model": profile["model"],
            "effort": profile["effort"],
            "task_dir": str(task_dir),
            "run_dir": str(run_dir),
            "worktree": str(worktree),
            "bottega": bottega_executable(),
        }
        argv = matrix_argv(self.name, role, values, profile.get("max_budget_usd"))
        cleanup = []
        if is_proxied(profile):
            config_dir = tempfile.mkdtemp(prefix="bottega-claude-config-")
            cleanup.append(config_dir)
            env, env_set, removed = proxied_env(profile, config_dir)
        else:
            env, env_set = base_env(profile)
            removed = []
        stdin = Path(prompt_path).read_text(encoding="utf-8")
        return Invocation(argv, env, stdin, worktree, env_set, removed, cleanup)

    def parse(self, run_dir, stdout, stderr, rc):
        parsed = Parsed()
        events, parsed.unparsed_lines = read_events(stdout)
        parsed.events = len(events)
        result = None
        init_model = None
        for event in events:
            kind = event.get("type")
            if kind == "system" and event.get("subtype") == "init":
                if init_model is None and isinstance(event.get("model"), str):
                    init_model = event["model"]
                parsed.saw_model(event.get("model"), identity=True)
            elif kind == "assistant":
                message = event.get("message")
                if isinstance(message, dict):
                    parsed.saw_model(message.get("model"), identity=True)
            elif kind == "result":
                result = event
        if result is not None:
            usage_by_model = result.get("modelUsage")
            if isinstance(usage_by_model, dict):
                for name in usage_by_model:
                    parsed.saw_model(name)
            parsed.usage = {
                "usage": result.get("usage"),
                "modelUsage": usage_by_model,
            }
            cost = result.get("total_cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                parsed.cost_usd = cost
            parsed.duration_ms = result.get("duration_ms")
            parsed.num_turns = result.get("num_turns")
            if result.get("is_error") is True:
                parsed.is_error = True
                parsed.error_detail = "result event has is_error: true (%s)" % (
                    result.get("subtype") or "no subtype"
                )
            final = result.get("result")
            if isinstance(final, str) and final.strip():
                parsed.final = final
        parsed.primary_model = init_model or (
            parsed.identity_models[0] if parsed.identity_models else None
        )
        return parsed
