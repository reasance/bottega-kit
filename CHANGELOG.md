# Changelog

All notable changes to bottega-kit. Dates are when the version was cut.

## [Unreleased]

### Added

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
- `plan`, `approve`, `run`, `resume` and `pr` are registered and exit 64 until
  their milestones land.
- `install.sh`, `uninstall.sh`, `doctor.sh`, the parallel test runner, the
  version-surface check, CI, and fake `claude`/`codex` executables for the
  suites.

## [0.0.0] — 2026-10-17

- Repository created. Nothing released.
