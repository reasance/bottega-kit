#!/usr/bin/env python3
"""The harness layer against the fakes: every flag of plan §4.5 per harness
and role, proxied Claude profiles, identity, timeouts, receipts."""

import json
import os
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import CANONICAL, ROOT, FakeCalls, Sandbox, main

from bottega import dispatch, harness
from bottega.harness import claude as claude_harness
from bottega.util import pid_alive

BOTTEGA = str(ROOT / "bin" / "bottega")

# Plan §4.5, written out cell by cell. Each tuple must appear in the argv as
# a contiguous run. These are deliberately not read from HARNESS_MATRIX: the
# test pins the plan, the matrix implements it.
CLAUDE_BASE = [
    ("-p",),
    ("--model", "{model}"),
    ("--effort", "{effort}"),
    ("--output-format", "stream-json"),
    ("--verbose",),
    ("--permission-prompts", "none"),
    ("--setting-sources", ""),
    ("--strict-mcp-config",),
    ("--mcp-config", '{"mcpServers":{}}'),
    ("--settings", '{"disableAllHooks":true}'),
    ("--disable-slash-commands",),
    ("--no-session-persistence",),
    ("--add-dir", "{task_dir}"),
]
CLAUDE_ROLES = {
    "planner": [("--permission-mode", "dontAsk"), ("--tools", "Read,Glob,Grep")],
    "implementer": [
        ("--permission-mode", "acceptEdits"),
        ("--tools", "Read,Edit,Write,Glob,Grep,Bash"),
        ("--allowedTools", "Bash"),
        ("--disallowedTools", "Bash(git push *)", "Bash(gh *)"),
    ],
    "reviewer": [
        ("--permission-mode", "dontAsk"),
        ("--tools", "Read,Glob,Grep,Bash"),
        ("--allowedTools", "Bash"),
        (
            "--disallowedTools",
            "Bash(git push *)",
            "Bash(gh *)",
            "Bash(git commit *)",
        ),
    ],
    "judge": [
        ("--permission-mode", "dontAsk"),
        ("--tools", "Read,Glob,Grep,Bash"),
        (
            "--allowedTools",
            "Bash(git diff *)",
            "Bash(git log *)",
            "Bash(git show *)",
            "Bash(%s signal *)" % BOTTEGA,
        ),
    ],
}
CODEX_BASE = [
    ("exec",),
    ("-m", "{model}"),
    ("-c", 'model_reasoning_effort="{effort}"'),
    ("-c", 'approval_policy="never"'),
    ("-c", "mcp_servers={}"),
    ("-c", "features.multi_agent=false"),
    ("--json",),
    ("-o", "{run_dir}/output.md"),
    ("--ephemeral",),
    ("--color", "never"),
    ("-C", "{worktree}"),
]
CODEX_ROLES = {
    "planner": [("--sandbox", "read-only")],
    "implementer": [("--sandbox", "workspace-write"), ("--add-dir", "{task_dir}")],
    "reviewer": [("--sandbox", "workspace-write"), ("--add-dir", "{task_dir}")],
    "judge": [("--sandbox", "workspace-write"), ("--add-dir", "{task_dir}")],
}
NEVER = ("--fallback-model", "--bare", "--ignore-user-config", "--tools=")


def contains_run(argv, cells):
    n = len(cells)
    return any(tuple(argv[i : i + n]) == tuple(cells) for i in range(len(argv)))


def flags(argv):
    return {arg for arg in argv if arg.startswith("-") and arg != "-"}


