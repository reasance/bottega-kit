# Compatibility and release verification

This page records how each harness is driven and what was observed to work, on
which machine, on which day. A successful run proves that the exact harness,
model, effort and role tested ran as described; it says nothing about which
model to use, which stays your choice in the configuration.

Each release replaces the snapshot below with what was actually observed
before tagging. Numbers are never carried forward from an earlier release.

## Verified snapshot

**0.1.1, verified live on 2026-10-23** on macOS 26.5.1 (Darwin 25.5.0),
python3 3.15.0, git 2.50.1, gh 2.103.0 and Claude Code 2.1.309, through an
install of the release commit in a scratch directory. One task on a
throwaway repository: a 21-line Python CLI with a two-test unittest suite,
on a private GitHub repository created for the run. The configuration was
the starter `bottega init` writes, with `timeout` 1800 and
`max_budget_usd` 3 added to each profile; the shipped prompts, no override.

| task | roles | dispatches | result |
|---|---|---|---|
| add a `--times N` option, N at least 1 | `fable` (`claude-fable-5-1`, max) as planner and judge, `opus-builder` and `opus-reviewer` (`claude-opus-5-5`, high) | 4 | done in round 1 of 3; then `bottega pr` |

Per dispatch (duration, and cost as Claude Code reported it):

| seq | role | harness | reported model | duration | cost USD | signal |
|---|---|---|---|---|---|---|
| 1 | planner | claude | claude-fable-5-1 | 160 s | 0.908 | — (plan) |
| 2 | implementer | claude | claude-opus-5-5 | 34 s | 0.243 | — |
| 3 | reviewer | claude | claude-opus-5-5 | 30 s | 0.235 | ready |
| 4 | judge | claude | claude-fable-5-1 | 49 s | 0.686 | ready |

Four dispatches, 2.07 USD, 4 min 33 s of dispatch time.

What the run showed:

- Every receipt says `model_identity_source: provider-reported`, and each
  reported name is the requested one; the starter needs no alias.
- The planner asked nothing: it listed eight decisions in the Overview "for
  the reviewer to audit", and seven to-do items. The implementer changed
  only the three files the plan named; the unit suite went from 2 to 8
  tests. The reviewer ran the suite and all nine manual QA commands, and
  one more of its own; the judge read the diff and signalled `ready`.
- No permission denial in any `result` event, and no warning in any
  `run.json`: no commit by the implementer, no new untracked file left by a
  read-only role.
- `bottega pr` committed the three files with the task title, pushed the
  branch over ssh and opened the pull request; a second `pr` printed
  `pr exists: <url>`.
- Nothing failed.

Not run for 0.1.1: Codex (0.164.0 is installed; the last Codex run was
0.163.0, in the 0.1.0 snapshot below), a proxied profile, and the
`questions`, `needs-work`, `blocked` and `resume` paths, which the offline
suites cover.

## The harness matrix

Every flag lives in `HARNESS_MATRIX`, in `bin/lib/bottega/harness/__init__.py`.
The `harness-matrix` suite pins each cell.

### Common to both

- The working directory is the task's worktree; the prompt goes on stdin.
- The environment is yours plus the profile's `env` (see
  [configuration.md](configuration.md) for proxied Claude profiles).
- A profile `timeout` kills the harness's process group; the task stops with
  `timeout`. After every run the process group is killed, so nothing the
  agent started outlives the dispatch.

### claude

Base command:

```
claude -p --model <model> --effort <effort> --output-format stream-json --verbose
  --permission-prompts none --setting-sources "" --strict-mcp-config
  --mcp-config '{"mcpServers":{}}' --settings '{"disableAllHooks":true}'
  --disable-slash-commands --no-session-persistence --add-dir <task dir>
  [--max-budget-usd <n>]
```

| role | added flags |
|---|---|
| planner | `--permission-mode dontAsk --tools Read,Glob,Grep` |
| implementer | `--permission-mode acceptEdits --tools Read,Edit,Write,Glob,Grep,Bash --allowedTools Bash --disallowedTools "Bash(git push *)" "Bash(gh *)"` |
| reviewer | `--permission-mode dontAsk --tools Read,Glob,Grep,Bash --allowedTools Bash --disallowedTools "Bash(git push *)" "Bash(gh *)" "Bash(git commit *)"` |
| judge | `--permission-mode dontAsk --tools Read,Glob,Grep,Bash --allowedTools "Bash(git diff *)" "Bash(git log *)" "Bash(git show *)" "Bash(<bottega> signal *)"` |

