#!/usr/bin/env python3
"""The strict {{var}} engine, the shipped prompts and their overrides."""

import re
import unittest
import zlib

from helpers import CANONICAL, ROOT, FakeCalls, Sandbox, main

from bottega import prompts, taskdoc

SHIPPED = sorted((ROOT / "prompts").glob("*.md"))
MODEL_WORDS = re.compile(
    r"claude|anthropic|openai|gpt|opus|sonnet|haiku|fable|mythos|gemini|glm|"
    r"kimi|grok|qwen|deepseek|codex",
    re.IGNORECASE,
)


def full_values():
    values = {name: "<%s>" % name for name in prompts.PROMPT_VARIABLES}
    values["plan_template"] = prompts.plan_template()
    return values


class Engine(unittest.TestCase):
    def test_render_replaces_word_variables_in_one_pass(self):
        text = prompts.render("a {{x}} b {{y}} {{x}}", {"x": "{{y}}", "y": "2"}, "test")
        self.assertEqual(text, "a {{y}} b 2 {{y}}")

    def test_missing_variable_raises(self):
        with self.assertRaises(prompts.PromptError) as caught:
            prompts.render("{{a}} and {{b}} and {{c}}", {"a": 1}, "t")
        self.assertIn("b, c", str(caught.exception))
        self.assertEqual(caught.exception.code, 2)

    def test_spaced_markers_are_literal(self):
        text = "{{ phase title }} {{x}} {{ x }} {{x-y}} {x}"
        self.assertEqual(prompts.names_in(text), ["x"])
        self.assertEqual(
            prompts.render(text, {"x": "1"}), "{{ phase title }} 1 {{ x }} {{x-y}} {x}"
        )

    def test_port_is_bottegas_formula(self):
        task = "20261017-1200-add-flag"
        self.assertEqual(prompts.port(task), 3100 + zlib.crc32(task.encode()) % 900)
        self.assertTrue(3100 <= prompts.port(task) < 4000)
        self.assertEqual(prompts.port(task), prompts.port(task))