class Fixture:
    profile_name = "opus-builder"

    def setUp(self):
        self.box = Sandbox(self)
        cfg = json.loads(json.dumps(CANONICAL))
        cfg["profiles"]["budgeted"] = {
            "harness": "claude",
            "model": "claude-opus-5",
            "effort": "low",
            "max_budget_usd": 2.5,
        }
        cfg["profiles"]["secretive"] = {
            "harness": "codex",
            "model": "gpt-5.6-sol",
            "effort": "medium",
            "env": {"MY_TOKEN": "${SECRET_SOURCE}", "PLAIN": "plain-value"},
        }
        self.cfg = cfg
        self.box.write_config(cfg)
        # The implementer, reviewer and judge prompts ship in M2; overrides
        # stand in for them here (and exercise the override path).
        overrides = self.box.root / "config" / "bottega-kit" / "prompts"
        overrides.mkdir(parents=True)
        for role in ("implementer", "reviewer", "judge"):
            (overrides / (role + ".md")).write_text(
                "%s for {{task_id}} in {{worktree}}; then {{signal_cmd}}\n" % role
            )
        self.repo = self.box.make_repo()
        self.task = self.box.new_task(self.repo, "Matrix")
        self.dir = self.box.task_dir(self.task)
        self.seq = 0

    def dispatch(self, role, profile_name, calls=(), default=None, extra_env=None):
        """One in-process dispatch with the fakes; returns (outcome, log entry)."""
        fake = FakeCalls(self.box, calls, default or {"final": "done"}, self.task)
        self.seq += 1
        env = {**self.box.env, **fake.env, **(extra_env or {})}
        st = self.box.state(self.task)
        with mock.patch.dict(os.environ, env, clear=True):
            outcome = dispatch.run(
                st,
                self.dir,
                self.seq,
                role,
                profile_name,
                self.cfg["profiles"][profile_name],
                3,
                "",
            )
        entries = fake.entries()
        return outcome, (entries[-1] if entries else None)

    def expand(self, cells, profile, run_dir):
        values = {
            "{model}": profile["model"],
            "{effort}": profile["effort"],
            "{task_dir}": str(self.dir),
            "{run_dir}": str(run_dir),
            "{worktree}": self.box.state(self.task)["worktree"],
        }
        out = []
        for cell in cells:
            expanded = []
            for arg in cell:
                for key, value in values.items():
                    arg = arg.replace(key, value)
                expanded.append(arg)
            out.append(tuple(expanded))
        return out


class Matrix(Fixture, unittest.TestCase):
    def check(self, harness_name, profile_name, base, roles, budget=None):
        profile = self.cfg["profiles"][profile_name]
        for role in state_roles():
            with self.subTest(harness=harness_name, role=role):
                outcome, entry = self.dispatch(role, profile_name)
                self.assertTrue(outcome.ok, outcome.record)
                argv = entry["argv"]
                self.assertEqual(entry["tool"], harness_name)
                expected = self.expand(base + roles[role], profile, outcome.run_dir)
                if budget:
                    expected.append(("--max-budget-usd", budget))
                for cell in expected:
                    self.assertTrue(
                        contains_run(argv, cell), "%r not in %r" % (cell, argv)
                    )
                # Nothing beyond the plan's flags.
                want = {a for cell in expected for a in cell if a.startswith("-")}
                self.assertEqual(flags(argv) - {"-"}, want - {"-"})
                for banned in NEVER:
                    self.assertNotIn(banned, argv)
                # Prompt on stdin, cwd = worktree, receipt matches.
                prompt = (outcome.run_dir / "prompt.md").read_text()
                self.assertEqual(entry["stdin"], prompt)
                worktree = self.box.state(self.task)["worktree"]
                self.assertEqual(Path(entry["cwd"]).resolve(), Path(worktree).resolve())
                self.assertEqual(outcome.record["argv"], [harness_name] + argv)
                self.assertEqual(outcome.record["cwd"], worktree)
                yield role, argv

    def test_claude_every_cell_every_role(self):
        for role, argv in self.check(
            "claude", "opus-builder", CLAUDE_BASE, CLAUDE_ROLES
        ):
            self.assertNotIn("-", argv)  # the prompt is on stdin, not an argument

    def test_claude_budget_cell(self):
        for _ in self.check(
            "claude", "budgeted", CLAUDE_BASE, CLAUDE_ROLES, budget="2.5"
        ):
            pass

    def test_codex_every_cell_every_role(self):
        for role, argv in self.check("codex", "sol-builder", CODEX_BASE, CODEX_ROLES):
            self.assertEqual(argv[0], "exec")
            self.assertEqual(argv[-1], "-")  # prompt from stdin
            if role == "planner":
                self.assertNotIn("--add-dir", argv)

    def test_matrix_has_one_bash_rule_spelling(self):
        rules = [
            arg
            for spec in harness.HARNESS_MATRIX.values()
            for role_args in spec["roles"].values()
            for arg in role_args
            if arg.startswith("Bash(")
        ]
        self.assertTrue(rules)
        for rule in rules:
            self.assertRegex(rule, r"^Bash\(.+ \*\)$")
        self.assertEqual(set(harness.HARNESS_MATRIX), {"claude", "codex"})
        for name, spec in harness.HARNESS_MATRIX.items():
            self.assertEqual(set(spec["roles"]), set(state_roles()))
            self.assertEqual(
                harness.get(name).efforts, harness.config.HARNESS_EFFORTS[name]
            )