`--fallback-model` and `--bare` are never used. Read from the `stream-json`
events: the final message from the `result` event's `.result`; the model
from the `system/init` event's `.model` and each assistant event's
`.message.model`; usage, cost, duration and turns from the `result` event;
`is_error: true` is a failed dispatch.

The Claude reviewer has Bash so it can run tests. That it does not change
code is enforced by the rails (HEAD and the tracked diff checked around the
run), not by a sandbox. The deny rules were verified on 2026-10-19 (the 0.1.0 snapshot, below):
they deny the bare command, the command with arguments, and a command joined
with `&&` that contains it.

### codex

Base command:

```
codex exec -m <model> -c model_reasoning_effort="<effort>" -c approval_policy="never"
  -c mcp_servers={} -c features.multi_agent=false --json -o <run dir>/output.md
  --ephemeral --color never -C <worktree> -
```

| role | added flags |
|---|---|
| planner | `--sandbox read-only` |
| implementer | `--sandbox workspace-write --add-dir <task dir>` |
| reviewer | `--sandbox workspace-write --add-dir <task dir>` |
| judge | `--sandbox workspace-write --add-dir <task dir>` |

`--ignore-user-config` is never used, because your provider and login may
live in `~/.codex/config.toml`. The final message is the `-o` file. The model
comes from the top-level `model` or `response.model` of any event, or the
model of a session or turn event; usage from the last `turn.completed`.

The Codex reviewer and judge can write in the worktree, because tests write
caches. The rails stop the task if tracked code changes. Codex has no deny
rules: a commit fails because Codex keeps the git directory read-only, a push
fails only while the sandbox blocks the network, and `gh` runs (see the 0.1.0 snapshot, below).

### gh, for bottega pr

```
gh pr view <branch> --repo <host/owner/repo> --json url,state
gh pr create --repo <host/owner/repo> --base <base> --head <branch> --title <title> --body-file <file>
```

`<host/owner/repo>` comes from `origin`'s configured URL. `pr` runs
`git push -u origin <branch>` itself; `gh` never pushes.

## Open unknowns

Still unverified after the live runs, this release's and 0.1.0's:

- `bottega pr` with `--repo` on a GitHub Enterprise host (github.com is
  verified);
- Codex CLI 0.164.0, in any role;
- the credential stripping of a proxied profile against a set
  `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`: on the 20th nothing was
  set, so there was nothing to remove. The offline suite covers it with a
  fake harness; the alias path stays offline too, since Z.AI reported the
  requested name.

## Reproduce the offline gates

```sh
ruff check bin tests && ruff format --check bin tests
git ls-files '*.sh' 'bin/*' 'tests/fakes/*' | while read -r f; do
  head -1 "$f" | grep -q '^#!.*\(bash\|sh\)' && printf '%s\n' "$f"
done | xargs shellcheck -S warning
bash tests/version-consistency.sh
node --test tests/npm-installer.test.mjs
./run-tests.sh
```

The release gate (`CLAUDE.md`, "Before tagging") is one live end-to-end run,
`new`, `plan`, `approve`, `run`, `pr`, on a throwaway repository, run only
when the owner authorizes it. Its results replace the snapshot above.

## The 0.1.0 snapshot

Kept as it was recorded for 0.1.0 and not re-run since: these numbers and
findings are about Claude Code 2.1.302 to 2.1.304 and Codex CLI 0.163.0.

**0.1.0, verified live on 2026-10-17, 2026-10-19 and 2026-10-20** on macOS
(Darwin 25.5.0), python3 3.15.0, git 2.50.1, Codex CLI 0.163.0, gh 2.102.0,
and Claude Code 2.1.302 on the 17th, 2.1.303 on the 19th, 2.1.304 on the
20th. Eight tasks on two throwaway repositories (a 20-line Python CLI with a
unittest suite; from the evening of the 19th, one whose suite sleeps 150 s),
run through the installed kit, one dispatch set at a time:

