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
0.163.0, in the 0.1.0 snapshot below), and the `questions`, `needs-work`,
`blocked` and `resume` paths, which the offline suites cover.

### Proxied profiles, 2026-10-23, after the 0.1.1 tag

Two more tasks on a local throwaway copy of the same greeter repository,
through an install of `main` in a scratch directory, Claude Code 2.1.309, the
shipped prompts. Each ran one proxied `claude` profile, at effort `high`, as
planner, implementer and reviewer, no judge, cap 2; the profiles are the ones
in the README. Keys came from `secrets.env`.

| seq | role | endpoint | reported model | duration | cost USD as Claude Code priced it | signal |
|---|---|---|---|---|---|---|
| 1 | planner | MiniMax | MiniMax-M3.1-Flash | 34 s | 0.132 | — (plan) |
| 2 | implementer | MiniMax | MiniMax-M3.1-Flash | 26 s | 0.253 | — |
| 3 | reviewer | MiniMax | MiniMax-M3.1-Flash | 46 s | 0.209 | ready |
| 1 | planner | Moonshot | kimi-k3 | 51 s | 0.088 | — (plan) |
| 2 | implementer | Moonshot | kimi-k3 | 104 s | 0.153 | — |
| 3 | reviewer | Moonshot | kimi-k3 | 66 s | 0.102 | ready |

- MiniMax, "add a `--times N` option": done in round 1, 11 tests passing.
  Claude Code priced the three dispatches at 0.59 USD; their tokens (45,273
  input, 224,633 cache reads, 10,231 output) cost 0.016 USD at MiniMax's
  pay-as-you-go list price (0.15 input, 0.015 cache read, 0.60 output per
  million), about 36 times less.
- Kimi, "add a `--shout` flag": done in round 1, 4 tests passing. Claude
  Code priced it at 0.34 USD; its tokens (1,372 input, 93,440 cache reads,
  4,853 output) cost 0.105 USD at Moonshot's K3 price (3 input, 0.30
  cached input, 15 output per million; read on 2026-10-24 from the source
  of platform.kimi.ai's price page, whose table renders only in the
  browser), about a third. The page also prices cache writes, 3 for a
  5-minute and 6 for a 1-hour entry; the figure counts none.
- Every receipt says `model_identity_source: provider-reported` with the
  requested name and no other model, so no alias was needed and Claude
  Code's own requests stayed on the endpoint. No permission denial, no
  warning; the reviewer signalled with the absolute path both times.
- `kimi-k3.1-pro`, released the same day, answered 404 on Moonshot's
  Anthropic endpoint for this key; `GET https://api.moonshot.ai/v1/models`
  listed `kimi-k2.6`, `kimi-k2.7-code`, `kimi-k2.7-code-highspeed` and
  `kimi-k3`.

### Kimi Code, native, 2026-10-23

Kimi Code 2.3.1, signed in to a Kimi Code plan, `kimi-code/k3.1-pro` at
effort `high` in every role, through an install of the `kimi-harness`
branch in a scratch directory, the shipped prompts, cap 2. One task, "add a
`--times N` option", on a local throwaway greeter repository whose `origin`
pointed nowhere:

| seq | role | duration | requests | tokens in / cache read / out | signal |
|---|---|---|---|---|---|
| 1 | planner | 29 s | 2 | 4,725 / 12,544 / 1,684 | — (plan) |
| 2 | implementer | 69 s | 9 | 12,318 / 112,640 / 3,387 | — |
| 3 | reviewer | 73 s | 8 | 17,550 / 106,752 / 3,252 | ready |
| 4 | judge | 26 s | 4 | 8,361 / 42,496 / 913 | ready |

- Done in round 1; the judge's verdict was "Merge: yes". Every receipt says
  `requested-only`, and the session logs show `k3.1-pro` requested at
  effort `high`. No warning, no new untracked file, the rails unchanged for
  the read-only roles.
- Before the run, a probe at effort `low` with the planner's agent file
  listed Glob, Grep, Read and `select_tools` as the agent's tools, and it
  could neither write a file nor run a shell command.
