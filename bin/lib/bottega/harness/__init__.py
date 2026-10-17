"""The harness layer: how each coding-agent CLI is driven (plan §4.5).

A harness turns (role, profile, prompt, worktree, task dir, run dir) into an
argv, an environment and stdin, and turns what the CLI printed back into a
final message, the model(s) it reported, usage and cost.

HARNESS_MATRIX below holds every flag of plan §4.5, per harness and per role,
including the permission-rule strings. It is the one place to change when a
live probe shows a flag or a rule spelling is wrong. Effort levels come from
config.HARNESS_EFFORTS.
"""

import json
import os
import re
import shutil
import subprocess

from .. import config

ROLES = config.ROLES

# Claude Code permission rules for Bash. Whether a rule is spelled
# `Bash(git push *)` or `Bash(git push:*)` is a live-probe unknown (plan
# §4.5); change BASH_RULE and every rule below follows.
BASH_RULE = "Bash(%s *)"


def bash_rule(prefix):
    return BASH_RULE % prefix


# Placeholders filled per dispatch. Only these names are substituted, so a
# JSON argument such as '{"mcpServers":{}}' is left alone.
PLACEHOLDER = re.compile(r"\{(model|effort|task_dir|run_dir|worktree|bottega)\}")

HARNESS_MATRIX = {
    "claude": {
        "binary": "claude",
        "base": (
            "-p",
            "--model",
            "{model}",
            "--effort",
            "{effort}",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-prompts",
            "none",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--settings",
            '{"disableAllHooks":true}',
            "--disable-slash-commands",
            "--no-session-persistence",
            "--add-dir",
            "{task_dir}",
        ),
        # Appended when the profile sets max_budget_usd.
        "budget": ("--max-budget-usd",),
        "roles": {
            # Read-only by construction; not `plan` mode, whose plan-file and
            # ExitPlanMode scaffolding would confuse a headless planner.
            "planner": ("--permission-mode", "dontAsk", "--tools", "Read,Glob,Grep"),
            "implementer": (
                "--permission-mode",
                "acceptEdits",
                "--tools",
                "Read,Edit,Write,Glob,Grep,Bash",
                "--allowedTools",
                "Bash",
                "--disallowedTools",
                bash_rule("git push"),
                bash_rule("gh"),
            ),
            "reviewer": (
                "--permission-mode",
                "dontAsk",
                "--tools",
                "Read,Glob,Grep,Bash",
                "--allowedTools",
                "Bash",
                "--disallowedTools",
                bash_rule("git push"),
                bash_rule("gh"),
                bash_rule("git commit"),
            ),
            "judge": (
                "--permission-mode",
                "dontAsk",
                "--tools",
                "Read,Glob,Grep,Bash",
                "--allowedTools",
                bash_rule("git diff"),
                bash_rule("git log"),
                bash_rule("git show"),
                bash_rule("{bottega} signal"),
            ),
        },
        "tail": (),
    },
    "codex": {
        "binary": "codex",
        "base": (
            "exec",
            "-m",
            "{model}",
            "-c",
            'model_reasoning_effort="{effort}"',
            "-c",
            'approval_policy="never"',
            "-c",
            "mcp_servers={}",
            "-c",
            "features.multi_agent=false",
            "--json",
            "-o",
            "{run_dir}/output.md",
            "--ephemeral",
            "--color",
            "never",
            "-C",
            "{worktree}",
        ),
        "budget": None,
        "roles": {
            "planner": ("--sandbox", "read-only"),
            "implementer": ("--sandbox", "workspace-write", "--add-dir", "{task_dir}"),
            # Tests write caches; the code-change rail (plan §2.7) is the guard.
            "reviewer": ("--sandbox", "workspace-write", "--add-dir", "{task_dir}"),
            "judge": ("--sandbox", "workspace-write", "--add-dir", "{task_dir}"),
        },
        # The prompt comes on stdin.
        "tail": ("-",),
    },
}

# Credentials that must never reach a third-party endpoint (plan §4.4).
ANTHROPIC_CREDENTIALS = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_AUTH_TOKEN",
)
# Also removed for a proxied profile, as delegation-kit's proxied driver does:
# a header could carry a credential, and the others would route the run away
# from the profile's endpoint or model. The profile's own env may set any of
# them again.
PROXY_STRIPPED = ANTHROPIC_CREDENTIALS + (
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_MODEL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
)


class Invocation:
    """What to spawn: argv, environment, stdin, cwd. `env_set` and
    `env_removed` are variable names only, for the receipt; `cleanup` lists
    temporary directories to delete after the run."""

    def __init__(self, argv, env, stdin, cwd, env_set=(), env_removed=(), cleanup=()):
        self.argv = list(argv)
        self.env = dict(env)
        self.stdin = stdin
        self.cwd = str(cwd)
        self.env_set = sorted(env_set)
        self.env_removed = sorted(env_removed)
        self.cleanup = list(cleanup)


