"""The personal configuration: profiles, role bindings, the round cap.

Schema (plan §4.4). A profile is harness + model + effort, plus optional env,
aliases, timeout and max_budget_usd. No secret goes in the configuration: env
values may reference ${NAME}, expanded at dispatch time from the environment
or, for a name the environment does not set, from the key file
(`secrets.env` beside config.json; NOTES.md, 2026-10-20).
"""

import json
import os
import re
import stat
from pathlib import Path

from . import xdg
from .util import Refused, UsageError, atomic_write_json

SCHEMA_VERSION = 1
DEFAULT_ROUNDS = 3

# Effort levels each harness accepts. The harness registry builds on this
# table; keep one source of truth.
HARNESS_EFFORTS = {
    "claude": ("low", "medium", "high", "xhigh", "max"),
    "codex": ("none", "minimal", "low", "medium", "high", "xhigh", "max"),
    # The levels Kimi Code declares for its K3 models (`support_efforts`).
    "kimi": ("low", "high", "max"),
    # The levels Grok Build lists for grok-4.6 and grok-4.7.
    "grok": ("low", "medium", "high", "xhigh"),
    # Gemini CLI takes no effort from its command line; a run thinks at the
    # CLI's default for the model.
    "gemini": ("default",),
    # `muse exec --reasoning-effort`.
    "muse": ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"),
}
# The executable each harness drives.
HARNESS_BINARIES = {name: name for name in HARNESS_EFFORTS}

REQUIRED_ROLES = ("planner", "implementer", "reviewer")
OPTIONAL_ROLES = ("judge",)
ROLES = REQUIRED_ROLES + OPTIONAL_ROLES
RESERVED_BINDINGS = ("auto",)

PROFILE_KEYS = {
    "harness",
    "model",
    "effort",
    "env",
    "aliases",
    "timeout",
    "max_budget_usd",
}
TOP_KEYS = {"schema_version", "profiles", "roles", "rounds"}

ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Refused):
    """The configuration is missing or invalid (exit 2)."""


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def profile_problems(name, profile):
    where = "profile %r" % name
    if not isinstance(profile, dict):
        return [where + ": must be an object"]
    problems = []
    for key in sorted(set(profile) - PROFILE_KEYS):
        problems.append("%s: unknown key %r" % (where, key))
    harness = profile.get("harness")
    if harness not in HARNESS_EFFORTS:
        problems.append(
            "%s: harness must be one of %s, got %r"
            % (where, ", ".join(sorted(HARNESS_EFFORTS)), harness)
        )
    model = profile.get("model")
    if not isinstance(model, str) or not model.strip():
        problems.append(where + ": model must be a non-empty string")
    effort = profile.get("effort")
    if harness in HARNESS_EFFORTS and effort not in HARNESS_EFFORTS[harness]:
        problems.append(
            "%s: effort for harness %s must be one of %s, got %r"
            % (where, harness, "|".join(HARNESS_EFFORTS[harness]), effort)
        )
    elif harness not in HARNESS_EFFORTS and not isinstance(effort, str):
        problems.append(where + ": effort must be a string")
    if "env" in profile:
        env = profile["env"]
        if not isinstance(env, dict):
            problems.append(where + ": env must be an object of strings")
        else:
            for key, value in env.items():
                if not ENV_NAME.match(key):
                    problems.append("%s: env name %r is not valid" % (where, key))
                if not isinstance(value, str):
                    problems.append("%s: env %s must be a string" % (where, key))
    if "aliases" in profile:
        aliases = profile["aliases"]
        if not isinstance(aliases, list) or not all(
            isinstance(a, str) and a.strip() for a in aliases
        ):
            problems.append(where + ": aliases must be a list of non-empty strings")
    if "timeout" in profile:
        if not _is_number(profile["timeout"]) or profile["timeout"] <= 0:
            problems.append(where + ": timeout must be a positive number of seconds")
    if "max_budget_usd" in profile:
        if harness != "claude":
            problems.append(where + ": max_budget_usd is supported by claude only")
        elif (
            not _is_number(profile["max_budget_usd"]) or profile["max_budget_usd"] <= 0
        ):
            problems.append(where + ": max_budget_usd must be a positive number")
    return problems


