#!/usr/bin/env python3
"""bottega plan against the fakes: questions, answers, plans, refusals, rails."""

import json
import os
import re
import unittest

from helpers import (
    CANONICAL,
    PLAN_MESSAGE,
    QUESTIONS_MESSAGE,
    FakeCalls,
    Sandbox,
    main,
)

from bottega import taskdoc

LINE = re.compile(
    r"^(\d{3}) planner (\S+) (\S+) → (planned|questions|failed \S+) "
    r"\((\d+s|\d+m\d{2}s)\)$"
)
REQUEST = "Add a --dry-run flag to `export`.\n\n  Keep the *old* output.\n"


class PlanFixture:
    def setUp(self):
        self.box = Sandbox(self)
        self.box.write_config(CANONICAL)
        self.repo = self.box.make_repo()
        self.task = self.box.new_task(self.repo, "Dry run", REQUEST)
        self.dir = self.box.task_dir(self.task)
        self.doc = self.dir / "task.md"

    def plan(self, *steps, rc=0, task=None):
        fake = FakeCalls(self.box, steps)
        proc = self.box.bottega("plan", task or self.task, rc=rc, env=fake.env)
        return proc, fake.entries()

    def first_line(self, proc):
        match = LINE.match(proc.stdout.splitlines()[0])
        self.assertIsNotNone(match, proc.stdout)
        return match


class Questions(PlanFixture, unittest.TestCase):
    def test_questions_then_answers_then_plan(self):
        proc, _ = self.plan({"final": QUESTIONS_MESSAGE})
        match = self.first_line(proc)
        self.assertEqual(
            match.group(1, 2, 3, 4),
            ("001", "fable", "claude-fable-5-1", "questions"),
        )
        self.assertIn("1. Should the dry run print JSON or text?", proc.stdout)
        st = self.box.state(self.task)
        self.assertEqual(st["phase"], "questions")
        self.assertEqual(st["runs"][0]["status"], "ok")
        self.assertIsNone(st["current_run"])
        doc = self.doc.read_text()
        titles = [t for t, _, _ in taskdoc.sections(doc)]
        self.assertEqual(
            titles.index("Questions for you") + 1, titles.index("Overview")
        )

        # The user answers inline; the next run sends the whole document.
        answered = doc.replace(
            "JSON is scriptable; text is shorter.",
            "JSON is scriptable; text is shorter.\n   Answer: text, please.",
        )
        self.doc.write_text(answered)
        proc, calls = self.plan({"final": QUESTIONS_MESSAGE + "\n2. Colour?"})
        self.assertEqual(self.first_line(proc).group(1, 4), ("002", "questions"))
        self.assertIn("Answer: text, please.", calls[0]["stdin"])
        doc = self.doc.read_text()
        self.assertEqual(doc.count("## Questions for you"), 1)  # replaced
        self.assertIn("2. Colour?", doc)
        self.assertNotIn("Answer: text", doc)

        proc, _ = self.plan({"final": PLAN_MESSAGE})
        self.assertEqual(proc.stdout.count("\n"), 1)  # exactly one line
        self.assertEqual(self.first_line(proc).group(1, 4), ("003", "planned"))
        doc = self.doc.read_text()
        self.assertNotIn("Questions for you", doc)
        self.assertEqual(
            [t for t, _, _ in taskdoc.sections(doc)],
            [
                "Original Request",
                "Overview",
                "Implementation Plan",
                "Testing Strategy",
                "To-Do List",
                "Project Docs Update",
                "Review Findings",
                "Verdict",
            ],
        )
        self.assertTrue(doc.startswith("# Task Dry run\n"))
        self.assertEqual(
            taskdoc.get_section(doc, "Original Request"),
            taskdoc.blockquote(REQUEST),
        )
        self.assertIn("bottega-kit writes this section", doc)  # findings kept
        st = self.box.state(self.task)
        self.assertEqual(st["phase"], "planned")
        self.assertEqual([r["seq"] for r in st["runs"]], [1, 2, 3])
        self.assertEqual({r["status"] for r in st["runs"]}, {"ok"})

    def test_prompt_carries_the_document_and_the_template(self):
        _, calls = self.plan({"final": PLAN_MESSAGE})
        stdin = calls[0]["stdin"]
        self.assertIn("<task-doc>\n# Task Dry run", stdin)
        self.assertIn(">   Keep the *old* output.", stdin)
        self.assertIn("<plan-template>\n## Overview", stdin)
        self.assertIn(str(self.doc), stdin)

    def test_replan_from_planned_and_fenced_message(self):
        self.plan({"final": PLAN_MESSAGE})
        fenced = "```markdown\n" + PLAN_MESSAGE.replace("Assumed", "Now") + "```\n"
        proc, _ = self.plan({"final": fenced})
        self.assertEqual(self.first_line(proc).group(4), "planned")
        self.assertIn("Now: text output.", self.doc.read_text())
        self.assertNotIn("```", self.doc.read_text())

    def test_extra_sections_and_owned_sections_from_the_planner(self):
        message = (
            "# Task Something else\n\n## Original Request\n\n> paraphrased\n\n"
            + PLAN_MESSAGE
            + "\n## Context files\n\n- export.py\n\n## Verdict\n\nship it\n"
        )
        self.plan({"final": message})
        doc = self.doc.read_text()
        self.assertTrue(doc.startswith("# Task Dry run\n"))
        self.assertNotIn("paraphrased", doc)
        self.assertNotIn("ship it", doc)
        self.assertIn("## Context files\n\n- export.py", doc)

    def test_codex_planner_through_a_task_override(self):
        other = self.box.new_task(
            self.repo, "Codex plans", "x", "--role", "planner=sol-builder"
        )
        proc, calls = self.plan({"final": PLAN_MESSAGE}, task=other)
        self.assertEqual(
            self.first_line(proc).group(2, 3, 4),
            ("sol-builder", "gpt-5.6-sol", "planned"),
        )
        self.assertEqual(calls[0]["tool"], "codex")
        self.assertIn("read-only", calls[0]["argv"])


