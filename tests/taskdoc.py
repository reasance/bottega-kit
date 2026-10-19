#!/usr/bin/env python3
"""task.md: seeding, sections, checkbox items, [T<n>] ids, plan hash."""

import unittest

from helpers import ROOT, main

from bottega import taskdoc

TEMPLATE = (ROOT / "templates" / "task.md").read_text()
HEADINGS = [
    "Original Request",
    "Overview",
    "Implementation Plan",
    "Testing Strategy",
    "To-Do List",
    "Project Docs Update",
    "Review Findings",
    "Verdict",
]

PLAN = """# Task Add a flag

## Original Request

> add a --dry-run flag

## Overview

Adds a flag.

```markdown
## Not a heading
- [ ] not an item
```

## Implementation Plan

### Phase 1: Flag

- [ ] stray checkbox outside the to-do list

## Testing Strategy

### Manual QA

Not needed: the flag only prints.

## To-Do List

### Implementation
- [ ] parse the flag
- [x] print the plan

### Testing
* [ ] unit test for the flag

## Project Docs Update

Not needed for this change.

## Review Findings

## Verdict
"""


class Seed(unittest.TestCase):
    def test_template_has_bottegas_order_plus_ours(self):
        titles = [title for title, _, _ in taskdoc.sections(TEMPLATE)]
        self.assertEqual(titles, HEADINGS)

    def test_seed_sets_title_and_quotes_the_request_verbatim(self):
        request = (
            "Fix the *login* bug.\n\n  Keep `--verbose` working.\n> already quoted\n"
        )
        text = taskdoc.seed(TEMPLATE, "Fix login", request)
        self.assertTrue(text.startswith("# Task Fix login\n"))
        body = taskdoc.get_section(text, "Original Request")
        self.assertEqual(
            body,
            "> Fix the *login* bug.\n>\n>   Keep `--verbose` working.\n> > already quoted",
        )
        unquoted = "\n".join(
            line[2:] if line != ">" else "" for line in body.split("\n")
        )
        self.assertEqual(unquoted, request.rstrip("\n"))
        self.assertEqual([t for t, _, _ in taskdoc.sections(text)], HEADINGS)


class Sections(unittest.TestCase):
    def test_get_ignores_fenced_headings(self):
        overview = taskdoc.get_section(PLAN, "Overview")
        self.assertIn("## Not a heading", overview)
        self.assertNotIn("Not a heading", [t for t, _, _ in taskdoc.sections(PLAN)])
        self.assertIsNone(taskdoc.get_section(PLAN, "Nope"))

    def test_replace_replaces_never_appends(self):
        once = taskdoc.replace_section(PLAN, "Review Findings", "first findings")
        twice = taskdoc.replace_section(once, "Review Findings", "second findings")
        self.assertEqual(
            taskdoc.get_section(twice, "Review Findings"), "second findings"
        )
        self.assertNotIn("first findings", twice)
        self.assertEqual(
            taskdoc.get_section(twice, "Overview"),
            taskdoc.get_section(PLAN, "Overview"),
        )
        self.assertIn("## Verdict", twice)

    def test_replace_inserts_a_missing_section(self):
        text = "# Task x\n\n## Overview\n\nhi\n\n## Verdict\n\nv\n"
        out = taskdoc.replace_section(text, "Review Findings", "f", before="Verdict")
        self.assertEqual(
            [t for t, _, _ in taskdoc.sections(out)],
            ["Overview", "Review Findings", "Verdict"],
        )
        out = taskdoc.replace_section(text, "Notes", "n")
        self.assertEqual([t for t, _, _ in taskdoc.sections(out)][-1], "Notes")
        self.assertTrue(out.endswith("## Notes\n\nn\n"))


class Items(unittest.TestCase):
    def test_only_the_todo_list_counts(self):
        items = taskdoc.todo_items(PLAN)
        self.assertEqual(
            [(i.checked, i.text) for i in items],
            [
                (False, "parse the flag"),
                (True, "print the plan"),
                (False, "unit test for the flag"),
            ],
        )

    def test_assign_ids_in_document_order(self):
        text, assigned = taskdoc.assign_ids(PLAN)
        self.assertEqual(assigned, ["T1", "T2", "T3"])
        self.assertIn("- [ ] [T1] parse the flag", text)
        self.assertIn("- [x] [T2] print the plan", text)
        self.assertIn("* [ ] [T3] unit test for the flag", text)
        self.assertIn("- [ ] stray checkbox outside the to-do list", text)
        again, more = taskdoc.assign_ids(text)
        self.assertEqual((again, more), (text, []))

    def test_assign_keeps_ids_and_continues_after_the_highest(self):
        text = PLAN.replace("- [ ] parse the flag", "- [ ] [T7] parse the flag")
        text, assigned = taskdoc.assign_ids(text)
        self.assertEqual(assigned, ["T8", "T9"])
        self.assertEqual(taskdoc.item_ids(text), ["T7", "T8", "T9"])

    def test_duplicate_ids_are_refused(self):
        text = PLAN.replace("parse the flag", "[T1] a").replace(
            "print the plan", "[T1] b"
        )
        with self.assertRaises(taskdoc.TaskDocError):
            taskdoc.assign_ids(text)

    def test_set_checked(self):
        text, _ = taskdoc.assign_ids(PLAN)
        ticked = taskdoc.set_checked(text, ["T1", "T3"], True)
        self.assertTrue(all(i.checked for i in taskdoc.todo_items(ticked)))
        unticked = taskdoc.set_checked(ticked, ["T2"], False)
        self.assertEqual(
            [i.checked for i in taskdoc.todo_items(unticked)], [True, False, True]
        )
        with self.assertRaises(taskdoc.TaskDocError):
            taskdoc.set_checked(text, ["T9"], True)