| day | task | roles | dispatches | result |
|---|---|---|---|---|
| 17 | add a `--shout` flag | planner claude · implementer **codex** · reviewer claude · judge claude | 4 | done in round 1 of 2 |
| 17 | add a `--repeat` option | planner claude · implementer **claude** · reviewer **codex** · judge claude | 9 (one `questions` round, one `cap-reached` stop, one `resume --rounds 1`) | done in round 3 of 3 |
| 19 | add a `--shout` flag | **codex** in every role | 4 | done in round 1 of 2; then `bottega pr` on a private GitHub repository |
| 19 | add a `--repeat` option | the starter configuration: `fable` as planner and judge, `opus-builder` and `opus-reviewer` | 4 | done in round 1 of 2 |
| 19, evening | add a `--bye` flag: two new files, a full suite that takes 150 s, and a permission probe in the prompts | plan written by hand and served by the fake harness · implementer **claude** · reviewer **claude** | 2 | done in round 1 of 1 |
| 19, evening | add a `--whisper` flag, same shape | plan written by hand · implementer **codex** · reviewer **codex** | 3 (one `blocked` stop, one `resume`) | done in round 1 of 2: the first reviewer gave up on the slow suite (below); resumed after the prompt change, the second waited for it |
| 19, late evening | add a `--shout` flag, same shape, with an override that asks for the `Write` tool | plan written by hand · implementer **claude** · the reviewer dispatch refused by the probe itself | 1 | the implementer finished; then stopped `dispatch-failed`, on purpose (below) |
| 20 | add a `--polite` flag, same shape | plan written by hand · implementer **claude** · reviewer **claude on Z.AI**: the README's proxied profile, `glm-5.3-flash`, key from `secrets.env` | 2 | done in round 1 of 1 |

Profiles on the 17th: `claude-sonnet-5-5` at effort `medium` for the Claude
roles (with `timeout` and `max_budget_usd`), `gpt-5.6-terra` at effort
`medium` for the Codex roles, chosen to keep the probe cheap. On the 19th:
`gpt-5.6-terra` at `medium` for Codex, and the starter configuration as
`bottega init` writes it (`claude-fable-5-1` at `max`, `claude-opus-5-5` at
`high`) with `timeout` and `max_budget_usd` added. In the evening of the
19th: `claude-sonnet-5-5` at `medium` and `gpt-5.6-terra` at `medium`, on a
repository whose full suite sleeps 150 s in an end-to-end test, with prompt
overrides that asked each role to try the forbidden commands one by one and
report what happened; the plans were written by hand and fed through the
kit's fake harness, so no planner model ran. Late in the evening, two more
dispatches: the whisper task was resumed with the changed reviewer prompt,
and a Sonnet implementer ran once more under an override asking for `Write`
for new files. For those two a wrapper on PATH passed exactly one dispatch
per harness to the real CLI and exited 75 for any other, so the loop stopped
as `dispatch-failed` instead of dispatching a reviewer nobody had authorized.
On the 20th: `claude-sonnet-5-5` at `medium` as implementer, and as reviewer
the README's proxied profile, `glm-5.3-flash` at `max` on
`https://api.z.ai/api/anthropic` with `aliases: ["opus"]`, `${ZAI_API_KEY}`
read from the key file; the shipped prompts, no override; the same kind of
wrapper passed one implementer and one proxied reviewer dispatch and refused
anything else. None of this says which model to use.

Per dispatch (duration, cost as Claude Code reported it; Codex usage is billed
to the ChatGPT plan and reports no cost). 2026-10-17:

| seq | role | harness | reported model | duration | cost USD | signal |
|---|---|---|---|---|---|---|
| 1 | planner | claude | claude-sonnet-5-5 | 15 s | 0.052 | — |
| 2 | implementer | codex | not reported | 27 s | — | — |
| 3 | reviewer | claude | claude-sonnet-5-5 | 9 s | 0.055 | ready |
| 4 | judge | claude | claude-sonnet-5-5 | 7 s | 0.033 | ready |
| 1 | planner | claude | claude-sonnet-5-5 | 16 s | 0.044 | — (questions) |
| 2 | planner | claude | claude-sonnet-5-5 | 17 s | 0.053 | — (plan) |
| 3 | implementer | claude | claude-sonnet-5-5 | 18 s | 0.072 | — |
| 4 | reviewer | codex | not reported | 54 s | — | no signal → needs-work (see below) |
| 5 | implementer | claude | claude-sonnet-5-5 | 6 s | 0.029 | — |
| 6 | reviewer | codex | not reported | 70 s | — | no signal → needs-work, cap reached |
| 7 | implementer | claude | claude-sonnet-5-5 | 6 s | 0.030 | — |
| 8 | reviewer | codex | not reported | 37 s | — | ready |
| 9 | judge | claude | claude-sonnet-5-5 | 9 s | 0.039 | ready |

