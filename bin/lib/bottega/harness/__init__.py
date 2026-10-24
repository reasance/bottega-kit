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
from ..util import bottega_executable

ROLES = config.ROLES

# Claude Code permission rules for Bash. Verified live on 2026-10-19 with
# Claude Code 2.1.303: as a deny rule, `Bash(git push *)` denies `git push`
# with arguments, bare `git push`, and a command joined with `&&` that
# contains it; as an allow rule, `Bash(git diff *)` allows `git diff …` and
# nothing else (not `git -C … diff`). Change BASH_RULE and every rule below
# follows.
BASH_RULE = "Bash(%s *)"


def bash_rule(prefix):
    return BASH_RULE % prefix


# Placeholders filled per dispatch. Only these names are substituted, so a
# JSON argument such as '{"mcpServers":{}}' is left alone.
PLACEHOLDER = re.compile(r"\{(model|effort|task_dir|run_dir|worktree|bottega|prompt)\}")

# Kimi Code: the tools each role's agent file allows (`tools:`), enforced by
# the CLI before every tool call. Everything else, Agent and the web tools
# included, is unavailable to the role.
KIMI_READ_TOOLS = ("Read", "Glob", "Grep")

# Grok Build's tool ids for `--tools` (the shell is `run_terminal_cmd`).
GROK_READ_TOOLS = "read_file,grep,list_dir"
GROK_SHELL_TOOL = "run_terminal_cmd"
GROK_EDIT_TOOLS = "search_replace,write"

# Antigravity CLI permission rules (`action(target)`), written per dispatch
# into the settings file of a fresh HOME. A deny rule beats every allow and
# the workspace default; `command(...)` matches a command prefix word by word.
AGY_NO_REACH = ("mcp(*)", "read_url(*)", "execute_url(*)")
AGY_READ_ONLY = ("write_file(*)",)
AGY_NO_PUSH = ("command(git push)", "command(gh)")

