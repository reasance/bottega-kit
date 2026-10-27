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
# Kimi Code (2026-10-23): the prompt is the value of -p; each role's tools are
# the `tools:` list of the agent file the dispatch writes.
KIMI_BASE = [
    ("-p", "{prompt}"),
    ("--output-format", "stream-json"),
    ("-m", "{model}"),
    ("--agent-file", "{run_dir}/kimi-agent.md"),
    ("--skills-dir", "{run_dir}/kimi-skills"),
    ("--add-dir", "{task_dir}"),
]
KIMI_ROLES = {role: [] for role in ("planner", "implementer", "reviewer", "judge")}
KIMI_TOOLS = {
    "planner": ["Read", "Glob", "Grep"],
    "implementer": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
    "reviewer": ["Read", "Glob", "Grep", "Bash"],
    "judge": ["Read", "Glob", "Grep", "Bash"],
}
KIMI_ENV = {
    "KIMI_MODEL_THINKING_EFFORT": "{effort}",
    "KIMI_CODE_NO_AUTO_UPDATE": "1",
    "KIMI_CODE_BUILTIN_PRODUCT_SKILLS": "0",
    "GH_TOKEN": "bottega-kimi-gh-disabled",
}
# Grok Build 1.0.62 (2026-10-24): Claude Code's permission flags with Grok's
# tool ids; the prompt is read from the run directory.
GROK_BASE = [
    ("--prompt-file", "{run_dir}/prompt.md"),
    ("--output-format", "streaming-messages-json"),
    ("-m", "{model}"),
    ("--reasoning-effort", "{effort}"),
    ("--no-subagents",),
    ("--disable-web-search",),
    ("--no-auto-update",),
    ("--deny", "MCPTool"),
]
GROK_ROLES = {
    "planner": [
        ("--permission-mode", "dontAsk"),
        ("--tools", "read_file,grep,list_dir"),
    ],
    "implementer": [
        ("--permission-mode", "acceptEdits"),
        ("--tools", "read_file,grep,list_dir,search_replace,write,run_terminal_cmd"),
        ("--allow", "Bash"),
        ("--allow", "Edit({task_dir}/**)"),
        ("--deny", "Bash(git push *)"),
        ("--deny", "Bash(gh *)"),
    ],
    "reviewer": [
        ("--permission-mode", "dontAsk"),
        ("--tools", "read_file,grep,list_dir,run_terminal_cmd"),
        ("--allow", "Bash"),
        ("--deny", "Bash(git push *)"),
        ("--deny", "Bash(gh *)"),
        ("--deny", "Bash(git commit *)"),
    ],
    "judge": [
        ("--permission-mode", "dontAsk"),
        ("--tools", "read_file,grep,list_dir,run_terminal_cmd"),
        ("--allow", "Bash(git diff *)"),
        ("--allow", "Bash(git log *)"),
        ("--allow", "Bash(git show *)"),
        ("--allow", "Bash(%s signal *)" % BOTTEGA),
    ],
}
GROK_ENV = {
    **{
        "GROK_%s_%s_ENABLED" % (source, kind): "0"
        for source in ("CLAUDE", "CURSOR")
        for kind in ("AGENTS", "HOOKS", "MCPS", "RULES", "SKILLS")
    },
    "GROK_DISABLE_AUTOUPDATER": "1",
    "GH_TOKEN": "bottega-gh-disabled",
}
# Antigravity CLI 1.4.7: the prompt is the value of -p; each role's
# permission rules are the settings file of the dispatch's own HOME.
AGY_BASE = [
    ("-p", "{prompt}"),
    ("--output-format", "stream-json"),
    ("--model", "{model}"),
    ("--effort", "{effort}"),
    ("--print-timeout", "0s"),
    ("--disable-slash-commands",),
    ("--sandbox",),
    ("--add-dir", "{worktree}"),
    ("--add-dir", "{task_dir}"),
]
AGY_ROLES = {
    "planner": [],
    "implementer": [("--mode", "accept-edits")],
    "reviewer": [],
    "judge": [],
}
AGY_NO_REACH = ["mcp(*)", "read_url(*)", "execute_url(*)"]
AGY_NO_PUSH = ["command(git push)", "command(gh)"]
AGY_PERMISSIONS = {
    "planner": {
        "allow": [],
        "deny": AGY_NO_REACH + ["write_file(*)", "command(*)"],
    },
    "implementer": {"allow": ["command(*)"], "deny": AGY_NO_REACH + AGY_NO_PUSH},
    "reviewer": {
        "allow": ["command(*)"],
        "deny": AGY_NO_REACH
        + ["write_file(*)"]
        + AGY_NO_PUSH
        + ["command(git commit)"],
    },
    "judge": {
        "allow": [
            "command(git diff)",
            "command(git log)",
            "command(git show)",
            "command(%s signal)" % BOTTEGA,
        ],
        "deny": AGY_NO_REACH + ["write_file(*)"],
    },
}
# Muse Code 1.4.12: `muse exec`; the prompt is read from the run directory.
MUSE_BASE = [
    ("exec",),
    ("--json",),
    ("--prompt-file", "{run_dir}/prompt.md"),
    ("--model", "{model}"),
    ("--reasoning-effort", "{effort}"),
    ("--contributor-mode", "off"),
    ("--workspace", "{worktree}"),
    ("--no-session-log",),
    ("--no-foreign-personal-context",),
    ("--disable-web-tools",),
    ("--disable-reminders",),
    ("--disable-request-user-input",),
    ("--approval-mode", "never"),
    ("--approval-judge", "off"),
]
MUSE_ROLES = {
    "planner": [("--disable-write",), ("--disable-shell",)],
    "implementer": [],
    "reviewer": [("--disable-write",)],
    "judge": [("--disable-write",)],
}
NEVER = ("--fallback-model", "--bare", "--ignore-user-config", "--tools=")
NEVER_KIMI = ("--yolo", "-y", "--auto", "--plan", "--session", "--continue")
NEVER_GROK = ("--yolo", "--always-approve", "-p", "--single", "--sandbox")
NEVER_AGY = ("--dangerously-skip-permissions", "--continue", "--conversation")
NEVER_MUSE = ("--yolo", "--disable-approval", "--trust-workspace", "--provider")
# The harnesses that read the prompt from the run directory's prompt.md.
PROMPT_FILE = ("grok", "muse")
# The harnesses that take the prompt as the value of -p.
PROMPT_ARG = ("kimi", "agy")
PUSH_GUARD = {"GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"}
GH_GUARD = {"GH_TOKEN": "bottega-gh-disabled"}


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
            "model": "claude-opus-5-5",
            "effort": "low",
            "max_budget_usd": 2.5,
        }
        cfg["profiles"]["secretive"] = {
            "harness": "codex",
            "model": "gpt-5.6-sol",
            "effort": "medium",
            "env": {"MY_TOKEN": "${SECRET_SOURCE}", "PLAIN": "plain-value"},
        }
        cfg["profiles"]["kimi"] = {
            "harness": "kimi",
            "model": "kimi-code/k3.1-pro",
            "effort": "high",
        }
        cfg["profiles"]["grok"] = {
            "harness": "grok",
            "model": "grok-4.7",
            "effort": "xhigh",
        }
        cfg["profiles"]["gemini"] = {
            "harness": "agy",
            "model": "gemini-3.8-flash-high",
            "effort": "high",
        }
        cfg["profiles"]["muse"] = {
            "harness": "muse",
            "model": "muse-wonder-1.0",
            "effort": "high",
        }
        self.cfg = cfg
        self.box.write_config(cfg)
        # Short overrides stand in for the implementer, reviewer and judge
        # prompts here (and exercise the override path); the loop suite
        # dispatches the shipped ones.
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
                if harness_name in PROMPT_ARG:
                    prompt = (outcome.run_dir / "prompt.md").read_text()
                    expected = [
                        tuple(prompt if arg == "{prompt}" else arg for arg in cell)
                        for cell in expected
                    ]
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
                # Prompt on stdin (kimi, agy: the value of -p, kept out of the
                # receipt's argv), cwd = worktree, receipt matches.
                prompt = (outcome.run_dir / "prompt.md").read_text()
                recorded = [harness_name] + argv
                if harness_name in PROMPT_ARG:
                    self.assertEqual(argv[argv.index("-p") + 1], prompt)
                    self.assertEqual(entry["stdin"], "")
                    recorded[recorded.index(prompt)] = "<prompt.md>"
                elif harness_name in PROMPT_FILE:
                    self.assertEqual(entry["stdin"], "")
                    self.assertNotIn(prompt, argv)
                else:
                    self.assertEqual(entry["stdin"], prompt)
                worktree = self.box.state(self.task)["worktree"]
                self.assertEqual(Path(entry["cwd"]).resolve(), Path(worktree).resolve())
                self.assertEqual(outcome.record["argv"], recorded)
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

    def test_terra_model_and_effort_reach_codex_for_every_role(self):
        profile = self.cfg["profiles"]["sol-builder"]
        profile["model"] = "gpt-6.1-terra"
        for effort in ("low", "max"):
            profile["effort"] = effort
            self.box.write_config(self.cfg)
            for _, argv in self.check("codex", "sol-builder", CODEX_BASE, CODEX_ROLES):
                self.assertTrue(contains_run(argv, ("-m", "gpt-6.1-terra")))
                self.assertTrue(
                    contains_run(
                        argv, ("-c", "model_reasoning_effort=" + json.dumps(effort))
                    )
                )

    def test_kimi_every_cell_every_role(self):
        for role, argv in self.check("kimi", "kimi", KIMI_BASE, KIMI_ROLES):
            run_dir = Path(argv[argv.index("--agent-file") + 1]).parent
            agent = (run_dir / "kimi-agent.md").read_text()
            front = agent.split("---\n")[1]
            tools = [line[4:] for line in front.splitlines() if line.startswith("  - ")]
            self.assertEqual(tools, KIMI_TOOLS[role])
            self.assertIn("name: bottega-%s\n" % role, front)
            self.assertIn("subagents: []\n", front)
            self.assertIn("${base_prompt}", agent.split("---\n", 2)[2])
            skills = run_dir / "kimi-skills"
            self.assertTrue(skills.is_dir())
            self.assertEqual(list(skills.iterdir()), [])
            for banned in NEVER_KIMI:
                self.assertNotIn(banned, argv)

    def test_grok_every_cell_every_role(self):
        for role, argv in self.check("grok", "grok", GROK_BASE, GROK_ROLES):
            for banned in NEVER_GROK:
                self.assertNotIn(banned, argv)
            if role != "implementer":
                self.assertNotIn("search_replace", " ".join(argv))

    def test_agy_every_cell_every_role(self):
        for role, argv in self.check("agy", "gemini", AGY_BASE, AGY_ROLES):
            for banned in NEVER_AGY:
                self.assertNotIn(banned, argv)
            run_dir = self.dir / "runs" / ("%03d-%s" % (self.seq, role))
            kept = json.loads((run_dir / "agy-settings.json").read_text())
            self.assertEqual(kept["permissions"], AGY_PERMISSIONS[role])
            self.assertEqual(kept["toolPermission"], "request-review")
            self.assertIs(kept["allowNonWorkspaceAccess"], False)
            self.assertIs(kept["enableTerminalSandbox"], True)
            # agy read the same file under the HOME it was given, and that
            # HOME is gone once the dispatch is over.
            first = (run_dir / "events.jsonl").read_text().splitlines()[0]
            init = json.loads(first)["init"]
            self.assertEqual(json.loads(init["fake_settings"]), kept)
            self.assertNotEqual(init["fake_home"], self.box.env["HOME"])
            self.assertFalse(Path(init["fake_home"]).exists())

    def test_muse_every_cell_every_role(self):
        for role, argv in self.check("muse", "muse", MUSE_BASE, MUSE_ROLES):
            self.assertEqual(argv[0], "exec")
            for banned in NEVER_MUSE:
                self.assertNotIn(banned, argv)

    def test_grok_muse_agy_environment(self):
        moved = {"HOME", "BOTTEGA_DATA_HOME"}
        for name, profile, extra, more in (
            ("grok", "grok", GROK_ENV, set()),
            ("muse", "muse", {"MUSE_NO_AUTO_UPDATE": "1", **GH_GUARD}, set()),
            ("agy", "gemini", GH_GUARD, moved),
        ):
            with self.subTest(harness=name):
                self.assertEqual(harness.HARNESS_MATRIX[name]["env"], extra)
                self.assertEqual(
                    harness.HARNESS_MATRIX[name]["git_config"],
                    {"remote.origin.pushurl": "bottega-push-disabled://"},
                )
                outcome, entry = self.dispatch("implementer", profile)
                self.assertTrue(outcome.ok, outcome.record)
                names = set(outcome.record["env"]["set"])
                self.assertEqual(names, set(extra) | PUSH_GUARD | more)
                self.assertLessEqual(names, set(entry["env_names"]))

    def test_grok_muse_agy_block_push_and_gh(self):
        probe = (
            "import os, subprocess, sys; "
            "url = subprocess.run(['git', 'config', '--get', 'remote.origin.pushurl'], "
            "capture_output=True, text=True).stdout.strip(); "
            "sys.stderr.write('pushurl=%s gh=%s\\n' % (url, os.environ['GH_TOKEN']))"
        )
        for profile in ("grok", "muse", "gemini"):
            with self.subTest(profile=profile):
                outcome, _ = self.dispatch(
                    "implementer", profile, default={"run": [["python3", "-c", probe]]}
                )
                self.assertTrue(outcome.ok, outcome.record)
                stderr = (outcome.run_dir / "stderr.log").read_text()
                self.assertIn("pushurl=bottega-push-disabled://", stderr)
                self.assertIn("gh=bottega-gh-disabled", stderr)

    def test_agy_sign_in_and_task_data(self):
        """With HOME moved, agy still finds your sign-in through a link,
        `bottega signal` is pointed at this kit's task data, and the SSH
        markers that would keep agy off the keychain are removed. (The loop
        suite has an agy reviewer and judge signal.)"""
        sign_in = Path(self.box.env["HOME"], ".gemini", "antigravity-cli")
        sign_in.mkdir(parents=True)
        (sign_in / "antigravity-oauth-token").write_text("not read\n")
        probe = (
            "import os, sys; "
            "sys.stderr.write('data=%s\\n' % os.environ['BOTTEGA_DATA_HOME'])"
        )
        outcome, entry = self.dispatch(
            "reviewer",
            "gemini",
            default={"run": [["python3", "-c", probe]]},
            extra_env={"SSH_CLIENT": "10.0.0.1 1 22", "SSH_TTY": "/dev/ttys009"},
        )
        self.assertTrue(outcome.ok, outcome.record)
        data = Path(self.box.env["XDG_DATA_HOME"]) / "bottega-kit"
        self.assertIn("data=%s\n" % data, (outcome.run_dir / "stderr.log").read_text())
        # The sign-in is a link to your file, never a copy of it.
        first = (outcome.run_dir / "events.jsonl").read_text().splitlines()[0]
        init = json.loads(first)["init"]
        self.assertEqual(init["fake_sign_in"], str(sign_in / "antigravity-oauth-token"))
        # Deleting the dispatch's HOME left your file alone.
        self.assertEqual(
            (sign_in / "antigravity-oauth-token").read_text(), "not read\n"
        )
        env = outcome.record["env"]
        self.assertNotIn("GIT_CONFIG_GLOBAL", env["set"])
        self.assertEqual(env["removed"], ["SSH_CLIENT", "SSH_TTY"])
        self.assertFalse({"SSH_CLIENT", "SSH_TTY"} & set(entry["env_names"]))

    def test_kimi_environment(self):
        outcome, entry = self.dispatch("implementer", "kimi")
        self.assertTrue(outcome.ok, outcome.record)
        names = set(outcome.record["env"]["set"])
        self.assertLessEqual(set(KIMI_ENV), names)
        self.assertLessEqual(
            {"GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"}, names
        )
        self.assertLessEqual(names, set(entry["env_names"]))
        # The effort reached Kimi Code: the fake writes it into the session log.
        self.assertEqual(outcome.record["usage"]["thinking_effort"], ["high"])

    def test_kimi_blocks_push_and_gh(self):
        probe = (
            "import os, subprocess, sys; "
            "url = subprocess.run(['git', 'config', '--get', 'remote.origin.pushurl'], "
            "capture_output=True, text=True).stdout.strip(); "
            "sys.stderr.write('pushurl=%s gh=%s\\n' % (url, os.environ['GH_TOKEN']))"
        )
        outcome, _ = self.dispatch(
            "implementer", "kimi", default={"run": [["python3", "-c", probe]]}
        )
        self.assertTrue(outcome.ok, outcome.record)
        stderr = (outcome.run_dir / "stderr.log").read_text()
        self.assertIn("pushurl=bottega-push-disabled://", stderr)
        self.assertIn("gh=bottega-kimi-gh-disabled", stderr)

    def test_kimi_git_config_follows_the_users(self):
        from bottega.harness import kimi

        env = kimi.git_config_env({"GIT_CONFIG_COUNT": "2"}, {"a.b": "c"})
        self.assertEqual(
            env,
            {
                "GIT_CONFIG_KEY_2": "a.b",
                "GIT_CONFIG_VALUE_2": "c",
                "GIT_CONFIG_COUNT": "3",
            },
        )

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
        self.assertEqual(
            set(harness.HARNESS_MATRIX),
            {"agy", "claude", "codex", "grok", "kimi", "muse"},
        )
        self.assertEqual(
            {k: list(v) for k, v in harness.HARNESS_MATRIX["kimi"]["tools"].items()},
            KIMI_TOOLS,
        )
        self.assertEqual(harness.HARNESS_MATRIX["kimi"]["env"], KIMI_ENV)
        self.assertEqual(
            harness.HARNESS_MATRIX["kimi"]["git_config"],
            {"remote.origin.pushurl": "bottega-push-disabled://"},
        )
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
        self.assertEqual(record["provider_reported_model"], "claude-opus-5-5")
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

    def test_kimi_final_usage_and_requested_only_identity(self):
        step = {
            "final": "K",
            "events": [
                {"role": "assistant", "tool_calls": [{"id": "t1"}]},
                {"role": "tool", "tool_call_id": "t1", "content": "1\tx"},
                {"role": "assistant", "content": [{"type": "text", "text": "early"}]},
            ],
        }
        outcome, _ = self.dispatch("reviewer", "kimi", default=step)
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.final, "K")
        record = outcome.record
        self.assertEqual(record["model_identity_source"], "requested-only")
        self.assertIsNone(record["provider_reported_model"])
        self.assertEqual(record["observed_models"], [])
        self.assertIsNone(record["cost_usd"])
        usage = record["usage"]
        self.assertEqual(usage["session_id"], "session_fake-1")
        self.assertEqual(usage["requested_models"], ["kimi-code/k3.1-pro", "k3.1-pro"])
        self.assertEqual(usage["tokens"]["inputOther"], 300)
        self.assertEqual(usage["tokens"]["output"], 60)
        self.assertEqual(usage["turn_endings"], ["completed"])
        self.assertEqual(record["num_turns"], 1)

    def test_kimi_session_id_is_never_a_pattern(self):
        from bottega.harness import kimi

        for bad in ("../x", "session_*", "a/b", "[x]", "", None):
            event = {"role": "meta", "type": "session.resume_hint", "session_id": bad}
            self.assertIsNone(kimi._session_id([event]), bad)
        good = {"type": "session.resume_hint", "session_id": "session_7bdc-01"}
        self.assertEqual(kimi._session_id([good]), "session_7bdc-01")

    def test_kimi_without_a_session_log(self):
        outcome, _ = self.dispatch("planner", "kimi", default={"no_session_log": True})
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.record["usage"], {"session_id": "session_fake-1"})
        self.assertIsNone(outcome.record["num_turns"])

    def test_parsers_tolerate_unknown_and_malformed_lines(self):
        raw = 'not json\n[1, 2]\n{"type": "mystery", "data": {"x": 1}}\n\n'
        for name in ("opus-builder", "sol-builder", "kimi"):
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

    def test_identity_mismatch_in_a_content_model_field(self):
        for step in (
            {"model": "claude-other"},
            {"assistant_model": "claude-other"},
        ):
            with self.subTest(step=step):
                outcome, _ = self.dispatch("planner", "opus-builder", default=step)
                self.assertEqual(outcome.reason, "identity-mismatch")
                error = self.error(outcome)
                self.assertEqual(error["phase"], "identity")
                self.assertIn("claude-other", error["detail"])
        outcome, _ = self.dispatch("planner", "sol-builder", default={"model": "gpt-x"})
        self.assertEqual(outcome.reason, "identity-mismatch")

    def test_helper_models_in_model_usage_are_observed_not_checked(self):
        step = {"usage_extra": ["claude-haiku-5-5"]}
        outcome, _ = self.dispatch("planner", "opus-builder", default=step)
        self.assertTrue(outcome.ok, outcome.record)
        record = outcome.record
        self.assertEqual(record["identity_models"], ["claude-opus-5-5"])
        self.assertEqual(
            sorted(record["observed_models"]), ["claude-haiku-5-5", "claude-opus-5-5"]
        )
        self.assertEqual(record["provider_reported_model"], "claude-opus-5-5")
        # A modelUsage key alone, even with no helper, is never compared.
        outcome, _ = self.dispatch(
            "planner", "opus-builder", default={"usage_model": "claude-other"}
        )
        self.assertTrue(outcome.ok, outcome.record)
        # The content model still is.
        step = {"usage_extra": ["claude-haiku-5-5"], "assistant_model": "claude-x"}
        outcome, _ = self.dispatch("planner", "opus-builder", default=step)
        self.assertEqual(outcome.reason, "identity-mismatch")
        self.assertIn("claude-x", self.error(outcome)["detail"])
        self.assertNotIn("haiku", self.error(outcome)["detail"])

    def test_claude_parser_identity_lists(self):
        stream = "\n".join(
            json.dumps(event)
            for event in (
                {"type": "system", "subtype": "init", "model": "claude-opus-5-5"},
                {"type": "assistant", "message": {"model": "claude-opus-5-5"}},
                {
                    "type": "result",
                    "result": "done",
                    "modelUsage": {"claude-opus-5-5": {}, "claude-haiku-5-5": {}},
                },
            )
        )
        parsed = harness.get("claude").parse(self.box.root, stream, "", 0)
        self.assertEqual(parsed.identity_models, ["claude-opus-5-5"])
        self.assertEqual(parsed.models, ["claude-opus-5-5", "claude-haiku-5-5"])
        self.assertEqual(
            harness.identity("claude-opus-5-5", parsed.identity_models, None),
            ("provider-reported", []),
        )

    def test_codex_identity_from_session_and_turn_events_only(self):
        step = {
            "events": [
                {"type": "item.completed", "item": {"type": "tool_call"}},
                {"type": "item.updated", "payload": {"model": "helper-model"}},
                {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
            ]
        }
        outcome, _ = self.dispatch("planner", "sol-builder", default=step)
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.record["identity_models"], ["gpt-5.6-sol"])
        self.assertIn("helper-model", outcome.record["observed_models"])
        step = {"events": [{"type": "session_configured", "msg": {"model": "gpt-x"}}]}
        outcome, _ = self.dispatch("planner", "sol-builder", default=step)
        self.assertEqual(outcome.reason, "identity-mismatch")

    def test_grok_identity_cost_and_the_unknown_model(self):
        outcome, _ = self.dispatch(
            "reviewer", "grok", default={"final": "G", "usage_extra": ["grok-helper"]}
        )
        self.assertTrue(outcome.ok, outcome.record)
        record = outcome.record
        self.assertEqual(outcome.final, "G")
        self.assertEqual(record["model_identity_source"], "provider-reported")
        self.assertEqual(record["provider_reported_model"], "grok-4.7")
        self.assertEqual(record["identity_models"], ["grok-4.7"])
        self.assertIn("grok-helper", record["observed_models"])
        self.assertEqual(record["cost_usd"], 0.0123)
        # "unknown" is Grok's word for no model: dropped, never a mismatch.
        outcome, _ = self.dispatch("planner", "grok", default={"model": "unknown"})
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.record["model_identity_source"], "requested-only")
        self.assertEqual(outcome.record["observed_models"], [])
        outcome, _ = self.dispatch(
            "planner", "grok", default={"assistant_model": "grok-4.5"}
        )
        self.assertEqual(outcome.reason, "identity-mismatch")

    def test_agy_final_usage_and_requested_only(self):
        step = {
            "final": "the verdict",
            "events": [
                {
                    "event": "step_update",
                    "step_update": {
                        "step_type": "agent_response",
                        "state": "ACTIVE",
                        "text_delta": "Reading.",
                    },
                },
                {
                    "event": "step_update",
                    "step_update": {
                        "step_type": "tool",
                        "state": "DONE",
                        "tool_name": "view_file",
                    },
                },
            ],
        }
        outcome, _ = self.dispatch("reviewer", "gemini", default=step)
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.final, "the verdict")
        record = outcome.record
        self.assertEqual(record["model_identity_source"], "requested-only")
        self.assertIsNone(record["provider_reported_model"])
        self.assertEqual(record["observed_models"], ["gemini-3.8-flash-high"])
        self.assertIsNone(record["cost_usd"])
        self.assertEqual(record["duration_ms"], 1500)
        self.assertEqual(record["num_turns"], 2)
        usage = record["usage"]
        self.assertEqual(usage["conversation_id"], "fake-agy-conversation-1")
        self.assertEqual(usage["tokens"]["cache_read_tokens"], 30)
        # An empty response: the text after the last tool step is the final.
        step = dict(step, no_response=True)
        outcome, _ = self.dispatch("reviewer", "gemini", default=step)
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.final, "the verdict")
        for step in ({"is_error": True}, {"no_final": True}):
            with self.subTest(step=step):
                outcome, _ = self.dispatch("planner", "gemini", default=step)
                self.assertEqual(outcome.reason, "dispatch-failed")
                self.assertEqual(self.error(outcome)["phase"], "parse")

    def test_muse_final_usage_and_identity(self):
        outcome, _ = self.dispatch("reviewer", "muse", default={"final": "M"})
        self.assertTrue(outcome.ok, outcome.record)
        self.assertEqual(outcome.final, "M")
        record = outcome.record
        self.assertEqual(record["model_identity_source"], "provider-reported")
        self.assertEqual(record["provider_reported_model"], "muse-wonder-1.0")
        self.assertIsNone(record["cost_usd"])
        usage = record["usage"]
        self.assertEqual(usage["session_id"], "fake-muse-session-1")
        self.assertEqual(usage["tokens"]["input_tokens"], 300)
        self.assertEqual(usage["tokens"]["cached_tokens"], 1200)
        self.assertEqual(usage["calls"], 2)
        outcome, _ = self.dispatch(
            "planner", "muse", default={"model": "muse-spark-1.3"}
        )
        self.assertEqual(outcome.reason, "identity-mismatch")
        for step in ({"is_error": True}, {"no_final": True}):
            with self.subTest(step=step):
                outcome, _ = self.dispatch("planner", "muse", default=step)
                self.assertEqual(outcome.reason, "dispatch-failed")
                self.assertEqual(self.error(outcome)["phase"], "parse")

    def test_muse_without_a_model_name_rests_on_the_request(self):
        stream = json.dumps(
            {
                "stream": {"kind": "session", "id": "s1"},
                "payload": {"kind": "run_usage", "models": [{"model": None}]},
            }
        )
        parsed = harness.get("muse").parse(self.box.root, stream, "", 0)
        self.assertEqual(parsed.identity_models, [])
        self.assertIsNone(parsed.final)

    def test_alias_is_accepted(self):
        self.cfg["profiles"]["opus-builder"]["aliases"] = ["claude-other"]
        outcome, _ = self.dispatch(
            "planner", "opus-builder", default={"assistant_model": "claude-other"}
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
        self.cfg["profiles"]["fable"].update(cfg_changes)
        self.box.write_config(self.cfg)
        fake = FakeCalls(self.box, default=step)
        return self.box.bottega("plan", self.task, rc=rc, env=fake.env)

    def test_identity_mismatch_exits_3_with_error_json(self):
        proc = self.plan({"model": "claude-impostor"})
        self.assertRegex(
            proc.stdout,
            r"^001 planner fable claude-fable-5-1 \u2192 failed "
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
            ok, detail = harness.get("kimi").check()
            self.assertTrue(ok)
            self.assertIn("2.3.1", detail)
            os.environ["PATH"] = "/usr/bin:/bin"
            ok, detail = harness.get("claude").check()
            self.assertFalse(ok)
            self.assertEqual(detail, "not on PATH")


if __name__ == "__main__":
    main()
