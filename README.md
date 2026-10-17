# bottega-kit

bottega-kit runs a planner, an implementer, a reviewer and an optional judge on the
coding agents you already have — Claude Code and Codex today — one role each, in a
git worktree, with a receipt for every step. You need git, gh, python3 and at least
one of those CLIs. This is not vdaubry/bottega: the process is
[theirs](https://github.com/vdaubry/bottega); the local, file-based, multi-vendor
loop is this project.

## Current release: 0.0.0

Nothing is released yet. The repository holds milestones M0 to M2:
configuration, tasks, worktrees, the `signal` command, the `claude` and `codex`
drivers, `plan`, `approve`, `run` and `resume`. `pr` comes next. The drivers
have been tested against fake harnesses only.

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

## Use

```sh
cd your-repo
bottega new --title "Add a dry-run flag" --request "Add --dry-run to the export command."
bottega plan <task>      # a unique prefix or suffix of the id is enough
bottega approve <task> --rounds 2
bottega run <task>
bottega resume <task> --rounds 1   # after a stop
bottega list
bottega show <task>
bottega rm <task> --yes  # removes the worktree and branch; keeps the task directory
```

`bottega plan` runs the planner once and prints one line:

```
001 planner fable-judge claude-fable-5-1 → questions (41s)
```

If the planner has questions, they are written into `task.md` under
`## Questions for you`. Answer under each question, in the file, and run
`bottega plan` again. When the planner writes a plan instead, it replaces the
plan sections of `task.md`; your original request stays as you wrote it. Read
the plan, edit it if you like, then `bottega approve`. Approval gives every
to-do item an id such as `[T3]` and records a hash of the plan, the roles and
the round cap; editing the plan afterwards means approving again.

`bottega run` starts the implementer, then the reviewer, and repeats the pair
until the reviewer is satisfied or the round cap is reached; then the judge, if
one is bound, gives the final word. Each dispatch prints one line:

```
002 implementer opus-builder claude-opus-5 → done (6m02s)
003 reviewer opus-reviewer claude-opus-5 → needs-work (2m14s)
004 implementer opus-builder claude-opus-5 → done (3m40s)
005 reviewer opus-reviewer claude-opus-5 → ready (1m55s)
006 judge fable-judge claude-fable-5-1 → ready (48s)
```

The implementer edits the worktree and ticks the to-do items in `task.md`; it
never commits. The reviewer's final message replaces `## Review Findings`, the
items it names with `--uncheck` are unticked for the next implementer, and the
judge's final message replaces `## Verdict`. A reviewer or judge that changes a
tracked file or commits stops the task.

A run ends in one of two ways:

- **done** (exit 0): the reviewer signalled `ready`, and so did the judge if
  there is one.
- **stopped** (exit 3), with the reason on stderr and in `bottega show`:
  `blocked` (the reviewer needs you), `cap-reached`, `judge-needs-work`,
  `dispatch-failed`, `timeout`, `identity-mismatch` (the harness reported
  another model), `role-modified-worktree`, or `interrupted` (Ctrl-C).

`bottega resume <task> [--rounds N]` continues a stopped task with a cap of
the current round plus N (default: the configuration's `rounds`). After
`cap-reached` or `judge-needs-work` it starts a new round with the
implementer; after any other stop it runs again the role that stopped. Nothing
is retried for you. If you edit the plan, approve it again first: `run` and
`resume` refuse a plan whose hash no longer matches the approval, and a
profile that was removed or a variable that is no longer set.

Exit codes: 0 done · 2 refused (wrong phase, plan changed, a binding no longer
works, the task is locked by another bottega) · 3 stopped · 64 bad invocation.

`bottega show <task>` prints the phase, the round and the cap, the next role,
the last signal, the stop reason and one line per run;
`bottega show <task> --json` adds every run's `run.json`.

Every dispatch leaves a receipt in the task directory, under
`runs/NNN-<role>/`: the prompt, the final message, the raw events, `run.json`,
`signal.json` when the agent signalled and, when it failed, `error.json`. A
failed dispatch exits 3 and changes nothing in `task.md`.

To change a prompt, copy it from the kit's `prompts/` directory to
`~/.config/bottega-kit/prompts/<name>.md` and edit it. Variables are written
`{{name}}`; an unknown name is refused before anything runs.

A repository may hold a `bottega.json` with `{"test_cmd": "...", "base": "main"}`:
`test_cmd` is given to the agents, `base` is the branch new tasks start from.

Tasks live in `~/.local/share/bottega-kit/tasks/<project>/<task-id>/`, outside the
repository, so they outlive the worktree.

## Licence

MIT. The process and parts of the templates come from
[vdaubry/bottega](https://github.com/vdaubry/bottega), also MIT; see `NOTICE`.
