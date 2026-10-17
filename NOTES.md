# Notes — decisions and deviations

Every deviation from the pasted brief, from the work plan, or from
vdaubry/bottega, with the reason. Newest milestone last. Dates are when the
decision was made.

## 2026-10-17 — from the work plan (§0, §2)

These were decided before any code; they are recorded here so the log is
complete.

- **Independent product, not a delegation-kit front end.** The brief had
  bottega-kit dispatch through delegation-kit. delegation-kit 0.27.0 dispatches
  `claude` and `codex` read-only and outside any worktree
  (`bin/delegation-run` 152–199), so no role could edit the worktree, run tests
  or run `bottega signal`. bottega-kit drives the CLIs itself and has no runtime
  dependency on delegation-kit; `bottega doctor` never mentions it.
  delegation-kit stays a reference for conventions (same author, MIT).
- **Owner's answers:** task id `YYYYMMDD-HHMM-<slug>`; `bottega pr` pushes to
  `origin` only; default `rounds` is 3.
- **Profiles are bottega-kit's own:** harness + model + effort, with optional
  `env`, `aliases`, `timeout`, `max_budget_usd`. No secrets stored; `${NAME}`
  references are expanded at dispatch and a missing one fails `doctor` and
  `approve` (exit 2).
- **0.1.0 ships two harnesses, `claude` and `codex`.** Kimi, Grok, Gemini and an
  `openai-compatible` text-patch harness are M4 (0.2.0), in `docs/later.md`.
- **Agents signal with a command** (`bottega signal`), writing `signal.json` in
  the current run directory; the orchestrator folds it in after the harness
  exits. No reviewer signal means `needs-work`.
- **Role products are final messages merged by the orchestrator** (plan,
  findings, verdict), replacing their `task.md` section. Reason: Codex cannot
  scope writes to one file, so a reviewer allowed to edit `task.md` could edit
  code too.
- **To-do items carry stable ids `[T<n>]`**, assigned at `approve`.
- **"The reviewer never fixes code" is enforced** by hashing HEAD and the
  tracked diff around every planner, reviewer and judge run.
- **Model identity mismatch is fatal** unless the reported name is an alias.
- **Nothing retries, falls back, widens a role or substitutes a profile.**
- **The plan is the only human gate;** `approve` records the plan-region hash.
- **`test_cmd` comes from `<repo>/bottega.json` only.** The brief also said "or
  CLAUDE.md"; parsing CLAUDE.md is a heuristic and is not built (later.md).
- **`bottega init` is non-interactive.** The brief's interactive picker chose
  among delegation-kit profiles, which are no longer a source.
- **From bottega:** the brief's prompt paths (`prompts/implementation.md`,
  `prompts/review.md`) were wrong; the real ones are under
  `reference/server/constants/prompts/`. The judge role is ours (bottega has
  none). bottega's refinement stage between READY and the PR is later.

## 2026-10-17 — milestone M0

- **No remote yet.** M0 was built on branch `m0-skeleton` and merged into `main`
  locally with `git merge --no-ff`. Milestone pull requests will be opened once
  the owner provides a remote. Nothing was pushed or tagged.
- **CHANGELOG carries both `[Unreleased]` and `[0.0.0] — 2026-10-17`.** The
  brief for M0 asked for an Unreleased changelog; the version check (copied
  from delegation-kit) requires a dated section for the current version. The
  0.0.0 section says "Repository created. Nothing released."
- **`bottega --version` prints `bottega-kit X.Y.Z`**, and
  `tests/version-consistency.sh` also runs it, so the printed string is a
  checked surface, not only the file.
- **`BOTTEGA_DATA_HOME` is honoured at runtime too.** install.sh installs into
  `${BOTTEGA_DATA_HOME:-${XDG_DATA_HOME:-~/.local/share}/bottega-kit}` and tasks
  live in `<that>/tasks`; using one variable for both keeps them together.
  install.sh replaces only `bin/`, `templates/`, `prompts/`, `LICENSE`,
  `NOTICE` there and never touches `tasks/`; uninstall.sh keeps `tasks/` and
  the configuration.
