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

## 2026-10-17 — milestone M2

- **No live probe, again.** The loop, its prompts and the identity fix are
  tested against the fakes only. Built on branch `m2-loop`, merged into
  `main` with `--no-ff`; nothing pushed or tagged.
- **Identity check, fixed.** M1 compared every model name Claude reported,
  including the `modelUsage` keys of the result event. Those keys also list
  helper models (Claude Code runs a small model for background tasks), so a
  correct run could stop as `identity-mismatch`. `Parsed` now has two lists:
  `identity_models` (Claude: the init event's `.model` and each assistant
  `.message.model`), which alone is compared with the request and the
  aliases, and `models`, everything observed. `run.json` records both
  (`identity_models`, `observed_models`). Codex identity comes from the
  top-level `model` and `response.model` of any event, as delegation-kit's
  driver reads them, and from the `session`/`payload`/`msg` model of a
  session or turn event (`thread.*`, `turn.*`, `session*`,
  `*_configured`); a model named in any other event is observed only. This
  supersedes the M1 "Claude parse" note.
- **Round accounting.** Plan §3 says "round += 1; round > cap → STOP". The
  loop stops when `round + 1 > cap` and leaves `state.round` at the cap, so
  `state.round` is always a round that ran. A resume after `cap-reached` or
  `judge-needs-work` opens the new round when it is granted (`round + 1`,
  implementer next) and sets the cap to the old round plus N, so
  `resume --rounds 1` runs exactly one more pair. After any other stop the
  role that stopped runs again in the same round, with cap = round + N.
- **`run`/`resume` re-validate the loop's bindings only:** implementer,
  reviewer, and the judge when one is approved. The team lead's brief said
  "every approved binding"; the planner does not run in the loop, and
  refusing a run because the planner's profile was deleted helps no one.
- **Every loop prompt is rendered once before anything changes**, so an
  override with an unknown or unset variable refuses (exit 2) with the task
  untouched.
- **A ninth stop reason, `interrupted`:** Ctrl-C or an unexpected exception
  during a dispatch stops the task there (exit 130 for Ctrl-C, from the CLI),
  with the run entry failed as `interrupted` and `next_role` set to the role
  that was running. `resume` also accepts a task left `running` when it can
  take the lock (the bottega that set `running` is gone): that run counts as
  interrupted and the task resumes from it.
- **`resume` on an approved task is `run`;** `--rounds N` then sets the cap.
  `run` on a stopped task refuses and names `resume`.
- **`approve` accepts a stopped task**, so the refusal "plan changed; run:
  bottega approve" can be acted on. It resets `round` to 0 and `stopped` to
  null; the next `run` starts at round 1 (run numbers keep counting). The
  "at least one unchecked item" rule is waived for a stopped task, since the
  loop may have ticked them all.
- **Signal folding.** `state.last_signal` is `{status, reason, uncheck, by,
  run, at}`, plus `implied: true` when the reviewer or judge did not signal
  (status `needs-work`, reason `no-signal`). A failed dispatch's
  `signal.json` is not folded; it stays in the run directory as evidence. A
  `signal.json` that does not parse, names another run, or carries a status
  the role may not emit counts as no signal, with a warning. An `--uncheck`
  id no longer in `task.md` when the loop folds the signal is a warning; the
  others are applied.
- **Dispatch line words:** implementer `done`; reviewer and judge the signal
  status, or `no-signal`; a failure `failed <reason>`, as in `plan`.
- **Receipts:** each `state.runs` entry carries `round`, and for a reviewer or
  judge `signal` (the status) and `reason: no-signal` when implied.
  `run.json` adds `round`, `warnings` (for example `implementer-committed:
  ...`) and `signal` (the folded record).
- **Merging a final message into `task.md`:** one outer code fence is
  removed; a leading `## Review Findings` or `## Verdict` heading the agent
  wrote is dropped; any other level-1 or level-2 heading outside a code fence
  becomes level 3. An agent's message can therefore never add, end or
  duplicate a section, and the plan hash is never touched.
- **The loop keeps the state in memory** from the moment it takes the lock and
  only writes `state.json`, never reads it back mid-run: the implementer can
  write in the task directory (`--add-dir`), so the file must not steer the
  loop. It reads `task.md` (the implementer's ticks) and the current run's
  `signal.json`, by design.
- **Implementer prompt** (from `implementation.md`, `code-delivery.js`
  170–198, `execution-loop.md`): kept the findings-first rule, plan order,
  tick-as-you-go, Testing items ticked only after running them, tests
  mandatory, no questions, stay in scope, never switch branches. Changed: it
  never commits (plan §9 sides with the server), so code-delivery's "Commit
  (required)" section and its TypeScript-only rule are dropped; it edits only
  the checkboxes of `task.md`; no sub-agents; it does not signal; its final
  message is a summary kept in the receipt and is not merged.
- **Reviewer prompt** (from `review.md`, `code-delivery.js` 201–232): every
  rule kept, mostly in bottega's words. Changed: findings by `[T<n>]` id; the
  early return also signals `needs-work` ("implementation in progress"),
  because no signal means the same thing and an explicit one reads better
  in `show`; "check CLAUDE.md for the test command" became `{{test_cmd}}` or
  the project's documented command; the Playwright and video rules are gone,
  and the server-isolation rule applies to any scenario that needs a server,
  with `{{port}}`; code-delivery's paragraph about live model conversations
  is product-specific and was not carried, except "needing a dev server or a
  live run is not a blocker"; the reviewer does not edit `task.md` (bottega
  -kit writes the findings and applies `--uncheck`). The signal section is
  last.
- **Judge prompt** (ours): reads `git diff <base>...HEAD`, `git diff HEAD`
  (the implementer never commits, so most of the change is uncommitted) and
  new untracked files directly, because its Claude permission rules allow
  only `git diff`, `git log`, `git show` and `bottega signal` (no
  `git status`). Final message `**Merge:** yes|no` and three reasons.
- **`show`:** the text view gains round, next role, last signal (and its
  unchecked ids), the stop and one line per run; the approved roles now show
  as `roles` and per-task overrides as `overrides`. `--json` adds `runs`, the
  `run.json` records by sequence number.
- **Fakes:** a step may set `usage_extra` (more `modelUsage` keys) and
  `events` (extra JSON events).
- **The Ctrl-C test** resets SIGINT in its child: `run-tests.sh` starts the
  suites as background jobs, which a non-interactive shell runs with SIGINT
  ignored, and that disposition is inherited.
- **CHANGELOG:** the identity fix is an "Added" line, since the M1 behaviour
  was never released.

### Live-probe unknowns added by M2

- Whether the judge, with only `Bash(git diff *)`, `Bash(git log *)`,
  `Bash(git show *)` and `Bash(<abs bottega> signal *)` allowed, can run the
  diff commands and the signal command as written in its prompt.
