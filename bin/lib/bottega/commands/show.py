"""bottega show: one task's state."""

import json

from .. import state, taskdoc


def add_parser(sub):
    parser = sub.add_parser("show", help="show a task")
    parser.add_argument("task", help="task id, or a unique prefix or suffix")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.set_defaults(handler=run)


def todo_summary(task_dir):
    try:
        text = state.task_doc(task_dir).read_text(encoding="utf-8")
    except OSError:
        return []
    return [item.as_dict() for item in taskdoc.todo_items(text)]


def run(args):
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    todo = todo_summary(task_dir)
    if args.json:
        print(
            json.dumps(
                {
                    "task_dir": str(task_dir),
                    "task_doc": str(state.task_doc(task_dir)),
                    "state": st,
                    "todo": todo,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    done = sum(1 for item in todo if item["checked"])
    rows = [
        ("task", st["task"]),
        ("title", st["title"]),
        ("phase", st["phase"]),
        ("repo", st["repo"]),
        ("worktree", st["worktree"]),
        ("branch", "%s (base %s)" % (st["branch"], st["base"])),
        ("task.md", str(state.task_doc(task_dir))),
        ("to-do", "%d of %d done" % (done, len(todo))),
    ]
    if st.get("roles"):
        rows.append(
            ("roles", ", ".join("%s=%s" % kv for kv in sorted(st["roles"].items())))
        )
    if st.get("rounds"):
        rows.append(("round", "%d of %d" % (st["round"], st["rounds"])))
    if st.get("last_signal"):
        sig = st["last_signal"]
        rows.append(
            (
                "signal",
                "%s by %s: %s" % (sig["status"], sig["by"], sig.get("reason") or ""),
            )
        )
    if st.get("stopped"):
        stop = st["stopped"]
        rows.append(("stopped", "%s %s" % (stop["reason"], stop.get("detail") or "")))
    for label, value in rows:
        print("%-9s %s" % (label, value))
    return 0
