"""bottega init: write a starter configuration from the harnesses on PATH."""

import shutil

from .. import config, xdg
from ..util import Refused


def add_parser(sub):
    parser = sub.add_parser("init", help="write a starter configuration")
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing configuration"
    )
    parser.set_defaults(handler=run)


def detect():
    return [
        harness
        for harness, binary in sorted(config.HARNESS_BINARIES.items())
        if shutil.which(binary)
    ]


def run(args):
    path = xdg.config_file()
    if path.exists() and not args.force:
        raise Refused("%s already exists; pass --force to overwrite it" % path)
    found = detect()
    starter = config.starter(found)
    config.write(starter, path)
    print("wrote %s" % path)
    if found:
        print("harnesses found on PATH: %s" % ", ".join(found))
    else:
        print(
            "no harness found on PATH (looked for: %s); the starter uses claude"
            % ", ".join(sorted(config.HARNESS_BINARIES.values()))
        )
    for role in config.ROLES:
        if role in starter["roles"]:
            name = starter["roles"][role]
            profile = starter["profiles"][name]
            print(
                "  %-11s %s (%s, %s, effort %s)"
                % (role, name, profile["harness"], profile["model"], profile["effort"])
            )
    print("next: bottega doctor")
    return 0