class Shipped(unittest.TestCase):
    def test_every_shipped_template_renders_with_the_full_set(self):
        self.assertTrue(SHIPPED, "no prompts shipped")
        values = full_values()
        for path in SHIPPED:
            with self.subTest(prompt=path.name):
                self.assertIn(path.stem, prompts.NAMES)
                text = path.read_text()
                self.assertEqual(prompts.unknown_names(text), [])
                rendered = prompts.render(text, values, path.name)
                self.assertNotRegex(rendered, r"\{\{\w+\}\}")
                self.assertIn("<task_doc>", rendered)
                self.assertIn("<task_doc_content>", rendered)
                self.assertIn("<worktree>", rendered)
                self.assertIn("<scratch_dir>", rendered)
                self.assertIsNone(MODEL_WORDS.search(text), "a model name")

    def test_all_four_roles_ship(self):
        self.assertEqual(sorted(p.stem for p in SHIPPED), sorted(prompts.NAMES))
        for path in SHIPPED:
            with self.subTest(prompt=path.name):
                text = path.read_text()
                self.assertIn(
                    "Empty means: find the project's documented test command", text
                )
                self.assertIn("{{test_cmd}}", text)
                self.assertIn("only authority", text)
                self.assertNotRegex(text, r"(?i)video|playwright")

    def test_loop_prompts_name_round_cap_and_port(self):
        values = full_values()
        for name in ("implementer", "reviewer", "judge"):
            with self.subTest(prompt=name):
                text = (ROOT / "prompts" / (name + ".md")).read_text()
                rendered = prompts.render(text, values)
                self.assertIn("round <round> of <rounds>", rendered)
                self.assertIn("<port>", rendered)
                if name != "implementer":  # its message is not merged
                    self.assertIn("no code fence around the message", rendered)

    def test_reviewer_and_judge_end_with_the_signal_and_the_implementer_never_signals(
        self,
    ):
        values = full_values()
        implementer = (ROOT / "prompts" / "implementer.md").read_text()
        self.assertNotIn("{{signal_cmd}}", implementer)
        self.assertIn("You do not signal", implementer)
        for name, statuses in (
            ("reviewer", ("ready", "needs-work", "blocked")),
            ("judge", ("ready", "needs-work")),
        ):
            with self.subTest(prompt=name):
                text = (ROOT / "prompts" / (name + ".md")).read_text()
                rendered = prompts.render(text, values).rstrip()
                last = rendered.split("\n## ")[-1]
                self.assertTrue(last.startswith("Signal: your last action"), last)
                for status in statuses:
                    self.assertIn("<signal_cmd> %s " % status, last)
                self.assertEqual("blocked" in last.split("Run")[0], name == "reviewer")

    def test_reviewer_keeps_bottegas_rules_and_formats(self):
        rendered = prompts.render(
            (ROOT / "prompts" / "reviewer.md").read_text(), full_values()
        )
        for rule in (
            "**Status:** IN_PROGRESS",
            "### Remaining Items",
            "**Status:** READY",
            "**Status:** NEEDS_WORK",
            "**Status:** BLOCKED",
            "### Checklist Verification",
            "- [T1] VERIFIED",
            "### Unit Tests",
            "### Manual Testing",
            "### Issues to Address",
            "Apply strict matching, not spirit matching",
            "is a **critical finding**",
            "in the foreground",
            "Do NOT background the suite",
            "Do not launch a second suite while one is running",
            "do not count automated tests as manual QA",
            "ALL testing scenarios in the Testing Strategy are MANDATORY",
            'Do NOT mark the test as "skipped"',
            "**Key question:**",
            "BLOCKED is a high bar",
            "NEVER stop a server you did not start",
            "lsof -i:<port>",
            "Do NOT fix any code",
            "never appends",
            "--uncheck T3 T7",
            "what is blocking, what you tried, what has to change",
        ):
            self.assertIn(rule, rendered)

    def test_implementer_rules(self):
        rendered = prompts.render(
            (ROOT / "prompts" / "implementer.md").read_text(), full_values()
        )
        for rule in (
            "## Review Findings",
            "address them first",
            "those are your priority",
            "in order",
            "Only tick a **Testing** item after you have actually run",
            "The plan's Testing Strategy is mandatory",
            "Do NOT ask any questions",
            "Stay in scope",
            "Never commit, push or open a pull request",
            "Never switch branches",
            "Do not spawn sub-agents",
        ):
            self.assertIn(rule, rendered)

    def test_judge_rules(self):
        rendered = prompts.render(
            (ROOT / "prompts" / "judge.md").read_text(), full_values()
        )
        for rule in (
            "would you merge this?",
            "git diff <base_branch>...HEAD",
            "three reasons",
            "**Merge:** yes",
            "You are read-only",
            "Do not re-run the tests",
        ):
            self.assertIn(rule, rendered)

    def test_planner_prompt(self):
        text = (ROOT / "prompts" / "planner.md").read_text()
        rendered = prompts.render(text, full_values())
        self.assertIn("## Questions for you", rendered)
        self.assertIn("<plan-template>\n## Overview", rendered)
        self.assertIn("<test_cmd>", rendered)
        self.assertIn("Empty means: find the project's documented test command", text)
        for rule in (
            "section-for-section, in the same order, with no sections removed",
            "Agent-Executable Steps Only",
            "Do not spawn sub-agents",
            "no code fence around the message",
            "**DON'T ASK**",
        ):
            self.assertIn(rule, rendered)

    def test_plan_template_is_the_planners_part_of_task_md(self):
        template = prompts.plan_template()
        titles = [title for title, _, _ in taskdoc.sections(template)]
        self.assertEqual(titles, list(taskdoc.PLAN_SECTIONS))
        self.assertIn("{{ phase title }}", template)  # guidance survives
        self.assertEqual(prompts.names_in(template), [])

    def test_task_template_uses_only_its_two_variables(self):
        text = prompts.TEMPLATE_FILE.read_text()
        self.assertEqual(
            sorted(prompts.names_in(text)), sorted(prompts.TEMPLATE_VARIABLES)
        )


