#!/usr/bin/env python3
"""state.json, the lock, and `bottega signal` with every validation."""

import io
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

from helpers import BOTTEGA, Sandbox, main

from bottega import state
from bottega.util import Refused, atomic_write_json

STATUSES = {"ready", "needs-work", "blocked"}


class TaskFixture:
    def setUp(self):
        self.box = Sandbox(self)
        self.repo = self.box.make_repo()
        request = "add a flag"
        self.task = self.box.new_task(self.repo, "Add flag", request)
        self.dir = self.box.task_dir(self.task)
        doc = self.dir / "task.md"
        doc.write_text(
            doc.read_text()
            .replace("{{ implementation step 1 }}", "[T1] parse it")
            .replace("{{ implementation step 2 }}", "[T2] print it")
        )

    def start_run(self, role, seq=2, phase="running"):
        st = self.box.state(self.task)
        name = "%03d-%s" % (seq, role)
        st["phase"] = phase
        st["current_run"] = name
        st["runs"].append(
            {
                "seq": seq,
                "role": role,
                "profile": "p",
                "status": "running",
                "started": "now",
            }
        )
        (self.dir / "state.json").write_text(json.dumps(st, indent=2))
        run_dir = self.dir / "runs" / name
        run_dir.mkdir(parents=True)
        return run_dir


