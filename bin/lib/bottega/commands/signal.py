"""bottega signal: how an agent reports its verdict (plan §2.4, §4.7).

It writes runs/<current>/signal.json atomically and appends one line to
runs/<current>/signal.log. It never touches state.json: the orchestrator
folds the signal in after the harness exits, so the agent and the
orchestrator never write the same file. Standard library only, no network,
any working directory.
"""

import json
import os

from .. import state, taskdoc
from ..loop import SIGNALLING
from ..util import Refused, UsageError, atomic_write_json, now_iso

STATUSES = ("ready", "needs-work", "blocked")


def add_parser(sub):
    parser = sub.add_parser(
        "signal", help="for agents: report ready, needs-work or blocked"
    )
    parser.add_argument("task", help="task id, or a unique prefix or suffix")
    parser.add_argument("status", help="|".join(STATUSES))
    parser.add_argument("reason", nargs="?", default="", help="one line of why")
    parser.add_argument(
        "--uncheck",
        nargs="+",
        default=[],
        metavar="ID",
        help="to-do ids (T3 ...) the reviewer found not done",
    )
    parser.set_defaults(handler=run)


def run(args):
    if args.status not in STATUSES:
        raise UsageError(
            "status must be one of %s, got %r" % ("|".join(STATUSES), args.status)
        )
    malformed = [i for i in args.uncheck if not taskdoc.ITEM_ID.match(i)]
    if malformed:
        raise UsageError("--uncheck takes ids like T3, got: " + ", ".join(malformed))
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    if st["phase"] != "running":
        raise Refused(
            "task %s is %s, not running; nothing to signal" % (st["task"], st["phase"])
        )
    current = st.get("current_run")
    if not current:
        raise Refused("task %s has no current run" % st["task"])
    role = state.current_role(st)
    if role is None:
        raise Refused("current run %s is not in the runs list" % current)
    allowed = SIGNALLING.get(role, ())
    if args.status not in allowed:
        if allowed:
            raise UsageError(
                "the %s may signal %s, not %s" % (role, "|".join(allowed), args.status)
            )
        raise UsageError("the %s does not signal" % role)
    if args.uncheck:
        text = state.task_doc(task_dir).read_text(encoding="utf-8")
        known = set(taskdoc.item_ids(text))
        unknown = [i for i in args.uncheck if i not in known]
        if unknown:
            raise Refused("no to-do item with id: " + ", ".join(unknown))
    run_path = state.run_dir(task_dir, current)
    if not run_path.is_dir():
        raise Refused("run directory %s does not exist" % run_path)
    record = {
        "status": args.status,
        "reason": args.reason,
        "uncheck": list(dict.fromkeys(args.uncheck)),
        "by": role,
        "run": current,
        "at": now_iso(),
        "pid": os.getpid(),
    }
    atomic_write_json(run_path / "signal.json", record)
    # One write per line with O_APPEND, so concurrent calls never interleave.
    line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(str(run_path / "signal.log"), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    print("signal recorded: %s (%s, run %s)" % (args.status, role, current))
    return 0
