"""bottega approve: the one human gate (plan §2.10, §4.3).

Checks the plan, gives every to-do item a `[T<n>]` id, validates every role
binding the run will use, and records the plan hash, the roles and the
round cap. Approving again after an edit keeps the ids already given. A
stopped task may be approved again (after an edit to the plan); the next
`run` then starts over at round 1.
"""

from .. import config, harness, state, taskdoc
from ..util import Refused, UsageError, atomic_write, now_iso

FROM_PHASES = ("planned", "approved", "stopped")


def add_parser(sub):
    parser = sub.add_parser(
        "approve", help="approve the plan; freeze its hash, the roles and the cap"
    )
    parser.add_argument("task", help="task id, or a unique prefix or suffix")
    parser.add_argument(
        "--rounds",
        type=int,
        metavar="N",
        help="implementer/reviewer round cap (default: the configuration's)",
    )
    parser.set_defaults(handler=run)


def check_phase(st):
    if st["phase"] not in FROM_PHASES:
        raise Refused(
            "task %s is %s; approve needs a plan (phase planned, approved or stopped)"
            % (st["task"], st["phase"])
        )


def validate_roles(cfg, st):
    """The effective bindings and their report; any problem refuses (exit 2)."""
    bindings = config.role_bindings(cfg, st.get("roles"))
    report = harness.binding_report(cfg, bindings)
    problems = [p for entry in report for p in entry["problems"]]
    if problems:
        raise config.ConfigError(
            "cannot approve; role bindings:\n  " + "\n  ".join(problems)
        )
    return {entry["role"]: entry["profile"] for entry in report}, report


def run(args):
    if args.rounds is not None and args.rounds < 1:
        raise UsageError("--rounds must be at least 1")
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    check_phase(st)
    cfg = config.load()
    roles, report = validate_roles(cfg, st)
    with state.locked(task_dir):
        st = state.load(task_dir)
        check_phase(st)
        doc_path = state.task_doc(task_dir)
        text = doc_path.read_text(encoding="utf-8")
        problems = taskdoc.approval_problems(
            text, require_unchecked=st["phase"] != "stopped"
        )
        if problems:
            raise taskdoc.TaskDocError(
                "cannot approve %s:\n  %s" % (doc_path, "\n  ".join(problems))
            )
        text, assigned = taskdoc.assign_ids(text)
        if assigned:
            atomic_write(doc_path, text)
        previous = st.get("approval") or {}
        rounds = args.rounds or previous.get("rounds") or cfg["rounds"]
        digest = taskdoc.plan_sha256(text)
        st["approval"] = {
            "plan_sha256": digest,
            "roles": roles,
            "rounds": rounds,
            "at": now_iso(),
        }
        st["rounds"] = rounds
        st["round"] = 0
        st["next_role"] = "implementer"
        st["stopped"] = None
        st["phase"] = "approved"
        state.save(task_dir, st)

    ids = taskdoc.item_ids(text)
    print("approved %s" % st["task"])
    by_role = {entry["role"]: entry for entry in report}
    for role in config.ROLES:
        entry = by_role.get(role)
        if entry is None:
            print("  %-11s none" % role)
            continue
        print(
            "  %-11s %s (%s, %s, effort %s)"
            % (
                role,
                entry["profile"],
                entry["harness"],
                entry["model"],
                entry["effort"],
            )
        )
    print("rounds    %d" % rounds)
    print("plan      sha256 %s" % digest[:12])
    print(
        "to-do     %d item(s), %s; %d new id(s)" % (len(ids), _span(ids), len(assigned))
    )
    print("next: bottega run %s" % st["task"])
    return 0


def _span(ids):
    if not ids:
        return "no ids"
    return "%s..%s" % (ids[0], ids[-1]) if len(ids) > 1 else ids[0]