2026-10-19:

| seq | role | harness | reported model | duration | cost USD | signal |
|---|---|---|---|---|---|---|
| 1 | planner | codex | not reported | 57 s | — | — |
| 2 | implementer | codex | not reported | 47 s | — | — |
| 3 | reviewer | codex | not reported | 42 s | — | ready |
| 4 | judge | codex | not reported | 38 s | — | ready |
| 1 | planner | claude | claude-fable-5-1 | 152 s | 0.895 | — |
| 2 | implementer | claude | claude-opus-5-5 | 43 s | 0.274 | — |
| 3 | reviewer | claude | claude-opus-5-5 | 37 s | 0.225 | ready |
| 4 | judge | claude | claude-fable-5-1 | 50 s | 0.764 | ready |
| 2 | implementer | claude | claude-sonnet-5-5 | 187 s | 0.068 | — |
| 3 | reviewer | claude | claude-sonnet-5-5 | 193 s | 0.082 | ready |
| 2 | implementer | codex | not reported | 239 s | — | — |
| 3 | reviewer | codex | not reported | 129 s | — | blocked |
| 4 | reviewer | codex | not reported | 187 s | — | ready (resumed, new wording) |
| 2 | implementer | claude | claude-sonnet-5-5 | 180 s | 0.081 | — |

2026-10-20:

| seq | role | harness | reported model | duration | cost USD | signal |
|---|---|---|---|---|---|---|
| 2 | implementer | claude | claude-sonnet-5-5 | 179 s | 0.059 | — |
| 3 | reviewer | claude, on Z.AI | glm-5.3-flash | 214 s | 0.209 as Claude Code priced it; about 0.014 at Z.AI's list price (below) | ready |

Twenty-nine dispatches: 0.41 USD on the Claude side on the 17th, 2.39 USD
on the 19th, 0.06 USD on the 20th plus the one dispatch billed by Z.AI.
Every implementation was correct, tested and documented; every
reviewer ran the unit tests and every manual QA scenario; the second planner
on the 17th asked a real question (the request mentioned a flag that was not
on the branch) and the answer, typed into `task.md`, produced the plan on the
next `plan`. On the 19th the Fable planner made its decisions without asking
and listed them in the Overview "for review before approval".

What the live runs settled:

- `claude --tools Read,Glob,Grep` and the longer lists are accepted as one
  comma-separated argument (the `init` event lists exactly those tools).
- `--permission-mode dontAsk` with `--allowedTools Bash` lets the reviewer run
  `git diff`, the test suite, the CLI under test and `bottega signal`, with no
  permission denial; the judge's four `Bash(… *)` allow rules let it run
  `git diff HEAD` and the signal command. So the `Bash(x *)` spelling works
  for allow rules.
