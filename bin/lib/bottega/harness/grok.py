"""Grok Build (`grok -p`): argv and environment; the parser is Claude Code's.

`--output-format streaming-messages-json` is Claude Code's stream-json shape:
a `system/init` event, `assistant` events whose `.message.model` names the
model, and a `result` event with the final text, usage, `modelUsage` and
`total_cost_usd`. Grok writes the literal model name "unknown" when it has
none; that name is dropped, so it never counts as a mismatch.

The prompt is read from the run directory's prompt.md (`--prompt-file`);
Grok Build reads no prompt from stdin.
"""

from . import Invocation, dispatch_values, guarded_env, matrix_argv
from .claude import ClaudeHarness

UNKNOWN_MODEL = "unknown"


class GrokHarness(ClaudeHarness):
    name = "grok"

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        values = dispatch_values(profile, worktree, task_dir, run_dir)
        argv = matrix_argv(self.name, role, values)
        env, env_set = guarded_env(self.name, profile, values)
        return Invocation(argv, env, "", worktree, env_set)

    def parse(self, run_dir, stdout, stderr, rc):
        parsed = super().parse(run_dir, stdout, stderr, rc)
        parsed.models = [m for m in parsed.models if m != UNKNOWN_MODEL]
        parsed.identity_models = [
            m for m in parsed.identity_models if m != UNKNOWN_MODEL
        ]
        if parsed.primary_model == UNKNOWN_MODEL:
            parsed.primary_model = (
                parsed.identity_models[0] if parsed.identity_models else None
            )
        return parsed