class Signal(TaskFixture, unittest.TestCase):
    def signal(self, *args, rc=0, cwd=None):
        return self.box.bottega("signal", *args, rc=rc, cwd=cwd)

    def test_reviewer_signal_from_another_cwd(self):
        run_dir = self.start_run("reviewer")
        before = (self.dir / "state.json").read_bytes()
        elsewhere = self.box.root / "home"
        proc = self.signal(
            self.task, "needs-work", "T2 not done", "--uncheck", "T2", cwd=elsewhere
        )
        self.assertIn("needs-work", proc.stdout)
        record = json.loads((run_dir / "signal.json").read_text())
        self.assertEqual(record["status"], "needs-work")
        self.assertEqual(record["reason"], "T2 not done")
        self.assertEqual(record["uncheck"], ["T2"])
        self.assertEqual(record["by"], "reviewer")
        self.assertEqual(record["run"], "002-reviewer")
        # The agent never writes state.json; the orchestrator folds the signal.
        self.assertEqual((self.dir / "state.json").read_bytes(), before)

    def test_signal_by_task_directory_without_the_orchestrator_environment(self):
        # An agent's shell may not inherit XDG_* or BOTTEGA_DATA_HOME (Codex
        # drops them under shell_environment_policy.inherit = "core"), so the
        # prompt names the task directory and the data home is never needed.
        run_dir = self.start_run("reviewer")
        bare = {"PATH": self.box.env["PATH"], "HOME": str(self.box.root / "other")}
        proc = subprocess.run(
            [str(BOTTEGA), "signal", str(self.dir), "ready", "all verified"],
            cwd=str(self.box.root),
            env=bare,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        record = json.loads((run_dir / "signal.json").read_text())
        self.assertEqual(record["status"], "ready")
        self.assertEqual(record["run"], "002-reviewer")
        # The id form still needs the data home: without it there is no task.
        proc = subprocess.run(
            [str(BOTTEGA), "signal", self.task, "ready", "x"],
            cwd=str(self.box.root),
            env=bare,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 64)
        self.assertIn("no task matches", proc.stderr)

    def test_absolute_path_that_is_not_a_task_directory(self):
        self.start_run("reviewer")
        proc = self.signal(str(self.box.root), "ready", "x", rc=64)
        self.assertIn("not a task directory", proc.stderr)

    def test_last_signal_wins_and_both_are_logged(self):
        run_dir = self.start_run("reviewer")
        self.signal(self.task, "needs-work")
        self.signal(self.task, "ready", "all good")
        self.assertEqual(
            json.loads((run_dir / "signal.json").read_text())["status"], "ready"
        )
        log = [
            json.loads(line)
            for line in (run_dir / "signal.log").read_text().splitlines()
        ]
        self.assertEqual([entry["status"] for entry in log], ["needs-work", "ready"])

    def test_task_by_unique_prefix_or_suffix(self):
        self.start_run("reviewer")
        self.signal(self.task[:13], "blocked", "no database")
        self.signal(self.task[-8:], "ready")

    def test_bad_status_word(self):
        self.start_run("reviewer")
        proc = self.signal(self.task, "done", rc=64)
        self.assertIn("ready|needs-work|blocked", proc.stderr)

    def test_unknown_task(self):
        self.start_run("reviewer")
        proc = self.signal("20990101-0000-nope", "ready", rc=64)
        self.assertIn("no task matches", proc.stderr)

    def test_stale_task_after_rm(self):
        self.box.bottega("rm", "--yes", self.task)
        proc = self.signal(self.task, "ready", rc=2)
        self.assertIn("removed, not running", proc.stderr)

    def test_wrong_phase(self):
        proc = self.signal(self.task, "ready", rc=2)
        self.assertIn("is new, not running", proc.stderr)
        self.start_run("reviewer", phase="approved")
        self.signal(self.task, "ready", rc=2)

    def test_no_current_run(self):
        self.start_run("reviewer")
        st = self.box.state(self.task)
        st["current_run"] = None
        (self.dir / "state.json").write_text(json.dumps(st))
        self.signal(self.task, "ready", rc=2)

    def test_role_may_only_emit_its_statuses(self):
        self.start_run("implementer")
        proc = self.signal(self.task, "ready", rc=64)
        self.assertIn("implementer does not signal", proc.stderr)

    def test_judge_ready_or_needs_work_only(self):
        run_dir = self.start_run("judge", seq=5)
        self.signal(self.task, "blocked", rc=64)
        self.signal(self.task, "needs-work", "missing tests")
        self.assertEqual(
            json.loads((run_dir / "signal.json").read_text())["by"], "judge"
        )

    def test_unknown_uncheck_id(self):
        run_dir = self.start_run("reviewer")
        proc = self.signal(self.task, "needs-work", "x", "--uncheck", "T1", "T99", rc=2)
        self.assertIn("T99", proc.stderr)
        self.assertFalse((run_dir / "signal.json").exists())
        self.signal(self.task, "needs-work", "x", "--uncheck", "3", rc=64)

    def test_missing_run_dir(self):
        run_dir = self.start_run("reviewer")
        run_dir.rmdir()
        self.signal(self.task, "ready", rc=2)

    def test_concurrent_reader_only_sees_complete_json(self):
        run_dir = self.start_run("reviewer")
        target = run_dir / "signal.json"
        stop = threading.Event()
        seen, errors = [], []

        def reader():
            while not stop.is_set():
                try:
                    text = target.read_text()
                except FileNotFoundError:
                    continue
                try:
                    seen.append(json.loads(text)["status"])
                except (ValueError, KeyError) as error:
                    errors.append((repr(error), text))

        thread = threading.Thread(target=reader)
        thread.start()
        try:
            words = ["ready", "needs-work", "blocked"]
            procs = [
                subprocess.Popen(
                    ["bottega", "signal", self.task, words[i % 3], "reason %d" % i],
                    env=self.box.env,
                    cwd=str(self.box.work),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                for i in range(24)
            ]
            for proc in procs:
                self.assertEqual(proc.wait(timeout=60), 0, proc.stderr.read())
                proc.stderr.close()
        finally:
            stop.set()
            thread.join()
        self.assertEqual(errors, [])
        self.assertTrue(seen)
        self.assertTrue(set(seen) <= STATUSES)
        self.assertEqual(len((run_dir / "signal.log").read_text().splitlines()), 24)


class FakeHarnesses(TaskFixture, unittest.TestCase):
    """The fakes drive the same `bottega signal` an agent would."""

    def fake(self, tool, argv, scenario, stdin="the prompt", cwd=None):
        scenario = dict(
            scenario, log=str(self.box.root / "calls.jsonl"), task=self.task
        )
        return subprocess.run(
            [tool, *argv],
            env={
                **self.box.env,
                "BOTTEGA_FAKE_SCENARIO": json.dumps(scenario),
                "SECRET_X": "s3cret",
            },
            cwd=str(cwd or self.box.state(self.task)["worktree"]),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def calls(self):
        path = self.box.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_fake_claude_reviewer(self):
        run_dir = self.start_run("reviewer", seq=3)
        step = {
            "final": "NEEDS_WORK: T2 is not done",
            "writes": {"notes/review.txt": "seen"},
            "tick": ["T1"],
            "signal": ["needs-work", "T2 missing", "--uncheck", "T2"],
        }
        proc = self.fake(
            "claude",
            ["-p", "--model", "claude-opus-5", "--add-dir", str(self.dir)],
            {"calls": [step]},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        events = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(
            [(e["type"], e.get("subtype")) for e in events],
            [("system", "init"), ("assistant", None), ("result", "success")],
        )
        self.assertEqual(events[0]["model"], "claude-opus-5")
        self.assertEqual(events[2]["result"], "NEEDS_WORK: T2 is not done")
        self.assertIn("claude-opus-5", events[2]["modelUsage"])
        worktree = self.box.state(self.task)["worktree"]
        self.assertEqual((Path(worktree) / "notes/review.txt").read_text(), "seen")
        self.assertIn("- [x] [T1] parse it", (self.dir / "task.md").read_text())
        record = json.loads((run_dir / "signal.json").read_text())
        self.assertEqual((record["status"], record["uncheck"]), ("needs-work", ["T2"]))
        [call] = self.calls()
        self.assertEqual(call["tool"], "claude")
        self.assertEqual(call["stdin"], "the prompt")
        self.assertIn("SECRET_X", call["env_names"])
        self.assertNotIn("s3cret", json.dumps(call))

    def test_fake_claude_identity_and_errors(self):
        scenario = {
            "calls": [
                {"model": "glm-5.3-flash", "is_error": True, "exit": 1},
                {"no_final": True},
            ]
        }
        proc = self.fake("claude", ["-p", "--model", "claude-opus-5"], scenario)
        self.assertEqual(proc.returncode, 1)
        events = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(events[0]["model"], "glm-5.3-flash")
        self.assertTrue(events[-1]["is_error"])
        events = [
            json.loads(line)
            for line in self.fake("claude", ["-p"], scenario).stdout.splitlines()
        ]
        self.assertNotIn("result", events[-1])

    def test_fake_codex_writes_the_o_file_and_follows_C(self):
        out = self.box.root / "output.md"
        worktree = self.box.state(self.task)["worktree"]
        scenario = {
            "calls": [
                {"final": "done", "writes": {"x.txt": "1"}},
                {"sleep": 0.1, "exit": 75},
            ]
        }
        argv = [
            "exec",
            "-m",
            "gpt-5.6-sol",
            "--json",
            "-o",
            str(out),
            "-C",
            worktree,
            "-",
        ]
        proc = self.fake("codex", argv, scenario, cwd=self.box.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(out.read_text(), "done")
        self.assertTrue((Path(worktree) / "x.txt").is_file())
        events = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(events[0]["model"], "gpt-5.6-sol")
        self.assertEqual(events[-1]["type"], "turn.completed")
        self.assertEqual(self.fake("codex", argv, scenario).returncode, 75)
        self.assertEqual(self.fake("codex", argv, scenario).returncode, 99)  # exhausted
        self.assertEqual([c["call"] for c in self.calls()], [1, 2])


class AtomicWrite(unittest.TestCase):
    def test_reader_never_sees_a_partial_file(self):
        box = Sandbox(self)
        target = box.root / "big.json"
        payload = {"status": "ready", "padding": "x" * 200000}
        atomic_write_json(target, payload)
        stop = threading.Event()
        errors = []

        def reader():
            while not stop.is_set():
                try:
                    json.loads(target.read_text())
                except ValueError as error:
                    errors.append(error)

        thread = threading.Thread(target=reader)
        thread.start()
        try:
            for i in range(150):
                atomic_write_json(target, dict(payload, n=i))
        finally:
            stop.set()
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(
            sorted(p.name for p in box.root.iterdir() if p.name.startswith(".")), []
        )


class StateAndLock(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.dir = self.box.root / "task"
        self.dir.mkdir()

    def test_round_trip_and_phase_checks(self):
        st = state.new_state("t", "p", "T", "/r", "/w", "bottega/t", "main", {})
        state.save(self.dir, st)
        self.assertEqual(state.load(self.dir), st)
        self.assertEqual(st["phase"], "new")
        with self.assertRaises(ValueError):
            state.save(self.dir, dict(st, phase="flying"))
        (self.dir / "state.json").write_text(json.dumps(dict(st, schema_version=2)))
        with self.assertRaises(Refused):
            state.load(self.dir)

    def test_lock_held_by_a_live_process_is_refused(self):
        state.acquire_lock(self.dir)
        with self.assertRaises(state.LockHeld) as caught:
            state.acquire_lock(self.dir)
        self.assertEqual(caught.exception.code, 2)
        state.release_lock(self.dir)
        self.assertFalse((self.dir / "lock").exists())

    def test_stale_lock_is_reclaimed_with_a_message(self):
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        (self.dir / "lock").write_text("%d\n" % dead.pid)
        out = io.StringIO()
        with state.locked(self.dir, out=out):
            self.assertEqual((self.dir / "lock").read_text().strip(), str(os.getpid()))
        self.assertIn("reclaimed a stale lock", out.getvalue())
        self.assertFalse((self.dir / "lock").exists())

    def test_release_leaves_another_holders_lock(self):
        (self.dir / "lock").write_text("1\n")
        state.release_lock(self.dir)
        self.assertTrue((self.dir / "lock").exists())

    def test_rm_refuses_while_another_process_holds_the_lock(self):
        repo = self.box.make_repo()
        task = self.box.new_task(repo)
        task_dir = self.box.task_dir(task)
        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        (task_dir / "lock").write_text("%d\n" % holder.pid)
        proc = self.box.bottega("rm", "--yes", task, rc=2)
        self.assertIn("locked by pid %d" % holder.pid, proc.stderr)
        self.assertEqual(self.box.state(task)["phase"], "new")


if __name__ == "__main__":
    main()