def binding_problem(role, value, profiles):
    """One role binding; None when valid. `profiles` is a dict or None."""
    if role not in ROLES:
        return "unknown role %r (roles: %s)" % (role, ", ".join(ROLES))
    if not isinstance(value, str) or not value.strip():
        return "role %s: must name a profile" % role
    if value in RESERVED_BINDINGS:
        return "role %s: %r is not supported yet" % (role, value)
    if profiles is not None and value not in profiles:
        return "role %s: no profile named %r" % (role, value)
    return None


def problems(config):
    """Every problem in `config`, as plain sentences. Empty when valid."""
    if not isinstance(config, dict):
        return ["the configuration must be a JSON object"]
    found = []
    for key in sorted(set(config) - TOP_KEYS):
        found.append("unknown top-level key %r" % key)
    if config.get("schema_version") != SCHEMA_VERSION:
        found.append(
            "schema_version must be %d, got %r"
            % (SCHEMA_VERSION, config.get("schema_version"))
        )
    profiles = config.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        found.append("profiles must be a non-empty object")
        profiles = {}
    for name in sorted(profiles):
        found.extend(profile_problems(name, profiles[name]))
    roles = config.get("roles")
    if not isinstance(roles, dict):
        found.append("roles must be an object")
        roles = {}
    for role in REQUIRED_ROLES:
        if role not in roles:
            found.append("role %s: required" % role)
    for role in sorted(roles):
        problem = binding_problem(role, roles[role], profiles)
        if problem:
            found.append(problem)
    if "rounds" in config:
        rounds = config["rounds"]
        if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 1:
            found.append("rounds must be a whole number of at least 1")
    return found


def validate(config):
    """Return `config` with defaults filled in, or raise ConfigError."""
    found = problems(config)
    if found:
        raise ConfigError("invalid configuration:\n  " + "\n  ".join(found))
    result = dict(config)
    result.setdefault("rounds", DEFAULT_ROUNDS)
    return result


def read(path=None):
    """Parse the file without validating it."""
    path = path or xdg.config_file()
    if not path.exists():
        raise ConfigError("no configuration at %s; run: bottega init" % path)
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except json.JSONDecodeError as error:
        raise ConfigError("%s is not valid JSON: %s" % (path, error)) from None


def load(path=None):
    return validate(read(path))


def env_references(profile):
    """The ${NAME} variables a profile's env needs, sorted."""
    names = set()
    for value in (profile.get("env") or {}).values():
        if isinstance(value, str):
            names.update(ENV_REFERENCE.findall(value))
    return sorted(names)


def read_secrets(path=None):
    """The key file as {NAME: value}, or {} when there is none.

    One `NAME=value` line each; blank lines and `#` comments are skipped, an
    `export ` prefix, quotes around the value and CRLF are tolerated. The
    file is parsed, never executed. A file that group or others can read is
    refused, not read: a credential anyone on the machine can open is not a
    secret, and saying so beats using it.
    """
    path = xdg.secrets_file() if path is None else Path(path)
    if not path.exists():
        return {}
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise ConfigError(
                "%s is mode %03o, readable by others; run: chmod 600 %s"
                % (path, mode, path)
            )
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError("cannot read %s: %s" % (path, error)) from None
    values = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("export ", "export\t")):
            line = line[7:].lstrip()
        name, sep, value = line.partition("=")
        name = name.rstrip()
        if not sep or not ENV_NAME.match(name):
            raise ConfigError("%s line %d: expected NAME=value" % (path, number))
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def environment(environ=None, secrets=None):
    """What ${NAME} expands from: the process environment, plus the key file
    for the names it does not set. For expansion only: a harness inherits the
    process environment and the expanded profile env, never the whole file."""
    environ = os.environ if environ is None else environ
    merged = dict(read_secrets() if secrets is None else secrets)
    merged.update(environ)
    return merged


def missing_env(profile, environ=None):
    """The referenced names `environ` does not set; `environ` defaults to
    the environment plus the key file."""
    environ = environment() if environ is None else environ
    return [name for name in env_references(profile) if name not in environ]


