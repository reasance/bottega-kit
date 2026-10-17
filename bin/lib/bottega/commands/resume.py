"""bottega resume: continue a stopped task with a fresh cap (plan §3).

cap = current round + N (N defaults to the configuration's `rounds`). The
loop restarts at state.next_role: after cap-reached or judge-needs-work the
implementer opens a new round; after any other stop the role that stopped
runs again, in the same round, with a new run number. On an approved task
resume is the same as run (with --rounds N as its cap). A task left
`running` by a bottega that died is first stopped as `interrupted`.
"""

from .. import config, loop, state
from ..util import Refused, UsageError

FROM_PHASES = ("stopped", "approved", "running")


def add_parser(sub):
    parser = sub.add_parser("resume", help="continue a stopped task with a fresh cap")
    parser.add_argument("task", help="task id, or a unique prefix or suffix")
    parser.add_argument(
        "--rounds",
        type=int,
        metavar="N",
        help="rounds to add to the current one (default: the configuration's)",
    )
    parser.set_defaults(handler=run)


def check_phase(st):
    if st["phase"] not in FROM_PHASES:
        raise Refused(
            "task %s is %s; resume continues a stopped task" % (st["task"], st["phase"])
        )


def run(args):
    if args.rounds is not None and args.rounds < 1:
        raise UsageError("--rounds must be at least 1")
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    check_phase(st)
    cfg = config.load()
    roles = loop.check_bindings(cfg, st)
    loop.check_plan(task_dir, st)
    test_cmd = loop.test_command(st)
    with state.locked(task_dir):
        st = state.load(task_dir)
        check_phase(st)
        if st["phase"] == "running":
            # We hold the lock, so whoever set `running` is gone.
            loop.recover_interrupted(task_dir, st)
        loop.check_plan(task_dir, st)
        if st["phase"] == "approved":
            loop.start_run(st)
            if args.rounds:
                st["rounds"] = args.rounds
        else:
            loop.start_resume(st, args.rounds or cfg["rounds"])
        loop.check_prompts(task_dir, st, roles, test_cmd)
        state.save(task_dir, st)
        return loop.Loop(task_dir, cfg, roles, test_cmd).drive()
