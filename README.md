# bottega-kit

bottega-kit runs a planner, an implementer, a reviewer and an optional judge on the
coding agents you already have — Claude Code and Codex today — one role each, in a
git worktree, with a receipt for every step. You need git, gh, python3 and at least
one of those CLIs.

Why roles: the agent that reviews the code is not the one that wrote it, and
it can run on another model or another vendor. You read and approve the plan
once; after that nothing asks you anything until the task is done or stops,
and every step is on disk for you to read.

This is not vdaubry/bottega: the process is
[theirs](https://github.com/vdaubry/bottega); the local, file-based, multi-vendor
loop is this project.

A task is one plan, which you approve, and then rounds of implementer and
reviewer until the reviewer is satisfied or the round cap is reached:

```
bottega new      task directory, worktree and branch; task.md holds your request
bottega plan     one planner dispatch; may end with questions; repeat until there is a plan
bottega approve  ids for the to-do items; plan hash, roles and cap recorded
bottega run      implementer and reviewer, round after round, up to the cap; then the judge
bottega pr       commit if needed, push to origin, open the pull request
bottega resume   after a stop, with a fresh cap
```

A round is one implementer pass and one reviewer pass; the cap is 3 unless
you change it. Each role runs under a profile from your configuration: a
harness, which is the CLI that runs the role (`claude` or `codex`), a model
and an effort. One profile may serve several roles.

## Current release: 0.1.1

Documentation: what to do after `run`, a task followed end to end, what a
task costs. The commands are those of 0.1.0: `init`, `doctor`, `new`,
`plan`, `approve`, `run`, `resume`, `pr` and the task commands, on the
`claude` and `codex` harnesses. 0.1.1 was verified live on 2026-10-23 with
Claude Code 2.1.309 and the starter configuration, through `bottega pr` on
GitHub; 0.1.0 was verified with Claude Code 2.1.302 to 2.1.304 and Codex CLI
0.163.0, each in every role, and a reviewer on Z.AI's endpoint. See
[docs/compatibility.md](docs/compatibility.md).

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
git clone https://github.com/reasance/bottega-kit
cd bottega-kit
./install.sh
```

Both copy the command to `~/.local/share/bottega-kit` and link
`~/.local/bin/bottega`. `./uninstall.sh`, from a clone, removes them and keeps
your tasks and configuration.

## Example: Fable plans and judges, Opus implements and reviews

`~/.config/bottega-kit/config.json`, which `bottega init` writes when `claude`
is on PATH:

```json
{
  "schema_version": 1,
  "profiles": {
    "fable":         {"harness": "claude", "model": "claude-fable-5-1", "effort": "max"},
    "opus-builder":  {"harness": "claude", "model": "claude-opus-5-5",  "effort": "high"},
    "opus-reviewer": {"harness": "claude", "model": "claude-opus-5-5",  "effort": "high"}
  },
  "roles": {"planner": "fable", "implementer": "opus-builder",
            "reviewer": "opus-reviewer", "judge": "fable"},
  "rounds": 3
}
```

With `codex` on PATH as well, `init` also writes a `sol-builder` profile
(`codex`, `gpt-5.6-sol`, effort `high`) and binds it to no role. With `codex`
alone, `sol-builder` is the planner, the implementer and the reviewer, and
there is no judge. Edit the file to bind the roles as you like; `bottega
doctor` checks it.

The whole sequence, from a repository with an `origin` on GitHub:

```sh
bottega init
bottega doctor
cd your-repo
echo '{"test_cmd": "make test"}' > bottega.json   # optional: the test command the agents run
bottega new --title "Add a dry-run flag" --request "Add --dry-run to the export command."
bottega plan 20261017-0930-add-a-dry-run-flag     # a unique prefix or suffix is enough
# read task.md; answer any questions in it and run plan again
bottega approve dry-run-flag
bottega run dry-run-flag
# read the changes in the worktree; bottega show dry-run-flag prints where it is
bottega pr dry-run-flag
```

`plan` and `run` print one line per dispatch on stdout, and `plan` adds the
planner's questions when it has any; everything else goes to stderr:

```
001 planner fable claude-fable-5-1 → planned (2m41s)
002 implementer opus-builder claude-opus-5-5 → done (6m02s)
003 reviewer opus-reviewer claude-opus-5-5 → needs-work (2m14s)
004 implementer opus-builder claude-opus-5-5 → done (3m40s)
005 reviewer opus-reviewer claude-opus-5-5 → ready (1m55s)
006 judge fable claude-fable-5-1 → ready (48s)
```

`pr` prints the pull request's URL, or `pr exists: <url>`.
[docs/process.md](docs/process.md#a-task-end-to-end) follows one task
through every command, with the `task.md` it ends with.

## After `run`

`bottega show <task>` prints the worktree, the branch and the path of
`task.md`, then the phase, the round, the last signal, why the task stopped,
and one line per dispatch. `bottega list` prints every task and its phase.

**Done** (exit 0). Read the work before you open the pull request. The
changes are in the worktree, uncommitted: `git status` and `git diff` there,
and new files are untracked until `pr` commits them. `task.md` holds the
reviewer's `## Review Findings` and the judge's `## Verdict`. Then
`bottega pr`.

**Stopped** (exit 3). `run` prints the reason, the receipt of the dispatch
that stopped it and the resume command; `show` prints them again. Then one
of:

- `bottega resume <task>`: the same plan, a fresh cap. After `cap-reached` or
  `judge-needs-work` a new round starts with the implementer; after any other
  stop the role that stopped runs again.
- Edit the plan in `task.md`, `bottega approve` it again and `bottega run`:
  the ids are kept and the loop starts over at round 1. After `blocked`, the
  reviewer's findings say what is missing.
- `bottega pr` anyway: the pull request's body starts with the stop reason.
- `bottega rm <task>`: removes the worktree and the branch. The task
  directory and its receipts stay.

## What a task costs

You pay your providers; bottega-kit adds nothing. Each Claude Code dispatch's
cost, as Claude Code reports it, is `cost_usd` in its `run.json`. Codex
reports none: its usage goes to your ChatGPT plan. For scale, on 2026-10-23
the starter configuration above added an option to a 21-line Python CLI in
one round: four dispatches, 2.07 USD and under five minutes, three quarters
of it the Fable planner and judge. In the 0.1.0 runs, Sonnet at effort
`medium` cost 0.03 to 0.08 USD a dispatch on the same kind of task. A larger
task costs more: more files to read, more rounds.
[docs/compatibility.md](docs/compatibility.md) lists every dispatch of the
live runs.

## Example: three vendors, no judge

The planner on Claude Code, the implementer on Codex, the reviewer on Claude
Code pointed at Z.AI's Anthropic-compatible endpoint:

```json
{
  "schema_version": 1,
  "profiles": {
    "fable":        {"harness": "claude", "model": "claude-fable-5-1", "effort": "max"},
    "sol-builder":  {"harness": "codex",  "model": "gpt-5.6-sol",     "effort": "high"},
    "glm-reviewer": {"harness": "claude", "model": "glm-5.3-flash",   "effort": "max",
                     "env": {"ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
                             "ANTHROPIC_AUTH_TOKEN": "${ZAI_API_KEY}",
                             "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3-flash"},
                     "aliases": ["opus"]}
  },
  "roles": {"planner": "fable", "implementer": "sol-builder",
            "reviewer": "glm-reviewer"},
  "rounds": 3
}
```

`${ZAI_API_KEY}` is read when the reviewer runs, from your environment or
from `~/.config/bottega-kit/secrets.env` (one `NAME=value` line each, mode
600, parsed and never executed); `doctor` and `approve` refuse while it is set
in neither. Because `ANTHROPIC_BASE_URL` is set, the reviewer runs with a fresh
Claude configuration directory and without your Anthropic credentials.
`aliases` lists other names the endpoint may report for the model; any other
name stops the run as `identity-mismatch` (on 2026-10-20 Z.AI reported
`glm-5.3-flash`, the requested name, so the alias went unused). To change one
role for one task only, pass `--role implementer=sol-builder` to `bottega new`.

MiniMax and Kimi run the same way, each through its own Anthropic-compatible
endpoint. Both ran planner, implementer and reviewer live on 2026-10-23:

```json
"minimax": {"harness": "claude", "model": "MiniMax-M3.1-Flash", "effort": "high",
            "env": {"ANTHROPIC_BASE_URL": "https://api.minimax.io/anthropic",
                    "ANTHROPIC_AUTH_TOKEN": "${MINIMAX_API_KEY}",
                    "ANTHROPIC_DEFAULT_OPUS_MODEL": "MiniMax-M3.1-Flash",
                    "ANTHROPIC_DEFAULT_SONNET_MODEL": "MiniMax-M3.1-Flash",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "MiniMax-M3.1-Flash"}},
"kimi":    {"harness": "claude", "model": "kimi-k3", "effort": "high",
            "env": {"ANTHROPIC_BASE_URL": "https://api.moonshot.ai/anthropic",
                    "ANTHROPIC_AUTH_TOKEN": "${KIMI_API_KEY}",
                    "ANTHROPIC_DEFAULT_OPUS_MODEL": "kimi-k3",
                    "ANTHROPIC_DEFAULT_SONNET_MODEL": "kimi-k3",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "kimi-k3"}}
```

The Kimi key is a Kimi Platform API key, not the login of the `kimi` CLI.
Kimi K3.1 Pro is not on that API yet; when `GET /v1/models` lists it, change
`model` and the three `ANTHROPIC_DEFAULT_*` values. See
[docs/configuration.md](docs/configuration.md).

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
- Bring a model of its own. Every dispatch runs a profile you bound. Claude
  Code reports the model it ran, and it must be the one you asked for; Codex
  reports none, so its receipts say `requested-only` and rest on the request.
- Put a secret in its configuration, its prompts, a task or a receipt.
  Profiles name environment variables; the key file you keep at mode 600 may
  hold their values; receipts record names, never values.
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
