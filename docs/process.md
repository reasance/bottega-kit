# The process

A task goes through one plan, one approval, a loop of implementer and
reviewer rounds, an optional judge, and a pull request. Each step is a
command you run; nothing runs in the background.

```
bottega new      task directory, worktree and branch; task.md holds your request
bottega plan     one planner dispatch; may end with questions; repeat until there is a plan
bottega approve  ids for the to-do items; plan hash, roles and cap recorded
bottega run      implementer and reviewer up to the cap, then the judge, then stop
bottega pr       commit if needed, push to origin, open the pull request
bottega resume   after a stop, with a fresh cap
```

## Phases

`state.json` holds the task's phase:

```
new → planning → questions | planned → approved → running → done | stopped
```

`removed` follows `bottega rm`. `bottega show <task>` prints the phase, the
round and the cap, the next role, the last signal, the stop reason and one
line per dispatch.

## The task document

`task.md` is the only thing the agents share. Its sections, in order:
`# Task <title>`, `## Original Request` (your words, verbatim, never
changed), `## Overview`, `## Implementation Plan`, `## Testing Strategy`,
`## To-Do List`, `## Project Docs Update`, then `## Review Findings` and
`## Verdict`, which bottega-kit writes from the reviewer's and the judge's
final messages.

## Planning

`bottega plan` sends the whole document to the planner. The planner reads the
repository without changing it and ends with one of two things:

- **A plan.** Its sections replace the plan sections of `task.md`.
- **A `## Questions for you` section.** It is written into `task.md` and
  printed. Answer under each question, in the file, and run `bottega plan`
  again. The planner asks only where a choice has real trade-offs and assumes
  the rest.

A planner output without the required sections stops `plan` (exit 3) with
its receipt kept, and `task.md` unchanged. You may edit the plan by hand before approving it.

## Approval

`bottega approve <task> [--rounds N]` checks that the plan has an Overview, a
Testing Strategy with at least one `### Manual QA` scenario (or an explicit
"Not needed" and why), and at least one unchecked to-do item. It then:

- gives each to-do item a stable id such as `[T3]`; ids are never renumbered;
- checks every role binding: the profile exists, its effort is valid, its
  harness answers `--version`, and every `${NAME}` it references is set;
- records the plan hash, the role bindings and the round cap.

The plan hash covers everything above `## Review Findings`, with ticked boxes
counted as unticked. Ticking items and rewriting the findings do not change
it; editing the plan does. `run` and `resume` refuse (exit 2) a plan that no
longer matches: approve it again.

A stopped task can be approved again after you edit the plan. The ids
already given are kept, the rule about an unchecked item is waived (the loop
may have ticked them all), and the next `run` starts over at round 1.

## The loop

`bottega run` starts round 1 with the implementer. After every dispatch,
bottega-kit applies the first rule that matches:

1. The harness could not start, exited non-zero, reported an error, or
   produced no final message: stop, `dispatch-failed`. A profile `timeout`
   stops with `timeout`.
2. The harness reported a model other than the one requested, and not one of
   the profile's `aliases`: stop, `identity-mismatch`.
3. A planner, reviewer or judge changed a tracked file or HEAD: stop,
   `role-modified-worktree`.
4. The implementer finished: the reviewer is next. If it committed, that is a
   warning, not a stop.
5. The reviewer finished: its final message replaces `## Review Findings`,
   and the items it named with `--uncheck` are unticked.
   - `ready`: the judge is next, or the task is done if there is no judge.
   - `blocked`: stop, `blocked`, with the reviewer's reason.
   - `needs-work`, or no signal at all: if this was the last round, stop,
     `cap-reached`; otherwise the implementer opens the next round.
6. The judge finished: its final message replaces `## Verdict`. `ready`: done.
   Anything else: stop, `judge-needs-work`.

Ctrl-C, or the process dying mid-dispatch, stops the task as `interrupted`.

`run` prints one line per dispatch:

```
003 reviewer opus-reviewer claude-opus-5 → needs-work (2m14s)
```

and exits 0 when the task is done, 3 when it stopped. The reason, the receipt
path and the resume command go to stderr.