class Refusals(PlanFixture, unittest.TestCase):
    def assert_failed(self, proc, reason, before, phase="new"):
        match = self.first_line(proc)
        self.assertEqual(match.group(4), "failed " + reason)
        self.assertEqual(self.doc.read_text(), before)
        run_dir = self.dir / "runs" / ("%s-planner" % match.group(1))
        error = json.loads((run_dir / "error.json").read_text())
        self.assertEqual(error["reason"], reason)
        record = json.loads((run_dir / "run.json").read_text())
        self.assertEqual((record["status"], record["reason"]), ("failed", reason))
        st = self.box.state(self.task)
        self.assertEqual(st["phase"], phase)
        self.assertEqual(st["runs"][-1]["status"], "failed")
        self.assertEqual(st["runs"][-1]["reason"], reason)
        self.assertIsNone(st["current_run"])
        self.assertIn(str(run_dir), proc.stderr)
        return run_dir, error

    def test_invalid_output_is_refused_and_the_receipt_kept(self):
        before = self.doc.read_text()
        proc, _ = self.plan({"final": "I think we should add the flag."}, rc=3)
        run_dir, error = self.assert_failed(proc, "planner-output-invalid", before)
        self.assertEqual(error["phase"], "parse")
        self.assertIn("missing section: ## Overview", error["detail"])
        self.assertEqual(
            (run_dir / "output.md").read_text(), "I think we should add the flag."
        )

    def test_plan_without_an_unchecked_item_is_refused(self):
        before = self.doc.read_text()
        ticked = PLAN_MESSAGE.replace("- [ ]", "- [x]")
        proc, _ = self.plan({"final": ticked}, rc=3)
        _, error = self.assert_failed(proc, "planner-output-invalid", before)
        self.assertIn("no unchecked item", error["detail"])

    def test_planner_that_modifies_the_worktree_is_stopped(self):
        before = self.doc.read_text()
        step = {"final": PLAN_MESSAGE, "writes": {"README.md": "changed\n"}}
        proc, _ = self.plan(step, rc=3)
        _, error = self.assert_failed(proc, "role-modified-worktree", before)
        self.assertEqual(error["phase"], "rails")

    def test_planner_that_commits_is_stopped(self):
        before = self.doc.read_text()
        step = {
            "final": PLAN_MESSAGE,
            "run": [["git", "commit", "-q", "--allow-empty", "-m", "sneaky"]],
        }
        proc, _ = self.plan(step, rc=3)
        self.assert_failed(proc, "role-modified-worktree", before)

    def test_new_untracked_file_is_only_a_warning(self):
        step = {"final": PLAN_MESSAGE, "writes": {".cache/x": "1"}}
        proc, _ = self.plan(step)
        self.assertEqual(self.first_line(proc).group(4), "planned")
        self.assertIn("new untracked file(s) in the worktree: .cache/x", proc.stderr)
        record = json.loads((self.dir / "runs/001-planner/run.json").read_text())
        self.assertEqual(record["rails"]["new_untracked"], [".cache/x"])

    def test_failure_from_questions_keeps_phase_questions(self):
        self.plan({"final": QUESTIONS_MESSAGE})
        before = self.doc.read_text()
        proc, _ = self.plan({"exit": 1, "stderr": "rate limited\n"}, rc=3)
        _, error = self.assert_failed(proc, "dispatch-failed", before, "questions")
        self.assertIn("rate limited", error["stderr_tail"])

    def test_wrong_phase_and_lock_are_refused(self):
        st = self.box.state(self.task)
        for phase in ("approved", "running", "done", "removed"):
            st["phase"] = phase
            (self.dir / "state.json").write_text(json.dumps(st))
            proc, calls = self.plan({"final": PLAN_MESSAGE}, rc=2)
            self.assertIn("is %s" % phase, proc.stderr)
            self.assertEqual(calls, [])
        st["phase"] = "new"
        (self.dir / "state.json").write_text(json.dumps(st))
        (self.dir / "lock").write_text("%d\n" % os.getpid())
        proc, calls = self.plan({"final": PLAN_MESSAGE}, rc=2)
        self.assertIn("locked", proc.stderr)
        self.assertEqual(calls, [])
        (self.dir / "lock").unlink()

    def test_unset_env_variable_refuses_before_dispatch(self):
        other = self.box.new_task(
            self.repo, "Proxied", "x", "--role", "planner=glm-reviewer"
        )
        proc, calls = self.plan({"final": PLAN_MESSAGE}, rc=2, task=other)
        self.assertIn("ZAI_API_KEY", proc.stderr)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    main()
