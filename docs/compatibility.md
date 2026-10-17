# Compatibility and release verification

This page records how each harness is driven and what was observed to work, on
which machine, on which day. A successful run proves that the exact harness,
model, effort and role tested ran as described; it says nothing about which
model to use, which stays your choice in the configuration.

Each release replaces the snapshot below with what was actually observed
before tagging. Numbers are never carried forward from an earlier release.

## Verified snapshot

**0.1.0, verified live on 2026-10-17** on macOS (Darwin 25.5.0), python3 3.15.0,
git 2.50.1, Claude Code 2.1.302, Codex CLI 0.163.0, gh 2.102.0. Two tasks on a
throwaway repository (a 20-line Python CLI with a unittest suite and a local
bare `origin`), run through the installed kit, one dispatch set at a time:

| task | roles | dispatches | result |
|---|---|---|---|
| add a `--shout` flag | planner claude · implementer **codex** · reviewer claude · judge claude | 4 | done in round 1 of 2 |
| add a `--repeat` option | planner claude · implementer **claude** · reviewer **codex** · judge claude | 9 (one `questions` round, one `cap-reached` stop, one `resume --rounds 1`) | done in round 3 of 3 |

Profiles: `claude-sonnet-5-5` at effort `medium` for the Claude roles (with
`timeout` and `max_budget_usd`), `gpt-5.6-terra` at effort `medium` for the
Codex roles. The models were chosen to keep the probe cheap; they say nothing
about which model to use.

Per dispatch (duration, cost as Claude Code reported it; Codex usage is billed
to the ChatGPT plan and reports no cost):

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

Thirteen dispatches, 0.41 USD on the Claude side. Both implementations were
correct, tested and documented; both reviewers ran the unit tests and every
manual QA scenario; the second planner asked a real question (the request
mentioned a flag that was not on the branch) and the answer, typed into
`task.md`, produced the plan on the next `plan`.

What the live runs settled:

- `claude --tools Read,Glob,Grep` and the longer lists are accepted as one
  comma-separated argument (the `init` event lists exactly those tools).
- `--permission-mode dontAsk` with `--allowedTools Bash` lets the reviewer run
  `git diff`, the test suite, the CLI under test and `bottega signal`, with no
  permission denial; the judge's four `Bash(… *)` allow rules let it run
  `git diff HEAD` and the signal command. So the `Bash(x *)` spelling works
  for allow rules. The deny rules (`Bash(git push *)`, `Bash(gh *)`,
  `Bash(git commit *)`) use the same spelling and were never triggered.
- `--permission-mode acceptEdits` with `--add-dir <task dir>` let the Claude
  implementer change the worktree and tick the boxes in `task.md`. It chose
  Bash (`python3 -`, `sed -i`) over the Edit and Write tools, so those two
  tools were not exercised.
- `stream-json` on 2.1.302: `system/init` carries `model`, `tools`,
  `permissionMode`, `additional_directories`; `assistant` events carry
  `message.model`; the `result` event carries `result`, `is_error`, `subtype`,
  `usage`, `modelUsage`, `total_cost_usd`, `duration_ms`, `num_turns`,
  `permission_denials`, `stop_reason`. Other event types seen:
  `user` (tool results) and `rate_limit_event`. `modelUsage` listed only the
  content model in every run.
- Claude Code reports the model exactly as requested (`claude-sonnet-5-5`), so
  no alias was needed.
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
- An `item.completed` of type `error` with the message "clamping SessionEnd
  hook timeout to 3s …" comes from the Codex plugin's hooks and is harmless;
  stderr may also carry an MCP OAuth refresh error for a user-configured
  server. Neither affects the run.
- **Found and fixed:** the Codex reviewer's `bottega signal <task-id> …`
  exited 64 ("no task matches") twice, which the loop correctly read as *no
  signal → needs-work* until the cap. Cause: Codex runs agent commands under
  `shell_environment_policy.inherit = "core"` (the user's `config.toml`), so
  `BOTTEGA_DATA_HOME` and `XDG_*` never reach the agent's shell and the task
  cannot be found by id. Fix: `bottega signal` accepts the absolute task
  directory, and every prompt's signal command names it. The resumed round
  signalled `ready` with exit 0.

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
run), not by a sandbox.

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
caches. The rails stop the task if tracked code changes.

### gh, for bottega pr

```
gh pr view <branch> --repo <host/owner/repo> --json url,state
gh pr create --repo <host/owner/repo> --base <base> --head <branch> --title <title> --body-file <file>
```

`<host/owner/repo>` comes from `origin`'s configured URL. `pr` runs
`git push -u origin <branch>` itself; `gh` never pushes.

## Open unknowns

Still unverified after the live runs above:

- Codex as planner (`--sandbox read-only`, no `--add-dir`, the final message
  written by `-o` into the task directory) and as judge: both tasks ran those
  roles on Claude Code;
- the Claude `Edit` and `Write` tools under `acceptEdits` with
  `--permission-prompts none` (the implementer chose Bash instead);
- the deny rules `Bash(git push *)`, `Bash(gh *)`, `Bash(git commit *)` (never
  triggered);
- `bottega pr` against a real GitHub repository (verified with a fake `gh`
  only), including `--repo` on a GitHub Enterprise host and what
  `gh pr view <branch> --json url,state` returns for a merged pull request;
- a reviewer whose test suite runs for minutes (the probe suites ran in
  seconds);
- the model names Claude Code reports for `claude-opus-5-5` and
  `claude-fable-5-1`, and whether a proxied profile (Z.AI) reports the proxied
  name or the alias.

## Reproduce the offline gates

```sh
ruff check bin tests && ruff format --check bin tests
bash tests/version-consistency.sh
node --test tests/npm-installer.test.mjs
./run-tests.sh
```

The release gate (`CLAUDE.md`, "Before tagging") is one live end-to-end run, `new`, `plan`,
`approve`, `run`, `pr`, on a throwaway repository, run only when the owner
authorizes it. Its results replace the snapshot above.
