"""bottega new: task directory, task.md, worktree and branch."""

import datetime
import shutil
import sys
from pathlib import Path

from .. import KIT_ROOT, config, state, taskdoc, worktree, xdg
from ..util import Refused, UsageError, atomic_write, slugify

TEMPLATE = KIT_ROOT / "templates" / "task.md"


def add_parser(sub):
    parser = sub.add_parser("new", help="create a task, its worktree and its branch")
    parser.add_argument(
        "--repo", help="the git repository (default: the current directory)"
    )
    parser.add_argument("--title", required=True, help="a short title for the task")
    request = parser.add_mutually_exclusive_group(required=True)
    request.add_argument("--request", help="the request, verbatim")
    request.add_argument(
        "--request-file", help="read the request from this file ('-' for stdin)"
    )
    parser.add_argument(
        "--base", help="branch or commit to start from (default: origin/HEAD)"
    )
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        metavar="ROLE=PROFILE",
        help="bind a role to a profile for this task only (repeatable)",
    )
    parser.set_defaults(handler=run)


def read_request(args):
    if args.request is not None:
        text = args.request
    elif args.request_file == "-":
        text = sys.stdin.read()
    else:
        try:
            text = Path(args.request_file).read_text(encoding="utf-8")
        except OSError as error:
            raise UsageError(
                "cannot read %s: %s" % (args.request_file, error)
            ) from None
    if not text.strip():
        raise UsageError("the request is empty")
    return text


def role_overrides(specs):
    if not specs:
        return {}
    overrides = {}
    for spec in specs:
        role, profile = config.parse_role_override(spec)
        overrides[role] = profile
    cfg = config.load()
    for role, profile in overrides.items():
        problem = config.binding_problem(role, profile, cfg["profiles"])
        if problem:
            raise config.ConfigError(problem)
    return overrides


def task_id_for(title, project_dir, now=None):
    now = now or datetime.datetime.now()
    base = "%s-%s" % (now.strftime("%Y%m%d-%H%M"), slugify(title))
    candidate, n = base, 2
    while (project_dir / candidate).exists():
        candidate = "%s-%d" % (base, n)
        n += 1
    return candidate


def run(args):
    title = args.title.strip()
    if not title:
        raise UsageError("the title is empty")
    request = read_request(args)
    overrides = role_overrides(args.role)
    repo = worktree.repo_root(Path(args.repo) if args.repo else Path.cwd())
    project = slugify(repo.name)
    base_ref = args.base or worktree.project_config(repo).get("base")
    base, start = worktree.detect_base(repo, base_ref)
    project_dir = xdg.tasks_dir() / project
    task_id = task_id_for(title, project_dir)
    task_dir = project_dir / task_id
    try:
        template = TEMPLATE.read_text(encoding="utf-8")
    except OSError as error:
        raise Refused("cannot read the task template: %s" % error) from None
    task_dir.mkdir(parents=True)
    try:
        atomic_write(state.task_doc(task_dir), taskdoc.seed(template, title, request))
        path, branch = worktree.create(repo, task_id, start)
    except BaseException:
        # Like bottega: a task whose worktree could not be made does not exist.
        shutil.rmtree(task_dir, ignore_errors=True)
        raise
    state.save(
        task_dir,
        state.new_state(task_id, project, title, repo, path, branch, base, overrides),
    )
    print("task      %s" % task_id)
    print("task.md   %s" % state.task_doc(task_dir))
    print("worktree  %s" % path)
    print("branch    %s (from %s)" % (branch, start))
    print("next: edit task.md if you like, then: bottega plan %s" % task_id)
    return 0
