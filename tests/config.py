#!/usr/bin/env python3
"""config.json: schema, validation, effort sets, ${NAME} expansion, starter."""

import copy
import json
import unittest

from helpers import CANONICAL, Sandbox, main

from bottega import config
from bottega.util import UsageError


def with_changes(mutate):
    value = copy.deepcopy(CANONICAL)
    mutate(value)
    return value


class Validation(unittest.TestCase):
    def assertProblem(self, value, fragment):
        found = config.problems(value)
        self.assertTrue(
            any(fragment in p for p in found), "%r not in %r" % (fragment, found)
        )
        with self.assertRaises(config.ConfigError):
            config.validate(value)

    def test_canonical_example_is_valid(self):
        self.assertEqual(config.problems(CANONICAL), [])
        self.assertEqual(config.validate(CANONICAL)["rounds"], 3)

    def test_rounds_defaults_to_three(self):
        value = with_changes(lambda c: c.pop("rounds"))
        self.assertEqual(config.validate(value)["rounds"], 3)

    def test_judge_is_optional(self):
        value = with_changes(lambda c: c["roles"].pop("judge"))
        self.assertEqual(config.problems(value), [])

    def test_required_roles(self):
        for role in ("planner", "implementer", "reviewer"):
            value = with_changes(lambda c, r=role: c["roles"].pop(r))
            self.assertProblem(value, "role %s: required" % role)

    def test_auto_is_reserved_and_refused(self):
        value = with_changes(lambda c: c["roles"].update(reviewer="auto"))
        self.assertProblem(value, "'auto' is not supported yet")

    def test_role_must_name_an_existing_profile(self):
        value = with_changes(lambda c: c["roles"].update(implementer="missing"))
        self.assertProblem(value, "no profile named 'missing'")

    def test_unknown_role(self):
        value = with_changes(lambda c: c["roles"].update(tester="opus-builder"))
        self.assertProblem(value, "unknown role 'tester'")

    def test_harness_must_be_registered(self):
        value = with_changes(
            lambda c: c["profiles"]["opus-builder"].update(harness="kimi")
        )
        self.assertProblem(value, "harness must be one of claude, codex")

    def test_model_must_be_non_empty(self):
        value = with_changes(lambda c: c["profiles"]["opus-builder"].update(model=" "))
        self.assertProblem(value, "model must be a non-empty string")

    def test_effort_sets_per_harness(self):
        for harness, effort, valid in [
            ("claude", "low", True),
            ("claude", "max", True),
            ("claude", "minimal", False),
            ("claude", "none", False),
            ("codex", "none", True),
            ("codex", "minimal", True),
            ("codex", "xhigh", True),
            ("codex", "max", True),
            ("codex", "extreme", False),
        ]:
            value = with_changes(
                lambda c, h=harness, e=effort: c["profiles"]["opus-builder"].update(
                    harness=h, effort=e
                )
            )
            found = config.problems(value)
            self.assertEqual(found == [], valid, (harness, effort, found))

    def test_env_shape(self):
        value = with_changes(lambda c: c["profiles"]["opus-builder"].update(env=["A"]))
        self.assertProblem(value, "env must be an object")
        value = with_changes(
            lambda c: c["profiles"]["opus-builder"].update(env={"1BAD": "x"})
        )
        self.assertProblem(value, "env name '1BAD' is not valid")
        value = with_changes(
            lambda c: c["profiles"]["opus-builder"].update(env={"A": 1})
        )
        self.assertProblem(value, "env A must be a string")

    def test_aliases_timeout_budget(self):
        value = with_changes(
            lambda c: c["profiles"]["opus-builder"].update(aliases="x")
        )
        self.assertProblem(value, "aliases must be a list")
        for bad in (0, -5, True, "60"):
            value = with_changes(
                lambda c, b=bad: c["profiles"]["opus-builder"].update(timeout=b)
            )
            self.assertProblem(value, "timeout must be a positive number")
        value = with_changes(
            lambda c: c["profiles"]["opus-builder"].update(
                timeout=600, max_budget_usd=5
            )
        )
        self.assertEqual(config.problems(value), [])
        value = with_changes(
            lambda c: c["profiles"]["sol-builder"].update(max_budget_usd=5)
        )
        self.assertProblem(value, "max_budget_usd is supported by claude only")

    def test_unknown_keys_and_schema_version(self):
        value = with_changes(lambda c: c["profiles"]["opus-builder"].update(temp=1))
        self.assertProblem(value, "unknown key 'temp'")
        value = with_changes(lambda c: c.update(extra=1))
        self.assertProblem(value, "unknown top-level key 'extra'")
        value = with_changes(lambda c: c.update(schema_version=2))
        self.assertProblem(value, "schema_version must be 1")

    def test_rounds_must_be_a_positive_integer(self):
        for bad in (0, -1, "3", True, 2.5):
            value = with_changes(lambda c, b=bad: c.update(rounds=b))
            self.assertProblem(value, "rounds must be a whole number")

    def test_every_problem_is_reported_at_once(self):
        value = with_changes(
            lambda c: (
                c["roles"].pop("planner"),
                c["profiles"]["opus-builder"].update(effort="turbo"),
            )
        )
        self.assertEqual(len(config.problems(value)), 2)


