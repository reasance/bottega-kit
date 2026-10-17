"""bottega doctor: is this machine ready to run the configured roles?"""

import json
import sys

from .. import config, xdg
from ..harness import probe
from ..util import EXIT_REFUSED
from ..version import __version__


def add_parser(sub):
    parser = sub.add_parser("doctor", help="check tools, configuration and harnesses")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.set_defaults(handler=run)


class Report:
    def __init__(self):
        self.checks = []

    def add(self, status, check, detail):
        self.checks.append({"check": check, "status": status, "detail": detail})

    def ok(self, check, detail=""):
        self.add("ok", check, detail)

    def warn(self, check, detail):
        self.add("warn", check, detail)

    def fail(self, check, detail):
        self.add("fail", check, detail)

    @property
    def failed(self):
        return any(c["status"] == "fail" for c in self.checks)


def check_tools(report):
    report.ok("python3", sys.version.split()[0])
    ok, detail = probe("git")
    (report.ok if ok else report.fail)("git", detail)
    ok, detail = probe("gh")
    if ok:
        report.ok("gh", detail)
    else:
        report.warn("gh", detail + "; bottega pr needs it")


def check_config(report):
    path = xdg.config_file()
    try:
        raw = config.read(path)
    except config.ConfigError as error:
        report.fail("config", str(error))
        return
    found = config.problems(raw)
    if found:
        for problem in found:
            report.fail("config", problem)
        return
    cfg = config.validate(raw)
    report.ok("config", "%s (rounds %d)" % (path, cfg["rounds"]))
    bound = set()
    probed = {}
    for role in config.ROLES:
        name = cfg["roles"].get(role)
        if name is None:
            report.ok("role " + role, "not configured (optional)")
            continue
        bound.add(name)
        profile = cfg["profiles"][name]
        harness = profile["harness"]
        binary = config.HARNESS_BINARIES[harness]
        if binary not in probed:
            probed[binary] = probe(binary)
        ok, detail = probed[binary]
        check = "role %s" % role
        summary = "%s -> %s, %s, effort %s" % (
            name,
            harness,
            profile["model"],
            profile["effort"],
        )
        if ok:
            report.ok(check, "%s; %s" % (summary, detail))
        else:
            report.fail(check, "%s; %s: %s" % (summary, binary, detail))
    for name in sorted(cfg["profiles"]):
        missing = config.missing_env(cfg["profiles"][name])
        if not missing:
            continue
        message = "profile %s needs unset variable(s): %s" % (
            name,
            ", ".join(missing),
        )
        if name in bound:
            report.fail("env", message)
        else:
            report.warn("env", message + " (not bound to a role)")


def run(args):
    report = Report()
    check_tools(report)
    check_config(report)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not report.failed,
                    "version": __version__,
                    "config": str(xdg.config_file()),
                    "data": str(xdg.data_dir()),
                    "checks": report.checks,
                },
                indent=2,
            )
        )
    else:
        labels = {"ok": "[ OK ]", "warn": "[WARN]", "fail": "[FAIL]"}
        print("bottega-kit %s" % __version__)
        for check in report.checks:
            detail = (": " + check["detail"]) if check["detail"] else ""
            print("  %s %s%s" % (labels[check["status"]], check["check"], detail))
        counts = {s: 0 for s in labels}
        for check in report.checks:
            counts[check["status"]] += 1
        print(
            "%d ok, %d warning(s), %d failure(s)"
            % (counts["ok"], counts["warn"], counts["fail"])
        )
    return EXIT_REFUSED if report.failed else 0