class Parsed:
    """What a harness reported. `final` is None when there is no final message.

    `identity_models` are the names that say which model did the work (the
    session's and each turn's model); only they are checked against the
    request. `models` is every name observed, helper models included (Claude
    Code reports a small background model in `modelUsage`); it goes into the
    receipt as `observed_models` and is never compared.
    """

    def __init__(self):
        self.final = None
        self.identity_models = []  # checked against the request and aliases
        self.models = []  # every model name the harness reported, first seen first
        self.primary_model = None  # the one recorded as provider_reported_model
        self.usage = None
        self.cost_usd = None
        self.duration_ms = None
        self.num_turns = None
        self.is_error = False
        self.error_detail = ""
        self.events = 0
        self.unparsed_lines = 0

    def saw_model(self, name, identity=False):
        """Record a reported name; `identity=True` also makes it a checked one."""
        if not isinstance(name, str) or not name.strip():
            return
        if name not in self.models:
            self.models.append(name)
        if identity and name not in self.identity_models:
            self.identity_models.append(name)


def fill(args, values):
    """Substitute the known placeholders in each argument."""
    return [
        PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), arg) for arg in args
    ]


def matrix_argv(harness, role, values, max_budget_usd=None):
    """The full argv for `harness` and `role`, from HARNESS_MATRIX."""
    spec = HARNESS_MATRIX[harness]
    if role not in spec["roles"]:
        raise ValueError("unknown role %r" % role)
    args = list(spec["base"])
    if max_budget_usd is not None and spec["budget"]:
        args += list(spec["budget"]) + [_number(max_budget_usd)]
    args += list(spec["roles"][role]) + list(spec["tail"])
    return [spec["binary"]] + fill(args, values)


def _number(value):
    return ("%g" % value) if isinstance(value, float) else str(value)


def read_events(text):
    """(events, unparsed line count) from a JSONL stream; never raises."""
    events, bad = [], 0
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            bad += 1
    return events, bad


def identity(requested, reported, aliases):
    """(model_identity_source, mismatched names).

    A reported name that is neither the requested model nor one of the
    profile's aliases is a mismatch (plan §2.8). Nothing reported means the
    identity rests on the request alone. Pass `Parsed.identity_models`, never
    every observed name: helper models are not the content model.
    """
    if not reported:
        return "requested-only", []
    allowed = {requested, *(aliases or ())}
    return "provider-reported", [name for name in reported if name not in allowed]


def probe(binary, timeout=10):
    """(ok, first line of `<binary> --version` or the reason it failed)."""
    path = shutil.which(binary)
    if not path:
        return False, "not on PATH"
    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, "%s --version did not finish in %ds" % (path, timeout)
    except OSError as error:
        return False, "%s --version could not start: %s" % (path, error)
    first = (proc.stdout or proc.stderr).strip().splitlines()
    if proc.returncode != 0:
        return False, "%s --version exited %d" % (path, proc.returncode)
    return True, "%s (%s)" % (first[0] if first else "version unknown", path)


class Harness:
    """The interface every harness implements."""

    name = None

    @property
    def binary(self):
        return HARNESS_MATRIX[self.name]["binary"]

    @property
    def efforts(self):
        return config.HARNESS_EFFORTS[self.name]

    def check(self):
        """(ok, version line or why the harness is unavailable)."""
        return probe(self.binary)

    def command(self, role, profile, prompt_path, worktree, task_dir, run_dir):
        raise NotImplementedError

    def parse(self, run_dir, stdout, stderr, rc):
        raise NotImplementedError


def get(name):
    """The registered harness called `name`."""
    from . import claude, codex

    registry = {"claude": claude.ClaudeHarness, "codex": codex.CodexHarness}
    if name not in registry:
        raise config.ConfigError(
            "unknown harness %r (harnesses: %s)" % (name, ", ".join(sorted(registry)))
        )
    return registry[name]()


def names():
    return tuple(sorted(HARNESS_MATRIX))


def base_env(profile, environ=None):
    """Inherited environment plus the profile's expanded env (codex, and claude
    profiles that are not proxied). Returns (env, names set)."""
    environ = dict(os.environ if environ is None else environ)
    extra = config.expand_env(profile, environ)
    environ.update(extra)
    return environ, sorted(extra)


def binding_report(cfg, bindings, probe_cache=None):
    """One entry per bound role: the profile, its harness, model and effort,
    and every problem that would stop a dispatch (shared by doctor and
    approve). Unbound optional roles are left out."""
    probe_cache = {} if probe_cache is None else probe_cache
    report = []
    profiles = cfg.get("profiles") or {}
    for role in ROLES:
        name = bindings.get(role)
        if name is None:
            if role in config.REQUIRED_ROLES:
                report.append(
                    {
                        "role": role,
                        "profile": None,
                        "problems": ["role %s: not bound to a profile" % role],
                    }
                )
            continue
        entry = {"role": role, "profile": name, "problems": []}
        report.append(entry)
        problem = config.binding_problem(role, name, profiles)
        if problem:
            entry["problems"].append(problem)
            continue
        profile = profiles[name]
        entry.update(
            harness=profile.get("harness"),
            model=profile.get("model"),
            effort=profile.get("effort"),
        )
        entry["problems"].extend(config.profile_problems(name, profile))
        if entry["problems"]:
            continue
        binary = HARNESS_MATRIX[profile["harness"]]["binary"]
        if binary not in probe_cache:
            probe_cache[binary] = probe(binary)
        ok, detail = probe_cache[binary]
        entry["harness_detail"] = detail
        if not ok:
            entry["problems"].append("%s: %s" % (binary, detail))
        missing = config.missing_env(profile)
        if missing:
            entry["problems"].append(
                "profile %s needs unset variable(s): %s" % (name, ", ".join(missing))
            )
    return report
