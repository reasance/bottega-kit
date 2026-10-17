#!/usr/bin/env python3
"""bottega pr: real git with a local bare origin, a fake gh first on PATH.

origin is configured as https://github.com/acme/app.git and rewritten to the
local bare repository with `url.<bare>.insteadOf`, so pushes are real and
gh is given a real-looking host/owner/repo.
"""

import json
import subprocess
import unittest

from helpers import BOTTEGA, GIT_IDENTITY, ROOT, main
from loop import LoopFixture, implement, judge, review

from bottega.commands import pr as pr_command

FAKE_GH = ROOT / "tests" / "fake-gh"
ORIGIN_URL = "https://github.com/acme/app.git"
GH_REPO = "github.com/acme/app"
PR_URL = "https://github.com/acme/app/pull/7"
WORK = {"feature.txt": "dry run\n"}


class PrFixture(LoopFixture):
    def setUp(self):
        super().setUp()
        self.bare = self.box.work / "app-origin.git"
        self.box.git("remote", "set-url", "origin", ORIGIN_URL, cwd=self.repo)
        self.box.git(
            "config", "url.%s.insteadOf" % self.bare, ORIGIN_URL, cwd=self.repo
        )
        self.gh_log = self.box.root / "gh-calls.jsonl"

    def done_task(self, writes=WORK, run=None):
        self.approved()
        step = implement(writes=writes)
        if run:
            step["run"] = run
        self.run_(step, review("ready", "all good"), judge("ready", "merge it"))
        return self.task

    def pr(self, rc=0, view=None, create=None, path=None, env=None):
        scenario = {"log": str(self.gh_log), "view": view or {}}
        scenario["create"] = create or {"url": PR_URL}
        extra = {
            "BOTTEGA_FAKE_GH": json.dumps(scenario),
            "PATH": path or "%s:%s" % (FAKE_GH, self.box.env["PATH"]),
        }
        extra.update(env or {})
        return self.box.bottega("pr", self.task, rc=rc, env=extra)

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]

    def wt_git(self, *args):
        return self.box.git(*args, cwd=self.state()["worktree"])

    def origin_branches(self):
        out = self.box.git("branch", "--format=%(refname:short)", cwd=self.bare)
        return out.split()

    def option(self, argv, name):
        return argv[argv.index(name) + 1]


class Pr(PrFixture, unittest.TestCase):
    def test_done_commits_pushes_and_creates(self):
        self.done_task()
        branch = "bottega/" + self.task
        proc = self.pr()
        self.assertEqual(proc.stdout, PR_URL + "\n")

        # One commit with the title and the task id; nothing left behind.
        message = self.wt_git("log", "-1", "--format=%B")
        self.assertEqual(message, "Dry run\n\nbottega task %s" % self.task)
        self.assertEqual(self.wt_git("status", "--porcelain"), "")
        self.assertEqual(self.wt_git("show", "HEAD:feature.txt"), "dry run")
        head = self.wt_git("rev-parse", "HEAD")

        # Pushed to origin, the branch tracks it.
        self.assertIn(branch, self.origin_branches())
        self.assertEqual(self.box.git("rev-parse", branch, cwd=self.bare), head)
        self.assertEqual(
            self.wt_git("rev-parse", "--abbrev-ref", "@{upstream}"), "origin/" + branch
        )

        # gh: view, then create, both pinned to origin's repository.
        calls = self.gh_calls()
        self.assertEqual(
            [c["argv"][:2] for c in calls], [["pr", "view"], ["pr", "create"]]
        )
        view, create = calls[0]["argv"], calls[1]["argv"]
        self.assertEqual(view[2], branch)
        self.assertEqual(self.option(view, "--repo"), GH_REPO)
        self.assertEqual(self.option(create, "--repo"), GH_REPO)
        self.assertEqual(self.option(create, "--base"), "main")
        self.assertEqual(self.option(create, "--head"), branch)
        self.assertEqual(self.option(create, "--title"), "Dry run")
        task_dir = self.box.task_dir(self.task)
        self.assertEqual(
            self.option(create, "--body-file"), str(task_dir / "pr-body.md")
        )
        self.assertNotIn("merge", " ".join(a for c in calls for a in c["argv"][:2]))

        body = calls[1]["body"]
        self.assertTrue(body.startswith("## Overview\n\nAdd a --dry-run flag"), body)
        self.assertIn("## What was verified\n\n**Status:** READY", body)
        self.assertIn("Rounds used: 1 of 3", body)
        self.assertIn("## Verdict\n\n**Merge:** yes", body)
        self.assertNotIn("Stopped", body)
        self.assertNotIn("task.md", body)
        self.assertNotIn("<!--", body)
        self.assertTrue(
            body.endswith("Opened by bottega-kit for task %s.\n" % self.task), body
        )

        st = self.state()
        self.assertEqual(st["phase"], "done")
        self.assertEqual(st["pr"]["url"], PR_URL)
        self.assertEqual(st["pr"]["commit"], head)
        self.assertTrue(st["pr"]["at"])
        self.assertIn("pr        " + PR_URL, self.box.bottega("show", self.task).stdout)

    def test_stopped_task_body_states_the_stop(self):
        self.approved()
        why = "needs a staging credential"
        self.run_(implement(writes=WORK), review("blocked", why), rc=3)
        self.assertEqual(self.pr().stdout, PR_URL + "\n")
        body = self.gh_calls()[-1]["body"]
        self.assertTrue(body.startswith("**Stopped: blocked — %s**" % why), body)
        self.assertIn("**Status:** BLOCKED", body)
        self.assertIn("Rounds used: 1 of 3", body)
        self.assertNotIn("## Verdict", body)  # the judge never ran
        self.assertEqual(self.state()["phase"], "stopped")

    def test_existing_pr_prints_its_url_and_creates_nothing(self):
        self.done_task()
        proc = self.pr(view={"url": PR_URL})
        self.assertEqual(proc.stdout, "pr exists: %s\n" % PR_URL)
        self.assertEqual([c["argv"][:2] for c in self.gh_calls()], [["pr", "view"]])
        self.assertIn("bottega/" + self.task, self.origin_branches())
        self.assertEqual(self.state()["pr"]["url"], PR_URL)

    def test_a_closed_pr_is_not_reused(self):
        self.done_task()
        self.pr(view={"url": PR_URL, "state": "CLOSED"}, create={"url": PR_URL + "8"})
        self.assertEqual(self.gh_calls()[-1]["argv"][:2], ["pr", "create"])

    def test_nothing_to_commit_still_pushes(self):
        commit = [["git", "add", "-A"], ["git", "commit", "-q", "-m", "by the agent"]]
        self.done_task(run=commit)
        head = self.wt_git("rev-parse", "HEAD")
        self.pr()
        self.assertEqual(self.wt_git("rev-parse", "HEAD"), head)  # no new commit
        self.assertEqual(self.wt_git("log", "-1", "--format=%s"), "by the agent")
        self.assertEqual(
            self.box.git("rev-parse", "bottega/" + self.task, cwd=self.bare), head
        )
        self.assertEqual(self.gh_calls()[-1]["argv"][:2], ["pr", "create"])

    def test_nothing_to_submit_is_refused(self):
        self.done_task(writes={})
        proc = self.pr(rc=2)
        self.assertIn("nothing to submit", proc.stderr)
        self.assertEqual(self.gh_calls(), [])
        self.assertNotIn("bottega/" + self.task, self.origin_branches())


