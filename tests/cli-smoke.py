#!/usr/bin/env python3
"""The CLI end to end against the fakes: version, init, doctor, new, show,
list, rm, and the subcommands later milestones implement."""

import datetime
import json
import re
import shutil
import unittest

from helpers import ROOT, Sandbox, main

from bottega.commands import new as new_command

VERSION = re.search(
    r'__version__ = "([^"]+)"', (ROOT / "bin/lib/bottega/version.py").read_text()
).group(1)
TASK_ID = re.compile(r"^\d{8}-\d{4}-[a-z0-9-]+$")


class Basics(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)

    def test_version(self):
        proc = self.box.bottega("--version")
        self.assertEqual(proc.stdout.strip(), "bottega-kit " + VERSION)

    def test_bad_invocation_is_64(self):
        self.box.bottega(rc=64)
        self.box.bottega("frobnicate", rc=64)
        self.box.bottega("show", rc=64)

    def test_unimplemented_subcommands_exit_64(self):
        for command in ("plan", "approve", "run", "resume", "pr"):
            proc = self.box.bottega(command, "some-task", "--rounds", "2", rc=64)
            self.assertIn("not implemented in this milestone", proc.stderr)

    def test_init_then_doctor(self):
        proc = self.box.bottega("init")
        self.assertIn("harnesses found on PATH: claude, codex", proc.stdout)
        written = json.loads(self.box.config_file.read_text())
        self.assertEqual(written["roles"]["planner"], "fable-judge")
        self.assertEqual(written["profiles"]["sol-builder"]["harness"], "codex")
        self.box.bottega("init", rc=2)
        self.box.config_file.write_text("{}")
        self.box.bottega("init", "--force")
        self.assertEqual(json.loads(self.box.config_file.read_text()), written)

        report = json.loads(self.box.bottega("doctor", "--json").stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["version"], VERSION)
        by_check = {c["check"]: c for c in report["checks"]}
        self.assertEqual(by_check["gh"]["status"], "warn")  # not on the test PATH
        self.assertEqual(by_check["git"]["status"], "ok")
        self.assertIn("2.1.302 (Claude Code)", by_check["role planner"]["detail"])
        self.assertIn("claude-fable-5-1", by_check["role judge"]["detail"])
        text = self.box.bottega("doctor").stdout
        self.assertIn("[WARN] gh", text)
        self.assertIn("0 failure(s)", text)

    def test_init_with_codex_only(self):
        only_codex = self.box.root / "only-codex"
        only_codex.mkdir()
        (only_codex / "codex").symlink_to(ROOT / "tests/fakes/codex")
        path = "%s:%s:/usr/bin:/bin" % (only_codex, self.box.root / "bin")
        self.box.bottega("init", env={"PATH": path})
        written = json.loads(self.box.config_file.read_text())
        self.assertEqual(set(written["roles"].values()), {"sol-builder"})
        self.box.bottega("doctor", env={"PATH": path})

    def test_doctor_without_config_fails(self):
        report = json.loads(self.box.bottega("doctor", "--json", rc=2).stdout)
        failed = [c for c in report["checks"] if c["status"] == "fail"]
        self.assertEqual([c["check"] for c in failed], ["config"])
        self.assertIn("bottega init", failed[0]["detail"])