class PlanHash(unittest.TestCase):
    def setUp(self):
        self.text, _ = taskdoc.assign_ids(PLAN)
        self.sha = taskdoc.plan_sha256(self.text)

    def test_stable_while_boxes_are_ticked_and_unticked(self):
        ticked = taskdoc.set_checked(self.text, ["T1", "T3"], True)
        self.assertEqual(taskdoc.plan_sha256(ticked), self.sha)
        self.assertEqual(
            taskdoc.plan_sha256(taskdoc.set_checked(ticked, ["T1", "T2", "T3"], False)),
            self.sha,
        )
        self.assertEqual(
            taskdoc.plan_sha256(self.text.replace("- [x]", "- [X]")), self.sha
        )

    def test_stable_when_findings_and_verdict_change(self):
        text = taskdoc.replace_section(self.text, "Review Findings", "NEEDS_WORK: T1")
        text = taskdoc.replace_section(text, "Verdict", "merge it")
        self.assertEqual(taskdoc.plan_sha256(text), self.sha)

    def test_stable_under_trailing_whitespace_and_crlf(self):
        noisy = "\r\n".join(line + "  " for line in self.text.split("\n"))
        self.assertEqual(taskdoc.plan_sha256(noisy), self.sha)

    def test_broken_by_any_plan_edit(self):
        for old, new in [
            ("Adds a flag.", "Adds two flags."),
            ("parse the flag", "parse the flags"),
            ("[T1]", "[T4]"),
            ("Not needed: the flag only prints.", "Not needed."),
        ]:
            self.assertNotEqual(
                taskdoc.plan_sha256(self.text.replace(old, new)), self.sha, old
            )

    def test_ids_are_part_of_the_hash(self):
        self.assertNotEqual(taskdoc.plan_sha256(PLAN), self.sha)

    def test_region_stops_at_review_findings(self):
        region = taskdoc.plan_region(self.text)
        self.assertNotIn("## Review Findings", region)
        self.assertIn("## Project Docs Update", region)
        self.assertNotIn("- [x]", region)
        self.assertTrue(region.endswith("Not needed for this change.\n"))


class Fences(unittest.TestCase):
    # A ``` block nested in a ```` block, as a planner writes a README snippet
    # with a shell example in it (seen live, 2026-10-19).
    NESTED = (
        "## Overview\n\nAdds --repeat.\n\n## Implementation Plan\n\n"
        "````markdown\nUse `--repeat N`:\n\n```sh\npython3 greet.py --repeat 3 Ada\n"
        "# Hello, Ada!\n# Hello, Ada!\n```\n````\n\n## Testing Strategy\n\n"
        "### Manual QA\n- Scenario: run it\n\n## To-Do List\n\n- [ ] do it\n\n"
        "## Project Docs Update\n\nNot needed for this change.\n"
    )

    def test_a_fence_nested_in_a_longer_fence_stays_inside_it(self):
        titles = [t for t, _, _ in taskdoc.sections(self.NESTED)]
        self.assertNotIn("Hello, Ada!", titles)
        self.assertEqual(taskdoc.plan_problems(self.NESTED), [])
        merged = taskdoc.merge_plan(PLAN, self.NESTED, "Add a flag")
        plan = taskdoc.get_section(merged, "Implementation Plan")
        self.assertEqual(plan.count("# Hello, Ada!"), 2)
        self.assertTrue(plan.endswith("```\n````"))
        self.assertEqual(
            [t for t, _, _ in taskdoc.sections(merged)][-2:],
            ["Review Findings", "Verdict"],
        )

    def test_unwrap_removes_an_outer_fence_around_nested_fences(self):
        # NESTED has a four-backtick block, so the wrapper needs five.
        wrapped = "`````markdown\n" + self.NESTED + "`````"
        self.assertEqual(taskdoc.unwrap(wrapped), self.NESTED.strip("\n"))
        # A fence that closes before the end is a code block, not a wrapper.
        block = "```\ncode\n```\n\n## Overview\n\ntext\n\n```\nmore\n```"
        self.assertEqual(taskdoc.unwrap(block), block)
        # A shorter closing marker does not close a longer fence.
        self.assertEqual(
            taskdoc.unwrap("````\n## Overview\n```"), "````\n## Overview\n```"
        )


if __name__ == "__main__":
    main()