class Refusals(PrFixture, unittest.TestCase):
    def assert_untouched(self):
        self.assertEqual(self.gh_calls(), [])
        self.assertNotIn("bottega/" + self.task, self.origin_branches())
        self.assertIsNone(self.state().get("pr"))

    def test_approved_task_is_refused(self):
        self.approved()
        proc = self.pr(rc=2)
        self.assertIn(
            "is approved; bottega pr needs a task that is done or stopped", proc.stderr
        )
        self.assert_untouched()

    def test_no_origin_is_refused(self):
        self.done_task()
        self.box.git("remote", "remove", "origin", cwd=self.repo)
        proc = self.pr(rc=2)
        self.assertIn("no origin remote", proc.stderr)
        self.assertEqual(self.gh_calls(), [])
        self.assertNotEqual(self.wt_git("status", "--porcelain"), "")  # no commit

    def test_origin_that_is_not_a_github_url_is_refused(self):
        self.done_task()
        self.box.git("remote", "set-url", "origin", str(self.bare), cwd=self.repo)
        proc = self.pr(rc=2)
        self.assertIn("not a host/owner/repo URL", proc.stderr)
        self.assert_untouched()

    def test_gh_missing_is_refused_before_anything_changes(self):
        self.done_task()
        proc = self.pr(rc=2, path=self.box.env["PATH"])
        self.assertIn("gh is not on PATH", proc.stderr)
        self.assert_untouched()
        self.assertNotEqual(self.wt_git("status", "--porcelain"), "")

    def test_gh_create_failure_is_refused_with_its_message(self):
        self.done_task()
        proc = self.pr(rc=2, create={"exit": 1, "stderr": "GraphQL: base not found\n"})
        self.assertIn("gh pr create failed", proc.stderr)
        self.assertIn("GraphQL: base not found", proc.stderr)
        self.assertIsNone(self.state().get("pr"))

    def test_commit_without_identity_is_refused_with_gits_message(self):
        self.done_task()
        self.box.git("config", "user.useConfigOnly", "true", cwd=self.repo)
        env = {k: v for k, v in self.box.env.items() if k not in GIT_IDENTITY}
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["BOTTEGA_FAKE_GH"] = json.dumps({"log": str(self.gh_log)})
        env["PATH"] = "%s:%s" % (FAKE_GH, env["PATH"])
        proc = subprocess.run(
            [str(BOTTEGA), "pr", self.task],
            cwd=str(self.box.work),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("git commit failed", proc.stderr)
        self.assertRegex(proc.stderr, "(?i)identity|email")
        self.assert_untouched()


class GhRepo(unittest.TestCase):
    def test_remote_url_forms(self):
        cases = {
            "https://github.com/acme/app.git": "github.com/acme/app",
            "https://github.com/acme/app": "github.com/acme/app",
            "https://user@ghe.example.com/team/tool.git/": "ghe.example.com/team/tool",
            "ssh://git@github.com:22/acme/app.git": "github.com/acme/app",
            "git@github.com:acme/app.git": "github.com/acme/app",
            "github.com:acme/app": "github.com/acme/app",
        }
        for url, expected in cases.items():
            self.assertEqual(pr_command.gh_repo(url), expected, url)
        for url in ("/tmp/app-origin.git", "file:///tmp/app.git", "../app", ""):
            self.assertIsNone(pr_command.gh_repo(url), url)


if __name__ == "__main__":
    main()
