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

## 2026-10-17 — milestone M1

- **The live probe was not run.** The M1 dispatch did not authorize it. Every
  harness flag, permission-rule spelling and event field below is pinned from
  the work plan and delegation-kit's drivers and tested against the fakes
  only. The open unknowns are listed at the end of this section.
- **`dispatch.py` was added** (not in the plan's layout): one role dispatch
  end to end (render, run directory, rails, spawn, parse, identity, receipt).
  `plan` uses it now and the M2 loop will. Failure order follows plan §3:
  could not start / non-zero exit / error result / no final message
  (`dispatch-failed`), `timeout`, `identity-mismatch`, then the rail
  (`role-modified-worktree`).
- **`HARNESS_MATRIX` holds placeholders** `{model}`, `{effort}`, `{task_dir}`,
  `{run_dir}`, `{worktree}`, `{bottega}`; only those names are substituted, so
  JSON arguments such as `{"mcpServers":{}}` pass through. Every Bash
  permission rule is built from one `BASH_RULE` string (`Bash(%s *)`), so the
  `Bash(x *)` / `Bash(x:*)` question is a one-line change.
- **`probe` moved from `doctor` to `harness`.** `doctor` imports it; `approve`
  uses `harness.binding_report`, which applies the same checks (binding,
  profile schema, `--version` probe, `${NAME}` variables) per bound role.
- **The absolute `bottega` path** for `signal_cmd` and the judge's permission
  rule is `<kit>/bin/bottega` of the running kit (the install directory, or
  the checkout), not `sys.argv[0]`, so the prompt and the rule always agree.
- **Receipts:** the run directory also holds `stderr.log` (the harness's full
  stderr); `error.json` keeps the last 40 lines as `stderr_tail`. `run.json`
  adds, beyond plan §4.2: `observed_models` (every name the harness
  reported), `env` (`{"set": [...], "removed": [...]}`, names only),
  `timeout_s`, `duration_ms` and `num_turns` (plan §4.5 asks for them),
  `events` and `unparsed_lines` (parser tolerance), and `reason`. `error.json`
  adds `detail`, one plain sentence. For Claude, `usage` is
  `{"usage": ..., "modelUsage": ...}` from the result event, raw; for Codex it
  is the last `turn.completed` usage, raw. `signal` stays null until M2 folds
  `signal.json`.
- **State:** a failed run's entry in `state.runs` carries `reason`. A planner
  failure does not set `state.stopped` (that field belongs to `run`); the
  phase simply returns to what it was.
- **Proxied Claude profiles** strip, besides the three credentials the plan
  names, `ANTHROPIC_CUSTOM_HEADERS`, `ANTHROPIC_MODEL` and
  `CLAUDE_CODE_USE_BEDROCK|VERTEX|FOUNDRY`, as delegation-kit's proxied driver
  does: a header can carry a credential and the others route the run away
  from the profile's endpoint. The profile's own `env` may set any of them
  again. The temporary `CLAUDE_CONFIG_DIR` is deleted after the run.
  `ZAI_API_KEY` and other non-Anthropic variables are left alone.
- **After a harness exits, its process group is killed** (SIGKILL), so a dev
  server or test runner it left behind does not outlive the dispatch. A
  timeout sends SIGTERM to the group, waits 5 seconds, then SIGKILL.
- **Claude parse:** the init event's model is `provider_reported_model`;
  every name from init, assistant `.message.model` and the result's
  `modelUsage` keys is checked against the request and the aliases. Codex
  parse: `model` at the top of any event or under `response`, `session`,
  `payload` or `msg`; `turn.failed` counts as an error result. The Codex final
  message is the `-o` file only (no fallback to `agent_message` events).
- **`templates/task.md` now uses the strict engine**: `{{task_title}}` and
  `{{original_request}}` (plan §9); `taskdoc.seed` renders it. The spaced
  `{{ … }}` guidance markers stay literal.
- **`{{plan_template}}` is the planner's part of the template only**, from
  `## Overview` up to `## Review Findings`, because that is exactly what the
  planner's final message must contain. Title, request, findings and verdict
  belong to bottega-kit.
- **Planner prompt, deviations from bottega's `planification.md`:** besides
  the changes plan §4.6 lists, the "Original Request quoted verbatim" rule
  becomes "bottega-kit keeps it verbatim; do not repeat or change it", since
  the planner no longer writes the file; the planner is told to record in the
  Overview every decision the user's answers settled, because the questions
  section is dropped once a plan exists; to-do items are plain checkboxes
  without ids. "Playwright MCP" and "Rails runner" became tool-neutral
  wording. `{{test_cmd}}` is always rendered, with "empty means: find the
  project's documented test command".
- **Merging the planner's message:** one outer code fence is removed if the
  whole message is fenced. Any `# Task` heading, `## Original Request`,
  `## Review Findings`, `## Verdict` or `## Questions for you` the planner
  wrote is dropped; extra sections it adds are kept in its order. The
  questions path is taken when the message has a non-empty
  `## Questions for you` section, even if it also has plan sections.
- **`plan` output:** exactly one line on stdout for a planned or failed run.
  For questions, the line is followed by the questions and a one-line hint.
  Failures name the reason and the receipt path on stderr; new untracked files
  in the worktree are a warning on stderr.
- **`approve`:** checks plan §4.3 exactly (Overview non-empty; Testing
  Strategy with a `### Manual QA` subsection that mentions a scenario, or
  "Not needed" anywhere in the section; at least one unchecked to-do item).
  Implementation Plan and Project Docs Update are checked at `plan` time, not
  again here. `approval.roles` maps each bound role to its profile name.
  Without `--rounds`, a re-approval keeps the previous approval's cap, else
  the configuration's. `--rounds 0` or a non-number is a bad invocation (64).
- **Fakes:** a step may now set `raw`, text written to stdout before any
  event, for the tolerant-parser tests. `tests/helpers.py` gained
  `PLAN_MESSAGE`, `QUESTIONS_MESSAGE` and `FakeCalls` (one log and call
  counter per instance).
- **The harness suite dispatches the implementer, reviewer and judge roles**
  with prompt overrides, because their shipped prompts are M2. This also
  exercises the override path.

### Live-probe unknowns still open (plan §4.5)

- The tool names `claude --tools` accepts (`Read,Glob,Grep`,
  `Read,Edit,Write,Glob,Grep,Bash`) and whether a comma list is one argument.
- The permission-rule spelling: `Bash(git push *)` or `Bash(git push:*)`.
- Whether `--permission-prompts none` with `acceptEdits` lets Edit/Write
  proceed in the worktree and in the `--add-dir` task directory, and whether
  `dontAsk` with `--allowedTools Bash` lets the reviewer run tests.
- Whether the variadic `--allowedTools` / `--disallowedTools` lists parse
  correctly as the last options with the prompt on stdin.
- The `stream-json` field names on claude 2.1.302 (`system/init .model`,
  assistant `.message.model`, result `.result/.is_error/.modelUsage/
  .total_cost_usd/.usage/.duration_ms/.num_turns`), and whether `modelUsage`
  lists helper models (a small model for background tasks) that the identity
  check would then reject.
- The exact model names Claude Code and Codex report for each profile (a
  dated suffix would need an alias).
- Codex 0.163.0 event names (`thread.started`, `turn.completed`,
  `turn.failed`), where it reports the model, and whether `-o` is written
  when the final message is empty.
- Whether `-c mcp_servers={}` and `-c features.multi_agent=false` are
  accepted as TOML overrides by `codex exec` 0.163.0.