## Rounds

A round is one implementer dispatch followed by one reviewer dispatch. With a
cap of 3, the third `needs-work` stops the task: there is never a fourth
implementer pass that no reviewer would check. The default cap is the
configuration's `rounds` (3 unless you set it); `approve --rounds N` sets it
for one task.

## Resume

`bottega resume <task> [--rounds N]` continues a stopped task. N defaults to
the configuration's `rounds`.

- After `cap-reached` or `judge-needs-work`, a new round starts with the
  implementer, and the cap becomes the last round plus N. `--rounds 1` runs
  exactly one more pair.
- After any other stop, the role that stopped runs again in the same round,
  and the cap becomes the current round plus N.

Nothing is retried for you; `resume` is how you retry. It checks the plan
hash and the bindings again, like `run`. `resume` on an approved task that has
never run is `run`. A task left `running` by a bottega that died is treated
as interrupted and resumed from the role that was running.

## Signals

The reviewer and the judge end their turn by running one command, which their
prompt gives with absolute paths:

```sh
bottega signal <task directory or id> ready|needs-work|blocked "<reason>" [--uncheck T3 T7]
```

- The reviewer may signal all three; the judge `ready` or `needs-work`. The
  implementer and the planner do not signal.
- It works only while the task is running, and writes `signal.json` in the
  current run's directory. The last call wins; every call is logged in
  `signal.log` beside it.
- `--uncheck` ids must exist in `task.md`. bottega-kit unticks them after the
  reviewer exits.
- A reviewer or judge that does not signal counts as `needs-work`, shown as
  `no-signal`.

bottega-kit reads the signal after the harness exits. It never interprets an
agent's prose.

## Rails

Before and after each planner, reviewer and judge dispatch, bottega-kit
records HEAD and a hash of the worktree's tracked changes. If either moved,
the task stops with `role-modified-worktree`. New untracked files, such as
test caches, are recorded and reported as a warning. The implementer is the
only role that edits the worktree; it should not commit, and a commit is a
warning in its receipt.

Each harness is also started with the narrowest permissions it offers for the
role: see [compatibility.md](compatibility.md).

## Receipts

Every dispatch leaves a directory `runs/NNN-<role>/` in the task directory:

| file | what it holds |
|---|---|
| `prompt.md` | the prompt, exactly as sent |
| `output.md` | the final message |
| `events.jsonl` | the harness's raw output |
| `stderr.log` | the harness's raw stderr |
| `run.json` | profile, harness, requested and reported model, effort, argv, timings, exit code, usage, cost, rails, signal, warnings, status |
| `error.json` | only on failure: the phase, the reason, the exit code, the last stderr lines |
| `signal.json`, `signal.log` | when the agent signalled |
| `scratch/` | a directory the agent may write in |

Receipts hold environment variable names, never their values. A failed
dispatch changes nothing in `task.md`.

## Locks

One bottega works on a task at a time: `plan`, `approve`, `run`, `resume`,
`pr` and `rm` take the task's lock, and a second one refuses (exit 2). A lock
left by a process that is gone is reclaimed with a message. Running several
tasks at once is up to you.

## The pull request

`bottega pr <task>` works on a task that is done or stopped. In the worktree
it:

1. commits any change with the message `<title>`, a blank line, and
   `bottega task <task-id>`, using your git identity;
2. refuses if the branch has no commit ahead of the base;
3. pushes the branch with `git push -u origin <branch>`;
4. prints `pr exists: <url>` if `gh` finds an open or merged pull request
   for the branch, or opens one with `gh pr create` and prints its URL.

The body has the plan's Overview, the last review's findings as "What was
verified", the rounds used out of the cap, the judge's verdict when there is
one, and a footer naming bottega-kit and the task id. A stopped task's body
starts with the stop reason and its detail. The body is kept as `pr-body.md`
in the task directory, and `state.json` records the URL, the time and the
commit.

`pr` only ever pushes to `origin`, and gives `gh` origin's repository
explicitly, so a remote called `upstream` is never used. It never merges.
