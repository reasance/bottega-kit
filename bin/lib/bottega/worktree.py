"""Git worktrees: one per task, a sibling of the repository (plan §2.11).

Provisioning belongs to the project: git runs the repository's own
post-checkout hook inside `git worktree add`. bottega-kit copies nothing.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from .util import Refused, UsageError, run_git

BRANCH_PREFIX = "bottega/"


def repo_root(path):
    """The top level of the git repository containing `path`."""
    path = Path(path)
    if not path.is_dir():
        raise UsageError("%s is not a directory" % path)
    proc = run_git(["rev-parse", "--show-toplevel"], path, check=False)
    if proc.returncode != 0:
        raise UsageError("%s is not inside a git repository" % path)
    return Path(proc.stdout.strip()).resolve()


def project_config(repo):
    """<repo>/bottega.json, or {} when absent (plan §2.13)."""
    path = Path(repo) / "bottega.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise Refused("%s is not valid JSON: %s" % (path, error)) from None
    if not isinstance(value, dict):
        raise Refused("%s must hold a JSON object" % path)
    return value


def _verify(repo, ref):
    proc = run_git(
        ["rev-parse", "--verify", "--quiet", ref + "^{commit}"], repo, check=False
    )
    return proc.returncode == 0


def detect_base(repo, explicit=None):
    """(base branch name, start point) for a new task branch.

    An explicit base is used as given. Otherwise origin/HEAD, then local main,
    then local master. Nothing is fetched: origin/HEAD is as fresh as the
    last fetch.
    """
    if explicit:
        if not _verify(repo, explicit):
            raise Refused("base %r is not a commit in %s" % (explicit, repo))
        name = (
            explicit[len("origin/") :] if explicit.startswith("origin/") else explicit
        )
        return name, explicit
    proc = run_git(
        ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        repo,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        start = proc.stdout.strip()  # e.g. origin/main
        if _verify(repo, start):
            return start.split("/", 1)[1], start
    for name in ("main", "master"):
        if _verify(repo, "refs/heads/" + name):
            return name, name
    raise Refused(
        "cannot find a base branch in %s (no origin/HEAD, main or master); "
        "pass --base" % repo
    )


def branch_name(task_id):
    return BRANCH_PREFIX + task_id


def worktree_path(repo, task_id):
    repo = Path(repo)
    return repo.parent / (repo.name + "-worktrees") / task_id


def branch_exists(repo, branch):
    return _verify(repo, "refs/heads/" + branch)


def create(repo, task_id, start):
    """`git worktree add -b bottega/<id> <path> <start>`; returns (path, branch)."""
    path = worktree_path(repo, task_id)
    branch = branch_name(task_id)
    if path.exists():
        raise Refused("%s already exists" % path)
    if branch_exists(repo, branch):
        raise Refused("branch %s already exists in %s" % (branch, repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    run_git(["worktree", "add", "-b", branch, str(path), start], repo)
    return path, branch


def remove(repo, path, branch):
    """`git worktree remove --force` + `git branch -D`. Returns what was done."""
    done = []
    path = Path(path)
    if path.exists():
        run_git(["worktree", "remove", "--force", str(path)], repo)
        done.append("removed worktree %s" % path)
    run_git(["worktree", "prune"], repo, check=False)
    if branch_exists(repo, branch):
        run_git(["branch", "-D", branch], repo)
        done.append("deleted branch %s" % branch)
    parent = path.parent
    if parent.name.endswith("-worktrees") and parent.is_dir():
        try:
            parent.rmdir()  # only when empty
        except OSError:
            pass
    return done


# Rails (used by the loop in M2): a role that must not change code is checked
# by hashing HEAD and the tracked diff before and after it runs.


def head(worktree):
    return run_git(["rev-parse", "HEAD"], worktree)


def tracked_diff_sha256(worktree):
    """sha256 of every tracked change against HEAD, staged or not."""
    proc = subprocess.run(
        ["git", "diff", "HEAD", "--binary", "--no-ext-diff", "--no-color"],
        cwd=str(worktree),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise Refused(
            "git diff failed in %s: %s"
            % (worktree, proc.stderr.decode("utf-8", "replace").strip())
        )
    return hashlib.sha256(proc.stdout).hexdigest()


def untracked(worktree):
    out = run_git(["ls-files", "--others", "--exclude-standard", "-z"], worktree)
    return sorted(name for name in out.split("\0") if name)


def snapshot(worktree):
    return {
        "head": head(worktree),
        "diff_sha": tracked_diff_sha256(worktree),
        "untracked": untracked(worktree),
    }


def rails(before, after):
    """The run.json `rails` block from two snapshots."""
    return {
        "head_before": before["head"],
        "head_after": after["head"],
        "diff_sha_before": before["diff_sha"],
        "diff_sha_after": after["diff_sha"],
        "new_untracked": sorted(set(after["untracked"]) - set(before["untracked"])),
    }


def changed(rail):
    """True when HEAD or the tracked diff moved."""
    return (
        rail["head_before"] != rail["head_after"]
        or rail["diff_sha_before"] != rail["diff_sha_after"]
    )
