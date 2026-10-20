#!/usr/bin/env python3
"""config.json: schema, validation, effort sets, ${NAME} expansion, the key
file, starter."""

import copy
import json
import os
import unittest
from unittest import mock

from helpers import CANONICAL, Sandbox, main

from bottega import config
from bottega.harness import base_env
from bottega.harness import claude as claude_harness
from bottega.util import UsageError

GLM = CANONICAL["profiles"]["glm-reviewer"]


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


class Secrets(unittest.TestCase):
    """The key file beside config.json: parsed, never executed; the
    environment wins; refused when others can read it."""

    def setUp(self):
        self.box = Sandbox(self)

    def test_parses_the_shapes_a_dotenv_invites(self):
        self.box.write_secrets(
            "# keys\n\nZAI_API_KEY=plain\r\n"
            'export QUOTED="with space"\n'
            "  SINGLE = 'x'  \nEMPTY=\n"
        )
        with self.box.active():
            self.assertEqual(
                config.read_secrets(),
                {
                    "ZAI_API_KEY": "plain",
                    "QUOTED": "with space",
                    "SINGLE": "x",
                    "EMPTY": "",
                },
            )

    def test_no_file_means_the_environment_alone(self):
        with self.box.active():
            self.assertEqual(config.read_secrets(), {})
            self.assertEqual(config.missing_env(GLM), ["ZAI_API_KEY"])
            with mock.patch.dict(os.environ, {"ZAI_API_KEY": "from-env"}):
                self.assertEqual(config.missing_env(GLM), [])

    def test_the_file_fills_in_and_the_environment_wins(self):
        self.box.write_secrets("ZAI_API_KEY=from-file\n")
        with self.box.active():
            self.assertEqual(config.missing_env(GLM), [])
            self.assertEqual(
                config.expand_env(GLM)["ANTHROPIC_AUTH_TOKEN"], "from-file"
            )
            with mock.patch.dict(os.environ, {"ZAI_API_KEY": "from-env"}):
                self.assertEqual(
                    config.expand_env(GLM)["ANTHROPIC_AUTH_TOKEN"], "from-env"
                )

    def test_an_explicit_environ_is_used_as_is(self):
        self.box.write_secrets("ZAI_API_KEY=from-file\n")
        with self.box.active():
            self.assertEqual(config.missing_env(GLM, {}), ["ZAI_API_KEY"])

    def test_refuses_a_file_others_can_read(self):
        for mode in (0o644, 0o640, 0o604):
            self.box.write_secrets("ZAI_API_KEY=x\n", mode=mode)
            with self.box.active():
                with self.assertRaises(config.ConfigError) as caught:
                    config.read_secrets()
            self.assertIn("chmod 600", str(caught.exception))
            self.assertIn("%03o" % mode, str(caught.exception))
            self.assertEqual(caught.exception.code, 2)
        self.box.write_secrets("ZAI_API_KEY=x\n", mode=0o400)
        with self.box.active():
            self.assertEqual(config.read_secrets(), {"ZAI_API_KEY": "x"})

    def test_refuses_a_malformed_line_naming_it(self):
        for text in ("ZAI_API_KEY=x\nnot a line\n", "ok=1\n2BAD=x\n"):
            self.box.write_secrets(text)
            with self.box.active():
                with self.assertRaises(config.ConfigError) as caught:
                    config.read_secrets()
            self.assertIn("line 2", str(caught.exception))
            self.assertIn("NAME=value", str(caught.exception))

    def test_only_the_expanded_profile_env_reaches_a_harness(self):
        self.box.write_secrets("ZAI_API_KEY=x\nOTHER_KEY=y\n")
        with self.box.active():
            env, names = base_env(GLM)
            proxied, proxied_names, _ = claude_harness.proxied_env(GLM, "/cfg")
        for value in (env, proxied):
            self.assertEqual(value["ANTHROPIC_AUTH_TOKEN"], "x")
            self.assertNotIn("ZAI_API_KEY", value)
            self.assertNotIn("OTHER_KEY", value)
        self.assertEqual(names, sorted(GLM["env"]))
        self.assertIn("ANTHROPIC_AUTH_TOKEN", proxied_names)


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

    def test_doctor_reads_the_key_file_and_refuses_a_readable_one(self):
        self.box.write_config(
            with_changes(lambda c: c["roles"].update(reviewer="glm-reviewer"))
        )
        self.box.write_secrets("ZAI_API_KEY=topsecretvalue\n")
        proc = self.box.bottega("doctor", "--json")
        self.assertNotIn("topsecretvalue", proc.stdout + proc.stderr)
        checks = {c["check"]: c for c in json.loads(proc.stdout)["checks"]}
        self.assertEqual(checks["secrets"]["status"], "ok")
        self.assertIn("ZAI_API_KEY", checks["secrets"]["detail"])
        self.assertEqual(checks["env"]["status"], "ok")
        self.assertIn("ZAI_API_KEY from secrets.env", checks["env"]["detail"])
        report = self.doctor(0, env={"ZAI_API_KEY": "from-env"})
        checks = {c["check"]: c for c in report["checks"]}
        self.assertIn("ZAI_API_KEY from the environment", checks["env"]["detail"])
        self.box.secrets_file.chmod(0o644)
        failures = {c["check"]: c for c in self.failures(self.doctor(2))}
        self.assertIn("chmod 600", failures["secrets"]["detail"])
        self.assertIn("ZAI_API_KEY", failures["env"]["detail"])

    def test_plan_refuses_a_readable_key_file(self):
        self.box.write_config(
            with_changes(lambda c: c["roles"].update(planner="glm-reviewer"))
        )
        repo = self.box.make_repo()
        task = self.box.new_task(repo)
        self.box.write_secrets("ZAI_API_KEY=x\n", mode=0o644)
        proc = self.box.bottega("plan", task, rc=2)
        self.assertIn("chmod 600", proc.stderr)

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