- Whether a reviewer under `dontAsk` with `--allowedTools Bash` can run the
  project's test suite in the foreground for up to ten minutes.
- Which model names Claude Code lists in `modelUsage` besides the content
  model.

## 2026-10-17 — milestone M3

- **No live run, again.** `pr`, the npm wrapper and the docs are tested
  against fake `claude`, `codex` and `gh` and local repositories only.
  `docs/compatibility.md` says so. Built on branch `m3-pr-docs-packaging`,
  merged into `main` with `--no-ff`; nothing pushed, tagged or published.
- **`pr` uses real git, a fake gh.** Plan §5 M3 said fake `git` and `gh`; the
  team lead's brief said real git with a local bare origin, which tests more.
  The fake gh lives in `tests/fake-gh/`, not `tests/fakes/`, so it is on PATH
  only in the `pr` suite and `doctor`'s "gh missing" warning stays testable.
  The suite configures origin as `https://github.com/acme/app.git` and
  rewrites it to the bare repository with `url.<bare>.insteadOf`.
- **gh is pinned to origin.** gh picks the base repository from the remotes
  and prefers one named `upstream`, which would break "origin only". `pr`
  therefore passes `--repo HOST/OWNER/REPO`, parsed from origin's configured
  URL (`remote.origin.url`, before any `insteadOf`), in https, ssh and scp
  forms. An origin that is not such a URL (a local path, say) is refused (2)
  like a missing origin, before anything changes.
- **Order and refusals in `pr`:** phase (done or stopped), the worktree
  exists, origin, gh on PATH, then the commit, then "nothing to submit"
  (2) when the branch has no commit ahead of `origin/<base>` (or local
  `<base>`) and nothing was uncommitted — bottega's PR agent stops in the
  same case — then the push, `gh pr view`, `gh pr create`. A failed commit,
  push or `gh pr create` exits 2 with the tool's whole message; the exit-code
  vocabulary has nothing closer. `state.pr` is written only on success.
- **`gh pr view --json url,state`**, not `url` alone: a CLOSED pull request
  for the branch is not reported as existing, and a new one is created. An
  open or merged one prints `pr exists: <url>`.
- **The PR body.** A stopped task's body *starts* with
  `**Stopped: <reason> — <detail>**` and one sentence, so a reader cannot miss
  it, rather than coming after the verdict. The template's HTML comments are
  removed, so an empty Review Findings or Verdict reads "No review findings
  were recorded." or is left out. The body is kept as `pr-body.md` in the task
  directory, as a receipt. The phase does not change after `pr`;
  `state.pr = {url, at, commit}` (the pushed HEAD), `new` writes `pr: null`,
  and `show` prints a `pr` row. `pr` takes the task lock.
- **`commands/stubs.py` is gone;** `cli-smoke` checks that `run`, `resume`
  and `pr` refuse an unknown task (64) instead.
- **npm wrapper:**
  - It clones `--depth 1 --branch <ref>`, so `--ref` takes a tag or a branch,
    not a commit.
  - With the default ref, the cloned `version.py` must equal the package's
    version, or it refuses (1). `--ref` is the user's choice and is not
    checked.
  - Unknown arguments are refused (64) instead of being forwarded as
    delegation-kit does, because `install.sh` takes none.
  - There is no `--uninstall` (in `docs/later.md`).
  - Errors are thrown and caught at the top, so the temporary clone is
    removed on every failure path. delegation-kit's `die()` inside `try`
    skipped its cleanup. Ctrl-C can still leave the clone behind.
  - A failing doctor makes the wrapper exit with doctor's code, as
    delegation-kit does, with a hint. A new machine has no configuration,
    so `npx bottega-kit` exits 2 there until `bottega init`. README says so.
- **`install.sh` records the npm source.** `BOTTEGA_INSTALL_SOURCE` and
  `BOTTEGA_INSTALL_REF`, set by the wrapper, become `source` and a new `ref`
  key in `installed-version.json`. A checkout install still records its
  directory and `ref: null`. The wrapper test checks that no installed file
  or link mentions the temporary directory.
- **The node test is a CI job** (`npm-wrapper`, ubuntu, node 20), not a
  `run-tests.sh` suite, as in delegation-kit, so the suites do not need
  node. CLAUDE.md lists it among the gates before a pull request.
- **A new suite, `tests/version-tag.sh`,** runs `version-consistency.sh
  --tag` on tags made in a temporary copy of the version surfaces: an
  annotated tag with the right subject passes; another version, a bare
  `v` tag, a missing tag, a lightweight tag and a wrong subject fail.
- **CHANGELOG 0.1.0** is one paragraph per milestone plus "Known limits", as
  the brief asked, replacing the line-per-feature Unreleased list. It is dated
  2026-10-17, the day of the bump; if the owner tags on another day, the date
  moves with the tag.
- **`package.json`** points `repository`, `homepage` and `bugs` at
  `https://github.com/matteoscurati/bottega-kit`, which does not exist yet.
  `npm pack --dry-run` lists six files: the wrapper, `package.json`, README,
  CHANGELOG, LICENSE, NOTICE.
- **README** keeps the §2.16 paragraph word for word, adds node 18 to "What
  you need" (only for `npx`), and its sample dispatch lines carry illustrative
  durations, not measured ones.
- **NOTICE** lost a sentence about which milestone ships which prompt.
- **Commit attribution:** the M3 commits carry no attribution lines, as the
  brief asked and as M0 to M2 did.

### Live-probe unknowns added by M3

- Whether gh accepts `--repo HOST/OWNER/REPO` for a GitHub Enterprise host,
  and whether an ssh host alias in origin's URL needs handling.
- What `gh pr view <branch> --json url,state` returns for a branch whose pull
  request was merged, and whether it ever prompts.

## 2026-10-17 — live probe, part 1 of the release gate

Authorized by the owner ("procedi intanto con 1"). Run by the lead, not by a
builder, through the installed kit in scratch directories, on a throwaway
repository. Full numbers in `docs/compatibility.md`.

- **Profiles:** `claude-sonnet-5-5` (effort medium) for the Claude roles and
  `gpt-5.6-terra` (effort medium) for the Codex roles, chosen for cost, not
  as a recommendation. Task 1: Codex implements, Claude reviews and judges.
  Task 2: Claude implements, Codex reviews, Claude judges.
- **Found:** the Codex reviewer's `bottega signal <task-id>` exited 64 twice
  ("no task matches"); the loop treated it as no signal and stopped at the
  cap, exactly as specified. Codex runs agent commands with
  `shell_environment_policy.inherit = "core"`, so `BOTTEGA_DATA_HOME` and
  `XDG_*` never reach the shell. Claude's Bash inherits everything, which is
  why task 1 worked.