def state_roles():
    return ("planner", "implementer", "reviewer", "judge")


class Receipts(Fixture, unittest.TestCase):
    def test_run_dir_layout_and_run_json_keys(self):
        outcome, _ = self.dispatch("planner", "opus-builder")
        run_dir = outcome.run_dir
        self.assertEqual(run_dir.name, "001-planner")
        for name in ("prompt.md", "output.md", "events.jsonl", "run.json"):
            self.assertTrue((run_dir / name).is_file(), name)
        self.assertTrue((run_dir / "scratch").is_dir())
        self.assertFalse((run_dir / "error.json").exists())
        record = json.loads((run_dir / "run.json").read_text())
        for key in (
            "seq",
            "role",
            "profile",
            "harness",
            "requested_model",
            "provider_reported_model",
            "model_identity_source",
            "effort",
            "argv",
            "cwd",
            "started",
            "finished",
            "duration_s",
            "exit_code",
            "usage",
            "cost_usd",
            "signal",
            "rails",
            "status",
        ):
            self.assertIn(key, record)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["provider_reported_model"], "claude-opus-5")
        self.assertEqual(record["model_identity_source"], "provider-reported")
        self.assertEqual(record["cost_usd"], 0.0123)
        self.assertEqual(record["num_turns"], 1)
        self.assertIn("modelUsage", record["usage"])
        self.assertEqual((run_dir / "output.md").read_text(), "done")
        for key in (
            "head_before",
            "head_after",
            "diff_sha_before",
            "diff_sha_after",
            "new_untracked",
        ):
            self.assertIn(key, record["rails"])

    def test_env_names_only_never_values(self):
        outcome, entry = self.dispatch(
            "implementer",
            "secretive",
            extra_env={"SECRET_SOURCE": "s3cr3t-value-123"},
        )
        self.assertTrue(outcome.ok, outcome.record)
        self.assertIn("MY_TOKEN", entry["env_names"])
        record = json.loads((outcome.run_dir / "run.json").read_text())
        self.assertEqual(record["env"], {"set": ["MY_TOKEN", "PLAIN"], "removed": []})
        for path in outcome.run_dir.rglob("*"):
            if path.is_file():
                text = path.read_text(errors="replace")
                self.assertNotIn("s3cr3t-value-123", text, path)
                self.assertNotIn("plain-value", text, path)

    def test_codex_usage_and_final_from_output_file(self):
        outcome, _ = self.dispatch("reviewer", "sol-builder", default={"final": "F"})
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.final, "F")
        self.assertEqual(outcome.record["usage"]["output_tokens"], 50)
        self.assertIsNone(outcome.record["cost_usd"])
        self.assertEqual(outcome.record["provider_reported_model"], "gpt-5.6-sol")

    def test_parsers_tolerate_unknown_and_malformed_lines(self):
        raw = 'not json\n[1, 2]\n{"type": "mystery", "data": {"x": 1}}\n\n'
        for name in ("opus-builder", "sol-builder"):
            with self.subTest(profile=name):
                outcome, _ = self.dispatch(
                    "planner", name, default={"final": "ok", "raw": raw}
                )
                self.assertTrue(outcome.ok, outcome.record)
                self.assertEqual(outcome.record["unparsed_lines"], 2)
                events = (outcome.run_dir / "events.jsonl").read_text()
                self.assertTrue(events.startswith("not json\n"))  # recorded raw


