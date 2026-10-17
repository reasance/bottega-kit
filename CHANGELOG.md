# Changelog

All notable changes to bottega-kit. Dates are when the version was cut.

## [Unreleased]

### Added

- Milestone M1: the harness layer, `plan` and `approve`. Tested against fake
  harnesses only; the live probe on real `claude` and `codex` has not run.
- `bottega plan` runs the planner once. Its final message becomes the plan in
  `task.md`, or a `## Questions for you` section you answer inline before the
  next `bottega plan`. One line per dispatch; exit 3 with a receipt when the
  dispatch fails, the model is not the one requested, the output is not a
  plan, or the planner changed the worktree.
- `bottega approve [--rounds N]` checks the plan, gives each to-do item a
  stable `[T<n>]` id, validates every role binding (profile, effort, harness
  on PATH, environment variables) and records the plan hash, the roles and the
  round cap. Approving again after an edit keeps the existing ids.
- The `claude` and `codex` drivers, with every flag in one table; proxied
  Claude profiles run with a fresh `CLAUDE_CONFIG_DIR` and without Anthropic
  credentials; profile timeouts kill the harness's process group.
- Receipts per run: `runs/NNN-<role>/` with the prompt, the final message,
  raw events, `run.json` (environment variable names only, never values) and
  `error.json` on failure.
- A strict `{{var}}` prompt engine with overrides in
  `~/.config/bottega-kit/prompts/`, and the planner prompt adapted from
  vdaubry/bottega.
- Milestone M0, the skeleton. No model is dispatched yet.
- `bottega init` writes a starter configuration for the harnesses it finds on
  PATH (`claude`, `codex`). `bottega doctor [--json]` checks python3, git, gh,
  the configuration, each role's harness and the `${NAME}` variables profiles
  reference.
- `bottega new` creates a task: its directory, `task.md` seeded with the title
  and the verbatim request, a worktree beside the repository and a
  `bottega/<task-id>` branch. `show`, `list` and `rm` manage tasks.
- `bottega signal`, the command agents run to report `ready`, `needs-work` or
  `blocked`, with every validation it will need in the loop.
- `run`, `resume` and `pr` are registered and exit 64 until their milestones
  land.
- `install.sh`, `uninstall.sh`, `doctor.sh`, the parallel test runner, the
  version-surface check, CI, and fake `claude`/`codex` executables for the
  suites.

## [0.0.0] — 2026-10-17

- Repository created. Nothing released.