- **The deny rules work, in the same spelling.** In the evening of the 19th
  a Sonnet implementer was asked to run `git push origin HEAD`, `git push`,
  `gh pr list`, `gh --version` and `echo probe && git push origin HEAD`, and
  a Sonnet reviewer those plus `git commit --allow-empty -m probe` and
  `git commit`. All eleven were denied before running ("Permission to use
  Bash with command git push has been denied"), each listed under
  `permission_denials` in the `result` event, and both agents carried on and
  finished their role. So `Bash(git push *)` covers the bare command, the
  command with arguments, and a compound command that contains it.
- The allow list is enforced as deny-by-default. On the 19th the Fable judge
  first ran `git -C <worktree> status … && git -C … log … && git -C … diff …`
  and then `git -C <worktree> diff HEAD`; both were denied (the `result`
  event lists them under `permission_denials`), it went on with plain
  `git log` and `git diff` and signalled `ready`. `-C`, `git status` and
  commands joined with `&&` fall outside `Bash(git diff *)`; the judge
  prompt now says so.
- `--permission-mode acceptEdits` with `--add-dir <task dir>` lets the Claude
  implementer change the worktree and tick the boxes in `task.md`. On the
  17th it chose Bash (`python3 -`, `sed -i`); on the 19th it used `Edit`,
  which is therefore verified under `--permission-prompts none`. In the
  evening of the 19th a plan that creates two new files was implemented by
  Sonnet with Bash heredocs, with `Write` listed in the `init` event's tools
  and unused. Later that evening, under an override that asked for `Write`
  for new files, Sonnet created both new files with `Write` and edited the
  rest with `Edit`, with no permission denial, and ticked the boxes with a
  Bash `sed -i`. **`Write` is verified** under `acceptEdits` with
  `--permission-prompts none`, like `Edit`.
- **A suite that takes minutes, on Claude Code.** The Bash tool's default
  timeout is 2 minutes (`BASH_DEFAULT_TIMEOUT_MS`), 10 at most
  (`BASH_MAX_TIMEOUT_MS`); the kit sets neither. The Sonnet reviewer gave the
  150 s suite a 600 000 ms timeout on its own, as the prompt asks, and saw it
  pass; the Sonnet implementer gave its test command 400 000 ms unprompted.
  The implementer prompt now asks for the timeout too.
- **A suite that takes minutes, on Codex: found, prompt changed, verified.**
  Codex runs commands as resumable sessions (`features.unified_exec`,
  on for everyone): the shell tool hands control back after a short yield
  while the command keeps running, and the model is expected to wait on it.
  The Terra implementer waited and saw the 150 s suite pass (`Ran 6 tests in
  150.028s`, exit 0). The Terra reviewer did not: it took the early return
  for the sandbox killing the suite, could not check (`ps` and `pgrep` are
  denied in the sandbox), marked T6 FAILED and signalled `blocked`; the
  suite's `item.started` never got its `item.completed`. The reviewer and
  implementer prompts now say that a shell tool handing control back means
  wait, not failed. The task was then resumed with that wording: the Terra
  reviewer ran `python3 -m unittest -v` once, in the foreground, with no
  `ps` or `pgrep` in between, saw `Ran 6 tests in 150.033s`, exit 0, verified
  every item and signalled `ready` (187 s; five commands in all). The prompt
  change was enough; `HARNESS_MATRIX` is unchanged.
- **What stops a Codex agent from committing or pushing.** Codex has no deny
  rules; the kit relies on `--sandbox workspace-write`, the prompts and the
  rails. In the same probe, `git commit --allow-empty -m probe` and
  `git commit` failed with "Unable to create '…/.git/worktrees/<task>/index.lock':
  Operation not permitted" (Codex keeps the git directory read-only, the
  worktree's included); `gh --version` and `gh pr list` ran (the latter failed
  because the origin was not on GitHub); and `git push origin HEAD` from
  **both** the implementer and the reviewer succeeded, because the probe's
  origin was a bare repository under `/tmp`, which `workspace-write` makes
  writable. A push to a network remote is stopped by the sandbox's network
  block, which `[sandbox_workspace_write] network_access = true` in
  `~/.codex/config.toml` lifts; with that set, only the prompt stands between
  a Codex implementer and `origin`. The rails do not see a push (HEAD does
  not move).
