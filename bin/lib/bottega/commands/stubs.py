"""Subcommands that later milestones implement. They exit 64 for now."""

import argparse
import sys

from ..util import EXIT_USAGE

PLANNED = {
    "plan": "one planner dispatch",
    "approve": "approve the plan and freeze roles and the round cap",
    "run": "implementer and reviewer rounds, then the judge",
    "resume": "continue a stopped run with a fresh cap",
    "pr": "push the branch and open the pull request",
}


def _not_implemented(args):
    print(
        "bottega %s: not implemented in this milestone" % args.command,
        file=sys.stderr,
    )
    return EXIT_USAGE


def add_parsers(sub):
    for name, summary in PLANNED.items():
        parser = sub.add_parser(name, help=summary + " (not implemented yet)")
        parser.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
        parser.set_defaults(handler=_not_implemented)
