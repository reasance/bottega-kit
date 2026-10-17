"""bottega run: the implementer/reviewer loop, then the judge (plan §3).

Phase approved -> running -> done | stopped. Refuses (exit 2) unless the
task is approved, the plan still hashes to what was approved, and every
approved binding still works. Exit 0 done, 3 stopped.
"""

from .. import config, loop, state
from ..util import Refused


def add_parser(sub):
    parser = sub.add_parser(
        "run", help="implementer and reviewer rounds up to the cap, then the judge"
    )
    parser.add_argument("task", help="task id, or a unique prefix or suffix")
    parser.set_defaults(handler=run)


def check_phase(st):
    if st["phase"] == "stopped":
        raise Refused(
            "task %s is stopped (%s); continue with: bottega resume %s"
            % (st["task"], (st.get("stopped") or {}).get("reason"), st["task"])
        )
    if st["phase"] != "approved":
        raise Refused(
            "task %s is %s; run needs an approved plan (bottega approve)"
            % (st["task"], st["phase"])
        )


def run(args):
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
        loop.check_plan(task_dir, st)
        loop.start_run(st)
        loop.check_prompts(task_dir, st, roles, test_cmd)
        state.save(task_dir, st)
        return loop.Loop(task_dir, cfg, roles, test_cmd).drive()