- An implementer dispatch built by the harness and asked to try them:
  `git config --get remote.origin.pushurl` printed
  `bottega-push-disabled://`; `git push origin HEAD` and
  `/usr/bin/git push origin HEAD` exited 128 ("remote helper
  'bottega-push-disabled' aborted session"); `gh auth status` exited 1
  ("The token in GH_TOKEN is invalid").
- `kimi -p ""` with the prompt on stdin exits 1, "Prompt cannot be empty":
  hence the prompt as an argument.

### Grok Build, native, 2026-10-24

Grok Build 1.0.62, signed in to grok.com, `grok-4.7` at effort `high` in
every role, from the `more-harnesses` branch checkout, the shipped prompts,
cap 2. The same task, "add a `--times N` option", on a local throwaway
greeter repository whose `origin` was a local bare repository:

| seq | role | duration | turns | cost USD | signal |
|---|---|---|---|---|---|
| 1 | planner | 195 s | 4 | 0.060 | — (plan) |
| 2 | implementer | 88 s | 9 | 0.091 | — |
| 3 | reviewer | 148 s | 7 | 0.082 | ready |
| 4 | judge | 45 s | 5 | 0.039 | ready |

- Done in round 1, 0.27 USD in all as Grok Build reported it; the judge's
  verdict was "Merge: yes". Every dispatch's `cost_usd` is its tokens at
  0.68 input, 0.17 cached input and 2.04 output per million: 0.34 times the
  `grok-4.7` API list price on docs.x.ai on 2026-10-24 (2, 0.50, 6 below a
  200 k prompt), at which the run would have cost 0.80 USD.
  Every receipt reports `grok-4.7`, the requested name; `modelUsage` also
  names `grok-4.7-build`, recorded as observed. The rails were unchanged
  for the read-only roles; the implementer's test run left `__pycache__/`.
- Before the run, two dispatches built by the harness: the planner could
  read but had no write and no shell tool; the implementer ticked a box in
  `task.md` and committed, `git push origin HEAD` and `gh auth status` were
  denied by Grok's rules, and the bare `git push` and `/usr/bin/git push
  origin HEAD` failed on the push guard ("'remote-bottega-push-disabled' is
  not a git command"). The local origin kept its one commit.
- Grok's `init` event lists `search_tool` and `use_tool` besides the
  role's tools: the meta-tools for MCP servers it loads from
  `~/.claude/plugins`. `--deny MCPTool` refuses their calls; that was not
  exercised live.

### Muse Code, native, 2026-10-24

Muse Code 1.4.12, signed in with an active subscription,
`muse-wonder-1.0` at effort `high` in every role, the same branch, prompts,
cap and task:

| seq | role | duration | calls | tokens in / cached / out | signal |
|---|---|---|---|---|---|
| 1 | planner | 26 s | 4 | 112,408 / 83,548 / 3,166 | — (plan) |
| 2 | implementer | 33 s | 12 | 437,248 / 397,308 / 2,948 | — |
| 3 | reviewer | 18 s | 6 | 207,231 / 170,820 / 1,196 | ready |
| 4 | judge | 10 s | 3 | 95,255 / 62,696 / 828 | ready |

- Done in round 1; the judge's verdict was "Merge: yes". Every receipt
  reports `muse-wonder-1.0`, checked against the request. The usage went to
  the Muse Code subscription; at the API price published for
  `muse-wonder-1.0` (4 input, 0.20 cached input, 20 output per million, in
  third-party copies of Meta's announcement, not read at Meta) the run
  would have cost about 0.86 USD. The reviewer's
  and judge's `bottega signal` wrote into the task directory from inside
  Muse Code's sandbox.
- Before the run, two dispatches built by the harness: the planner had no
  write and no shell tool and could read the worktree and `task.md`; the
  implementer ticked a box in `task.md` (outside `--workspace`) and
  committed; `git push origin HEAD`, `git push` and `/usr/bin/git push
  origin HEAD` failed on the push guard and `gh auth status` failed.
- Muse Code loaded 41 user skills in every dispatch.

### Antigravity CLI, native, 2026-10-24

Antigravity CLI (`agy`) 1.4.7, signed in with a Google account,
`gemini-3.8-flash-high` at effort `high` in every role, the same branch,
prompts, cap and task:

| seq | role | duration | tokens in / thinking / out | signal |
|---|---|---|---|---|
| 1 | planner | 79 s | 87,698 / 5,801 / 9,337 | — (plan) |
| 2 | implementer | 144 s | 95,648 / 4,464 / 9,723 | — |
| 3 | reviewer | 98 s | 71,939 / 3,994 / 5,719 | ready |
| 4 | judge | 50 s | 96,316 / 2,286 / 3,249 | ready |

- Done in round 1; the judge's verdict was "Merge: yes". Every receipt
  says `requested-only`. The usage went to the Google account `agy` signs
  in with; at the Gemini API's paid price for Gemini 3.8 Flash on
  ai.google.dev on 2026-10-24 (0.75 input, 0.075 cached input, 3.75 output
  and thinking per million, until 2026-12-31; double from 2027-01-01) the
  run would have cost about 0.50 USD. No new untracked file, the rails unchanged for the
  read-only roles, no dispatch HOME left behind. The planner's `ls -la` was
  refused by `command(*)`; the reviewer ran the tests and both signals
  reached the task directory from inside the sandbox.
- Before the run, two dispatches built by an earlier version of the
  harness: the planner's `write_file` and `echo hi` were refused by the
  deny rules; the implementer edited `task.md` and wrote a file, `git push
  origin HEAD`, a bare `git push` and `gh auth status` were refused by the
  `command(...)` rules. They also showed the three faults fixed before the
  run: the nested stream shape, the task directory taken as the working
  directory, and git failing on an unreadable `~/.gitconfig`.
- With an empty HOME and no link, `agy` asked for a browser sign-in and
  timed out after 60 s: on this machine the sign-in is the
  `antigravity-oauth-token` file, not the keychain.

## The harness matrix

Every flag lives in `HARNESS_MATRIX`, in `bin/lib/bottega/harness/__init__.py`,
with Kimi Code's per-role tools and environment. The `harness-matrix` suite
pins each cell.

### Common to all

- The working directory is the task's worktree; the prompt goes on stdin,
  except for `kimi` and `agy` (the value of `-p`) and `grok` and `muse`
  (`--prompt-file`).
- The environment is yours plus the profile's `env` (see
  [configuration.md](configuration.md) for proxied Claude profiles), and
  for `kimi`, `grok`, `muse` and `agy` the variables below.
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

### kimi

Base command, the same for every role:

```
kimi -p <prompt> --output-format stream-json -m <model>
  --agent-file <run dir>/kimi-agent.md --skills-dir <run dir>/kimi-skills
  --add-dir <task dir>
```

The prompt is the value of `-p`: Kimi Code reads no prompt from stdin. The
receipt's `argv` shows it as `<prompt.md>`; the text is in `prompt.md`. `-p`
runs under Kimi Code's `auto` permission policy, so nothing asks.

| role | `tools:` in the agent file |
|---|---|
| planner | `Read`, `Glob`, `Grep` |
| implementer | `Read`, `Glob`, `Grep`, `Edit`, `Write`, `Bash` |
| reviewer | `Read`, `Glob`, `Grep`, `Bash` |
| judge | `Read`, `Glob`, `Grep`, `Bash` |

The agent file (`name: bottega-<role>`, `subagents: []`, body
`${base_prompt}`) is written into the run directory and kept with the
receipt. Kimi Code enforces its `tools:` list before every call, so a role
has no other tool, `Agent` and the web tools included. `--skills-dir` names
an empty directory, which replaces your skills.

Environment added to yours: `KIMI_MODEL_THINKING_EFFORT=<effort>` (Kimi Code
has no effort flag), `KIMI_CODE_NO_AUTO_UPDATE=1`,
`KIMI_CODE_BUILTIN_PRODUCT_SKILLS=0`, and two guards, because Kimi Code has
no command-line deny rule for a shell command:
`GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` set
`remote.origin.pushurl` to `bottega-push-disabled://`, after any
`GIT_CONFIG_*` you set, so a push to origin fails; and `GH_TOKEN` is a
token GitHub refuses, so `gh` fails. A push to an explicit URL is not
blocked; the rails still stop a read-only role that commits.

No event names the model, so a Kimi receipt says `requested-only`. The final
message is the last `assistant` message with text. From the
`session.resume_hint` event's `session_id`, the parser reads Kimi Code's
session log, `<KIMI_CODE_HOME>/sessions/*/<session id>/agents/main/wire.jsonl`
(`~/.kimi-code` by default), into `usage`: the requests, the model alias and
model name Kimi Code asked for, the effort it sent, the turn endings and the
tokens (`inputOther`, `inputCacheRead`, `inputCacheCreation`, `output`);
`num_turns` and `duration_ms` come from its `turn.ended` events. A missing
log leaves only `session_id`.

Not narrowed: your Kimi Code hooks run, and your MCP servers start, though
the agent file gives the role none of their tools.

### grok

Base command:

```
grok --prompt-file <run dir>/prompt.md --output-format streaming-messages-json
  -m <model> --reasoning-effort <effort> --no-subagents --disable-web-search
  --no-auto-update --deny MCPTool
```

Grok Build reads no prompt from stdin; `--prompt-file` makes the run
headless.

| role | added flags |
|---|---|
| planner | `--permission-mode dontAsk --tools read_file,grep,list_dir` |
| implementer | `--permission-mode acceptEdits --tools read_file,grep,list_dir,search_replace,write,run_terminal_cmd --allow Bash --allow "Edit(<task dir>/**)" --deny "Bash(git push *)" --deny "Bash(gh *)"` |
| reviewer | `--permission-mode dontAsk --tools read_file,grep,list_dir,run_terminal_cmd --allow Bash --deny "Bash(git push *)" --deny "Bash(gh *)" --deny "Bash(git commit *)"` |
| judge | `--permission-mode dontAsk --tools read_file,grep,list_dir,run_terminal_cmd --allow "Bash(git diff *)" "Bash(git log *)" "Bash(git show *)" "Bash(<bottega> signal *)"` |

The flags follow Claude Code's: `--tools` is the role's tool set, a deny
rule beats every allow, and `dontAsk` refuses what no rule allows. Unlike
Claude Code's, `Bash(git push *)` does not match a bare `git push`, so the
push and gh guards below stand behind the deny rules.

Environment added to yours: `GROK_CLAUDE_{AGENTS,HOOKS,MCPS,RULES,SKILLS}_ENABLED=0`
and the same five `GROK_CURSOR_*` variables, so Grok Build does not load
Claude Code's or Cursor's configuration; `GROK_DISABLE_AUTOUPDATER=1`; and
the push and gh guards of `kimi` (`remote.origin.pushurl` through
`GIT_CONFIG_*`, a `GH_TOKEN` GitHub refuses).

The stream is Claude Code's `stream-json` shape and is read the same way:
the final message, usage and `total_cost_usd` from the `result` event, the
model from the `system/init` and `assistant` events. Grok writes the
literal name `unknown` when it has none; that name is dropped. The model
reported is the requested one (`grok-4.7`); `modelUsage` also names a
`grok-4.7-build`, which is recorded as observed and never compared.

Not narrowed: Grok Build's own plugins, hooks (`~/.grok/hooks`) and the
plugins it loads from `~/.claude/plugins` still run, and the permission
allows in `~/.claude/settings.local.json` still apply; `GROK_CONFIG` takes
only an allowlist of keys, none of which turns them off. `--deny MCPTool`
keeps every MCP tool from the role.

### muse

Base command:

```
muse exec --json --prompt-file <run dir>/prompt.md --model <model>
  --reasoning-effort <effort> --contributor-mode off --workspace <worktree>
  --no-session-log --no-foreign-personal-context --disable-web-tools
  --disable-reminders --disable-request-user-input --approval-mode never
  --approval-judge off
```

| role | added flags |
|---|---|
| planner | `--disable-write --disable-shell` |
| implementer | none |
| reviewer | `--disable-write` |
| judge | `--disable-write` |

`--contributor-mode off` is passed on every dispatch, whatever your Muse
Code setting, so no session is shared for training. `--approval-mode never`
with the judge off means nothing asks; the sandbox stays on. Muse Code has
no deny rule for a shell command, so the reviewer and judge shells are
whole, and `kimi`'s push and gh guards are set, with
`MUSE_NO_AUTO_UPDATE=1`.

Each `--json` line is a record whose `.payload.kind` says what it is. The
final message is the `run_terminal` payload's `.text` when its `.terminal`
is `completed`; any other terminal is a failed dispatch. The `run_usage`
payload names each model that served the run, with its tokens: those names
are the identity, checked against the request. No cost is reported.

Not narrowed: your Muse Code user skills load (`muse exec` has no flag to
leave them out of one run; `--no-foreign-personal-context` drops only those
of other tools).

### agy

Base command, the same for every role but the implementer's `--mode`:

```
agy -p <prompt> --output-format stream-json --model <model> --effort <effort>
  --print-timeout 0s --disable-slash-commands --sandbox
  --add-dir <worktree> --add-dir <task dir>
```

The implementer adds `--mode accept-edits`. As for `kimi`, the receipt's
`argv` shows the prompt as `<prompt.md>`. The workspace is the two
`--add-dir` folders: with the task directory alone, the agent took it for
its working directory.

`agy` reads permission rules only from its settings file, so each dispatch
runs with `HOME` set to a temporary directory holding
`.gemini/antigravity-cli/settings.json` (a copy is kept as
`agy-settings.json` in the run directory) and a symbolic link to your
`antigravity-oauth-token`; the directory is deleted after the run. The
settings set `toolPermission` `request-review`, `allowNonWorkspaceAccess`
off, the terminal sandbox on, and these rules (`mcp(*)`, `read_url(*)` and
`execute_url(*)` are denied to every role):

| role | allow | deny, besides the three above |
|---|---|---|
| planner | — | `write_file(*)`, `command(*)` |
| implementer | `command(*)` | `command(git push)`, `command(gh)` |
| reviewer | `command(*)` | `write_file(*)`, `command(git push)`, `command(gh)`, `command(git commit)` |
| judge | `command(git diff)`, `command(git log)`, `command(git show)`, `command(<bottega> signal)` | `write_file(*)` |

A deny rule beats every allow and the workspace's default, which lets any
file in the workspace be read and written; without a TTY a command no rule
allows is refused. `command(...)` matches a command prefix word by word, so
`command(git push)` denies a bare `git push` too, but not `/usr/bin/git
push`. Environment added to yours: `HOME` as above, `BOTTEGA_DATA_HOME` (so
`bottega signal` finds the task), the push and gh guards of `kimi`; the SSH
session markers (`SSH_CLIENT`, `SSH_CONNECTION`, `SSH_TTY`), which keep
`agy` off the keychain, are removed. Git runs without your global config:
the sandbox refuses to read `~/.gitconfig`, and no role commits.

Each stream-json line is `{"event": <kind>, <kind>: {...}}`. The final
message is the `result`'s `response`, or the `agent_response` text after
the last `tool` step; a `status` other than `SUCCESS` is a failed dispatch.
Only `init` names the model, the requested one, so receipts say
`requested-only`. `usage` keeps the `conversation_id` and the tokens; no
cost is reported.

Not narrowed: the tools `agy` offers (sixty on 2026-10-24, browser and
subagent tools among them) are not trimmed; no rule names the browser
tools.

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
- Kimi K3.1 Pro through Moonshot's Anthropic endpoint: not served to the
  key used on 2026-10-23; `kimi-k3` is verified;
- Kimi Code with another provider than its own Kimi Code login, and
  with a `KIMI_CODE_HOME` of its own;
- Grok Build's `--deny MCPTool` against a call through `use_tool`;
- `agy` and a push that no rule denies (`/usr/bin/git push`): the push
  guard is set, but the probe of 2026-10-24 failed earlier, on the global
  git config it then pointed at;
- `agy` renewing its sign-in through the link in the dispatch's HOME;
- `agy`'s other edit tools (`edit_file`, `replace_file_content`,
  `sed_file`) against `write_file(*)` in a read-only role: the docs give
  the `write_file` action for file edits, and only `write_file` itself was
  tried; the rails stop a read-only role that changes tracked code;
- Gemini CLI with `GEMINI_API_KEY` or Vertex (there is no driver);
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