- **Fixed, here, by the lead (small, test-covered):** `state.resolve` accepts
  an absolute task directory; `prompts.values` renders `signal_cmd` with the
  task directory instead of the id; two tests in `state-and-signal`, the
  `prompts` and `loop` expectations updated. The resumed round signalled
  `ready` from the Codex sandbox. The id form still works for people.
- **Not changed:** the Codex environment policy. Widening it
  (`shell_environment_policy.inherit = "all"`) would leak the user's whole
  environment into the agent's shell; naming the path is enough.
- **Observed, recorded in `docs/compatibility.md`:** the exact `stream-json`
  and Codex JSONL shapes; Codex names no model, so its identity stays
  `requested-only`; the Claude implementer edited through Bash, so Edit and
  Write stay unverified; a harmless Codex hooks "error" item.
- **Still open for part 2:** `bottega pr` on a real GitHub repository (needs
  the repository the owner has not created yet), the deny rules, the Opus and
  Fable model names, a proxied profile, and Codex as planner and as judge
  (both tasks ran those roles on Claude Code).

## 2026-10-17 — code review after the live probe

`/code-review max --fix` over the whole repository, applied by the review
agent and verified by the lead: an unclosed code fence in a reviewer's or
judge's message could hide every later section of `task.md` (fixed: the fence
is closed and a test pins it); `bottega.json` `base` is now type-checked like
`test_cmd`; the "new untracked files" warning is printed for read-only roles
only (receipts keep it for every role); the prompt is sent to the harness as
UTF-8 regardless of the locale; `bottega signal` reads the role→status table
from `loop.SIGNALLING` instead of a copy; `taskdoc.set_title` and
`harness.names` (no callers) are gone. Documentation corrected: Codex was
verified as implementer and reviewer, not in every role; `--role` belongs to
`bottega new`; profiles are read when `plan`, `run` or `resume` start, not at
every dispatch. Two findings deferred to `docs/later.md`: `pr` committing
untracked caches, and `--role` on `plan`.


## 2026-10-19 — smoke tests and documentation review

Two fake-driven end-to-end smokes through the installed kit (`install.sh`
into a scratch data home, `init`, `doctor`, `new`, `plan`, `approve`, `run`,
`pr`, `pr` again, `show`, `list`, `rm`, `uninstall.sh`), after the code
review fixes:

- the happy path: Claude in every role, `ready` in round 1, the judge
  `ready`, a pull request created then reported as existing;
- the unhappy path: Codex as implementer (`--role implementer=sol-builder`),
  `approve --rounds 1`, a reviewer `needs-work --uncheck T3` whose message
  leaves a code fence open (the fence is closed, `## Verdict` survives),
  `cap-reached` (exit 3), `pr` on the stopped task (the body starts with the
  stop), `resume --rounds 1` signalling by the absolute task directory, done
  in round 2 of 2, `pr exists`. Receipts hold no environment values.

