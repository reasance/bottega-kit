"""bottega show: one task's state, its signal, its stop and its runs."""

import json

from .. import loop, state, taskdoc
from ..util import format_duration


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


def run_lines(st, records):
    """One line per run: seq role profile status reason signal duration."""
    by_seq = {record.get("seq"): record for record in records}
    lines = []
    for entry in st.get("runs") or []:
        record = by_seq.get(entry.get("seq")) or {}
        seconds = record.get("duration_s")
        lines.append(
            "%03d %-11s %-16s %-7s %-22s %-10s %s"
            % (
                entry.get("seq", 0),
                entry.get("role", "?"),
                entry.get("profile", "?"),
                entry.get("status", "?"),
                entry.get("reason") or "-",
                entry.get("signal") or "-",
                format_duration(seconds) if seconds is not None else "-",
            )
        )
    return lines


def run(args):
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    todo = todo_summary(task_dir)
    records = loop.records(task_dir)
    if args.json:
        print(
            json.dumps(
                {
                    "task_dir": str(task_dir),
                    "task_doc": str(state.task_doc(task_dir)),
                    "state": st,
                    "todo": todo,
                    "runs": records,
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
            ("overrides", ", ".join("%s=%s" % kv for kv in sorted(st["roles"].items())))
        )
    approval = st.get("approval")
    if approval:
        rows.append(
            (
                "roles",
                ", ".join("%s=%s" % kv for kv in sorted(approval["roles"].items())),
            )
        )
    if st.get("rounds"):
        rows.append(("round", "%d of %d" % (st.get("round") or 0, st["rounds"])))
    if st.get("next_role"):
        rows.append(("next", st["next_role"]))
    sig = st.get("last_signal")
    if sig:
        rows.append(
            (
                "signal",
                "%s by %s (run %s)%s"
                % (
                    sig["status"],
                    sig["by"],
                    sig.get("run") or "?",
                    ": " + sig["reason"] if sig.get("reason") else "",
                ),
            )
        )
        if sig.get("uncheck"):
            rows.append(("unchecked", " ".join(sig["uncheck"])))
    stop = st.get("stopped")
    if stop:
        rows.append(
            ("stopped", "%s: %s" % (stop["reason"], stop.get("detail") or "")),
        )
    for label, value in rows:
        print("%-9s %s" % (label, value))
    lines = run_lines(st, records)
    if lines:
        print()
        print(
            "%-3s %-11s %-16s %-7s %-22s %-10s %s"
            % ("seq", "role", "profile", "status", "reason", "signal", "duration")
        )
        for line in lines:
            print(line)
    return 0
