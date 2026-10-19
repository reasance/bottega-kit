# Changelog

All notable changes to bottega-kit. Dates are when the version was cut.

## [Unreleased]

## [0.1.0] — 2026-10-17

The first release. A planner, an implementer, a reviewer and an optional judge
run on Claude Code and Codex in a git worktree, with a receipt for every
dispatch.

**Tasks and configuration.** `bottega init` writes a starter configuration for
the harnesses it finds on PATH, and `bottega doctor` checks python3, git, gh,
the configuration, each role's harness and the environment variables profiles
reference. `bottega new` creates a task: a directory outside the repository
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

**Verified live.** On 2026-10-17 two tasks ran end to end on a throwaway
repository with Claude Code 2.1.302 and Codex CLI 0.163.0, each harness as
implementer and as reviewer (`docs/compatibility.md`). The run found one bug:
a Codex reviewer could not find the task by id, because Codex does not pass
the orchestrator's environment to the agent's shell. `bottega signal` now also
accepts the absolute task directory, and every prompt names it.

**Pull requests and packaging.** `bottega pr` commits what is left in the
worktree, pushes the branch to `origin` and opens the pull request with `gh`.
It works on a done or a stopped task, and a stopped task's pull request says
why it stopped. An existing pull request is reported, not duplicated.
`npx bottega-kit` installs the release that matches the npm package. The
README and `docs/` describe the process, the configuration and the harness
flags.

### Known limits

- Verified live on one machine, on two days, with Claude Code 2.1.302 and
  2.1.303 and Codex CLI 0.163.0, each in every role, and `bottega pr` on a
  private github.com repository (`docs/compatibility.md`). The Claude `Write`
  tool, the Bash deny rules, a GitHub Enterprise host and a proxied profile
  were not exercised; Codex reports no model, so its identity stays
  `requested-only`.
- Two harnesses: `claude` and `codex`.
- A text-patch harness for chat-completion endpoints, and Kimi, Grok and
  Gemini drivers, are planned for later (`docs/later.md`).

## [0.0.0] — 2026-10-17

- Repository created. Nothing released.