Both passed. The suites also pass under Apple's python3 3.9.6, so the
"python3 3.9 or newer" claim holds after the review fixes (`dispatch.py`'s
parenthesised `with` is accepted by 3.9's parser).

Documentation corrected against the code, nothing else changed:

- README said `plan` and `run` print nothing but the dispatch line on stdout;
  `plan` also prints the planner's questions.
- `docs/process.md` now says a stopped task can be approved again (ids kept,
  the unchecked-item rule waived, the next `run` starts at round 1), and that
  `pr exists:` covers a merged pull request as well as an open one.
- `docs/configuration.md`: an unset `${NAME}` also fails `plan`;
  `XDG_DATA_HOME` is read by the shell scripts too.
- `docs/compatibility.md`: the open unknown about model names now names what
  the starter configuration writes, not a name it does not; the
  offline-gates block gained the shellcheck line.
- The `task` argument's help in every command says it also takes the task
  directory, which `state.resolve` has accepted since the live probe.

**Opus is `claude-opus-5-5` from today.** The plan (§4.4) and the starter
configuration bound `opus-builder` and `opus-reviewer` to `claude-opus-5`,
the previous Opus generation. On the owner's word ("modifica opus in 5.5")
the name is `claude-opus-5-5` in `config.py`, the suites, the npm wrapper
test, the README and `docs/`. The name is still unverified live, like
`claude-fable-5-1`: the probe ran `claude-sonnet-5-5`, and part 2 of the
release gate should run the starter's names once.

**The planning-and-judging profile is `fable`, not `fable-judge`.** The
plan (§4.4) named it `fable-judge`, but it is bound to the planner as well,
and the name read oddly in the README's first example. On the owner's word
(the readability review, then "applica") the starter profile is `fable` in
`config.py`, the suites, the npm wrapper test, the README and `docs/`. The
same pass put the command sequence, the definition of a round and the
definition of profile and harness in the README before its first example,
added a `bottega.json` line to the example sequence, and linked the task
template from `docs/process.md`. The CHANGELOG is untouched: 0.1.0 is not
tagged yet.

The CHANGELOG's 0.1.0 date stays 2026-10-17 until the tag is cut and moves
to that day.

## 2026-10-19 — live probe, part 2: every harness in every role

Authorized by the owner ("andiamo di 1 2 e 3"), run from an isolated install
in the session scratchpad on a fresh copy of the greeter repository, one
dispatch set at a time:

1. Codex (`gpt-5.6-terra`, medium) as planner, implementer, reviewer and
   judge: `ready` in round 1 of 2, four dispatches, about three minutes.
2. The starter configuration as `bottega init` writes it, on Claude Code
   2.1.303: `fable` (`claude-fable-5-1`, max) as planner and judge,
   `opus-builder` and `opus-reviewer` (`claude-opus-5-5`, high): `ready` in
   round 1 of 2, four dispatches, 2.16 USD. Both names are reported exactly.
3. `bottega pr` on a private GitHub repository created for the probe
   (`matteoscurati/bottega-probe`): pull request opened, `pr exists:` on the
   open and then on the merged pull request, repository deleted afterwards.
   Z.AI (item 4) is deferred by the owner until the rest is settled.

Before the live runs, an offline smoke (`smoke3.sh`, in the scratchpad) ran
the fake Codex in every role and a fake proxied Claude profile in every
role, including the alias path, the credential stripping and the exit-2
refusal when `${ZAI_API_KEY}` is unset.

Findings, all recorded in `docs/compatibility.md`:

- **Fence bug, fixed.** A ``` block nested in a ```` block was read as
  closing it, so comment lines inside became headings and `merge_plan`
  dropped five lines of the Fable planner's README snippet. `taskdoc` and the
  loop's section merge now track fences by CommonMark rules (same character,
  at least the same length), with regression tests in `taskdoc` and `loop`.
- **Judge permission denials.** Two `git -C …` commands, one of them joined
  with `&&` and `git status`, fell outside the judge's allow list and were
  denied; the judge recovered with plain `git diff` and `git log`. The judge
  prompt now says which commands are allowed. Recording `permission_denials`
  in `run.json` is a line in `docs/later.md`.
- `Edit` under `acceptEdits` is now verified; `Write` is not.
- The probe's `XDG_CONFIG_HOME` override hides gh's login; `GH_CONFIG_DIR`
  fixes it. Not a kit matter.

The CHANGELOG is still untouched: 0.1.0 is not tagged.

## 2026-10-19 — live probe, part 3: the open points

Authorized by the owner ("ok, lavoriamo ai punti aperti allora", after the
proposal "chiudere i primi tre punti in una sonda breve, circa quattro
dispatch su Sonnet e terra, sotto 1 USD"). Four live dispatches on a throwaway
repository whose full suite sleeps 150 s in an end-to-end test: a Sonnet
implementer and reviewer on "add a --bye flag" (two new files), a Terra
implementer and reviewer on "add a --whisper flag". The plans were written
by hand and served by the kit's fake `claude` on `plan`, so no planner model
ran; prompt overrides in the probe's own config dir asked each role to try
the forbidden commands and report. Claude cost 0.15 USD. Z.AI stays deferred;
`ZAI_API_KEY` is not exported in this session anyway.

Findings, all in `docs/compatibility.md`:

- The Bash deny rules work as spelled: eleven forbidden commands, eleven
  denials, including bare `git push`, `gh --version` and `echo probe && git
  push origin HEAD`. The BASH_RULE comment in `harness/__init__.py` now says
  so instead of calling the spelling an unknown.
- Claude handles a slow suite: the reviewer set a 600 000 ms Bash timeout as
  the prompt asks, the implementer 400 000 ms without being asked.
- **Found:** the Codex reviewer gave up on the slow suite. Codex's resumable
  command execution hands control back after a short yield while the command
  runs on; the reviewer read that as the sandbox killing the suite, could not
  check with `ps`/`pgrep` (denied in the sandbox), marked the suite item
  FAILED and signalled `blocked`. The Codex implementer, on the same suite,
  waited and saw it pass. Change: the reviewer prompt's step 3.2 and the
  implementer prompt's item 5 now say to give the command a long timeout and,
  if the shell tool hands control back while the command runs, to wait for
  that command; not yet re-run on Codex (one `resume` would do it; needs the
  owner's word).
- Codex has no deny rules: a commit in the worktree fails because Codex keeps
  the git directory read-only; `gh` runs; a push to the probe's local bare
  origin under `/tmp` went through from both roles, because `workspace-write`
  makes `/tmp` writable. For a network remote the sandbox's network block is
  what stops a push, unless `config.toml` lifts it. Documented in
  compatibility.md and process.md; a per-profile `-c` passthrough is a
  later.md line, not built.
- `Write` is still unexercised: Sonnet created the new files with Bash
  heredocs although `Write` was offered. Same permission class as `Edit`.

`HARNESS_MATRIX` is unchanged. `CHANGELOG.md`'s 0.1.0 section stays dated
2026-10-17 and untagged; its known-limits bullet is updated.

## 2026-10-19 — live probe, part 4: the last two dispatches

Authorized by the owner ("ok per bottega resume e l'implementer"): one
`bottega resume` of the whisper task, so a Terra reviewer runs with the
changed prompt wording, and one Sonnet implementer dispatch nudged to use
`Write`. Exactly two real dispatches. To keep it at two, a wrapper for
`claude` and one for `codex` sat first on PATH: `--version` passed through,
the first dispatch per harness went to the real CLI, and any other exited 75
with "probe guard: … refused", so the loop stopped as `dispatch-failed`
instead of dispatching a reviewer nobody had authorized. The kit was
reinstalled first, so the installed prompts carried the part 3 wording; the
reviewer override from part 3 was removed, and the implementer override
replaced by one that asks for `Write` for new files and `Edit` for the rest.

Findings, in `docs/compatibility.md`:

- **The Codex fix holds.** With the new reviewer wording, the Terra reviewer
  ran `python3 -m unittest -v` once, in the foreground, with no `ps` or
  `pgrep` in between, saw `Ran 6 tests in 150.033s`, verified all seven items
  and signalled `ready`; the task finished in round 1 of 2. Same model, same
  suite, same sandbox as the `blocked` run: only the prompt changed.
- **`Write` works under `acceptEdits`.** Sonnet created `shout.py` and
  `test_shout.py` with `Write`, edited the rest with `Edit`, no permission
  denial, suite waited with a 600 000 ms timeout, 180 s, 0.081 USD. It ticked
  the boxes with a Bash `sed -i`, which `--add-dir` allows.
- The refused reviewer left a `003-reviewer` receipt with `error.json`
  (`dispatch-failed`, exit 75, the guard's stderr) and the task `stopped`,
  which is what the loop should do when a harness fails to start.

No code change. `HARNESS_MATRIX` unchanged. Open unknowns are now the GitHub
Enterprise host and the proxied (Z.AI) profile only. `CHANGELOG.md`'s 0.1.0
section stays dated 2026-10-17 and untagged; its known-limits bullet is
updated. Twenty-seven live dispatches in all; 2.39 USD on the 19th.

## 2026-10-20 — a key file for `${NAME}` references

Deviation from plan §2.2 ("bottega-kit stores no secrets"), on the owner's
request ("ma non possiamo creare un .env per bottega-kit?", then "procedi").
The occasion: the Z.AI key lives in delegation-kit's key file and in no shell
startup file, so a `claude` profile pointed at Z.AI could not pass `doctor`
from a fresh shell, or from this session, without an export by hand.

What changed: `${XDG_CONFIG_HOME:-~/.config}/bottega-kit/secrets.env`, one
`NAME=value` line each, is read for a referenced name the environment does
not set. The rules, taken from delegation-kit's key files: parsed, never
executed (`export`, quotes and CRLF tolerated); refused, with the `chmod 600`
to run, while group or others can read it (`doctor` fails; `plan`,
`approve`, `run` and `resume` exit 2); the environment wins; only the
expanded profile `env` reaches a harness, never the rest of the file;
receipts still hold names only; no project `.env` is ever read. `doctor`
prints the file's variable names and, per bound profile, whether each
reference comes from the environment or from the file. `config.environment`
is the one merge point; `missing_env` and `expand_env` use it when no
explicit environment is given, and `base_env` and `proxied_env` pass the
inherited environment through it for expansion only. What §2.2 protects is
restated in the README: no secret in the configuration, the prompts, the
tasks or the receipts. Nine tests in the `config` suite, one through
`bottega plan`. CHANGELOG 0.1.0 "Tasks and configuration" updated; still
untagged, nothing pushed.

## 2026-10-20 — live probe, part 5: the proxied profile on Z.AI

Authorized by the owner ("lavoriamo alla sonda z.a: autorizzo"), as proposed:
two dispatches, a Sonnet implementer and a reviewer on the README's proxied
profile (`claude`, `glm-5.3-flash` at `max`, `ANTHROPIC_BASE_URL` on Z.AI,
`ANTHROPIC_AUTH_TOKEN` from `${ZAI_API_KEY}`, `aliases: ["opus"]`), on a new
task in the slow-suite repository, the plan written by hand and served by
the fake planner. The key came from the probe's `secrets.env`, a symlink to
delegation-kit's key file, so no copy of the value was made; `ZAI_API_KEY`
was set in no shell. The shipped prompts ran, no override. The wrapper on
PATH passed one `acceptEdits` dispatch and one `dontAsk` dispatch with
`ANTHROPIC_BASE_URL` set, and refused anything else. Kit at 363a424,
Claude Code 2.1.304 (updated since the 19th).

Findings, in `docs/compatibility.md`:

- **Identity:** Claude Code reported `glm-5.3-flash`, the requested name, in
  `init`, every turn and `modelUsage`: `provider-reported`, no alias needed.
  stderr: one `[claude-code:unrecognized_model]` line, harmless. `--effort
  max` accepted. `apiKeySource: none` with the fresh `CLAUDE_CONFIG_DIR`,
  which was deleted after the run.
- **The receipt:** env names set `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`,
  `ANTHROPIC_DEFAULT_OPUS_MODEL`, `CLAUDE_CONFIG_DIR`; removed none, because
  this machine sets no Anthropic variable, so the live run did not exercise
  the stripping (the suite does). The key's value appears in no receipt and
  no log, checked by grep.
- **The review:** GLM Flash read the document and the diff, ran the targeted
  tests, the 150 s suite in the foreground with a 600 000 ms timeout, the
  manual QA, and signalled `ready` with well-formed findings; 12 tool calls,
  0 denials, 214 s. Sonnet implemented in 179 s, 0.059 USD, with Bash
  heredocs again (no override asked for `Write` this time).
- **Cost:** Claude Code priced the unknown model at its default table
  (5 / 25 USD per million, 0.5 for cache reads): 0.209 USD reported, about
  0.014 USD at Z.AI's list price. `cost_usd` records the estimate as
  reported, and `max_budget_usd` is enforced on it. Documented in
  `configuration.md` and `compatibility.md`; no code change, since the kit
  never prices anything itself.
- **2.1.304 events:** `system/task_started`, `system/task_notification`,
  `tool_progress` heartbeats, `system/thinking_tokens` (1 074 in the GLM
  run) and `system/ui_invalidate` are new; the parser ignored them,
  `unparsed_lines` 0.

No code change. `HARNESS_MATRIX` unchanged. The only open unknown left is
the GitHub Enterprise host; the live stripping of a set Anthropic variable
is noted as not exercised. Twenty-nine live dispatches in all. Still
untagged, nothing pushed.

## 2026-10-20 — the showcase site

The owner asked for a showcase site like delegation-kit.sh, running on
Cloudflare with analytics there, and asked me to keep it current. It is a
repository of its own, `../bottega-kit.sh`: Astro 5, Tailwind 4, static,
the sibling site's shape and scripts adapted. Its `scripts/sync-kit.mjs`
regenerates every page about the kit from this checkout: the README as
"Getting started", `docs/*.md`, the template and the four prompts verbatim,
the CHANGELOG, and the kit's own tables (version, efforts, roles, exit
codes, the starter configuration, the harness argv per role) through a
python3 import of `config`, `util` and `harness`, never a command of the kit.
It refuses a checkout that is dirty or not on its release tag unless told
`--allow-unreleased`; the first sync used that flag, since 0.1.0 is untagged.
`--check` runs before every build and skips itself when the checkout is
absent or unreleased, so a refactor in progress here cannot leak there.

Deployed by hand with wrangler, as the owner's OAuth login, to Cloudflare
Workers with static assets: `https://bottega-kit-sh.8004dev.workers.dev`.
No domain exists for the kit on the account; registering one is the owner's
call, and the site's origin then changes in three named places. Cloudflare
Web Analytics is on through a site created in the dashboard for that
hostname; its token sits in the site repository's ignored `.env` and goes in
the CI variable `PUBLIC_CF_BEACON_TOKEN` once the repository is on GitHub.
The site links `github.com/matteoscurati/bottega-kit` and `npx bottega-kit`
as the README does; both work only once the owner publishes. Nothing was
pushed: the site repository has no remote, like this one.

No code change here. `CLAUDE.md` gains a section naming the site and the
"sync the showcase site" step in "Release tagging".

## 2026-10-21 — the site's copy file, and housekeeping

`CLAUDE.md` names `src/data/copy.json` as the site's one hand-written
description of the kit: the home page copy moved there from `index.astro`,
with placeholders filled from the kit's tables, and a workflow cut it from
1219 to 727 words. No kit code changed for that.

Housekeeping the same day, after the owner asked for it:

- The six merged branches (`m0-skeleton` to `m3-pr-docs-packaging`,
  `probe-fixes`, `review-fixes`) were deleted; the workflow says a branch
  goes after its merge, and these had stayed.
- `ruff.toml`. `ruff check bin tests` had been skipping the four Python
  executables without a `.py` suffix (`bin/bottega`, `tests/fakes/claude`,
  `tests/fakes/codex`, `tests/fake-gh/gh`): 42 files, not 46. `extend-include`
  names them and `target-version = "py39"` pins the floor the README states.
  All four already passed; now the gate sees them. CI needs no change, ruff
  reads the file.
- `loop.stop()` refuses a reason outside `STOP_REASONS`, a tuple nothing had
  read until now.
- `install.sh` copies `prompts/` unconditionally; the "once they exist"
  guard was M0's, before the prompts were written.
- Three comments described milestones as future work (`config.py`,
  `worktree.py`, `commands/pr.py`); reworded in the present.
- The showcase site: `sharp` is now declared, the OG script had imported it
  through Astro's own dependency; the MDX integration, which no page used,
  is gone; prettier formatted two files it had never seen. `npm audit`
  there lists Astro 5.18 advisories fixed only in Astro 7, and sharp
  advisories fixed in 0.35, outside Astro's range: the site is static and
  rasterises only its own card, so none of them applies at runtime; the
  upgrade is a pass of its own, when the owner wants it.

## 2026-10-23 — the repository lives under the reasance organisation

The owner moved the kit to `https://github.com/reasance/bottega-kit`. It had
never been pushed, so nothing was transferred: the repository is created
there. `package.json` (`repository`, `homepage`, `bugs`), the npm wrapper's
`DEFAULT_REPO` and the README's `git clone` line point at it; `author.url`
stays the owner's profile. The earlier entries that name
`matteoscurati/bottega-kit` are left as written. No version is on npm yet,
so no published wrapper clones the old URL.

## 2026-10-23 — 0.1.0 tagged without a fresh live run

The owner asked to tag and publish 0.1.0 now. `CLAUDE.md` asks for a live
end-to-end run before tagging; this release carries the "Verified snapshot"
of 2026-10-17, 19 and 20 forward instead, by the owner's decision. What
changed since that run: the housekeeping of 2026-10-21 (ruff configuration,
`loop.stop()` checking its reason, `install.sh` copying `prompts/`
unconditionally, comments) and the repository URL. All gates pass locally
and in CI.

- **CHANGELOG** 0.1.0 is dated 2026-10-23, the day of the tag, as the entry
  of 2026-10-17 said it would be.
- **0.1.0 is published by hand**, from the owner's machine at the tag, with
  npm's two-factor check: npm configures a trusted publisher only on a
  package that already exists, and the owner chose that over a CI token
  that bypasses two-factor. So 0.1.0 has no provenance statement; it cannot
  gain one later. `publish-npm.yml` is disabled while the tag is pushed, so
  the tag push does not run a publish that has no credential.
- **`publish-npm.yml`** moves to trusted publishing for 0.1.1 onward:
  `id-token: write`, no `NPM_TOKEN`, Node 22 with npm pinned to 11.6.2
  (trusted publishing needs 11.5.1 or later), `npm publish --provenance
  --access public`. It is re-enabled once the package's Trusted Publisher
  names `reasance/bottega-kit` and `publish-npm.yml`. The first tag that
  runs it is its first test.

## 2026-10-23 — 0.1.1: a live run on the starter configuration

The owner asked to merge, tag and release the documentation pass of the same
day as 0.1.1, and chose the live run with the starter configuration ("Run
live con lo starter") over a cheaper one or none. One task, "add a
`--times N` option", on a throwaway greeter repository pushed to a private
`matteoscurati/bottega-probe`, through an install of `main` at the merge of
the documentation pull request in the session scratchpad
(`BOTTEGA_DATA_HOME`, `BOTTEGA_BIN_HOME`, `XDG_CONFIG_HOME` there,
`GH_CONFIG_DIR` at the real `~/.config/gh`). Claude Code 2.1.309; Fable at
max as planner and judge, Opus at high as implementer and reviewer, each
profile with `timeout` 1800 and `max_budget_usd` 3.

Four dispatches, done in round 1 of 3, 2.07 USD; `bottega pr` opened the
pull request and a second `pr` printed `pr exists:`. Both models were
reported by name, no permission denial, no warning. Nothing in
`HARNESS_MATRIX` changes. Codex 0.164.0 is installed but was not run, and is
now an open unknown in `docs/compatibility.md`.

`docs/compatibility.md`: the "Verified snapshot" is this run. The 0.1.0
snapshot is not dropped: it moves, unchanged, to a section of its own at
the end, marked as not re-run, because its findings (the deny rules, the
Codex event shapes, the fixes) are still the only record of them. Nothing
from it is presented as verified for 0.1.1. The README's cost paragraph
uses this run's numbers and dates the Sonnet range to 0.1.0.

The 0.1.1 tag is the first one `publish-npm.yml` runs on: npm trusted
publishing, with provenance.

## 2026-10-23 — 0.1.1 published by hand: npm trusted publishing refuses this repository

The tag push ran `publish-npm.yml` for the first time (run 39974239667).
Every guard passed and the provenance statement was signed, then the PUT
failed: `E403 OIDC permission denied for this action`. A re-run after the
owner checked the Trusted Publisher failed the same way. The configuration
is right: `npm trust list bottega-kit` shows GitHub, `reasance/bottega-kit`,
`publish-npm.yml`, no environment (so `npm trust github` answered 400: one
already exists).

Cause: `reasance/bottega-kit` was created on 2026-10-23, after 2026-07-15,
so GitHub signs its OIDC tokens with immutable subject claims;
`gh api repos/reasance/bottega-kit/actions/oidc/customization/sub` says
`use_immutable_subject: true`, prefix
`repo:reasance@247802277/bottega-kit@1430949588`. npm's trusted publishing
matches only `repo:OWNER/REPO:…`. Open upstream as npm/cli#9969, untriaged
since late September; other projects report the same error. It cannot be
turned off on GitHub's side.

What was done: the owner published 0.1.1 by hand with two-factor, from a
clean worktree of the tag; the tarball's shasum (`0c034a3a…`) is the one
the CI run built. npm serves 0.1.1 as `latest`, without provenance;
`npx bottega-kit` installs the tag `bottega-kit--v0.1.1` at `6ca1985`. The
entry above that said 0.1.1 would be the first release with provenance is
wrong.

`publish-npm.yml` stays as it is: it will work unchanged once npm matches
the new subject, and until then a tag push fails at the publish step after
the guards, harmlessly. Each release is published by hand, then the failed
run is left as it is (a re-run refuses the version, already on npm).
`CLAUDE.md`'s release steps say so. No `NPM_TOKEN`: a token that bypasses
two-factor is what the owner declined for 0.1.0.

## 2026-10-23 — MiniMax and Kimi as proxied Claude profiles

The owner asked for MiniMax M3.1 Flash and Kimi K3.1 Pro, and chose proxied
`claude` profiles with a live run each over native drivers (`docs/later.md`
keeps the Kimi driver and the `openai-compatible` harness as 0.2.0
candidates). No code changes: both providers serve an Anthropic-compatible
endpoint, the path Z.AI already took.

Keys: the owner asked me to make `~/.config/bottega-kit/secrets.env` and to
find the keys elsewhere, read-only. `MINIMAX_API_KEY` was copied, without
being shown, from `~/.config/delegation-kit/.env` into a new `secrets.env`
created at mode 600; that file was only read. No Kimi API key existed: the
`kimi` CLI signs in to Kimi Code with OAuth, and its token was not reused.
The owner created a Kimi Platform key and added `KIMI_API_KEY` to
`secrets.env` themselves.

Kimi K3.1 Pro: `kimi-k3.1-pro` answered 404 on
`https://api.moonshot.ai/anthropic` and `GET /v1/models` listed up to
`kimi-k3`. On the owner's choice the run used `kimi-k3`, and the docs say
to change the model name once the API lists K3.1 Pro.

Before each run, one 16-token request to the endpoint confirmed the model
name it accepts and reports. Then planner, implementer and reviewer on one
profile each: both done in round 1, every receipt `provider-reported` with
the requested name alone, so no alias. Mapping the three
`ANTHROPIC_DEFAULT_*_MODEL` variables to the same model kept Claude Code's
own requests on it. Numbers in `docs/compatibility.md`.

## 2026-10-23 — Kimi Code as a native harness

The owner asked for Kimi K3.1 Pro in bottega-kit. Moonshot's API does not
serve it to the owner's key (see the entry on proxied profiles); Kimi Code,
the owner's subscription, does, through the `kimi` CLI and its OAuth login.
On the owner's word ("vai con driver nativo") the `kimi` harness, a 0.2.0
candidate in `docs/later.md`, is built now. Decisions, from Kimi Code
2.3.1's documentation (`llms-full.txt`) and a live probe:

- **Prompt as an argument.** `kimi -p` reads no prompt from stdin (`-p ""`
  exits 1, "Prompt cannot be empty"). `Invocation` gains `recorded_argv`, so
  the receipt's `argv` shows `<prompt.md>` instead of the prompt. The
  prompt is visible in the process list while the dispatch runs.
- **Role permissions through an agent file**, `--agent-file
  <run dir>/kimi-agent.md`, whose `tools:` Kimi Code enforces before each
  call; the body is `${base_prompt}`. `-p` runs under the `auto` policy and
  cannot take `--yolo`, `--auto` or `--plan`.
- **No deny rule for a shell command** outside `config.toml`, which is the
  user's. The push and gh guards are environment: `remote.origin.pushurl`
  through `GIT_CONFIG_*` (appended after the user's), and an invalid
  `GH_TOKEN`. Verified live: `git push` and `/usr/bin/git push` exit 128,
  `gh auth status` exits 1. A push to an explicit URL is not blocked.
- **Effort** has no flag; `KIMI_MODEL_THINKING_EFFORT` sets it, and the
  session log showed the value sent. The effort set is `low`, `high`, `max`,
  the levels Kimi Code declares for its K3 models.
- **No isolated `KIMI_CODE_HOME`**: a fresh home has no login, and copying
  the user's OAuth credentials could rotate their refresh token. So the
  user's config runs, hooks and MCP servers included, as `codex` runs with
  the user's `config.toml`; `--skills-dir` with an empty directory replaces
  skills, and the agent file gives no MCP tool. Each dispatch is a session
  in the user's Kimi Code history.
- **Identity:** no stream-json event names a model, so `requested-only`.
  The session log (`wire.jsonl`, found through the `session.resume_hint`
  event) records what Kimi Code requested and the tokens; the parser reads
  them into `usage`, never into the identity check, and tolerates a missing
  log.
- **The matrix renders without a prompt:** `fill()` leaves a placeholder
  that has no value as it is, so a caller that passes no prompt keeps
  working. On the owner's word the showcase site gained a `kimi` section
  (reasance/bottega-kit.sh#1, to merge with the sync of the release that
  ships it); its sync passes `<prompt.md>`, as the receipts record it.

Live run, in `docs/compatibility.md`: K3.1 Pro at effort `high` as planner,
implementer, reviewer and judge on a throwaway repository, done in round 1,
the judge's verdict "Merge: yes".

## 2026-10-24 — Grok Build, Muse Code and Antigravity as harnesses

On the owner's word ("lavora anche agli harness futuri, incluse muse") the
`grok` and `gemini` drivers of `docs/later.md` are built, with Muse Code as
a sixth harness. Gemini ends up driven through the Antigravity CLI, not
Gemini CLI (below). Decisions, from each CLI's own documentation and live
probes on the owner's subscriptions:

- **`grok` follows Claude Code's flags.** Grok Build 1.0.62's
  `streaming-messages-json` is Claude Code's stream-json shape, so the
  driver subclasses the claude one and drops the literal model name
  `unknown`. The prompt is read with `--prompt-file`: headless Grok reads
  no stdin. `Bash(git push *)` uses prefix-and-glob matching and misses a
  bare `git push` (Claude Code's matches it), so the `kimi` push and gh
  guards are set too. Grok Build loads Claude Code's and Cursor's hooks,
  MCP servers, skills, rules and agents unless the ten
  `GROK_{CLAUDE,CURSOR}_*_ENABLED` variables say no; they do. Not narrowed:
  Grok's own plugins and hooks, the plugins it loads from
  `~/.claude/plugins` (their MCP servers start; `--deny MCPTool` refuses
  their tools), and the permission allows of `~/.claude/settings.local.json`:
  `GROK_CONFIG` takes only an allowlist of keys. The model is reported and
  checked; `modelUsage` adds `grok-4.7-build`, recorded as observed.
- **`muse` uses Muse Code's own switches**: `--disable-write`,
  `--disable-shell`, `--approval-mode never` with the approval judge off,
  the sandbox left on. `--contributor-mode off` is forced on every
  dispatch, although the owner's setting has it on: a dispatch's code must
  not go to training without a decision made for it. No deny rule for a
  shell command exists, so the push and gh guards are set. Muse Code's user
  skills still load (`muse exec` has no switch for one run). `run_usage`
  names the models that served the run; they are the identity.
- **Gemini CLI is dropped before shipping.** Gemini CLI 0.65.0 refused the
  owner's Google sign-in ("This client is no longer supported for Gemini
  Code Assist for individuals … migrate to the Antigravity suite"); two
  probe dispatches failed at authentication, before any model call. It
  would still run with `GEMINI_API_KEY` or Vertex, which nothing here can
  verify. Its offline driver (admin-tier `--admin-policy` files; a system
  settings file is refused unless its directory is root-owned) is removed.
- **`agy`, the Antigravity CLI, in its place** (owner's choice, "Fai
  l'harness Antigravity"). `agy` reads permission rules only from
  `~/.gemini/antigravity-cli/settings.json`, so each dispatch gets a fresh
  HOME with the role's rules, deleted afterwards (a copy stays in the run
  directory). The first attempt counted on the keychain, as
  delegation-kit's runner does; on this machine `agy` keeps the sign-in in
  `antigravity-oauth-token` under HOME, and the empty HOME started a
  browser sign-in, which timed out unused. On the owner's choice ("Link al
  file di accesso") the fresh HOME holds a symbolic link to that file;
  bottega-kit never opens or copies it. If `agy` ever renews the token by
  replacing the file rather than writing through the link, the renewal
  lands in the deleted HOME and the next run uses the old token. With HOME
  moved, `BOTTEGA_DATA_HOME` points at the kit's task data, so `bottega
  signal` works.
- **What the two `agy` probes changed** (planner and implementer, on the
  owner's word for about six dispatches). The planner's write and shell
  calls were refused by the settings' deny rules, and the implementer's
  `git push` (bare too) and `gh` by `command(...)` rules. But (1) the
  stream is `{"event": kind, kind: {...}}`, not the flat shape the
  headless docs describe, so the parser was rewritten on the real output;
  (2) with only the task directory under `--add-dir`, the agent treated it
  as its working directory, so the worktree is passed first; (3) the
  terminal sandbox refuses to read `~/.gitconfig`, so `GIT_CONFIG_GLOBAL`
  made every git command fail; it is gone, and git runs without a global
  config (no role commits).
- **Prices checked on 2026-10-24** (owner: "verifica online tutti i
  costi aggiornati"), at the official pages where they could be read:
  MiniMax-M3.1-Flash 0.15 / 0.015 cache read / 0.60 (platform.minimax.io),
  GLM-5.3-Flash 0.15 / 0.03 cached / 0.50 (docs.z.ai), both as the docs had
  them; kimi-k3 3 / 0.30 cached / 15, with cache writes at 3 (5 min) and
  6 (1 h), read from the source of platform.kimi.ai's price page, which
  also lists `kimi-k3.1-pro` at 2 / 10 / 0.20. On 2026-10-25, with the
  owner's OK, one `GET https://api.moonshot.ai/v1/models` on the owner's
  key listed `kimi-k2.6`, `kimi-k2.7-code`, `kimi-k2.7-code-highspeed`,
  `kimi-k3` and `kimi-k3.1-pro`; no dispatch has tried K3.1 Pro on the
  Anthropic endpoint since its 404, so the examples keep `kimi-k3`;
  `grok-4.7` 2 / 0.50 / 6 below a 200 k prompt (docs.x.ai); Gemini 3.8 Flash 0.75 / 0.075 / 3.75 until
  2026-12-31, double from 2027-01-01 (ai.google.dev). `muse-wonder-1.0` at
  4 / 0.20 / 20 comes only from third-party copies of Meta's announcement.
  Grok Build's own `cost_usd` was 0.34 times the `grok-4.7` list price on
  every dispatch of the run; why is not documented.

## 2026-10-25 — 0.2.0: a live run on the new harnesses

The owner gave the word for 0.2.0 ("ok per entrambe", for the release and
the Kimi model-list check) and chose one live run of four dispatches on
the new harnesses ("Un run, 4 dispatch") over the runs of 2026-10-24 alone
or the Claude starter. One task, "add a `--times N` option", on a
throwaway greeter repository pushed to a private
`matteoscurati/bottega-probe-020`, through an install of `main` at the
merge of the harness pull request (`05d4015`) in the session scratchpad
(`BOTTEGA_DATA_HOME` and `BOTTEGA_BIN_HOME` there; the configuration was a
temporary `~/.config/bottega-kit/config.json` written by `bottega init`,
removed afterwards, since moving `XDG_CONFIG_HOME` would have moved the
harnesses' own sign-ins too). Planner and judge `grok` (`grok-4.7`, Grok
Build 1.0.62), implementer `muse` (`muse-wonder-1.0`, Muse Code 1.4.13),
reviewer `gemini` on `agy` (`gemini-3.8-flash-high`, Antigravity CLI
1.4.7), all at effort `high`, `timeout` 1800, `rounds` 1 so that a
`needs-work` could not dispatch beyond the four authorized.

Four dispatches, done in round 1 of 1; Grok Build reported 0.086 USD,
about 0.80 USD at list prices for the whole run. `bottega pr` opened the
pull request and a second `pr` printed `pr exists:`. No warning, nothing
in `HARNESS_MATRIX` changes. The pull request also holds two
`__pycache__/*.pyc` files, from the `python3 -m unittest` run in the
worktree to check it before `pr`; the greeter has no `.gitignore` and
`pr` commits with `git add -A`, as documented. Recorded in the snapshot as
observed, not changed.

`docs/compatibility.md`: the "Verified snapshot" is this run; the 0.1.1
snapshot moves, unchanged, to a section of its own above the 0.1.0 one,
marked as not re-run. The dated live sections of 2026-10-23 and
2026-10-24 stay under the snapshot. `docs/later.md`'s "0.2.0 candidates"
become "Next-version candidates", none of them done.

## 2026-10-25 — 0.2.0 published by hand

The tag push ran `publish-npm.yml` (run 40174444686): the guards passed
(tag against `package.json`, the version check with `--tag`, the npm
wrapper test, 7 of 7), and the publish failed with `E403 OIDC permission
denied`, as for 0.1.1 (npm/cli#9969). The owner published by hand with
two-factor, from the main checkout rather than a worktree of the tag: it
was at the tag's commit (`4061dea`) with nothing tracked changed, and
`npm pack --dry-run` there gave the shasum the CI run built,
`1d6dc7a2042eb3e7d0970773cabd91e0e704d690`; `files` in `package.json`
keeps ignored and untracked files out of the tarball. npm serves 0.2.0 as
`latest` since 08:06 UTC, without provenance, with the same shasum.

npm warns at every publish, CI and by hand alike, that the `bin` entry
"was invalid and removed" and suggests `npm pkg fix`; the registry keeps
`bin: {"bottega-kit": "bin/npm-installer.mjs"}` for 0.1.1 and 0.2.0 alike,
and `npx bottega-kit@0.2.0 --help`, from an empty npm cache, prints the
usage. Why npm warns is not established; `package.json` is unchanged.

## 2026-10-25 — 0.3.0

- **Model data from controller-models.** The effort table and the starter
  profiles in `config.py` sit between `controller-models` markers and are
  written by that tool from its registry; edit the registry, not the block.
- **The live run used isolated XDG directories**, and `bottega pr` then
  found `gh` logged out: `gh` follows `XDG_CONFIG_HOME` too. `GH_CONFIG_DIR`
  fixed it for the run. Not a bottega bug; recorded in
  `docs/compatibility.md` so the next live run isolates differently.
- **Published by hand.** The tag `bottega-kit--v0.3.0` (merge `21f434d`)
  ran `publish-npm.yml`: the guards passed and the publish failed with
  `E403 OIDC permission denied`, as for 0.1.1 and 0.2.0 (npm/cli#9969). The
  owner published by hand with two-factor from the main checkout at the
  tag, nothing tracked changed; `npm pack --dry-run` there gave shasum
  `b875a2c81a0b9be51093271f2e25afabc8d29db3`, and npm serves 0.3.0 as
  `latest` with the same shasum, without provenance.


## 2026-10-27 — 0.3.1 Terra verification

- The optional Terra Codex profile completed the greeter task through `new`, `plan`, `approve`, one `run` round and `pr` with the shipped prompts. Three owner-authorized dispatches at `low`, no judge, retry or fallback; the lead independently verified the three-file scope, five tests and CLI exit/output checks.
- Receipts report requested-only identity and no dollar cost. The starter profiles and harness implementation did not change.