class Overrides(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)
        self.box.write_config(CANONICAL)
        self.dir = self.box.root / "config" / "bottega-kit" / "prompts"
        self.dir.mkdir(parents=True)
        self.repo = self.box.make_repo(
            files={"README.md": "hi\n", "bottega.json": '{"test_cmd": "make check"}'}
        )
        self.task = self.box.new_task(self.repo, "Override", "do the thing")

    def plan(self, rc, final="## Questions for you\n\n1. Why?"):
        fake = FakeCalls(self.box, default={"final": final})
        proc = self.box.bottega("plan", self.task, rc=rc, env=fake.env)
        return proc, fake.entries()

    def test_override_wins_and_gets_every_value(self):
        names = " ".join("%s=[{{%s}}]" % (n, n) for n in prompts.PROMPT_VARIABLES)
        (self.dir / "planner.md").write_text("CUSTOM " + names)
        _, calls = self.plan(0)
        stdin = calls[0]["stdin"]
        self.assertTrue(stdin.startswith("CUSTOM "))
        st = self.box.state(self.task)
        task_dir = self.box.task_dir(self.task)
        run_dir = task_dir / "runs" / "001-planner"
        self.assertEqual((run_dir / "prompt.md").read_text(), stdin)
        expected = {
            "task_doc": str(task_dir / "task.md"),
            "task_id": self.task,
            "task_title": "Override",
            "worktree": st["worktree"],
            "base_branch": "main",
            "signal_cmd": "%s signal %s" % (ROOT / "bin" / "bottega", self.task),
            "test_cmd": "make check",
            "round": "0",
            "rounds": "3",
            "scratch_dir": str(run_dir / "scratch"),
            "port": str(prompts.port(self.task)),
        }
        for name, value in expected.items():
            self.assertIn("%s=[%s]" % (name, value), stdin)
        self.assertIn("> do the thing", stdin)  # task_doc_content
        self.assertIn("plan_template=[## Overview", stdin)

    def test_unknown_variable_in_an_override_is_refused_before_dispatch(self):
        (self.dir / "planner.md").write_text("{{task_id}} {{nonsense}} {{ fine }}")
        proc, calls = self.plan(2)
        self.assertIn("unknown variable(s): nonsense", proc.stderr)
        self.assertEqual(calls, [])
        task_dir = self.box.task_dir(self.task)
        self.assertFalse((task_dir / "runs").exists())
        st = self.box.state(self.task)
        self.assertEqual(
            (st["phase"], st["runs"], st["current_run"]), ("new", [], None)
        )

    def test_known_but_unset_variable_raises(self):
        # plan_template is known, but only the planner gets a value for it.
        (self.dir / "reviewer.md").write_text("{{plan_template}}")
        st = self.box.state(self.task)
        task_dir = self.box.task_dir(self.task)
        with self.box.active():
            text, path = prompts.load("reviewer")
            self.assertEqual(path, self.dir / "reviewer.md")
            values = prompts.values(
                st, task_dir, task_dir / "x", "reviewer", 3, "", "b"
            )
            with self.assertRaises(prompts.PromptError):
                prompts.render(text, values)

    def test_without_bottega_json_test_cmd_is_empty(self):
        other = self.box.make_repo("other")
        task = self.box.new_task(other, "No config")
        fake = FakeCalls(self.box, default={"final": "## Questions for you\n\n1. ?"})
        self.box.bottega("plan", task, env=fake.env)
        stdin = fake.entries()[0]["stdin"]
        self.assertIn("Project test command: ``. Empty means", stdin)
        self.assertNotRegex(stdin, r"\{\{\w+\}\}")


if __name__ == "__main__":
    main()
