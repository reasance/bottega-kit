#!/usr/bin/env python3
"""bottega run and resume against the fakes: every row of the transition
table (plan §3), the refusals, the lock, resume, and show after a stop."""

import json
import os
import re
import signal
import subprocess
import time
import unittest

from helpers import BOTTEGA, CANONICAL, PLAN_MESSAGE, FakeCalls, Sandbox, main

from bottega import taskdoc

LINE = re.compile(
    r"^(\d{3}) (implementer|reviewer|judge) (\S+) (\S+) → (.+) "
    r"\((\d+s|\d+m\d{2}s)\)$"
)
ALL = ["T1", "T2", "T3", "T4"]


def implement(tick=ALL, **extra):
    return dict({"final": "implemented", "tick": list(tick)}, **extra)


def findings(status, issue="none"):
    return (
        "**Status:** %s\n\n### Checklist Verification\n- [T1] VERIFIED — ok\n\n"
        "### Unit Tests\n- Result: PASS\n\n### Manual Testing\n"
        "- [x] Scenario 1: PASS — ok\n\n### Issues to Address\n- %s\n" % (status, issue)
    )


def review(status, reason="", uncheck=(), final=None, **extra):
    signal = [status, reason] + (["--uncheck", *uncheck] if uncheck else [])
    word = status.upper().replace("-", "_")
    return dict({"final": final or findings(word, reason), "signal": signal}, **extra)


def judge(status, reason="", final="**Merge:** yes\n\n1. a\n2. b\n3. c"):
    return {"final": final, "signal": [status, reason]}


