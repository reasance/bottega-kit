"""bottega plan: one planner dispatch; a plan, or questions for you (plan §3).

Phase new|questions|planned -> planning -> questions|planned. A failed
dispatch leaves the phase where it was, keeps the receipt and exits 3.
"""

import sys

from .. import config, dispatch, loop, receipts, state, taskdoc
from ..util import EXIT_STOPPED, Refused, atomic_write, now_iso

ROLE = "planner"
FROM_PHASES = ("new", "questions", "planned")


def add_parser(sub):
    parser = sub.add_parser(
        "plan", help="one planner dispatch: a plan in task.md, or questions for you"
    )
    parser.add_argument(
        "task", help="task id, a unique prefix or suffix, or the task directory"
    )
    parser.set_defaults(handler=run)


def check_phase(st):
    if st["phase"] not in FROM_PHASES:
        raise Refused(
            "task %s is %s; plan runs when the task is %s"
            % (st["task"], st["phase"], "|".join(FROM_PHASES))
        )


def planner_profile(cfg, st):
    """(profile name, profile) for the task's effective planner binding."""
    bindings = config.role_bindings(cfg, st.get("roles"))
    name = bindings.get(ROLE)
    problem = config.binding_problem(ROLE, name, cfg["profiles"])
    if problem:
        raise config.ConfigError(problem)
    profile = cfg["profiles"][name]
    missing = config.missing_env(profile)
    if missing:
        raise config.ConfigError(
            "profile %s needs unset variable(s): %s" % (name, ", ".join(missing))
        )
    return name, profile


def _finish_entry(st, run_name, status, reason=None):
    for entry in st["runs"]:
        if state.run_name(entry["seq"], entry["role"]) == run_name:
            entry["status"] = status
            entry["finished"] = now_iso()
            if reason:
                entry["reason"] = reason
    st["current_run"] = None


def run(args):
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    check_phase(st)
    cfg = config.load()
    name, profile = planner_profile(cfg, st)
    command_test = loop.test_command(st)
    with state.locked(task_dir):
        st = state.load(task_dir)
        check_phase(st)
        previous = st["phase"]
        seq = receipts.next_seq(st, task_dir)
        run_name = state.run_name(seq, ROLE)
        st["phase"] = "planning"
        st["current_run"] = run_name
        st["runs"].append(
            {
                "seq": seq,
                "role": ROLE,
                "profile": name,
                "status": "running",
                "started": now_iso(),
            }
        )
        state.save(task_dir, st)
        rounds = st.get("rounds") or cfg["rounds"]
        try:
            outcome = dispatch.run(
                st, task_dir, seq, ROLE, name, profile, rounds, command_test
            )
        except BaseException:
            st = state.load(task_dir)
            if state.run_dir(task_dir, run_name).is_dir():
                _finish_entry(st, run_name, "failed", "interrupted")
            else:
                st["runs"] = [
                    e
                    for e in st["runs"]
                    if state.run_name(e["seq"], e["role"]) != run_name
                ]
                st["current_run"] = None
            st["phase"] = previous
            state.save(task_dir, st)
            raise
        result, asked = merge(task_dir, st, outcome)
        st = state.load(task_dir)
        if outcome.ok:
            _finish_entry(st, run_name, "ok")
            st["phase"] = result
        else:
            _finish_entry(st, run_name, "failed", outcome.reason)
            st["phase"] = previous
        state.save(task_dir, st)

    seconds = outcome.record["duration_s"]
    word = result if outcome.ok else "failed " + outcome.reason
    print(dispatch.line(seq, ROLE, name, profile["model"], word, seconds))
    rails = outcome.record.get("rails") or {}
    if rails.get("new_untracked"):
        print(
            "bottega plan: warning: new untracked file(s) in the worktree: %s"
            % ", ".join(rails["new_untracked"]),
            file=sys.stderr,
        )
    if not outcome.ok:
        error = outcome.record
        print(
            "bottega plan: %s; receipt: %s" % (error["reason"], outcome.run_dir),
            file=sys.stderr,
        )
        return EXIT_STOPPED
    if asked:
        print()
        print(asked)
        print()
        print(
            "answer in %s, then run: bottega plan %s"
            % (state.task_doc(task_dir), st["task"])
        )
    return 0


def merge(task_dir, st, outcome):
    """Fold the planner's final message into task.md.

    Returns (new phase, questions text or None). An unusable message turns the
    outcome into a failure (planner-output-invalid) and leaves task.md as it was.
    """
    if not outcome.ok:
        return None, None
    doc_path = state.task_doc(task_dir)
    doc = doc_path.read_text(encoding="utf-8")
    asked = taskdoc.questions(outcome.final)
    if asked is not None:
        atomic_write(doc_path, taskdoc.with_questions(doc, asked))
        return "questions", asked
    problems = taskdoc.plan_problems(outcome.final)
    if problems:
        dispatch.fail(outcome, "parse", "planner-output-invalid", "; ".join(problems))
        return None, None
    atomic_write(doc_path, taskdoc.merge_plan(doc, outcome.final, st["title"]))
    return "planned", None
