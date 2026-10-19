# bottega-kit

bottega-kit runs a planner, an implementer, a reviewer and an optional judge on the
coding agents you already have — Claude Code and Codex today — one role each, in a
git worktree, with a receipt for every step. You need git, gh, python3 and at least
one of those CLIs. This is not vdaubry/bottega: the process is
[theirs](https://github.com/vdaubry/bottega); the local, file-based, multi-vendor
loop is this project.

## Current release: 0.1.0

The first release: `init`, `doctor`, `new`, `plan`, `approve`, `run`, `resume`,
`pr` and the task commands, on the `claude` and `codex` harnesses. The loop
was verified live on 2026-10-17 with Claude Code 2.1.302 in every role and
Codex CLI 0.163.0 as implementer and reviewer; `bottega pr` is verified with
a fake `gh` only. See [docs/compatibility.md](docs/compatibility.md).

## What you need

- git
- gh, logged in, for `bottega pr`
- python3 3.9 or newer
- at least one of `claude` (Claude Code) and `codex` (Codex CLI), logged in
- node 18 or newer, only for `npx bottega-kit`

## Install

```sh
npx bottega-kit
```

This clones the release that matches the npm package, runs its `./install.sh`,
then `./doctor.sh`, and deletes the clone. `doctor` fails on a new machine
until you run `bottega init`. Or from a clone:

```sh
git clone https://github.com/matteoscurati/bottega-kit
cd bottega-kit
./install.sh
```

Both copy the command to `~/.local/share/bottega-kit` and link
`~/.local/bin/bottega`. `./uninstall.sh`, from a clone, removes them and keeps
your tasks and configuration.

## Example: Fable plans and judges, Opus implements and reviews

`~/.config/bottega-kit/config.json`, which `bottega init` writes when it finds
`claude`:

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

The whole sequence, from a repository with an `origin` on GitHub:

```sh
bottega init
bottega doctor
cd your-repo
bottega new --title "Add a dry-run flag" --request "Add --dry-run to the export command."
bottega plan 20261017-0930-add-a-dry-run-flag     # a unique prefix or suffix is enough
# read task.md; answer any questions in it and run plan again
bottega approve dry-run-flag
bottega run dry-run-flag
bottega pr dry-run-flag
```

`plan` and `run` print one line per dispatch on stdout, and `plan` adds the
planner's questions when it has any; everything else goes to stderr:

```
001 planner fable-judge claude-fable-5-1 → planned (2m41s)
002 implementer opus-builder claude-opus-5 → done (6m02s)
003 reviewer opus-reviewer claude-opus-5 → needs-work (2m14s)
004 implementer opus-builder claude-opus-5 → done (3m40s)
005 reviewer opus-reviewer claude-opus-5 → ready (1m55s)
006 judge fable-judge claude-fable-5-1 → ready (48s)
```

`pr` prints the pull request's URL, or `pr exists: <url>`.

## Example: three vendors, no judge

The planner on Claude Code, the implementer on Codex, the reviewer on Claude
Code pointed at Z.AI's Anthropic-compatible endpoint:

```json
{
  "schema_version": 1,
  "profiles": {
    "fable-judge":  {"harness": "claude", "model": "claude-fable-5-1", "effort": "max"},
    "sol-builder":  {"harness": "codex",  "model": "gpt-5.6-sol",     "effort": "high"},
    "glm-reviewer": {"harness": "claude", "model": "glm-5.3-flash",   "effort": "max",
                     "env": {"ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
                             "ANTHROPIC_AUTH_TOKEN": "${ZAI_API_KEY}",
                             "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3-flash"},
                     "aliases": ["opus"]}
  },
  "roles": {"planner": "fable-judge", "implementer": "sol-builder",
            "reviewer": "glm-reviewer"},
  "rounds": 3
}
```

`${ZAI_API_KEY}` is read from your environment when the reviewer runs;
bottega-kit stores no secret, and `doctor` and `approve` refuse while it is
unset. Because `ANTHROPIC_BASE_URL` is set, the reviewer runs with a fresh
Claude configuration directory and without your Anthropic credentials.
`aliases` lists other names the endpoint may report for the model; any other
name stops the run as `identity-mismatch`. To change one role for one task
only, pass `--role implementer=sol-builder` to `bottega new`.

## The roles

| role | what it does | what it may change | its product |
|---|---|---|---|
| planner | reads the repository and the request, writes the plan or asks questions | nothing | its final message becomes the plan in `task.md` |
| implementer | works through the unchecked to-do items, adds tests, ticks items | the worktree and the boxes in `task.md`; never commits or pushes | a summary, kept in the receipt |
| reviewer | checks every ticked item, runs the tests and the manual QA scenarios | nothing it keeps: a changed tracked file stops the task | `## Review Findings` and a signal: `ready`, `needs-work` or `blocked` |
| judge | optional; reads the plan and the diff, says whether to merge | nothing | `## Verdict` and a signal: `ready` or `needs-work` |

Agents report back by running `bottega signal`. bottega-kit decides what
happens next from that signal and the files on disk, never from the agent's
prose. [docs/process.md](docs/process.md) has the loop step by step.

## Exit codes

| code | meaning |
|---|---|
| 0 | done |
| 2 | refused: wrong phase, plan changed since approval, invalid configuration, a binding that no longer works, task locked |
| 3 | stopped: `blocked`, `cap-reached`, `judge-needs-work`, `dispatch-failed`, `timeout`, `identity-mismatch`, `role-modified-worktree`, `interrupted` |
| 64 | bad invocation |

A stopped task continues with `bottega resume <task> [--rounds N]`.

## Where things live

- Configuration: `~/.config/bottega-kit/config.json`, and prompt overrides in
  `~/.config/bottega-kit/prompts/`.
- Tasks: `~/.local/share/bottega-kit/tasks/<project>/<task-id>/`, holding
  `task.md`, `state.json` and one receipt directory per dispatch under `runs/`.
  They live outside the repository, so they outlive the worktree.
- The worktree: `<repo>-worktrees/<task-id>/`, beside the repository, on the
  branch `bottega/<task-id>`. `bottega rm` removes it and the branch.
- A repository may hold `bottega.json` with `test_cmd` and `base`.

[docs/configuration.md](docs/configuration.md) covers every setting.

## What bottega-kit never does

- Retry a failed dispatch, fall back to another model, or substitute a profile.
- Bring a model of its own. Every dispatch runs a profile you bound, and the
  harness must report the model you asked for.
- Store a secret. Profiles name environment variables; receipts record names,
  never values.
- Merge, or push anywhere but `origin`.
- Let the planner, the reviewer or the judge change your code: their runs are
  checked against the worktree before and after.

## Not vdaubry/bottega

[vdaubry/bottega](https://github.com/vdaubry/bottega) is a web platform with a
server, a database and a UI. bottega-kit took its process: the spec-first task
document, the planner, implementer and reviewer prompts, the plan template,
the "agents signal with a command" rule, the review cap with no unreviewed fix
pass, and one worktree per task. It did not take the platform. The judge
role, the profiles across vendors and the receipts are this project's. See
`NOTICE` for the files adapted.

## Documentation

- [docs/process.md](docs/process.md): the loop, rounds, resume, signals,
  receipts, rails.
- [docs/configuration.md](docs/configuration.md): profiles, roles,
  `bottega.json`, prompt overrides, environment variables.
- [docs/compatibility.md](docs/compatibility.md): what each harness is run
  with, and what has been verified.
- [docs/later.md](docs/later.md): what is not built yet.

## Licence

MIT. The process and parts of the prompts and the template come from
[vdaubry/bottega](https://github.com/vdaubry/bottega), also MIT; see `NOTICE`.
