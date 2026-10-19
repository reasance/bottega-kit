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