# For a harness without a command-line deny rule that covers every spelling
# of a push: origin's push URL is unusable, and gh gets a token GitHub
# refuses. GIT_CONFIG_* is appended to any the user has.
PUSH_DISABLED = {"remote.origin.pushurl": "bottega-push-disabled://"}
GH_DISABLED = "bottega-gh-disabled"

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
    "kimi": {
        "binary": "kimi",
        # `kimi -p` takes the prompt as an argument, not on stdin, and runs
        # under the `auto` permission policy: every tool the agent file allows
        # runs without asking.
        "base": (
            "-p",
            "{prompt}",
            "--output-format",
            "stream-json",
            "-m",
            "{model}",
            "--agent-file",
            "{run_dir}/kimi-agent.md",
            "--skills-dir",
            "{run_dir}/kimi-skills",
            "--add-dir",
            "{task_dir}",
        ),
        "budget": None,
        "roles": {"planner": (), "implementer": (), "reviewer": (), "judge": ()},
        "tail": (),
        "tools": {
            "planner": KIMI_READ_TOOLS,
            "implementer": KIMI_READ_TOOLS + ("Edit", "Write", "Bash"),
            "reviewer": KIMI_READ_TOOLS + ("Bash",),
            "judge": KIMI_READ_TOOLS + ("Bash",),
        },
        # Kimi Code has no command-line deny rule for a shell command, so the
        # environment does what Claude Code's `Bash(git push *)` and
        # `Bash(gh *)` rules do: origin's push URL is unusable, and gh gets a
        # token GitHub refuses. GIT_CONFIG_* is appended to any the user has.
        "env": {
            "KIMI_MODEL_THINKING_EFFORT": "{effort}",
            "KIMI_CODE_NO_AUTO_UPDATE": "1",
            "KIMI_CODE_BUILTIN_PRODUCT_SKILLS": "0",
            "GH_TOKEN": "bottega-kimi-gh-disabled",
        },
        "git_config": PUSH_DISABLED,
    },
    "grok": {
        "binary": "grok",
        # Grok Build's permission flags follow Claude Code's: `--tools` is
        # the role's tool set, `--deny` rules beat every allow, and
        # `dontAsk` refuses whatever no rule allows. Its stream is Claude
        # Code's stream-json shape.
        "base": (
            "--prompt-file",
            "{run_dir}/prompt.md",
            "--output-format",
            "streaming-messages-json",
            "-m",
            "{model}",
            "--reasoning-effort",
            "{effort}",
            "--no-subagents",
            "--disable-web-search",
            "--no-auto-update",
            "--deny",
            "MCPTool",
        ),
        "budget": None,
        "roles": {
            "planner": (
                "--permission-mode",
                "dontAsk",
                "--tools",
                GROK_READ_TOOLS,
            ),
            "implementer": (
                "--permission-mode",
                "acceptEdits",
                "--tools",
                ",".join((GROK_READ_TOOLS, GROK_EDIT_TOOLS, GROK_SHELL_TOOL)),
                "--allow",
                "Bash",
                "--allow",
                "Edit({task_dir}/**)",
                "--deny",
                bash_rule("git push"),
                "--deny",
                bash_rule("gh"),
            ),
            "reviewer": (
                "--permission-mode",
                "dontAsk",
                "--tools",
                ",".join((GROK_READ_TOOLS, GROK_SHELL_TOOL)),
                "--allow",
                "Bash",
                "--deny",
                bash_rule("git push"),
                "--deny",
                bash_rule("gh"),
                "--deny",
                bash_rule("git commit"),
            ),
            "judge": (
                "--permission-mode",
                "dontAsk",
                "--tools",
                ",".join((GROK_READ_TOOLS, GROK_SHELL_TOOL)),
                "--allow",
                bash_rule("git diff"),
                "--allow",
                bash_rule("git log"),
                "--allow",
                bash_rule("git show"),
                "--allow",
                bash_rule("{bottega} signal"),
            ),
        },
        "tail": (),
        # Grok Build reads Claude Code's and Cursor's configuration too
        # (hooks, MCP servers, skills, rules, agents); these switch that off.
        # A `Bash(git push *)` rule misses a bare `git push`, so the push and
        # gh guards stand behind the deny rules.
        "env": {
            "GROK_CLAUDE_AGENTS_ENABLED": "0",
            "GROK_CLAUDE_HOOKS_ENABLED": "0",
            "GROK_CLAUDE_MCPS_ENABLED": "0",
            "GROK_CLAUDE_RULES_ENABLED": "0",
            "GROK_CLAUDE_SKILLS_ENABLED": "0",
            "GROK_CURSOR_AGENTS_ENABLED": "0",
            "GROK_CURSOR_HOOKS_ENABLED": "0",
            "GROK_CURSOR_MCPS_ENABLED": "0",
            "GROK_CURSOR_RULES_ENABLED": "0",
            "GROK_CURSOR_SKILLS_ENABLED": "0",
            "GROK_DISABLE_AUTOUPDATER": "1",
            "GH_TOKEN": GH_DISABLED,
        },
        "git_config": PUSH_DISABLED,
    },
    "agy": {
        "binary": "agy",
        # Antigravity CLI in print mode. The prompt is the value of `-p`.
        # The workspace is the `--add-dir` folders, the worktree first; the
        # working directory alone did not make one on 2026-10-24.
        # `agy` reads permission rules only from its settings file, so each
        # dispatch runs with a fresh HOME whose settings hold the role's
        # rules (below); the terminal sandbox stays on.
        "base": (
            "-p",
            "{prompt}",
            "--output-format",
            "stream-json",
            "--model",
            "{model}",
            "--effort",
            "{effort}",
            "--print-timeout",
            "0s",
            "--disable-slash-commands",
            "--sandbox",
            "--add-dir",
            "{worktree}",
            "--add-dir",
            "{task_dir}",
        ),
        "budget": None,
        "roles": {
            "planner": (),
            "implementer": ("--mode", "accept-edits"),
            "reviewer": (),
            "judge": (),
        },
        "tail": (),
        # `permissions` in the dispatch's settings file. Without a TTY a
        # tool that needs approval is refused, so a command runs only when
        # an allow rule covers it.
        "permissions": {
            "planner": {
                "allow": (),
                "deny": AGY_NO_REACH + AGY_READ_ONLY + ("command(*)",),
            },
            "implementer": {
                "allow": ("command(*)",),
                "deny": AGY_NO_REACH + AGY_NO_PUSH,
            },
            "reviewer": {
                "allow": ("command(*)",),
                "deny": AGY_NO_REACH
                + AGY_READ_ONLY
                + AGY_NO_PUSH
                + ("command(git commit)",),
            },
            "judge": {
                "allow": (
                    "command(git diff)",
                    "command(git log)",
                    "command(git show)",
                    "command({bottega} signal)",
                ),
                "deny": AGY_NO_REACH + AGY_READ_ONLY,
            },
        },
        # `command(git push)` misses `/usr/bin/git push`.
        "env": {"GH_TOKEN": GH_DISABLED},
        "git_config": PUSH_DISABLED,
    },
    "muse": {
        "binary": "muse",
        # `muse exec`: one prompt, headless. Contributor mode is off for
        # every dispatch, whatever the user's setting; nothing is persisted.
        "base": (
            "exec",
            "--json",
            "--prompt-file",
            "{run_dir}/prompt.md",
            "--model",
            "{model}",
            "--reasoning-effort",
            "{effort}",
            "--contributor-mode",
            "off",
            "--workspace",
            "{worktree}",
            "--no-session-log",
            "--no-foreign-personal-context",
            "--disable-web-tools",
            "--disable-reminders",
            "--disable-request-user-input",
            "--approval-mode",
            "never",
            "--approval-judge",
            "off",
        ),
        "budget": None,
        "roles": {
            "planner": ("--disable-write", "--disable-shell"),
            "implementer": (),
            "reviewer": ("--disable-write",),
            "judge": ("--disable-write",),
        },
        "tail": (),
        # Muse Code has no deny rule for a shell command.
        "env": {"MUSE_NO_AUTO_UPDATE": "1", "GH_TOKEN": GH_DISABLED},
        "git_config": PUSH_DISABLED,
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
    temporary directories to delete after the run. `recorded_argv` is the argv
    the receipt keeps, when it differs from the one spawned (a prompt passed
    as an argument is already in prompt.md)."""

    def __init__(
        self,
        argv,
        env,
        stdin,
        cwd,
        env_set=(),
        env_removed=(),
        cleanup=(),
        recorded_argv=None,
    ):
        self.argv = list(argv)
        self.env = dict(env)
        self.stdin = stdin
        self.cwd = str(cwd)
        self.env_set = sorted(env_set)
        self.env_removed = sorted(env_removed)
        self.cleanup = list(cleanup)
        self.recorded_argv = list(recorded_argv or argv)


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
    """Substitute the known placeholders in each argument. A placeholder with
    no value is left as it is, so the matrix can be rendered for display
    without a prompt."""
    return [
        PLACEHOLDER.sub(
            lambda match: str(values.get(match.group(1), match.group(0))), arg
        )
        for arg in args
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
    from . import agy, claude, codex, grok, kimi, muse

    registry = {
        "agy": agy.AgyHarness,
        "claude": claude.ClaudeHarness,
        "codex": codex.CodexHarness,
        "grok": grok.GrokHarness,
        "kimi": kimi.KimiHarness,
        "muse": muse.MuseHarness,
    }
    if name not in registry:
        raise config.ConfigError(
            "unknown harness %r (harnesses: %s)" % (name, ", ".join(sorted(registry)))
        )
    return registry[name]()


def base_env(profile, environ=None):
    """Inherited environment plus the profile's expanded env (codex, and claude
    profiles that are not proxied). `${NAME}` expands from the environment and
    the key file; only the expanded env is added. Returns (env, names set)."""
    environ = dict(os.environ if environ is None else environ)
    extra = config.expand_env(profile, config.environment(environ))
    environ.update(extra)
    return environ, sorted(extra)


def git_config_env(environ, settings):
    """GIT_CONFIG_COUNT/KEY_n/VALUE_n adding `settings` after any already set."""
    try:
        start = int(environ.get("GIT_CONFIG_COUNT") or 0)
    except ValueError:
        start = 0
    env = {}
    for offset, (key, value) in enumerate(sorted(settings.items())):
        env["GIT_CONFIG_KEY_%d" % (start + offset)] = key
        env["GIT_CONFIG_VALUE_%d" % (start + offset)] = value
    env["GIT_CONFIG_COUNT"] = str(start + len(settings))
    return env


def guarded_env(name, profile, values):
    """base_env plus the harness's own `env` (placeholders filled) and its
    `git_config`. Returns (env, names set)."""
    spec = HARNESS_MATRIX[name]
    env, env_set = base_env(profile)
    harness_env = {
        key: fill([value], values)[0] for key, value in spec.get("env", {}).items()
    }
    if spec.get("git_config"):
        harness_env.update(git_config_env(env, spec["git_config"]))
    env.update(harness_env)
    return env, sorted(set(env_set) | set(harness_env))


def dispatch_values(profile, worktree, task_dir, run_dir):
    """The placeholder values every harness fills."""
    return {
        "model": profile["model"],
        "effort": profile["effort"],
        "task_dir": str(task_dir),
        "run_dir": str(run_dir),
        "worktree": str(worktree),
        "bottega": bottega_executable(),
    }


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
