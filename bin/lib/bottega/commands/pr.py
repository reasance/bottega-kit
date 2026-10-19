"""bottega pr: commit if needed, push to origin, open the pull request.

Deterministic, no agent (plan §2.12, §5 M3). Allowed when the task is done
or stopped; a stopped task's PR says so in its body. Only `origin` is ever
touched; nothing is merged. gh is always given `--repo` from origin's URL,
because gh on its own prefers a remote named `upstream`.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from .. import state, taskdoc
from ..util import Refused, atomic_write, now_iso, run_git

ALLOWED_PHASES = ("done", "stopped")
BODY_FILE = "pr-body.md"
REMOTE = "origin"

# https://host/owner/repo(.git), ssh://[user@]host[:port]/owner/repo, git://...
_URL = re.compile(
    r"^(?:https?|ssh|git)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/([^/]+)/([^/]+?)(?:\.git)?/?$"
)
# [user@]host:owner/repo(.git)
_SCP = re.compile(r"^(?:[^@/]+@)?([^/:]+):([^/]+)/([^/]+?)(?:\.git)?/?$")


def add_parser(sub):
    parser = sub.add_parser(
        "pr", help="commit if needed, push the branch to origin, open the pull request"
    )
    parser.add_argument(
        "task", help="task id, a unique prefix or suffix, or the task directory"
    )
    parser.set_defaults(handler=run)


def check_phase(st):
    if st["phase"] not in ALLOWED_PHASES:
        raise Refused(
            "task %s is %s; bottega pr needs a task that is done or stopped"
            % (st["task"], st["phase"])
        )


def gh_repo(url):
    """HOST/OWNER/REPO for gh's --repo, from a remote URL; None if not one."""
    url = (url or "").strip()
    match = _URL.match(url) or _SCP.match(url)
    if not match:
        return None
    return "%s/%s/%s" % match.groups()


def origin_repo(worktree):
    """origin's URL as configured (before any insteadOf) and its gh repo."""
    proc = run_git(["config", "--get", "remote.%s.url" % REMOTE], worktree, check=False)
    url = proc.stdout.strip()
    if proc.returncode != 0 or not url:
        raise Refused(
            "the repository has no %s remote; bottega pr pushes to %s only"
            % (REMOTE, REMOTE)
        )
    repo = gh_repo(url)
    if repo is None:
        raise Refused(
            "%s is %s, which is not a host/owner/repo URL gh can open a pull "
            "request on" % (REMOTE, url)
        )
    return repo


def git_or_refuse(args, worktree, what):
    """Run git; on failure refuse with git's whole message."""
    proc = run_git(args, worktree, check=False)
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout).strip() or "exit %d" % proc.returncode
        raise Refused("%s failed:\n%s" % (what, message))
    return proc.stdout.strip()


def gh(args, worktree):
    return subprocess.run(
        ["gh", *args], cwd=str(worktree), capture_output=True, text=True
    )


def base_ref(worktree, base):
    """The ref the PR compares against: origin/<base> when known, else <base>."""
    for ref in ("refs/remotes/%s/%s" % (REMOTE, base), "refs/heads/" + base, base):
        proc = run_git(
            ["rev-parse", "--verify", "--quiet", ref + "^{commit}"],
            worktree,
            check=False,
        )
        if proc.returncode == 0:
            return ref
    return None


def commit_message(st):
    return "%s\n\nbottega task %s" % (st["title"], st["task"])


def commit_if_dirty(st, worktree):
    """`git add -A && git commit` when the worktree has changes. True if it did."""
    if not run_git(["status", "--porcelain"], worktree):
        return False
    git_or_refuse(["add", "-A"], worktree, "git add -A")
    git_or_refuse(["commit", "-q", "-m", commit_message(st)], worktree, "git commit")
    return True


