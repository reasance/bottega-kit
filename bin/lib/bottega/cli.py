"""Argument parsing and dispatch for `bottega`."""

import argparse
import sys

from .commands import (
    approve,
    doctor,
    init,
    new,
    plan,
    resume,
    rm,
    show,
    signal,
    stubs,
)
from .commands import run as run_command
from .commands import list as listing
from .util import EXIT_USAGE, BottegaError
from .version import __version__

COMMANDS = (
    init,
    doctor,
    new,
    plan,
    approve,
    run_command,
    resume,
    show,
    listing,
    rm,
    signal,
)


class Parser(argparse.ArgumentParser):
    """argparse exits 2 on bad usage; bottega reserves 2 for refusals."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, "%s: %s\n" % (self.prog, message))


def build_parser():
    parser = Parser(
        prog="bottega",
        description="Run a planner, an implementer, a reviewer and an optional "
        "judge on your coding agents, in a git worktree.",
    )
    parser.add_argument(
        "--version", action="version", version="bottega-kit %s" % __version__
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True
    for module in COMMANDS:
        module.add_parser(sub)
    stubs.add_parsers(sub)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except BottegaError as error:
        print("bottega %s: %s" % (args.command, error), file=sys.stderr)
        return error.code
    except KeyboardInterrupt:
        print("bottega: interrupted", file=sys.stderr)
        return 130
