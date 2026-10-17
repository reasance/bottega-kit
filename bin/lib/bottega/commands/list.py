"""bottega list: every task, one line each."""

from .. import state
from ..util import BottegaError


def add_parser(sub):
    parser = sub.add_parser("list", help="list tasks")
    parser.set_defaults(handler=run)


def run(args):
    tasks = state.all_tasks()
    if not tasks:
        print("no tasks")
        return 0
    for task_id, task_dir in tasks:
        try:
            st = state.load(task_dir)
            phase, title = st["phase"], st["title"]
        except BottegaError as error:
            phase, title = "unreadable", str(error)
        print("%-50s %-10s %-20s %s" % (task_id, phase, task_dir.parent.name, title))
    return 0
