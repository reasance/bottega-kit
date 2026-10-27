# Changelog

All notable changes to bottega-kit. Dates are when the version was cut.

## [Unreleased]

- Document an optional GPT-6.1 Terra Codex profile and verify model/effort forwarding for every role with fake harness runs. Starter profiles and runtime behavior stay unchanged.

## [0.3.0] — 2026-10-25

Models only: no command, harness or role changes. Removing two `codex`
efforts and one `muse` effort would break a configuration that names them,
so the release is a minor one.

**Models.** Kept in line with controller-models' registry, which now
generates the effort table and the starter profiles in `config.py` between
`controller-models` markers.

- `codex` efforts are `low` to `max` plus `ultra`, the levels Codex lists
  for the models it serves. `none` and `minimal` are no longer accepted.
- `muse` no longer accepts `none`: Muse models reject it.
- The `sol-builder` starter profile runs `gpt-6.1-sol`, because GPT-5.6 Sol
  is retired.
- The Kimi example on Moonshot's Anthropic-compatible endpoint uses
  `kimi-k3.1-pro`, which ran a planner dispatch there on 2026-10-25. K3 is
  retired.

## [0.2.0] — 2026-10-25

Four new harnesses: Kimi Code, Grok Build, Muse Code and the Antigravity
CLI, next to Claude Code and Codex.

**Documentation.** MiniMax M3.1 Flash and Kimi K3 as proxied `claude`
profiles: README examples, a table of the Anthropic-compatible endpoints
that have run live in `docs/configuration.md`, and the two live runs of
2026-10-23 in `docs/compatibility.md`.

**A third harness: Kimi Code.** `"harness": "kimi"` runs a role with
`kimi -p` on your own Kimi Code login, for instance
`kimi-code/k3.1-pro`; effort `low`, `high` or `max`. Each dispatch writes an
agent file whose `tools:` list is the role's tool set, replaces your skills
with an empty directory, sets the effort through
`KIMI_MODEL_THINKING_EFFORT`, and makes `git push` to origin and `gh` fail
through the environment, since Kimi Code has no deny rule for a shell
command. Kimi Code reports no model, so its receipts say `requested-only`;
they record the requested model, the effort and the tokens from Kimi Code's
session log. `bottega init` adds a `kimi` profile when it finds `kimi`.
Verified live on 2026-10-23 with Kimi Code 2.3.1 and K3.1 Pro in every role.

**Three more harnesses: Grok Build, Muse Code and the Antigravity CLI.**

- `"harness": "grok"` runs a role with `grok` on your Grok login, for
  instance `grok-4.7`; effort `low` to `xhigh`. Each role gets its tool set
  and Claude Code-style allow and deny rules; Claude Code's and Cursor's
  configuration, which Grok Build otherwise loads, is switched off. The
  model is reported and checked, and the cost recorded.
- `"harness": "muse"` runs a role with `muse exec`, for instance
  `muse-wonder-1.0`; effort `none` to `ultra`. The planner runs without
  writes or shell, the reviewer and judge without writes; contributor mode
  is off for every dispatch, whatever your setting. The models Muse Code
  names are checked.
- `"harness": "agy"` runs a role with the Antigravity CLI, for instance
  `gemini-3.8-flash-high`; effort `low` to `max`. Each dispatch runs with a
  temporary HOME whose settings hold the role's permission rules, and a
  link to your `agy` sign-in; your own settings, hooks, plugins and MCP
  servers stay out. Receipts say `requested-only`.
- For all three, `git push` to origin and `gh` fail through the
  environment, as for `kimi`. `bottega init` adds a `grok`, `muse` or
  `gemini` profile for each CLI it finds.

**Verification.** `docs/compatibility.md` has a new verified snapshot: one
live task on 2026-10-25 with Grok Build as planner and judge, Muse Code as
implementer and the Antigravity CLI as reviewer, done in round 1, then
`bottega pr` on GitHub. The 0.1.1 snapshot is kept below it, marked as not
re-run. Kimi Code's run of 2026-10-23 and the Grok, Muse and Antigravity
runs of 2026-10-24 are kept beside it, dated.

## [0.1.1] — 2026-10-23

Documentation only; the commands behave as in 0.1.0.

**Documentation.** The README says why the roles are separate, what to do
after `run` (read the worktree, `show`, `list`, the four ways on from a stop,
`pr` on a stopped task, `rm`), what a task costs, and which starter `init`
writes for each set of CLIs. `docs/process.md` opens with one task followed
through every command, including the `task.md` it ends with and a task that
stops. The README and `docs/configuration.md` no longer say every harness
must report its model: Codex reports none, and its receipts say
`requested-only`.