def expand_env(profile, environ=None):
    """The profile's env with every ${NAME} replaced from `environ` (the
    environment plus the key file when None).

    A referenced variable that is not set is a ConfigError, never an empty
    string: a blank credential would be sent as-is.
    """
    environ = environment() if environ is None else environ
    missing = missing_env(profile, environ)
    if missing:
        raise ConfigError("environment variable(s) not set: %s" % ", ".join(missing))
    return {
        key: ENV_REFERENCE.sub(lambda m: environ[m.group(1)], value)
        for key, value in (profile.get("env") or {}).items()
    }


def role_bindings(config, overrides=None):
    """Effective role -> profile map: config roles, then per-task overrides."""
    bindings = dict(config.get("roles") or {})
    bindings.update(overrides or {})
    return bindings


def parse_role_override(text):
    """`role=profile` from --role; raises UsageError or ConfigError."""
    role, sep, profile = text.partition("=")
    role, profile = role.strip(), profile.strip()
    if not sep or not role or not profile:
        raise UsageError("--role takes role=profile, got %r" % text)
    if role not in ROLES:
        raise UsageError("unknown role %r (roles: %s)" % (role, ", ".join(ROLES)))
    if profile in RESERVED_BINDINGS:
        raise ConfigError("role %s: %r is not supported yet" % (role, profile))
    return role, profile


# The README's canonical example (plan §4.4): Fable plans and judges, Opus
# implements and reviews, all through Claude Code.
CLAUDE_PROFILES = {
    "fable": {"harness": "claude", "model": "claude-fable-5-1", "effort": "max"},
    "opus-builder": {"harness": "claude", "model": "claude-opus-5-5", "effort": "high"},
    "opus-reviewer": {
        "harness": "claude",
        "model": "claude-opus-5-5",
        "effort": "high",
    },
}
CLAUDE_ROLES = {
    "planner": "fable",
    "implementer": "opus-builder",
    "reviewer": "opus-reviewer",
    "judge": "fable",
}
CODEX_PROFILES = {
    "sol-builder": {"harness": "codex", "model": "gpt-5.6-sol", "effort": "high"},
}
CODEX_ROLES = {
    "planner": "sol-builder",
    "implementer": "sol-builder",
    "reviewer": "sol-builder",
}
# A model alias of Kimi Code's own config.toml, provisioned by `kimi login`.
KIMI_PROFILES = {
    "kimi": {"harness": "kimi", "model": "kimi-code/k3.1-pro", "effort": "high"},
}
KIMI_ROLES = {
    "planner": "kimi",
    "implementer": "kimi",
    "reviewer": "kimi",
}


GROK_PROFILES = {
    "grok": {"harness": "grok", "model": "grok-4.7", "effort": "high"},
}
GEMINI_PROFILES = {
    "gemini": {
        "harness": "gemini",
        "model": "gemini-3.8-flash",
        "effort": "default",
    },
}
MUSE_PROFILES = {
    "muse": {"harness": "muse", "model": "muse-wonder-1.0", "effort": "high"},
}


def _one_profile_roles(name):
    return {"planner": name, "implementer": name, "reviewer": name}


# In order of preference: the first harness found binds the roles; every
# harness found adds its profiles.
STARTERS = (
    ("claude", CLAUDE_PROFILES, CLAUDE_ROLES),
    ("codex", CODEX_PROFILES, CODEX_ROLES),
    ("kimi", KIMI_PROFILES, KIMI_ROLES),
    ("grok", GROK_PROFILES, _one_profile_roles("grok")),
    ("gemini", GEMINI_PROFILES, _one_profile_roles("gemini")),
    ("muse", MUSE_PROFILES, _one_profile_roles("muse")),
)


def starter(harnesses):
    """A starter configuration for the harnesses found on PATH (claude's
    when none is)."""
    found = set(harnesses) & {name for name, _, _ in STARTERS} or {"claude"}
    profiles, roles = {}, {}
    for name, starter_profiles, starter_roles in STARTERS:
        if name in found:
            profiles.update(starter_profiles)
            if not roles:
                roles.update(starter_roles)
    return validate(
        {
            "schema_version": SCHEMA_VERSION,
            "profiles": profiles,
            "roles": roles,
            "rounds": DEFAULT_ROUNDS,
        }
    )


def write(config, path=None):
    atomic_write_json(path or xdg.config_file(), config)