class Failures(Fixture, unittest.TestCase):
    def error(self, outcome):
        return json.loads((outcome.run_dir / "error.json").read_text())

    def test_nonzero_exit_is_dispatch_failed(self):
        outcome, _ = self.dispatch(
            "planner", "opus-builder", default={"exit": 1, "stderr": "boom\n"}
        )
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.reason, "dispatch-failed")
        error = self.error(outcome)
        self.assertEqual(error["phase"], "run")
        self.assertEqual(error["exit_code"], 1)
        self.assertIn("boom", error["stderr_tail"])

    def test_no_final_message_or_is_error_is_dispatch_failed(self):
        for name, step in (
            ("opus-builder", {"no_final": True}),
            ("opus-builder", {"is_error": True}),
            ("sol-builder", {"no_final": True}),
        ):
            with self.subTest(profile=name, step=step):
                outcome, _ = self.dispatch("planner", name, default=step)
                self.assertEqual(outcome.reason, "dispatch-failed")
                self.assertEqual(self.error(outcome)["phase"], "parse")

    def test_missing_binary_is_dispatch_failed_at_spawn(self):
        path = "%s:/usr/bin:/bin" % (self.box.root / "bin")
        outcome, entry = self.dispatch(
            "planner", "opus-builder", extra_env={"PATH": path}
        )
        self.assertIsNone(entry)
        self.assertEqual(outcome.reason, "dispatch-failed")
        self.assertEqual(self.error(outcome)["phase"], "spawn")

    def test_identity_mismatch_in_any_reported_field(self):
        for step in (
            {"model": "claude-other"},
            {"assistant_model": "claude-other"},
            {"usage_model": "claude-other"},
        ):
            with self.subTest(step=step):
                outcome, _ = self.dispatch("planner", "opus-builder", default=step)
                self.assertEqual(outcome.reason, "identity-mismatch")
                error = self.error(outcome)
                self.assertEqual(error["phase"], "identity")
                self.assertIn("claude-other", error["detail"])
        outcome, _ = self.dispatch("planner", "sol-builder", default={"model": "gpt-x"})
        self.assertEqual(outcome.reason, "identity-mismatch")

    def test_alias_is_accepted(self):
        self.cfg["profiles"]["opus-builder"]["aliases"] = ["claude-other"]
        outcome, _ = self.dispatch(
            "planner", "opus-builder", default={"usage_model": "claude-other"}
        )
        self.assertTrue(outcome.ok, outcome.record)

    def test_nothing_reported_is_requested_only(self):
        outcome, _ = self.dispatch("planner", "opus-builder", default={"model": ""})
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.record["model_identity_source"], "requested-only")
        self.assertIsNone(outcome.record["provider_reported_model"])

    def test_timeout_kills_the_process_group(self):
        self.cfg["profiles"]["opus-builder"]["timeout"] = 1
        pidfile = self.box.root / "child.pid"
        step = {
            "run": [["/bin/sh", "-c", "sleep 60 & echo $! > %s" % pidfile]],
            "sleep": 60,
        }
        started = time.monotonic()
        outcome, _ = self.dispatch("implementer", "opus-builder", default=step)
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual(outcome.reason, "timeout")
        error = self.error(outcome)
        self.assertEqual(error["reason"], "timeout")
        self.assertEqual(outcome.record["timeout_s"], 1)
        child = int(pidfile.read_text())
        deadline = time.monotonic() + 5
        while pid_alive(child) and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertFalse(pid_alive(child), "the harness's child survived")


