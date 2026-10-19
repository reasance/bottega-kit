#!/usr/bin/env python3
"""bottega approve: plan checks, [T<n>] ids, the plan hash, role validation."""

import json
import unittest

from helpers import CANONICAL, PLAN_MESSAGE, FakeCalls, Sandbox, main

from bottega import taskdoc


class ApproveFixture:
    def setUp(self):
        self.box = Sandbox(self)
        self.cfg = json.loads(json.dumps(CANONICAL))
        self.box.write_config(self.cfg)
        self.repo = self.box.make_repo()

    def planned(self, message=PLAN_MESSAGE, *extra):
        task = self.box.new_task(self.repo, "Dry run", "add --dry-run", *extra)
        fake = FakeCalls(self.box, [{"final": message}])
        self.box.bottega("plan", task, env=fake.env)
        self.task = task
        self.dir = self.box.task_dir(task)
        self.doc = self.dir / "task.md"
        return task

    def approve(self, *args, rc=0, env=None):
        return self.box.bottega("approve", self.task, *args, rc=rc, env=env)

    def configure(self, change):
        change(self.cfg)
        self.box.write_config(self.cfg)


class Approve(ApproveFixture, unittest.TestCase):
    def test_approve_assigns_ids_and_records_the_approval(self):
        self.planned()
        proc = self.approve("--rounds", "2")
        lines = proc.stdout.splitlines()
        self.assertEqual(lines[0], "approved %s" % self.task)
        self.assertIn(
            "  planner     fable (claude, claude-fable-5-1, effort max)", lines
        )
        self.assertIn(
            "  implementer opus-builder (claude, claude-opus-5-5, effort high)", lines
        )
        self.assertIn("rounds    2", lines)
        doc = self.doc.read_text()
        self.assertEqual(taskdoc.item_ids(doc), ["T1", "T2", "T3", "T4"])
        self.assertIn("- [ ] [T1] Parse --dry-run", doc)
        st = self.box.state(self.task)
        approval = st["approval"]
        self.assertEqual(approval["plan_sha256"], taskdoc.plan_sha256(doc))
        self.assertIn("plan      sha256 %s" % approval["plan_sha256"][:12], lines)
        self.assertEqual(
            approval["roles"],
            {
                "planner": "fable",
                "implementer": "opus-builder",
                "reviewer": "opus-reviewer",
                "judge": "fable",
            },
        )
        self.assertEqual(approval["rounds"], 2)
        self.assertTrue(approval["at"])
        self.assertEqual(
            (st["phase"], st["rounds"], st["next_role"]), ("approved", 2, "implementer")
        )

    def test_hash_is_stable_under_ticks_and_findings_and_broken_by_an_edit(self):
        self.planned()
        self.approve()
        approved = self.box.state(self.task)["approval"]["plan_sha256"]
        doc = self.doc.read_text()
        ticked = taskdoc.set_checked(doc, ["T1", "T3"], True)
        reviewed = taskdoc.replace_section(
            ticked, "Review Findings", "**Status:** NEEDS_WORK\n\n- T3 fails"
        )
        judged = taskdoc.replace_section(reviewed, "Verdict", "Not yet.")
        self.assertEqual(taskdoc.plan_sha256(ticked), approved)
        self.assertEqual(taskdoc.plan_sha256(judged), approved)
        unticked = taskdoc.set_checked(judged, ["T1"], False)
        self.assertEqual(taskdoc.plan_sha256(unticked), approved)
        edited = judged.replace("Assumed: text output.", "Assumed: JSON output.")
        self.assertNotEqual(taskdoc.plan_sha256(edited), approved)
        retitled = judged.replace("Parse --dry-run", "Parse --dry_run")
        self.assertNotEqual(taskdoc.plan_sha256(retitled), approved)

    def test_reapprove_after_an_edit_keeps_ids_and_the_cap(self):
        self.planned()
        self.approve("--rounds", "5")
        first = self.box.state(self.task)["approval"]
        doc = self.doc.read_text()
        doc = doc.replace(
            "- [ ] [T2] Skip writes when it is set",
            "- [ ] [T2] Skip writes when it is set\n- [ ] Log what would be written",
        )
        self.doc.write_text(doc)
        proc = self.approve()
        self.assertIn("1 new id(s)", proc.stdout)
        doc = self.doc.read_text()
        self.assertIn("- [ ] [T1] Parse --dry-run", doc)
        self.assertIn("- [ ] [T5] Log what would be written", doc)
        second = self.box.state(self.task)["approval"]
        self.assertNotEqual(first["plan_sha256"], second["plan_sha256"])
        self.assertEqual(second["rounds"], 5)
        self.approve("--rounds", "1")
        self.assertEqual(self.box.state(self.task)["rounds"], 1)

    def test_default_rounds_come_from_the_configuration(self):
        self.configure(lambda c: c.update(rounds=4))
        self.planned()
        self.approve()
        self.assertEqual(self.box.state(self.task)["approval"]["rounds"], 4)

    def test_task_override_is_frozen_and_judge_is_optional(self):
        def no_judge(cfg):
            del cfg["roles"]["judge"]

        self.configure(no_judge)
        self.planned(PLAN_MESSAGE, "--role", "implementer=sol-builder")
        proc = self.approve()
        self.assertIn("  judge       none", proc.stdout)
        self.assertIn("sol-builder (codex, gpt-5.6-sol, effort high)", proc.stdout)
        roles = self.box.state(self.task)["approval"]["roles"]
        self.assertEqual(roles["implementer"], "sol-builder")
        self.assertNotIn("judge", roles)