**Verification.** `docs/compatibility.md` has a new verified snapshot: one
live task on 2026-10-23 with Claude Code 2.1.309 and the starter
configuration, done in round 1, 2.07 USD, then `bottega pr` on GitHub. The
0.1.0 snapshot is kept below it, marked as not re-run.

## [0.1.0] — 2026-10-23

The first release. A planner, an implementer, a reviewer and an optional judge
run on Claude Code and Codex in a git worktree, with a receipt for every
dispatch.

**Tasks and configuration.** `bottega init` writes a starter configuration for
the harnesses it finds on PATH, and `bottega doctor` checks python3, git, gh,
the configuration, each role's harness and the environment variables profiles
reference. A `${NAME}` a profile references is read from your environment or
from `~/.config/bottega-kit/secrets.env`, one `NAME=value` line each, parsed
and never executed, refused while anyone but you can read it. `bottega new`
creates a task: a directory outside the repository
with `task.md` holding your request verbatim, a worktree beside the repository
and a `bottega/<task-id>` branch. `show`, `list` and `rm` manage tasks.
`bottega signal` is the command agents run to report `ready`, `needs-work` or
`blocked`.

**Planning and approval.** `bottega plan` runs the planner once; its final
message becomes the plan, or questions you answer inside `task.md` before the
next `plan`. `bottega approve` checks the plan, gives each to-do item a stable
`[T<n>]` id, and freezes the plan's hash, the roles and the round cap. The
`claude` and `codex` drivers keep every flag in one table. A proxied Claude
profile runs without your Anthropic credentials. Prompts can be overridden
per user.

**The loop.** `bottega run` alternates the implementer and the reviewer up to
the cap, then asks the judge if one is bound. It ends done (exit 0) or stopped
(exit 3) with a reason, and never retries. The reviewer's findings and the
judge's verdict replace their sections of `task.md`. A planner, reviewer or
judge that changes tracked code stops the task, and so does a harness that
reports another model. `bottega resume` continues a stopped task with a fresh
cap.

**Verified live.** On 2026-10-17 and 2026-10-19 seven tasks ran on two
throwaway repositories with Claude Code 2.1.302 and 2.1.303 and Codex CLI
0.163.0, each harness in every role, and `bottega pr` opened a pull request
on GitHub (`docs/compatibility.md`). The runs found two bugs. A Codex reviewer
could not find the task by id, because Codex does not pass the orchestrator's
environment to the agent's shell: `bottega signal` now also accepts the
absolute task directory, and every prompt names it. A plan with a fenced
block inside a longer fence lost five lines in the merge: a fence now closes
only with the same character and at least the same length, as in CommonMark.
The runs also changed the prompts: the implementer and the reviewer are told
to give a test suite a long timeout, and that a shell tool handing control
back while the command runs means wait, not failed. On 2026-10-20 the
README's proxied profile ran as reviewer: Claude Code 2.1.304 on Z.AI's
endpoint reported the requested `glm-5.3-flash`, with the key read from
`secrets.env`.

**Pull requests and packaging.** `bottega pr` commits what is left in the
worktree, pushes the branch to `origin` and opens the pull request with `gh`.
It works on a done or a stopped task, and a stopped task's pull request says
why it stopped. An existing pull request is reported, not duplicated.
`npx bottega-kit` installs the release that matches the npm package. The
README and `docs/` describe the process, the configuration and the harness
flags.

### Known limits

- Verified live on one machine, on three days, with Claude Code 2.1.302 to
  2.1.304 and Codex CLI 0.163.0, each in every role, and `bottega pr` on a
  private github.com repository (`docs/compatibility.md`). The Claude Bash
  deny rules were seen to deny every forbidden command; a 150 s test suite
  passed under a Claude reviewer and, after a prompt change, under a Codex
  reviewer that had first given up on it; the Claude `Write` tool created
  files under `acceptEdits`; a proxied profile on Z.AI ran once, as
  reviewer, and Claude Code priced it at its own default rate. A GitHub
  Enterprise host was not exercised; Codex reports no model, so its identity
  stays `requested-only`.
- Two harnesses: `claude` and `codex`.
- A text-patch harness for chat-completion endpoints, and Kimi, Grok and
  Gemini drivers, are planned for later (`docs/later.md`).

## [0.0.0] — 2026-10-17

- Repository created. Nothing released.
