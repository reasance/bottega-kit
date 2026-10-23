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

## A task, end to end

One task on a small repository at `~/code/export-tool`. The commands and
what they print are the kit's own, run against its test fakes; the words of
the plan, the findings and the verdict show the shape a model writes, not a
recorded model. Durations are left out, and paths shortened.

```
$ bottega new --title "Add a dry-run flag" --request "Add --dry-run to the export command."
task      20261023-1634-add-a-dry-run-flag
task.md   ~/.local/share/bottega-kit/tasks/export-tool/20261023-1634-add-a-dry-run-flag/task.md
worktree  ~/code/export-tool-worktrees/20261023-1634-add-a-dry-run-flag
branch    bottega/20261023-1634-add-a-dry-run-flag (from main)
next: edit task.md if you like, then: bottega plan 20261023-1634-add-a-dry-run-flag

$ bottega plan dry-run-flag
001 planner fable claude-fable-5-1 → questions

1. Should `--dry-run` print the rows it would export, or only their count? Rows make the output as long as a real export; a count is one line but shows less.

answer in ~/.local/share/bottega-kit/tasks/export-tool/20261023-1634-add-a-dry-run-flag/task.md, then run: bottega plan 20261023-1634-add-a-dry-run-flag
```

The question is now a `## Questions for you` section in `task.md`. Write the
answer under it, in the file, and plan again:

```markdown
## Questions for you

1. Should `--dry-run` print the rows it would export, or only their count? ...

   A count. One line is enough.
```

```
$ bottega plan dry-run-flag
002 planner fable claude-fable-5-1 → planned

$ bottega approve dry-run-flag
approved 20261023-1634-add-a-dry-run-flag
  planner     fable (claude, claude-fable-5-1, effort max)
  implementer opus-builder (claude, claude-opus-5-5, effort high)
  reviewer    opus-reviewer (claude, claude-opus-5-5, effort high)
  judge       fable (claude, claude-fable-5-1, effort max)
rounds    3
plan      sha256 0c979d92811c
to-do     3 item(s), T1..T3; 3 new id(s)
next: bottega run 20261023-1634-add-a-dry-run-flag

$ bottega run dry-run-flag
003 implementer opus-builder claude-opus-5-5 → done
004 reviewer opus-reviewer claude-opus-5-5 → needs-work
005 implementer opus-builder claude-opus-5-5 → done
006 reviewer opus-reviewer claude-opus-5-5 → ready
007 judge fable claude-fable-5-1 → ready
bottega run: done: the reviewer and the judge found it ready in round 2 of 3
next: read the branch bottega/20261023-1634-add-a-dry-run-flag, then: bottega pr 20261023-1634-add-a-dry-run-flag
```

In round 1 the reviewer found the test incomplete, signalled `needs-work`
and unticked `[T2]`; in round 2 the implementer finished it and the reviewer
found it ready. `task.md` at the end, below `## Original Request`:

```markdown
## Overview

Add `--dry-run` to `export`: it reads and validates the rows as usual, prints how
many it would write and to which file, and writes nothing. Decided from your
answer: a count, not the rows. Assumed: the exit code is the same as a real
export's, so scripts can use `--dry-run` as a check.

## Implementation Plan

### Phase 1: the flag

**Files to modify / create:**
- `export.py` — parse `--dry-run`; skip the write when it is set and print
  `would export N rows to PATH`.

## Testing Strategy

### Unit tests
- `test_export.py` — `--dry-run` writes no file and prints the count.

### Manual QA
- **Tool:** the CLI, `python3 export.py`.
- **Setup and safety:** a temporary directory as the output target; deleted afterwards.
- **Scenario:** run `python3 export.py --dry-run --out $TMP/out.csv`.
- **Expected evidence:** `would export 3 rows to $TMP/out.csv` on stdout, and no `out.csv`.

## To-Do List

### Implementation
- [x] [T1] Parse `--dry-run` in `export.py` and skip the write

### Testing
- [x] [T2] Add `test_export.py` covering `--dry-run`
- [x] [T3] Run the manual QA scenario

## Project Docs Update

Add `--dry-run` to the usage line in `README.md`.

## Review Findings

- [T1] Verified in `export.py`.
- [T2] Verified: the test now asserts the file does not exist; `python3 -m unittest` passes, 4 tests.
- [T3] Ran the scenario again: `would export 3 rows to /tmp/qa/out.csv`, no file.

## Verdict

Merge. The change is small, matches the plan, and the test covers the one
behaviour that matters: nothing is written.
```

The answered question is gone: the planner records what it settled in the
Overview. Read the changes in the worktree, then `bottega pr dry-run-flag`.

A task that stops looks like this, with the reasons and the receipt on
stderr:

```
$ bottega run failed-uploads
002 implementer opus-builder claude-opus-5-5 → done
003 reviewer opus-reviewer claude-opus-5-5 → blocked
bottega run: stopped: blocked: no way to test retries without a fake upload server
receipt: ~/.local/share/bottega-kit/tasks/export-tool/20261023-1635-retry-failed-uploads/runs/003-reviewer
findings: ~/.local/share/bottega-kit/tasks/export-tool/20261023-1635-retry-failed-uploads/task.md
resume with: bottega resume 20261023-1635-retry-failed-uploads [--rounds N] (restarts at the reviewer)

$ bottega show failed-uploads
...
phase     stopped
round     1 of 3
next      reviewer
signal    blocked by reviewer (run 003-reviewer): no way to test retries without a fake upload server
stopped   blocked: no way to test retries without a fake upload server

seq role        profile          status  reason                 signal     duration
001 planner     fable            ok      -                      -          ...
002 implementer opus-builder     ok      -                      -          ...
003 reviewer    opus-reviewer    ok      -                      blocked    ...
```

From here: `resume`, or edit the plan, approve it again and `run`, or `pr`
anyway, or `rm`. [Resume](#resume) and the README's "After `run`" say what
each does.

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

[`templates/task.md`](../templates/task.md) is the template `bottega new`
fills in: your title and request, then guidance under each heading for the
planner. After `approve`, every to-do item carries its id:
`- [ ] [T3] Add the flag`.

## Planning

`bottega plan` sends the whole document to the planner. The planner reads the
repository without changing it and ends with one of two things:

- **A plan.** Its sections replace the plan sections of `task.md`.
- **A `## Questions for you` section.** It is written into `task.md` and
  printed. Answer under each question, in the file, and run `bottega plan`
  again. The planner asks only where a choice has real trade-offs and assumes
  the rest.

A planner output without the required sections stops `plan` (exit 3) with
its receipt kept, and `task.md` unchanged. You may edit the plan by hand
before approving it.

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
003 reviewer opus-reviewer claude-opus-5-5 → needs-work (2m14s)
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
warning in its receipt. On Claude Code, `git push` and `gh` are denied to
the implementer and the reviewer, and `git commit` to the reviewer; on Codex
the sandbox makes a commit in the worktree fail and blocks the network; on
Kimi Code each role's agent file lists its tools, and the environment makes
a push to origin and `gh` fail. See
[compatibility.md](compatibility.md) for what each of those was seen to do.

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
