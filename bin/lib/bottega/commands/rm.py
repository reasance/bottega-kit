"""bottega rm: remove a task's worktree and branch; keep its directory."""

import sys
from pathlib import Path

from .. import state, worktree
from ..util import Refused


def add_parser(sub):
    parser = sub.add_parser(
        "rm", help="remove a task's worktree and branch (the task directory stays)"
    )
    parser.add_argument(
        "task", help="task id, a unique prefix or suffix, or the task directory"
    )
    parser.add_argument("--yes", action="store_true", help="do not ask")
    parser.set_defaults(handler=run)


def confirm(st):
    prompt = (
        "remove worktree %s and delete branch %s (unpushed commits are lost)? [y/N] "
        % (st["worktree"], st["branch"])
    )
    if not sys.stdin.isatty():
        raise Refused("pass --yes to remove %s without a prompt" % st["task"])
    answer = input(prompt)
    return answer.strip().lower() in ("y", "yes")


def run(args):
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    if st["phase"] == "removed":
        print("%s: already removed" % st["task"])
        return 0
    with state.locked(task_dir):
        if not args.yes and not confirm(st):
            print("nothing removed")
            return 0
        repo = Path(st["repo"])
        if repo.is_dir():
            done = worktree.remove(repo, st["worktree"], st["branch"])
        else:
            done = ["repository %s is gone; nothing to remove there" % repo]
        st = state.load(task_dir)
        st["phase"] = "removed"
        st["current_run"] = None
        state.save(task_dir, st)
    for line in done:
        print(line)
    print("kept %s" % task_dir)
    return 0