class LoopFixture:
    rounds = 3

    def setUp(self):
        self.box = Sandbox(self)
        self.cfg = json.loads(json.dumps(CANONICAL))
        self.box.write_config(self.cfg)
        self.repo = self.box.make_repo()

    def approved(self, *new_args, rounds=None, judge=True):
        if not judge:
            del self.cfg["roles"]["judge"]
            self.box.write_config(self.cfg)
        task = self.box.new_task(self.repo, "Dry run", "add --dry-run", *new_args)
        self.box.bottega("plan", task, env=FakeCalls(self.box, [PLAN_MESSAGE_STEP]).env)
        self.box.bottega("approve", task, "--rounds", str(rounds or self.rounds))
        self.task = task
        self.dir = self.box.task_dir(task)
        self.doc = self.dir / "task.md"
        return task

    def loop(self, command, *steps, rc=0, args=()):
        fake = FakeCalls(self.box, steps, task=self.task)
        proc = self.box.bottega(command, self.task, *args, rc=rc, env=fake.env)
        self.calls = fake.entries()
        self.lines = [LINE.match(line) for line in proc.stdout.splitlines()]
        self.assertTrue(all(self.lines), proc.stdout)
        return proc

    def run_(self, *steps, rc=0):
        return self.loop("run", *steps, rc=rc)

    def resume(self, *steps, rc=0, rounds=None):
        args = ("--rounds", str(rounds)) if rounds else ()
        return self.loop("resume", *steps, rc=rc, args=args)

    def assert_refused(self, command, text, *args):
        fake = FakeCalls(self.box, [implement()], task=self.task)
        before = self.state()
        proc = self.box.bottega(command, self.task, *args, rc=2, env=fake.env)
        self.assertIn(text, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(fake.entries(), [])
        self.assertEqual(self.state(), before)
        return proc

    def summary(self):
        """[(seq, role, result)] from the last command's stdout."""
        return [(int(m.group(1)), m.group(2), m.group(5)) for m in self.lines]

    def state(self):
        return self.box.state(self.task)

    def run_json(self, seq, role):
        path = self.dir / "runs" / ("%03d-%s" % (seq, role)) / "run.json"
        return json.loads(path.read_text())

    def section(self, title):
        return taskdoc.get_section(self.doc.read_text(), title)

    def checked(self):
        return {i.id: i.checked for i in taskdoc.todo_items(self.doc.read_text())}


PLAN_MESSAGE_STEP = {"final": PLAN_MESSAGE}


class Transitions(LoopFixture, unittest.TestCase):
    def test_ready_on_round_one_then_judge_ready(self):
        self.approved()
        proc = self.run_(implement(), review("ready", "all good"), judge("ready", "ok"))
        self.assertEqual(
            self.summary(),
            [
                (2, "implementer", "done"),
                (3, "reviewer", "ready"),
                (4, "judge", "ready"),
            ],
        )
        self.assertEqual(self.lines[0].group(3, 4), ("opus-builder", "claude-opus-5-5"))
        self.assertEqual(self.lines[2].group(3, 4), ("fable", "claude-fable-5-1"))
        self.assertEqual(proc.stdout.count("\n"), 3)  # nothing else on stdout
        self.assertIn("done", proc.stderr)
        st = self.state()
        self.assertEqual(st["phase"], "done")
        self.assertEqual((st["round"], st["rounds"]), (1, 3))
        self.assertIsNone(st["next_role"])
        self.assertIsNone(st["stopped"])
        self.assertIsNone(st["current_run"])
        self.assertEqual(st["last_signal"]["by"], "judge")
        self.assertEqual(st["last_signal"]["status"], "ready")
        self.assertTrue(self.section("Review Findings").startswith("**Status:** READY"))
        self.assertTrue(self.section("Verdict").startswith("**Merge:** yes"))
        self.assertEqual(set(self.checked().values()), {True})
        self.assertEqual(
            [(r["seq"], r["role"], r["status"], r.get("signal")) for r in st["runs"]],
            [
                (1, "planner", "ok", None),
                (2, "implementer", "ok", None),
                (3, "reviewer", "ok", "ready"),
                (4, "judge", "ok", "ready"),
            ],
        )
        record = self.run_json(3, "reviewer")
        self.assertEqual(record["signal"]["status"], "ready")
        self.assertEqual(record["round"], 1)
        # The prompts carry the round, the cap and the signal command.
        self.assertIn("round 1 of 3", self.calls[0]["stdin"])
        self.assertIn(
            "signal %s ready" % self.box.task_dir(self.task), self.calls[1]["stdin"]
        )
        self.assertNotIn("signal %s" % self.task, self.calls[0]["stdin"])

    def test_ready_without_a_judge_is_done(self):
        self.approved(judge=False)
        self.run_(implement(), review("ready"))
        self.assertEqual([r for _, r, _ in self.summary()], ["implementer", "reviewer"])
        self.assertEqual(self.state()["phase"], "done")
        self.assertIn("<!-- bottega-kit writes", self.section("Verdict"))

    def test_needs_work_twice_then_ready(self):
        self.approved()
        self.run_(
            implement(),
            review(
                "needs-work", "T2 is wrong", ["T2"], final=findings("NEEDS_WORK", "one")
            ),
            implement(["T2"]),
            review(
                "needs-work",
                "T4 failed",
                ["T4", "T2"],
                final=findings("NEEDS_WORK", "two"),
            ),
            implement(["T2", "T4"]),
            review("ready"),
            judge("ready"),
        )
        self.assertEqual(
            [r for _, r, _ in self.summary()],
            ["implementer", "reviewer"] * 3 + ["judge"],
        )
        doc = self.doc.read_text()
        self.assertEqual(doc.count("## Review Findings"), 1)
        self.assertEqual(doc.count("**Status:**"), 1)  # replaced, not appended
        self.assertNotIn("- two", doc)
        self.assertTrue(self.section("Review Findings").startswith("**Status:** READY"))
        st = self.state()
        self.assertEqual((st["phase"], st["round"]), ("done", 3))
        self.assertEqual([r["round"] for r in st["runs"][1:]], [1, 1, 2, 2, 3, 3, 3])
        # The unchecked items reached the implementer unchecked, and it ticked them.
        second_prompt = self.calls[2]["stdin"]
        self.assertIn("- [ ] [T2]", second_prompt)
        self.assertIn("- [x] [T1]", second_prompt)
        self.assertIn("- two", self.calls[4]["stdin"])
        third = self.calls[4]["stdin"]
        self.assertIn("- [ ] [T4]", third)
        self.assertIn("- [ ] [T2]", third)
        self.assertEqual(set(self.checked().values()), {True})
        self.assertEqual(
            self.run_json(5, "reviewer")["signal"]["uncheck"], ["T4", "T2"]
        )

    def test_blocked_stops_with_the_reason(self):
        self.approved()
        why = "needs a staging credential; tried the sandbox; give me access"
        proc = self.run_(implement(), review("blocked", why), rc=3)
        self.assertEqual(self.summary()[-1][1:], ("reviewer", "blocked"))
        self.assertIn("stopped: blocked: " + why, proc.stderr)
        st = self.state()
        self.assertEqual(st["phase"], "stopped")
        self.assertEqual(st["stopped"]["reason"], "blocked")
        self.assertEqual(st["stopped"]["detail"], why)
        self.assertEqual(st["next_role"], "reviewer")
        self.assertTrue(
            self.section("Review Findings").startswith("**Status:** BLOCKED")
        )

    def test_cap_reached_without_a_fourth_implementer(self):
        self.approved(rounds=3)
        steps = []
        for _ in range(3):
            steps += [implement(), review("needs-work", "again", ["T1"])]
        proc = self.run_(*steps, rc=3)
        roles = [r for _, r, _ in self.summary()]
        self.assertEqual(roles, ["implementer", "reviewer"] * 3)
        self.assertEqual(len(self.calls), 6)
        st = self.state()
        self.assertEqual(st["stopped"]["reason"], "cap-reached")
        self.assertEqual((st["round"], st["rounds"]), (3, 3))
        self.assertEqual(st["next_role"], "implementer")
        self.assertIn("stopped: cap-reached", proc.stderr)
        self.assertFalse(self.checked()["T1"])

        # resume --rounds 1 runs exactly one more pair.
        self.resume(implement(), review("needs-work", "still"), rc=3, rounds=1)
        self.assertEqual(
            self.summary(), [(8, "implementer", "done"), (9, "reviewer", "needs-work")]
        )
        st = self.state()
        self.assertEqual((st["round"], st["rounds"]), (4, 4))
        self.assertEqual(st["stopped"]["reason"], "cap-reached")
        self.assertIn("round 4 of 4", self.calls[0]["stdin"])

    def test_reviewer_without_signal_is_needs_work_no_signal(self):
        self.approved(rounds=2)
        self.run_(
            implement(),
            {"final": findings("NEEDS_WORK", "forgot to signal")},
            implement(),
            review("ready"),
            judge("ready"),
        )
        self.assertEqual(self.summary()[1][1:], ("reviewer", "no-signal"))
        st = self.state()
        self.assertEqual(st["phase"], "done")
        entry = st["runs"][2]
        self.assertEqual(
            (entry["signal"], entry["reason"]), ("needs-work", "no-signal")
        )
        record = self.run_json(3, "reviewer")
        self.assertEqual(record["signal"]["status"], "needs-work")
        self.assertEqual(record["signal"]["reason"], "no-signal")
        self.assertTrue(record["signal"]["implied"])

    def test_judge_needs_work_stops_and_resume_opens_a_new_round(self):
        self.approved(rounds=2)
        verdict = "**Merge:** no\n\n1. x\n2. y\n3. z"
        proc = self.run_(
            implement(),
            review("ready"),
            judge("needs-work", "split the module", final=verdict),
            rc=3,
        )
        self.assertEqual(self.summary()[-1][1:], ("judge", "needs-work"))
        st = self.state()
        self.assertEqual(st["stopped"]["reason"], "judge-needs-work")
        self.assertEqual(st["stopped"]["detail"], "split the module")
        self.assertEqual(st["next_role"], "implementer")
        self.assertIn("judge-needs-work", proc.stderr)
        self.assertEqual(self.section("Verdict"), verdict)

        self.resume(implement(), review("ready"), judge("ready"), rounds=1)
        st = self.state()
        self.assertEqual(st["phase"], "done")
        self.assertEqual((st["round"], st["rounds"]), (2, 2))
        self.assertEqual(self.section("Verdict"), "**Merge:** yes\n\n1. a\n2. b\n3. c")

    def test_judge_without_signal_stops(self):
        self.approved()
        self.run_(implement(), review("ready"), {"final": "**Merge:** yes"}, rc=3)
        self.assertEqual(self.summary()[-1][1:], ("judge", "no-signal"))
        self.assertEqual(self.state()["stopped"]["reason"], "judge-needs-work")

    def test_implementer_commit_is_a_warning(self):
        self.approved()
        commit = ["git", "commit", "-q", "--allow-empty", "-m", "implementer commit"]
        proc = self.run_(implement(run=[commit]), review("ready"), judge("ready"))
        self.assertEqual(self.state()["phase"], "done")
        self.assertIn("implementer-committed", proc.stderr)
        record = self.run_json(2, "implementer")
        self.assertEqual(len(record["warnings"]), 1)
        self.assertTrue(record["warnings"][0].startswith("implementer-committed"))

    def test_an_agent_writing_state_json_does_not_steer_the_loop(self):
        self.approved()
        forged = json.dumps({"schema_version": 1, "phase": "done", "next_role": None})
        path = self.dir / "state.json"
        scribble = ["/bin/sh", "-c", "printf '%%s' '%s' > %s" % (forged, path)]
        self.run_(implement(run=[scribble]), review("ready"), judge("ready"))
        self.assertEqual(
            [r for _, r, _ in self.summary()], ["implementer", "reviewer", "judge"]
        )
        st = self.state()
        self.assertEqual(st["phase"], "done")
        self.assertEqual(st["task"], self.task)
        self.assertEqual(len(st["runs"]), 4)

    def test_reviewer_that_modifies_a_tracked_file_is_stopped(self):
        self.approved()
        bad = review("ready", writes={"README.md": "fixed it myself\n"})
        proc = self.run_(implement(), bad, rc=3)
        self.assertEqual(
            self.summary()[-1][1:], ("reviewer", "failed role-modified-worktree")
        )
        st = self.state()
        self.assertEqual(st["stopped"]["reason"], "role-modified-worktree")
        self.assertEqual(st["next_role"], "reviewer")
        self.assertIsNone(st["last_signal"])  # a failed run's signal is not folded
        self.assertIn("receipt: ", proc.stderr)
        error = json.loads((self.dir / "runs/003-reviewer/error.json").read_text())
        self.assertEqual(error["phase"], "rails")

    def test_untracked_files_from_the_reviewer_are_a_warning(self):
        self.approved()
        proc = self.run_(
            implement(writes={"src.py": "x\n"}),
            review("ready", writes={".cache/x": "1"}),
            judge("ready"),
        )
        self.assertEqual(self.state()["phase"], "done")
        self.assertIn("new untracked file(s) in the worktree: .cache/x", proc.stderr)
        # The implementer's own new files are its job, not a warning; the
        # receipt still records them.
        self.assertNotIn("src.py", proc.stderr)
        self.assertEqual(
            self.run_json(2, "implementer")["rails"]["new_untracked"], ["src.py"]
        )

    def test_identity_mismatch_stops(self):
        self.approved()
        self.run_(implement(model="claude-impostor"), rc=3)
        self.assertEqual(
            self.summary(), [(2, "implementer", "failed identity-mismatch")]
        )
        st = self.state()
        self.assertEqual(st["stopped"]["reason"], "identity-mismatch")
        self.assertIn("claude-impostor", st["stopped"]["detail"])
        self.assertEqual(st["next_role"], "implementer")

    def test_helper_model_in_model_usage_does_not_stop(self):
        self.approved()
        self.run_(
            implement(usage_extra=["claude-haiku-5-5"]), review("ready"), judge("ready")
        )
        self.assertEqual(self.state()["phase"], "done")

    def test_mixed_codex_implementer_and_claude_reviewer(self):
        self.approved("--role", "implementer=sol-builder")
        self.run_(implement(), review("ready"), judge("ready"))
        self.assertEqual(
            [(c["tool"], m.group(3)) for c, m in zip(self.calls, self.lines)],
            [
                ("codex", "sol-builder"),
                ("claude", "opus-reviewer"),
                ("claude", "fable"),
            ],
        )
        self.assertIn("workspace-write", self.calls[0]["argv"])
        self.assertEqual(self.state()["phase"], "done")
        self.assertEqual(self.lines[0].group(4), "gpt-5.6-sol")

    def test_kimi_implementer_and_reviewer(self):
        self.approved("--role", "implementer=kimi", "--role", "reviewer=kimi")
        self.run_(implement(), review("ready"), judge("ready"))
        self.assertEqual(
            [(c["tool"], m.group(3)) for c, m in zip(self.calls, self.lines)],
            [("kimi", "kimi"), ("kimi", "kimi"), ("claude", "fable")],
        )
        self.assertEqual(self.state()["phase"], "done")
        self.assertEqual(self.lines[0].group(4), "kimi-code/k3.1-pro")
        reviewer = self.run_json(3, "reviewer")
        self.assertEqual(reviewer["signal"]["status"], "ready")
        self.assertEqual(reviewer["model_identity_source"], "requested-only")


class Merging(LoopFixture, unittest.TestCase):
    def test_findings_cannot_add_or_end_a_section(self):
        self.approved()
        message = (
            "```markdown\n## Review Findings\n\n**Status:** NEEDS_WORK\n\n"
            "## Unit Tests\n- Result: FAIL\n\n# Verdict\n- not mine\n\n"
            "   ## indented\n```\n"
        )
        self.run_(
            implement(),
            review("needs-work", "x", final=message),
            implement(),
            review("ready"),
            judge("ready", final="## Verdict\n\n**Merge:** yes"),
        )
        doc = self.doc.read_text()
        titles = [t for t, _, _ in taskdoc.sections(doc)]
        self.assertEqual(titles[-2:], ["Review Findings", "Verdict"])
        self.assertEqual(titles.count("Verdict"), 1)
        self.assertEqual(self.section("Verdict"), "**Merge:** yes")
        # The first review, as the second implementer saw it.
        seen = self.calls[2]["stdin"]
        self.assertIn(
            "## Review Findings\n\n**Status:** NEEDS_WORK\n\n### Unit Tests\n", seen
        )
        self.assertIn("### Verdict\n- not mine", seen)
        self.assertIn("### indented", seen)
        self.assertNotIn("```", seen.split("## Review Findings")[1])

    def test_an_unclosed_fence_cannot_hide_the_sections_after_it(self):
        self.approved()
        verdict = "**Merge:** yes\n\n1. a\n2. b\n3. c"
        self.run_(
            implement(),
            review("ready", final="**Status:** READY\n\n### Unit Tests\n~~~~\nPASS"),
            judge("ready", final=verdict),
        )
        doc = self.doc.read_text()
        titles = [t for t, _, _ in taskdoc.sections(doc)]
        self.assertEqual(titles[-2:], ["Review Findings", "Verdict"])
        self.assertEqual(self.section("Verdict"), verdict)
        # Closed with the fence that was opened, so renderers agree too.
        self.assertTrue(self.section("Review Findings").endswith("~~~~\nPASS\n~~~~"))

    def test_a_fence_nested_in_a_longer_fence_stays_inside_it(self):
        self.approved()
        findings = (
            "**Status:** READY\n\n### Unit Tests\n````markdown\n```sh\nmake test\n"
            "# Hello, Ada!\n```\n## Not a heading\n````\nPASS"
        )
        self.run_(
            implement(),
            review("ready", final=findings),
            judge("ready", final="**Merge:** yes\n\n1. a\n2. b\n3. c"),
        )
        self.assertEqual(self.section("Review Findings"), findings)
        titles = [t for t, _, _ in taskdoc.sections(self.doc.read_text())]
        self.assertNotIn("Not a heading", titles)


class Interrupt(LoopFixture, unittest.TestCase):
    def test_ctrl_c_stops_as_interrupted_and_resume_reruns_the_role(self):
        self.approved()
        fake = FakeCalls(self.box, [implement(), {"sleep": 60}], task=self.task)
        proc = subprocess.Popen(
            [str(BOTTEGA), "run", self.task],
            cwd=str(self.box.work),
            env={**self.box.env, **fake.env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # run-tests.sh starts suites as background jobs, which a
            # non-interactive shell runs with SIGINT ignored; undo that.
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if len(fake.entries()) == 2:
                break
            time.sleep(0.1)
        self.assertEqual(len(fake.entries()), 2)
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 130, err)
        self.assertEqual(out.count("\n"), 1)  # only the implementer's line
        st = self.state()
        self.assertEqual(st["phase"], "stopped")
        self.assertEqual(st["stopped"]["reason"], "interrupted")
        self.assertEqual(st["next_role"], "reviewer")
        self.assertEqual(
            (st["runs"][-1]["status"], st["runs"][-1]["reason"]),
            ("failed", "interrupted"),
        )
        self.assertFalse((self.dir / "lock").exists())
        self.resume(review("ready"), judge("ready"))
        self.assertEqual(self.summary()[0], (4, "reviewer", "ready"))
        self.assertEqual(self.state()["phase"], "done")


class Failures(LoopFixture, unittest.TestCase):
    def test_dispatch_failed_and_resume_redispatches_the_same_role(self):
        for code in (1, 69, 75):
            with self.subTest(exit=code):
                self.approved()
                proc = self.run_(
                    implement(), {"exit": code, "stderr": "upstream said no\n"}, rc=3
                )
                self.assertEqual(
                    self.summary()[-1], (3, "reviewer", "failed dispatch-failed")
                )
                st = self.state()
                self.assertEqual(st["stopped"]["reason"], "dispatch-failed")
                self.assertEqual(st["stopped"]["detail"], "claude exited %d" % code)
                self.assertEqual(st["next_role"], "reviewer")
                self.assertEqual(st["runs"][-1]["status"], "failed")
                error = json.loads(
                    (self.dir / "runs/003-reviewer/error.json").read_text()
                )
                self.assertEqual(error["exit_code"], code)
                self.assertIn("upstream said no", error["stderr_tail"])
                self.assertIn(str(self.dir / "runs/003-reviewer"), proc.stderr)

                self.resume(review("ready"), judge("ready"))
                self.assertEqual(
                    self.summary(), [(4, "reviewer", "ready"), (5, "judge", "ready")]
                )
                st = self.state()
                self.assertEqual(st["phase"], "done")
                self.assertEqual((st["round"], st["rounds"]), (1, 4))
                self.assertEqual(
                    [r["status"] for r in st["runs"]],
                    ["ok", "ok", "failed", "ok", "ok"],
                )

    def test_timeout_stops(self):
        self.cfg["profiles"]["opus-reviewer"]["timeout"] = 1
        self.box.write_config(self.cfg)
        self.approved()
        self.run_(implement(), {"sleep": 30, "final": "late"}, rc=3)
        self.assertEqual(self.summary()[-1][1:], ("reviewer", "failed timeout"))
        st = self.state()
        self.assertEqual(st["stopped"]["reason"], "timeout")
        self.assertEqual(st["next_role"], "reviewer")

    def test_no_final_message_is_dispatch_failed(self):
        self.approved()
        self.run_({"no_final": True, "tick": ALL}, rc=3)
        self.assertEqual(self.state()["stopped"]["reason"], "dispatch-failed")
        self.assertEqual(self.state()["next_role"], "implementer")


class Refusals(LoopFixture, unittest.TestCase):
    def test_plan_edited_after_approval(self):
        self.approved()
        text = self.doc.read_text().replace("Parse --dry-run", "Parse --dry-run twice")
        self.doc.write_text(text)
        self.assert_refused(
            "run", "plan changed since it was approved; run: bottega approve"
        )
        # Approving again lets it run.
        self.box.bottega("approve", self.task)
        self.run_(implement(), review("ready"), judge("ready"))

    def test_ticks_and_findings_do_not_break_the_hash(self):
        self.approved()
        text = taskdoc.set_checked(self.doc.read_text(), ["T1"], True)
        text = taskdoc.replace_section(text, "Review Findings", "**Status:** x")
        self.doc.write_text(text)
        self.run_(implement(), review("ready"), judge("ready"))

    def test_profile_removed_between_approve_and_run(self):
        self.approved()
        del self.cfg["profiles"]["opus-reviewer"]
        self.cfg["roles"]["reviewer"] = "opus-builder"
        self.box.write_config(self.cfg)
        self.assert_refused("run", "no profile named 'opus-reviewer'")

    def test_harness_gone_or_env_unset(self):
        self.box.env["ZAI_API_KEY"] = "x"
        self.approved("--role", "reviewer=glm-reviewer")
        del self.box.env["ZAI_API_KEY"]
        self.assert_refused("run", "ZAI_API_KEY")
        self.box.env["ZAI_API_KEY"] = "x"
        self.box.env["PATH"] = "%s:/usr/bin:/bin" % (self.box.root / "bin")
        self.assert_refused("run", "claude: not on PATH")

    def test_planner_profile_removed_is_not_the_loops_business(self):
        self.approved()
        self.cfg["profiles"]["planner-only"] = dict(self.cfg["profiles"]["fable"])
        self.cfg["roles"]["planner"] = "planner-only"
        self.box.write_config(self.cfg)
        st = self.state()
        st["approval"]["roles"]["planner"] = "planner-only"
        (self.dir / "state.json").write_text(json.dumps(st))
        del self.cfg["profiles"]["planner-only"]
        self.cfg["roles"]["planner"] = "fable"
        self.box.write_config(self.cfg)
        self.run_(implement(), review("ready"), judge("ready"))

    def test_lock_held_by_a_live_pid(self):
        self.approved()
        (self.dir / "lock").write_text("%d\n" % os.getpid())
        self.assert_refused("run", "locked by pid %d" % os.getpid())
        (self.dir / "lock").unlink()

    def test_stale_lock_is_reclaimed(self):
        self.approved()
        (self.dir / "lock").write_text("999999\n")
        proc = self.run_(implement(), review("ready"), judge("ready"))
        self.assertIn("reclaimed a stale lock", proc.stderr)
        self.assertFalse((self.dir / "lock").exists())

    def test_wrong_phases(self):
        task = self.box.new_task(self.repo, "Not planned")
        self.task = task
        self.dir = self.box.task_dir(task)
        self.assert_refused("run", "is new; run needs an approved plan")
        self.assert_refused("resume", "is new; resume continues a stopped task")
        self.approved()
        self.run_(implement(), review("ready"), judge("ready"))
        self.assert_refused("run", "is done")
        self.assert_refused("resume", "is done")

    def test_run_on_a_stopped_task_points_to_resume(self):
        self.approved()
        self.run_(implement(), review("blocked", "no access"), rc=3)
        self.assert_refused("run", "continue with: bottega resume")


class Resume(LoopFixture, unittest.TestCase):
    def test_resume_on_an_approved_task_is_run(self):
        self.approved(rounds=3)
        self.resume(
            implement(),
            review("needs-work"),
            implement(),
            review("ready"),
            judge("ready"),
            rounds=2,
        )
        st = self.state()
        self.assertEqual((st["phase"], st["round"], st["rounds"]), ("done", 2, 2))

    def test_resume_after_blocked_reruns_the_reviewer(self):
        self.approved(rounds=2)
        self.run_(implement(), review("blocked", "no access"), rc=3)
        self.resume(review("ready"), judge("ready"))
        self.assertEqual(
            self.summary(), [(4, "reviewer", "ready"), (5, "judge", "ready")]
        )
        st = self.state()
        self.assertEqual((st["phase"], st["round"], st["rounds"]), ("done", 1, 4))

    def test_resume_default_rounds_come_from_the_configuration(self):
        self.cfg["rounds"] = 2
        self.box.write_config(self.cfg)
        self.approved(rounds=1)
        self.run_(implement(), review("needs-work"), rc=3)
        st = self.state()
        self.assertEqual((st["round"], st["stopped"]["reason"]), (1, "cap-reached"))
        self.resume(
            implement(), review("needs-work"), implement(), review("needs-work"), rc=3
        )
        st = self.state()
        self.assertEqual((st["round"], st["rounds"]), (3, 3))
        self.assertEqual(len(self.calls), 4)

    def test_task_left_running_by_a_dead_bottega(self):
        self.approved()
        self.run_(implement(), review("blocked", "x"), rc=3)
        st = self.state()
        st["phase"] = "running"
        st["stopped"] = None
        st["next_role"] = "reviewer"
        st["current_run"] = "004-reviewer"
        st["runs"].append(
            {
                "seq": 4,
                "role": "reviewer",
                "profile": "opus-reviewer",
                "round": 1,
                "status": "running",
                "started": "x",
            }
        )
        (self.dir / "state.json").write_text(json.dumps(st))
        (self.dir / "lock").write_text("999999\n")
        self.assert_refused("run", "is running")
        proc = self.resume(review("ready"), judge("ready"))
        self.assertIn("counts as interrupted", proc.stderr)
        st = self.state()
        self.assertEqual(st["phase"], "done")
        self.assertEqual(
            [(r["seq"], r["status"], r.get("reason")) for r in st["runs"][3:]],
            [(4, "failed", "interrupted"), (5, "ok", None), (6, "ok", None)],
        )

    def test_reapprove_a_stopped_task_after_editing_the_plan(self):
        self.approved()
        self.run_(implement(), review("blocked", "plan is wrong"), rc=3)
        text = self.doc.read_text().replace("Parse --dry-run", "Parse --dry-run -n")
        self.doc.write_text(text)
        self.assert_refused("resume", "plan changed since it was approved")
        self.box.bottega("approve", self.task)
        st = self.state()
        self.assertEqual(
            (st["phase"], st["round"], st["stopped"]), ("approved", 0, None)
        )
        self.run_(implement(), review("ready"), judge("ready"))
        self.assertEqual(self.state()["phase"], "done")


class Show(LoopFixture, unittest.TestCase):
    def test_show_after_a_stop(self):
        self.approved()
        self.run_(
            implement(),
            review("needs-work", "T3 is wrong", ["T3"]),
            implement(),
            review("blocked", "need a key"),
            rc=3,
        )
        shown = json.loads(self.box.bottega("show", self.task, "--json").stdout)
        st = shown["state"]
        self.assertEqual(st["phase"], "stopped")
        self.assertEqual(st["stopped"]["reason"], "blocked")
        self.assertEqual(st["stopped"]["detail"], "need a key")
        self.assertEqual(st["last_signal"]["status"], "blocked")
        self.assertEqual(st["last_signal"]["run"], "005-reviewer")
        self.assertEqual(
            (st["round"], st["rounds"], st["next_role"]), (2, 3, "reviewer")
        )
        self.assertEqual([r["seq"] for r in shown["runs"]], [1, 2, 3, 4, 5])
        self.assertEqual(shown["runs"][2]["signal"]["uncheck"], ["T3"])
        self.assertEqual(shown["runs"][4]["role"], "reviewer")

        text = self.box.bottega("show", self.task).stdout
        self.assertIn("phase     stopped", text)
        self.assertIn("round     2 of 3", text)
        self.assertIn("next      reviewer", text)
        self.assertIn(
            "signal    blocked by reviewer (run 005-reviewer): need a key", text
        )
        self.assertIn("stopped   blocked: need a key", text)
        self.assertRegex(
            text, r"\n003 reviewer\s+opus-reviewer\s+ok\s+-\s+needs-work\s+\d+s\n"
        )
        self.assertRegex(
            text, r"\n002 implementer\s+opus-builder\s+ok\s+-\s+-\s+\d+s\n"
        )


class SignalDuringTheLoop(LoopFixture, unittest.TestCase):
    """bottega signal as M0 built it, seen from the loop's side."""

    def test_implementer_cannot_signal_and_unknown_ids_are_refused(self):
        self.approved()
        out = self.box.root / "signal-out"
        step = implement(
            run=[
                [
                    "/bin/sh",
                    "-c",
                    "bottega signal %s ready > %s 2>&1; echo rc=$? >> %s"
                    % (self.task, out, out),
                ]
            ]
        )
        bad_uncheck = review("needs-work", "x", ["T99"])
        self.run_(step, bad_uncheck, implement(), review("ready"), judge("ready"))
        text = out.read_text()
        self.assertIn("the implementer does not signal", text)
        self.assertIn("rc=64", text)
        # The reviewer's signal with an unknown id was refused, so it counts
        # as no signal.
        self.assertEqual(self.summary()[1][1:], ("reviewer", "no-signal"))

    def test_signal_after_the_loop_is_refused(self):
        self.approved()
        self.run_(implement(), review("ready"), judge("ready"))
        proc = self.box.bottega("signal", self.task, "ready", rc=2)
        self.assertIn("is done, not running", proc.stderr)


if __name__ == "__main__":
    main()