class Refusals(ApproveFixture, unittest.TestCase):
    def assert_refused(self, *args, text, env=None):
        before = self.doc.read_text()
        state_before = self.box.state(self.task)
        proc = self.approve(*args, rc=2, env=env)
        self.assertIn(text, proc.stderr)
        self.assertEqual(self.doc.read_text(), before)
        self.assertEqual(self.box.state(self.task), state_before)
        return proc

    def test_wrong_phase(self):
        self.task = self.box.new_task(self.repo, "Not planned")
        self.dir = self.box.task_dir(self.task)
        self.doc = self.dir / "task.md"
        self.assert_refused(text="approve needs a plan")

    def test_missing_profile(self):
        self.planned(PLAN_MESSAGE, "--role", "implementer=sol-builder")

        def drop(cfg):
            del cfg["profiles"]["sol-builder"]

        self.configure(drop)
        self.assert_refused(text="no profile named 'sol-builder'")

    def test_bad_effort(self):
        self.planned()
        self.configure(lambda c: c["profiles"]["opus-reviewer"].update(effort="ultra"))
        self.assert_refused(text="effort for harness claude must be one of")

    def test_auto_is_refused(self):
        self.planned()
        self.configure(lambda c: c["roles"].update(reviewer="auto"))
        self.assert_refused(text="'auto' is not supported yet")

    def test_missing_env_variable(self):
        self.planned()
        self.configure(lambda c: c["roles"].update(reviewer="glm-reviewer"))
        self.assert_refused(text="needs unset variable(s): ZAI_API_KEY")
        self.approve(env={"ZAI_API_KEY": "set"})
        roles = self.box.state(self.task)["approval"]["roles"]
        self.assertEqual(roles["reviewer"], "glm-reviewer")

    def test_harness_not_on_path(self):
        self.planned()
        path = "%s:/usr/bin:/bin" % (self.box.root / "bin")
        self.assert_refused(text="claude: not on PATH", env={"PATH": path})

    def test_plan_without_manual_qa_or_not_needed(self):
        message = PLAN_MESSAGE.replace("### Manual QA", "### Other checks").replace(
            "Not needed for this change.", "README gets a line."
        )
        self.planned(message)
        self.assert_refused(text="needs a ### Manual QA scenario")

    def test_not_needed_is_accepted(self):
        message = PLAN_MESSAGE.split("### Manual QA")[0] + (
            "### Manual QA\nNot needed: the change only edits a comment.\n\n"
            + "## To-Do List"
            + PLAN_MESSAGE.split("## To-Do List")[1]
        )
        self.planned(message)
        self.approve()

    def test_every_item_already_checked(self):
        self.planned()
        self.doc.write_text(self.doc.read_text().replace("- [ ]", "- [x]"))
        self.assert_refused(text="has no unchecked item")

    def test_duplicate_ids(self):
        self.planned()
        self.doc.write_text(
            self.doc.read_text()
            .replace("- [ ] Parse", "- [ ] [T1] Parse")
            .replace("- [ ] Skip", "- [ ] [T1] Skip")
        )
        self.assert_refused(text="duplicate to-do id(s): T1")

    def test_bad_rounds(self):
        self.planned()
        proc = self.approve("--rounds", "0", rc=64)
        self.assertIn("--rounds must be at least 1", proc.stderr)
        self.approve("--rounds", "two", rc=64)


if __name__ == "__main__":
    main()