- **`bin/lib/bottega/cli.py` was added** (not in the plan's layout) to hold the
  argparse tree, so `bin/bottega` stays a few lines. argparse's own usage
  errors are remapped from its default 2 to 64.
- **The effort table lives in `config.py` (`HARNESS_EFFORTS`).** M1's harness
  registry should import it rather than repeat it.
- **`new` stores only the `--role` overrides in `state.roles`.** The effective
  binding (config roles, then overrides) is resolved and frozen at `approve`,
  so editing the configuration between `new` and `approve` takes effect.
  `new` reads the configuration only when `--role` is given. `state.rounds` is
  null until `approve`.
- **Same title in the same minute:** the second task id gets `-2`, then `-3`.
- **Exit codes for references:** an unknown or ambiguous task reference is a
  bad invocation (64). State-dependent refusals are 2. For `signal`: a bad
  status word, a malformed `--uncheck` id, or a status the current role may
  not emit is 64 (the plan names 64 for the role case); an `--uncheck` id that
  is well-formed but not in `task.md` is 2.
- **`signal.log` sits next to `signal.json`** in the run directory (the plan
  names the file, not its place). `signal.json` holds `status, reason, uncheck,
  by, run, at, pid`. The log line is one `O_APPEND` write, so concurrent calls
  never interleave.
- **Base branch precedence:** `--base`, then `bottega.json` `base` (plan §2.13
  lists the key), then `origin/HEAD`, `main`, `master`. The state records the
  branch name (an `origin/` prefix is stripped); `new` prints the start point.
  Nothing is fetched, so `origin/HEAD` is as fresh as the last fetch.
- **Plan region edge cases:** if `## Review Findings` is missing the region
  stops at `## Verdict`, else it is the whole document. Leading and trailing
  blank lines are dropped and the region ends with one newline, so a blank line
  added before `## Review Findings` does not break the approval.
- **Checkbox parsing** accepts `-` and `*` bullets, ignores anything inside a
  fenced code block, and assigns ids only inside `## To-Do List`. Duplicate ids
  are refused.
- **The template keeps bottega's `{{ … }}` placeholder prose.** A freshly seeded
  `task.md` therefore shows placeholder to-do items until the planner replaces
  the sections; `show` counts them.
- **Starter configuration:** with `claude` on PATH (or nothing found) `init`
  writes the canonical Fable/Opus roles; with `codex` it adds `sol-builder`;
  with only `codex`, `sol-builder` is bound to planner, implementer and
  reviewer and there is no judge. With nothing found it still writes the
  Claude starter and says so, rather than refusing; `doctor` then fails.
- **`doctor`:** an unset `${NAME}` in a profile bound to a role fails (exit 2);
  in an unbound profile it is a warning. `gh` missing is a warning. Any
  failure exits 2.
- **`rm`** asks on a terminal and refuses (exit 2) without one unless `--yes`;
  it takes the task lock; repeating it is a no-op; an empty `<repo>-worktrees`
  directory is removed.
- **`new` rolls back:** if the worktree cannot be created the task directory is
  deleted, as bottega does.
- **The fakes** send the output of commands they run (such as `bottega signal`)
  to stderr, so their stdout stays a clean event stream, as a real CLI's
  would. They count calls in `<log>.count`; a call past the scenario's end
  exits 99 unless a `default` step exists.
- **`package.json` has no `repository`/`homepage`** until a remote exists.
  `bin/npm-installer.mjs` is a stub that exits 1 ("not yet released").
- **Python 3.9 or newer** (install.sh checks). The code avoids newer syntax.
- **`./doctor.sh --json`** sends its installed-version section to stderr so
  stdout stays one JSON document.
- **Commit attribution:** the M0 commits carry no attribution lines, per the
  builder's instructions. Plan §8 defers to the builder session's rule, which
  asked for one; the owner may want to settle which applies from M1 on.