class Tasks(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.repo = self.box.make_repo()
        self.box.bottega("init")

    def test_new_show_list_rm(self):
        request = self.box.root / "request.md"
        request.write_text("Please add `--dry-run`.\n\nIt must not write files.\n")
        proc = self.box.bottega(
            "new",
            "--repo",
            str(self.repo),
            "--title",
            "Smoke: dry run!",
            "--request-file",
            str(request),
        )
        task = proc.stdout.split()[1]
        self.assertRegex(task, TASK_ID)
        self.assertTrue(task.endswith("-smoke-dry-run"))
        task_dir = self.box.task_dir(task)
        self.assertEqual(task_dir.parent.name, "app")
        doc = (task_dir / "task.md").read_text()
        self.assertTrue(doc.startswith("# Task Smoke: dry run!\n"))
        self.assertIn("> Please add `--dry-run`.\n>\n> It must not write files.\n", doc)

        shown = json.loads(self.box.bottega("show", task, "--json").stdout)
        st = shown["state"]
        worktree = self.repo.parent / "app-worktrees" / task
        self.assertEqual(st["phase"], "new")
        self.assertEqual(st["worktree"], str(worktree))
        self.assertEqual(st["branch"], "bottega/" + task)
        self.assertEqual(st["base"], "main")
        self.assertEqual(st["repo"], str(self.repo))
        self.assertEqual(st["roles"], {})
        self.assertIsNone(st["approval"])
        self.assertEqual(shown["task_doc"], str(task_dir / "task.md"))
        self.assertTrue(worktree.is_dir())
        self.assertEqual(
            self.box.git("rev-parse", "--abbrev-ref", "HEAD", cwd=worktree),
            "bottega/" + task,
        )
        text = self.box.bottega("show", task[-10:]).stdout
        self.assertIn("phase     new", text)

        listing = self.box.bottega("list").stdout
        self.assertIn(task, listing)
        self.assertIn("Smoke: dry run!", listing)

        self.box.bottega("rm", task, rc=2)  # no tty, no --yes
        self.assertTrue(worktree.is_dir())
        out = self.box.bottega("rm", "--yes", task).stdout
        self.assertIn("removed worktree", out)
        self.assertIn("deleted branch bottega/" + task, out)
        self.assertFalse(worktree.exists())
        self.assertTrue((task_dir / "task.md").is_file())
        self.assertEqual(self.box.state(task)["phase"], "removed")
        self.assertIn("already removed", self.box.bottega("rm", "--yes", task).stdout)

    def test_new_from_inside_the_repo_and_from_stdin(self):
        sub = self.repo / "src"
        sub.mkdir()
        proc = self.box.bottega(
            "new",
            "--title",
            "From cwd",
            "--request-file",
            "-",
            cwd=sub,
            stdin="via stdin\n",
        )
        task = proc.stdout.split()[1]
        self.assertIn("> via stdin", (self.box.task_dir(task) / "task.md").read_text())

    def test_new_outside_a_repo_or_with_an_empty_request(self):
        self.box.bottega(
            "new", "--title", "x", "--request", "y", rc=64, cwd=self.box.root
        )
        self.box.bottega(
            "new", "--repo", str(self.repo), "--title", "x", "--request", " ", rc=64
        )
        self.box.bottega("new", "--repo", str(self.repo), "--title", "x", rc=64)

    def test_role_overrides(self):
        task = self.box.new_task(
            self.repo, "Mixed", "x", "--role", "implementer=sol-builder"
        )
        self.assertEqual(self.box.state(task)["roles"], {"implementer": "sol-builder"})
        proc = self.box.bottega(
            "new",
            "--repo",
            str(self.repo),
            "--title",
            "a",
            "--request",
            "b",
            "--role",
            "planner=auto",
            rc=2,
        )
        self.assertIn("not supported yet", proc.stderr)
        self.box.bottega(
            "new",
            "--repo",
            str(self.repo),
            "--title",
            "a",
            "--request",
            "b",
            "--role",
            "planner=missing",
            rc=2,
        )
        self.box.bottega(
            "new",
            "--repo",
            str(self.repo),
            "--title",
            "a",
            "--request",
            "b",
            "--role",
            "planner",
            rc=64,
        )

    def test_base_from_flag_and_from_bottega_json(self):
        self.box.git("branch", "develop", cwd=self.repo)
        task = self.box.new_task(self.repo, "Flag base", "x", "--base", "develop")
        self.assertEqual(self.box.state(task)["base"], "develop")
        (self.repo / "bottega.json").write_text('{"base": "develop"}')
        task = self.box.new_task(self.repo, "File base", "x")
        self.assertEqual(self.box.state(task)["base"], "develop")

    def test_failed_worktree_leaves_no_task(self):
        proc = self.box.bottega(
            "new",
            "--repo",
            str(self.repo),
            "--title",
            "a",
            "--request",
            "b",
            "--base",
            "no-such-branch",
            rc=2,
        )
        self.assertIn("no-such-branch", proc.stderr)
        self.assertEqual(self.box.bottega("list").stdout.strip(), "no tasks")
        # A worktree path already taken: the task directory is rolled back.
        now = datetime.datetime.now()
        blocker = self.repo.parent / "app-worktrees"
        for minute in (now, now + datetime.timedelta(minutes=1)):
            (blocker / ("%s-taken" % minute.strftime("%Y%m%d-%H%M"))).mkdir(
                parents=True
            )
        self.box.bottega(
            "new", "--repo", str(self.repo), "--title", "taken", "--request", "b", rc=2
        )
        self.assertEqual(self.box.bottega("list").stdout.strip(), "no tasks")

    def test_same_title_same_minute_gets_a_suffix(self):
        project = self.box.root / "project"
        now = datetime.datetime(2026, 10, 17, 9, 5)
        (project / "20261017-0905-same").mkdir(parents=True)
        self.assertEqual(
            new_command.task_id_for("Same", project, now), "20261017-0905-same-2"
        )

    def test_rm_after_the_repository_is_gone(self):
        task = self.box.new_task(self.repo, "Gone", "x")
        shutil.rmtree(self.repo)
        out = self.box.bottega("rm", "--yes", task).stdout
        self.assertIn("is gone; nothing to remove there", out)
        self.assertEqual(self.box.state(task)["phase"], "removed")

    def test_ambiguous_prefix(self):
        a = self.box.new_task(self.repo, "Alpha", "x")
        self.box.new_task(self.repo, "Beta", "x")
        proc = self.box.bottega("show", a[:8], rc=64)
        self.assertIn("matches several tasks", proc.stderr)


if __name__ == "__main__":
    main()