class Proxied(Fixture, unittest.TestCase):
    CREDENTIALS = {
        "ANTHROPIC_API_KEY": "anthropic-key",
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth-token",
        "ANTHROPIC_AUTH_TOKEN": "anthropic-auth",
    }

    def test_proxied_env_strips_credentials_then_applies_the_profile(self):
        profile = CANONICAL["profiles"]["glm-reviewer"]
        environ = {
            **self.CREDENTIALS,
            "ZAI_API_KEY": "zai-key",
            "HOME": "/h",
            "ANTHROPIC_CUSTOM_HEADERS": "x-api-key: leaked",
            "CLAUDE_CODE_USE_BEDROCK": "1",
        }
        env, env_set, removed = claude_harness.proxied_env(
            profile, "/tmp/fresh", environ
        )
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "zai-key")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://api.z.ai/api/anthropic")
        self.assertEqual(env["ANTHROPIC_DEFAULT_OPUS_MODEL"], "glm-5.3-flash")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], "/tmp/fresh")
        self.assertEqual(env["HOME"], "/h")
        self.assertNotIn("ANTHROPIC_CUSTOM_HEADERS", env)
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", env)
        self.assertEqual(
            sorted(removed),
            sorted(
                [
                    *self.CREDENTIALS,
                    "ANTHROPIC_CUSTOM_HEADERS",
                    "CLAUDE_CODE_USE_BEDROCK",
                ]
            ),
        )
        self.assertIn("CLAUDE_CONFIG_DIR", env_set)
        self.assertNotIn("anthropic-key", json.dumps([env_set, removed]))

    def test_proxied_dispatch_end_to_end(self):
        dump = self.box.root / "env.txt"
        step = {
            "run": [["/bin/sh", "-c", "env > %s" % dump]],
            "model": "glm-5.3-flash",
            "usage_model": "opus",
        }
        outcome, entry = self.dispatch(
            "reviewer",
            "glm-reviewer",
            default=step,
            extra_env={**self.CREDENTIALS, "ZAI_API_KEY": "zai-key"},
        )
        self.assertTrue(outcome.ok, outcome.record)  # "opus" is an alias
        seen = dict(
            line.split("=", 1) for line in dump.read_text().splitlines() if "=" in line
        )
        self.assertNotIn("ANTHROPIC_API_KEY", seen)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", seen)
        self.assertEqual(seen["ANTHROPIC_AUTH_TOKEN"], "zai-key")
        config_dir = seen["CLAUDE_CONFIG_DIR"]
        self.assertFalse(config_dir.startswith(str(self.box.root / "home")))
        self.assertFalse(Path(config_dir).exists(), "temporary config dir removed")
        self.assertNotIn("ANTHROPIC_API_KEY", entry["env_names"])
        record = outcome.record
        self.assertEqual(sorted(record["env"]["removed"]), sorted(self.CREDENTIALS))
        self.assertIn("CLAUDE_CONFIG_DIR", record["env"]["set"])
        text = (outcome.run_dir / "run.json").read_text()
        for value in ("zai-key", "anthropic-key", "oauth-token", "anthropic-auth"):
            self.assertNotIn(value, text)

    def test_plain_claude_profile_keeps_the_users_login(self):
        dump = self.box.root / "env.txt"
        step = {"run": [["/bin/sh", "-c", "env > %s" % dump]]}
        outcome, _ = self.dispatch(
            "reviewer", "opus-reviewer", default=step, extra_env=self.CREDENTIALS
        )
        self.assertTrue(outcome.ok)
        text = dump.read_text()
        self.assertIn("ANTHROPIC_API_KEY=anthropic-key", text)
        self.assertNotIn("CLAUDE_CONFIG_DIR=", text)
        self.assertEqual(outcome.record["env"], {"set": [], "removed": []})


class Cli(Fixture, unittest.TestCase):
    """Through `bottega plan`: identity mismatch and timeout exit 3."""

    def plan(self, step, rc=3, **cfg_changes):
        self.cfg["profiles"]["fable-judge"].update(cfg_changes)
        self.box.write_config(self.cfg)
        fake = FakeCalls(self.box, default=step)
        return self.box.bottega("plan", self.task, rc=rc, env=fake.env)

    def test_identity_mismatch_exits_3_with_error_json(self):
        proc = self.plan({"model": "claude-impostor"})
        self.assertRegex(
            proc.stdout,
            r"^001 planner fable-judge claude-fable-5-1 \u2192 failed "
            r"identity-mismatch \(\d+s\)\n$",
        )
        error = json.loads((self.dir / "runs/001-planner/error.json").read_text())
        self.assertEqual(error["reason"], "identity-mismatch")
        st = self.box.state(self.task)
        self.assertEqual(st["phase"], "new")
        self.assertEqual(st["runs"][0]["status"], "failed")
        self.assertIsNone(st["current_run"])

    def test_timeout_exits_3(self):
        proc = self.plan({"sleep": 30}, timeout=1)
        self.assertIn("failed timeout", proc.stdout)
        error = json.loads((self.dir / "runs/001-planner/error.json").read_text())
        self.assertEqual(error["reason"], "timeout")
        self.assertEqual(self.box.state(self.task)["phase"], "new")


class Doctor(unittest.TestCase):
    def test_check_reports_version_or_absence(self):
        box = Sandbox(self)
        with box.active():
            ok, detail = harness.get("codex").check()
            self.assertTrue(ok)
            self.assertIn("codex-cli 0.163.0", detail)
            os.environ["PATH"] = "/usr/bin:/bin"
            ok, detail = harness.get("claude").check()
            self.assertFalse(ok)
            self.assertEqual(detail, "not on PATH")


if __name__ == "__main__":
    main()