def render_body(st, doc):
    """The PR body from task.md and the state. No link to the local task.md."""
    parts = []
    stop = st.get("stopped") if st["phase"] == "stopped" else None
    if stop:
        detail = (stop.get("detail") or "").strip()
        parts += [
            "**Stopped: %s%s**"
            % (stop.get("reason") or "?", " — " + detail if detail else ""),
            "",
            "The loop did not finish; review this pull request with that in mind.",
            "",
        ]
    overview = (taskdoc.get_section(doc, taskdoc.OVERVIEW) or "").strip()
    parts += ["## Overview", "", overview or "No overview was written.", ""]
    findings = _content(taskdoc.get_section(doc, taskdoc.FINDINGS))
    parts += [
        "## What was verified",
        "",
        findings or "No review findings were recorded.",
        "",
        "Rounds used: %d of %d" % (st.get("round") or 0, st.get("rounds") or 0),
        "",
    ]
    verdict = _content(taskdoc.get_section(doc, taskdoc.VERDICT))
    if verdict:
        parts += ["## Verdict", "", verdict, ""]
    parts += ["---", "", "Opened by bottega-kit for task %s." % st["task"]]
    return "\n".join(parts) + "\n"


_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _content(body):
    """A section body without the template's HTML comments; '' when empty."""
    return _COMMENT.sub("", body or "").strip()


def existing_pr(st, worktree, repo):
    """The URL of a pull request already open (or merged) for the branch."""
    proc = gh(
        ["pr", "view", st["branch"], "--repo", repo, "--json", "url,state"], worktree
    )
    if proc.returncode != 0:
        return None
    try:
        found = json.loads(proc.stdout or "{}")
    except ValueError:
        return None
    url = found.get("url") if isinstance(found, dict) else None
    if not url or found.get("state") == "CLOSED":
        return None
    return url


def create_pr(st, worktree, repo, body_file):
    proc = gh(
        [
            "pr",
            "create",
            "--repo",
            repo,
            "--base",
            st["base"],
            "--head",
            st["branch"],
            "--title",
            st["title"],
            "--body-file",
            str(body_file),
        ],
        worktree,
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout).strip() or "exit %d" % proc.returncode
        raise Refused("gh pr create failed:\n%s" % message)
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    urls = [line for line in lines if line.startswith(("https://", "http://"))]
    if not urls:
        raise Refused("gh pr create printed no URL: %s" % proc.stdout.strip())
    return urls[-1]


def run(args):
    task_dir = state.resolve(args.task)
    st = state.load(task_dir)
    check_phase(st)
    with state.locked(task_dir):
        st = state.load(task_dir)
        check_phase(st)
        worktree = Path(st["worktree"])
        if not worktree.is_dir():
            raise Refused("the worktree %s is gone" % worktree)
        repo = origin_repo(worktree)
        if shutil.which("gh") is None:
            raise Refused("gh is not on PATH; bottega pr opens the PR with it")
        commit_if_dirty(st, worktree)
        ref = base_ref(worktree, st["base"])
        if ref is not None:
            ahead = run_git(["rev-list", "--count", ref + "..HEAD"], worktree)
            if ahead.strip() == "0":
                raise Refused(
                    "nothing to submit: %s has no commit ahead of %s and no "
                    "uncommitted change" % (st["branch"], st["base"])
                )
        git_or_refuse(
            ["push", "-q", "-u", REMOTE, st["branch"]],
            worktree,
            "git push -u %s %s" % (REMOTE, st["branch"]),
        )
        commit = run_git(["rev-parse", "HEAD"], worktree)
        url = existing_pr(st, worktree, repo)
        if url:
            line = "pr exists: " + url
        else:
            doc = state.task_doc(task_dir).read_text(encoding="utf-8")
            body_file = Path(task_dir) / BODY_FILE
            atomic_write(body_file, render_body(st, doc))
            url = create_pr(st, worktree, repo, body_file)
            line = url
        st["pr"] = {"url": url, "at": now_iso(), "commit": commit}
        state.save(task_dir, st)
    print(line)
    return 0
