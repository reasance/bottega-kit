# bottega-kit

bottega-kit runs a planner, an implementer, a reviewer and an optional judge on the
coding agents you already have — Claude Code and Codex today — one role each, in a
git worktree, with a receipt for every step. You need git, gh, python3 and at least
one of those CLIs. This is not vdaubry/bottega: the process is
[theirs](https://github.com/vdaubry/bottega); the local, file-based, multi-vendor
loop is this project.

## Current release: 0.0.0

Nothing is released yet. The repository holds milestone M0: configuration,
tasks, worktrees and the `signal` command. No model is dispatched until M1.

## How it works

```
bottega new      task directory, worktree and branch; task.md holds your request
bottega plan     the planner writes the plan into task.md, or asks you questions
bottega approve  you approve the plan once; its hash, the roles and the cap are frozen
bottega run      implementer and reviewer take turns, up to the round cap; then the judge
bottega pr       commit if needed, push to origin, open the pull request
```

Each role is bound to a profile: a harness (`claude` or `codex`), a model and an
effort. Agents report back by running `bottega signal`; bottega-kit decides what
happens next from that signal and from the files on disk, never from the
agent's prose.

## Configuration

`~/.config/bottega-kit/config.json`. Fable plans and judges, Opus implements and
reviews, all through Claude Code:

```json
{
  "schema_version": 1,
  "profiles": {
    "fable-judge":   {"harness": "claude", "model": "claude-fable-5-1", "effort": "max"},
    "opus-builder":  {"harness": "claude", "model": "claude-opus-5",   "effort": "high"},
    "opus-reviewer": {"harness": "claude", "model": "claude-opus-5",   "effort": "high"}
  },
  "roles": {"planner": "fable-judge", "implementer": "opus-builder",
            "reviewer": "opus-reviewer", "judge": "fable-judge"},
  "rounds": 3
}
```

A profile may also set `env` (values may reference your environment as
`${NAME}`; bottega-kit stores no secrets), `aliases`, `timeout` and, on
`claude`, `max_budget_usd`. The judge is optional.

## Install

```sh
git clone <this repository> bottega-kit
cd bottega-kit
./install.sh            # copies to ~/.local/share/bottega-kit, links ~/.local/bin/bottega
bottega init            # starter config from the CLIs found on PATH
bottega doctor          # checks tools, config and harnesses
```

`./uninstall.sh` removes the command and keeps your tasks and configuration.

## Use (M0)

```sh
cd your-repo
bottega new --title "Add a dry-run flag" --request "Add --dry-run to the export command."
bottega list
bottega show <task>      # a unique prefix or suffix of the id is enough
bottega rm <task> --yes  # removes the worktree and branch; keeps the task directory
```

Tasks live in `~/.local/share/bottega-kit/tasks/<project>/<task-id>/`, outside the
repository, so they outlive the worktree.

## Licence

MIT. The process and parts of the templates come from
[vdaubry/bottega](https://github.com/vdaubry/bottega), also MIT; see `NOTICE`.