- **A proxied profile (Z.AI), verified.** On the 20th the README's
  `glm-reviewer` shape ran as reviewer: Claude Code 2.1.304 with
  `--model glm-5.3-flash --effort max`, `ANTHROPIC_BASE_URL` on Z.AI's
  Anthropic-compatible endpoint, `ANTHROPIC_AUTH_TOKEN` from `${ZAI_API_KEY}`
  in the key file, a fresh `CLAUDE_CONFIG_DIR` (`apiKeySource: none` in the
  `init` event). It reported `glm-5.3-flash`, the requested name, in the
  session model, every turn and `modelUsage`, so the receipt says
  `provider-reported` and `aliases: ["opus"]` went unused. stderr had one
  line, `[claude-code:unrecognized_model] {"model":"glm-5.3-flash",…}`, and
  nothing else. The receipt's `env` names: set `ANTHROPIC_AUTH_TOKEN`,
  `ANTHROPIC_BASE_URL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `CLAUDE_CONFIG_DIR`;
  removed none, because this machine sets no Anthropic variable (the offline
  suite covers the stripping). The key's value is in no receipt and no log
  (checked with grep). The GLM reviewer read the task document and the
  changed files, ran the targeted tests, then the 150 s suite in the
  foreground with a 600 000 ms timeout, then the manual QA, and signalled
  `ready`: 12 tool calls, 0 denials, 214 s. The temporary configuration
  directory was deleted after the run. **Claude Code does not know the
  endpoint's prices:** it priced the run at its default table, 5 / 25 USD per
  million tokens in and out and 0.5 for cache reads, 0.209 USD for 85 k input
  and 2.6 k output tokens, which is about 0.014 USD at Z.AI's list price. The
  receipt's `cost_usd` is that estimate, and `max_budget_usd` is enforced on
  it: for a proxied profile, set it about fifteen times what you mean, or
  leave it out.
- `stream-json` on 2.1.302, 2.1.303 and 2.1.304: `system/init` carries
  `model`, `tools`, `permissionMode`, `additional_directories`,
  `claude_code_version`; `assistant` events carry `message.model`; the
  `result` event carries `result`, `is_error`, `subtype`, `usage`,
  `modelUsage`, `total_cost_usd`, `duration_ms`, `num_turns`,
  `permission_denials`, `stop_reason`. Other event types seen: `user` (tool
  results), `rate_limit_event` and, from 2.1.304, `system/task_started` and
  `system/task_notification` around a Bash command, `tool_progress`
  heartbeats every 30 s while it runs, `system/thinking_tokens` (1 074 of
  them in the GLM run) and `system/ui_invalidate`; the parser ignores all of
  these. `modelUsage` listed only the content model in every run.
- Claude Code reports the model exactly as requested: `claude-sonnet-5-5` on
  the 17th, `claude-fable-5-1` and `claude-opus-5-5` on the 19th, in the
  session model, every turn and `modelUsage`. The starter configuration needs
  no alias, and `--effort max` is accepted for Fable.
- Codex 0.163.0 `--json` emits `thread.started`, `turn.started`,
  `item.started`, `item.completed` (items of type `agent_message`,
  `command_execution` with `command`, `exit_code`, `aggregated_output`,
  `file_change`, `error`) and `turn.completed` with `usage`
  (`input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`,
  `output_tokens`, `reasoning_output_tokens`). **No event names the model**, so
  a Codex receipt always says `model_identity_source: requested-only`. The
  `-o` file is written. `-c mcp_servers={}` and `-c features.multi_agent=false`
  are accepted. `--sandbox workspace-write --add-dir <task dir>` let the
  Codex implementer edit the worktree and `task.md`.
- Codex in the two roles the 17th had not run: as planner,
  `--sandbox read-only` with no `--add-dir` read the repository, and the
  `-o` file landed in the task directory and merged as the plan; as judge it
  read `git log` and `git diff` and signalled. Its reviewer and judge both
  signalled with the absolute paths the prompt gives, exit 0.
- An `item.completed` of type `error` with the message "clamping SessionEnd
  hook timeout to 3s …" comes from the Codex plugin's hooks and is harmless;
  stderr may also carry an MCP OAuth refresh error for a user-configured
  server. Neither affects the run.
- `bottega pr` against GitHub: on a private repository reached over ssh,
  `git push -u origin <branch>` and `gh pr create --repo github.com/<owner>/<repo>`
  opened the pull request and printed its URL; the commit carried the
  owner's git identity and the body from `pr-body.md`. A second `pr` printed
  `pr exists: <url>` from `gh pr view <branch> --json url,state`
  (`"state":"OPEN"`); after `gh pr merge` the same call returned
  `"state":"MERGED"` and `pr` printed `pr exists:` again. The repository was
  deleted after the probe.
- **Found and fixed (17th):** the Codex reviewer's `bottega signal <task-id> …`
  exited 64 ("no task matches") twice, which the loop correctly read as *no
  signal → needs-work* until the cap. Cause: Codex runs agent commands under
  `shell_environment_policy.inherit = "core"` (the user's `config.toml`), so
  `BOTTEGA_DATA_HOME` and `XDG_*` never reach the agent's shell and the task
  cannot be found by id. Fix: `bottega signal` accepts the absolute task
  directory, and every prompt's signal command names it. The resumed round
  signalled `ready` with exit 0.
- **Found and fixed (19th):** the Fable planner wrote a README snippet as a
  ```` block with a ```sh example inside it. The kit read the inner ``` as
  closing the outer fence, so the `# Hello, Ada!` comment lines in between
  counted as headings and `merge_plan` dropped five lines of the plan (the
  reviewer noticed the cut; the implementer completed the snippet from its
  context). Fence tracking in `taskdoc` and in the loop's section merge now
  follows CommonMark: a fence closes only with the same character and at
  least the same length. One regression test each.
- For whoever repeats the probe: it overrides `XDG_CONFIG_HOME`, and gh keeps
  its login there, so `bottega pr` found gh logged out until `GH_CONFIG_DIR`
  pointed at the real `~/.config/gh`. A normal install overrides nothing.
