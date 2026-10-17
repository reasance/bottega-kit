# Later

Ideas that do not serve the loop in 0.1.0. Each one is a line here, not code,
until the owner decides otherwise. Seeded from the work plan (§7 and M4) and
refreshed for 0.1.0 on 2026-10-17 with what the milestones deferred.

## 0.2.0 candidates (M4; not started without the owner's word)

- An `openai-compatible` text-patch harness (DeepSeek, Qwen, the GLM API, local
  endpoints): a context pack (`git ls-files`, `bottega.json`, files the plan lists
  under `## Context files`, size-capped), unified-diff output, a fail-closed
  verifier (relative paths, no `..`, `.git`/`.github`/`.env*`/hooks denied,
  add/modify only, `git apply --check`), applied in the worktree, verdict in the
  receipt. Text-patch profiles are implementer-only: they have no shell, so they
  cannot signal, and `approve` refuses them in other roles.
- Agentic drivers for `kimi`, `grok` and `gemini`.

## Later

- A PR/CI agent that drives checks to green and resolves conflicts.
- A refinement stage between READY and the PR (bottega has one).
- YOLO mode.
- Epics, explore, webhooks, a kanban, several users, authentication.
- `auto` role bindings through a router. Today `auto` is parsed and refused.
- Locks across tasks. One `run` per task is enforced; running several tasks at
  once is the user's call.
- Dashboards.
- An interactive `bottega init`.
- Finding `test_cmd` in the project's CLAUDE.md. Today it comes from
  `bottega.json` only.
- `bottega pr --remote`. Today the PR goes to `origin` only.
- Structured verdicts as a second channel: Claude `--json-schema`, Codex
  `--output-schema`.
- Narrowing `--add-dir` from the whole task directory to a `doc/` subdirectory
  that holds only `task.md`. Today an implementer can technically touch the
  receipts and `state.json`; the orchestrator re-reads nothing from them
  mid-run, so the exposure is low.
- Checking the plan hash after every implementer dispatch, not only when
  `run` and `resume` start. Today an implementer that edits the plan text
  mid-run is caught at the next `resume`, not at once.
- `npx bottega-kit --uninstall`. Today uninstalling needs a clone and its
  `./uninstall.sh`.
- `bottega pr` for an `origin` whose URL uses an ssh host alias
  (`work:owner/repo`): gh is then given the alias as the host. Today the user
  sets a plain `github.com` URL.
- `bottega pr --draft`, labels, reviewers. Today `pr` opens a plain pull
  request; `gh pr edit` does the rest.