class EnvExpansion(unittest.TestCase):
    profile = CANONICAL["profiles"]["glm-reviewer"]

    def test_expands_references(self):
        env = config.expand_env(self.profile, {"ZAI_API_KEY": "secret"})
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "secret")
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://api.z.ai/api/anthropic")

    def test_expands_inside_text_and_leaves_other_dollars(self):
        profile = {"env": {"H": "Bearer ${A}-${B}", "P": "$HOME/x"}}
        env = config.expand_env(profile, {"A": "1", "B": "2"})
        self.assertEqual(env, {"H": "Bearer 1-2", "P": "$HOME/x"})

    def test_missing_variable_fails_naming_it(self):
        with self.assertRaises(config.ConfigError) as caught:
            config.expand_env(self.profile, {})
        self.assertIn("ZAI_API_KEY", str(caught.exception))
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(config.missing_env(self.profile, {}), ["ZAI_API_KEY"])

    def test_empty_value_counts_as_set(self):
        env = config.expand_env(self.profile, {"ZAI_API_KEY": ""})
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "")


class Starter(unittest.TestCase):
    def test_claude_gets_the_canonical_roles(self):
        value = config.starter(["claude"])
        self.assertEqual(value["roles"], config.CLAUDE_ROLES)
        self.assertNotIn("sol-builder", value["profiles"])

    def test_codex_only(self):
        value = config.starter(["codex"])
        self.assertEqual(set(value["profiles"]), {"sol-builder"})
        self.assertEqual(set(value["roles"].values()), {"sol-builder"})
        self.assertNotIn("judge", value["roles"])

    def test_both_and_none(self):
        both = config.starter(["claude", "codex"])
        self.assertEqual(both["roles"], config.CLAUDE_ROLES)
        self.assertIn("sol-builder", both["profiles"])
        self.assertEqual(config.starter([])["roles"], config.CLAUDE_ROLES)


class RoleOverride(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(
            config.parse_role_override("implementer=sol-builder"),
            ("implementer", "sol-builder"),
        )
        for bad in ("implementer", "=x", "implementer=", "tester=x"):
            with self.assertRaises(UsageError):
                config.parse_role_override(bad)
        with self.assertRaises(config.ConfigError):
            config.parse_role_override("planner=auto")

    def test_bindings_merge_overrides(self):
        merged = config.role_bindings(CANONICAL, {"implementer": "sol-builder"})
        self.assertEqual(merged["implementer"], "sol-builder")
        self.assertEqual(merged["planner"], "fable")


class FileAndDoctor(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(self)

    def test_missing_file_points_to_init(self):
        with self.box.active():
            with self.assertRaises(config.ConfigError) as caught:
                config.load()
        self.assertIn("bottega init", str(caught.exception))

    def test_invalid_json(self):
        self.box.config_file.parent.mkdir(parents=True)
        self.box.config_file.write_text("{nope")
        with self.box.active():
            with self.assertRaises(config.ConfigError):
                config.load()

    def doctor(self, rc, env=None):
        proc = self.box.bottega("doctor", "--json", rc=rc, env=env)
        return json.loads(proc.stdout)

    def failures(self, report):
        return [c for c in report["checks"] if c["status"] == "fail"]

    def test_doctor_fails_on_an_unset_variable_of_a_bound_profile(self):
        self.box.write_config(
            with_changes(lambda c: c["roles"].update(reviewer="glm-reviewer"))
        )
        report = self.doctor(2)
        self.assertFalse(report["ok"])
        [failure] = self.failures(report)
        self.assertEqual(failure["check"], "env")
        self.assertIn("ZAI_API_KEY", failure["detail"])
        report = self.doctor(0, env={"ZAI_API_KEY": "x"})
        self.assertTrue(report["ok"])

    def test_doctor_only_warns_for_an_unbound_profile(self):
        self.box.write_config(CANONICAL)
        report = self.doctor(0)
        warnings = [c for c in report["checks"] if c["check"] == "env"]
        self.assertEqual([w["status"] for w in warnings], ["warn"])

    def test_doctor_reports_invalid_config_and_auto(self):
        self.box.write_config(with_changes(lambda c: c["roles"].update(judge="auto")))
        report = self.doctor(2)
        details = [c["detail"] for c in self.failures(report)]
        self.assertTrue(any("not supported yet" in d for d in details), details)

    def test_doctor_fails_when_a_harness_is_missing(self):
        self.box.write_config(
            with_changes(lambda c: c["roles"].update(implementer="sol-builder"))
        )
        path = "%s:/usr/bin:/bin" % (self.box.root / "bin")  # no fakes
        report = self.doctor(2, env={"PATH": path})
        checks = {c["check"]: c for c in self.failures(report)}
        self.assertIn("role implementer", checks)
        self.assertIn("codex: not on PATH", checks["role implementer"]["detail"])


if __name__ == "__main__":
    main()
