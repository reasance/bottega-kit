"""Shared fixtures for the suites: a sandboxed environment and git repos.

Each test gets its own temporary HOME, XDG directories and PATH (the fakes,
python3, git and this checkout's bottega, then /usr/bin:/bin), so a test can
neither read the user's configuration nor reach a real harness.
"""

import contextlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BOTTEGA = ROOT / "bin" / "bottega"
FAKES = ROOT / "tests" / "fakes"
sys.path.insert(0, str(ROOT / "bin" / "lib"))

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "bottega test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "bottega test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}
SCRUBBED = (
    "BOTTEGA_DATA_HOME",
    "BOTTEGA_BIN_HOME",
    "BOTTEGA_FAKE_SCENARIO",
    "BOTTEGA_FAKE_LOG",
    "BOTTEGA_FAKE_BOTTEGA",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "OPENAI_API_KEY",
)


class Sandbox:
    def __init__(self, testcase):
        temp = tempfile.TemporaryDirectory(prefix="bottega-test-")
        testcase.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        for name in ("home", "config", "data", "cache", "state", "bin", "work"):
            (self.root / name).mkdir()
        bin_dir = self.root / "bin"
        os.symlink(sys.executable, bin_dir / "python3")
        os.symlink(shutil.which("git"), bin_dir / "git")
        os.symlink(BOTTEGA, bin_dir / "bottega")
        env = {k: v for k, v in os.environ.items() if k not in SCRUBBED}
        env.update(GIT_IDENTITY)
        env.update(
            {
                "HOME": str(self.root / "home"),
                "XDG_CONFIG_HOME": str(self.root / "config"),
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_CACHE_HOME": str(self.root / "cache"),
                "XDG_STATE_HOME": str(self.root / "state"),
                "PATH": "%s:%s:/usr/bin:/bin" % (FAKES, bin_dir),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        self.env = env
        self.work = self.root / "work"

    @property
    def config_file(self):
        return self.root / "config" / "bottega-kit" / "config.json"

    @property
    def tasks_dir(self):
        return self.root / "data" / "bottega-kit" / "tasks"

    def write_config(self, value):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(json.dumps(value, indent=2))

    @contextlib.contextmanager
    def active(self):
        """Run in-process code with this sandbox's environment."""
        with mock.patch.dict(os.environ, self.env, clear=True):
            yield

    def bottega(self, *args, rc=0, cwd=None, stdin=None, env=None, check=True):
        proc = subprocess.run(
            [str(BOTTEGA), *args],
            cwd=str(cwd or self.work),
            env={**self.env, **(env or {})},
            input=stdin,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if check and proc.returncode != rc:
            raise AssertionError(
                "bottega %s: expected exit %d, got %d\nstdout:\n%s\nstderr:\n%s"
                % (" ".join(args), rc, proc.returncode, proc.stdout, proc.stderr)
            )
        return proc

    def git(self, *args, cwd):
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            env=self.env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError("git %s failed: %s" % (" ".join(args), proc.stderr))
        return proc.stdout.strip()

    def make_repo(self, name="app", origin=True, branch="main", files=None):
        """A repository with one commit; with origin=True, a bare origin it
        has pushed to and an origin/HEAD that points at `branch`."""
        repo = self.work / name
        repo.mkdir()
        self.git("init", "-q", "-b", branch, cwd=repo)
        for rel, content in (files or {"README.md": "hello\n"}).items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.git("add", "-A", cwd=repo)
        self.git("commit", "-q", "-m", "initial", cwd=repo)
        if origin:
            bare = self.work / (name + "-origin.git")
            self.git("init", "-q", "--bare", "-b", branch, str(bare), cwd=self.work)
            self.git("remote", "add", "origin", str(bare), cwd=repo)
            self.git("push", "-q", "-u", "origin", branch, cwd=repo)
            self.git("remote", "set-head", "origin", branch, cwd=repo)
        return repo

    def new_task(self, repo, title="Smoke test", request="hello", *extra):
        proc = self.bottega(
            "new", "--repo", str(repo), "--title", title, "--request", request, *extra
        )
        first = proc.stdout.splitlines()[0]
        return first.split()[1]

    def task_dir(self, task_id):
        matches = list(self.tasks_dir.glob("*/" + task_id))
        if len(matches) != 1:
            raise AssertionError(
                "expected one task dir for %s: %s" % (task_id, matches)
            )
        return matches[0]

    def state(self, task_id):
        return json.loads((self.task_dir(task_id) / "state.json").read_text())


CANONICAL = {
    "schema_version": 1,
    "profiles": {
        "fable": {
            "harness": "claude",
            "model": "claude-fable-5-1",
            "effort": "max",
        },
        "opus-builder": {
            "harness": "claude",
            "model": "claude-opus-5-5",
            "effort": "high",
        },
        "opus-reviewer": {
            "harness": "claude",
            "model": "claude-opus-5-5",
            "effort": "high",
        },
        "sol-builder": {"harness": "codex", "model": "gpt-5.6-sol", "effort": "high"},
        "glm-reviewer": {
            "harness": "claude",
            "model": "glm-5.3-flash",
            "effort": "max",
            "env": {
                "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
                "ANTHROPIC_AUTH_TOKEN": "${ZAI_API_KEY}",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3-flash",
            },
            "aliases": ["opus"],
        },
    },
    "roles": {
        "planner": "fable",
        "implementer": "opus-builder",
        "reviewer": "opus-reviewer",
        "judge": "fable",
    },
    "rounds": 3,
}


def main():
    unittest.main(verbosity=1)


# A planner's final message that passes `plan` and `approve`.
PLAN_MESSAGE = """## Overview

Add a --dry-run flag to the export command. Assumed: text output.

## Implementation Plan

### Phase 1: The flag

**Files to modify / create:**
- `export.py` — parse and honour --dry-run

## Testing Strategy

### Unit tests
- `test_export.py` covers the flag

### Manual QA
- **Tool:** the real command
- **Setup and safety:** a temporary directory
- **Scenario:** run `export --dry-run`
- **Expected evidence:** nothing is written

## To-Do List

### Implementation
- [ ] Parse --dry-run
- [ ] Skip writes when it is set

### Testing
- [ ] Unit tests for the flag
- [ ] Manual QA: run export --dry-run

## Project Docs Update

Not needed for this change.
"""

QUESTIONS_MESSAGE = """## Questions for you

1. Should the dry run print JSON or text? JSON is scriptable; text is shorter.
"""


class FakeCalls:
    """A BOTTEGA_FAKE_SCENARIO for the sandbox, and the calls the fakes logged.
    Each instance has its own log, so its call counter starts at 1."""

    serial = itertools.count(1)

    def __init__(self, box, calls=(), default=None, task=None):
        self.log = box.root / ("calls-%d.jsonl" % next(FakeCalls.serial))
        scenario = {"log": str(self.log), "calls": list(calls)}
        if default is not None:
            scenario["default"] = default
        if task:
            scenario["task"] = task
        self.env = {"BOTTEGA_FAKE_SCENARIO": json.dumps(scenario)}

    def entries(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]
