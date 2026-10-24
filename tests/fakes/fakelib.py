"""Shared engine for the fake harness executables (claude, codex, kimi, grok,
gemini, muse).

The fakes stand in for the real CLIs in every suite; no suite ever dispatches
a real model. They are driven by BOTTEGA_FAKE_SCENARIO, which is either inline
JSON or the path of a JSON file:

    {
      "log": "/abs/calls.jsonl",       # where each call is recorded
      "task": "<task id>",             # used by the "signal" action
      "calls": [ {step}, {step}, ... ],# consumed one per invocation, in order
      "default": {step}                # used once "calls" runs out
    }

A step may hold, all optional:

    model           the model the fake reports (default: the requested one)
    assistant_model / usage_model   claude, grok: report a different name there
    usage_extra     claude, grok: more modelUsage keys (helper models);
                    gemini: more stats.models keys
    events          extra JSON events written after the first one
    final           the final message (default "fake final message")
    no_final        true: produce no final message
    is_error        claude, grok: the result event says is_error; gemini:
                    the result status is "error"; muse: the run is "failed"
    writes          {relative path: content} written under the working dir
    tick / untick   to-do ids to tick or untick in task.md
    task_doc        task.md path (default: <--add-dir>/task.md)
    signal          ["needs-work", "reason", "--uncheck", "T2"]: runs
                    `bottega signal <task> ...` (bottega from PATH, or
                    BOTTEGA_FAKE_BOTTEGA)
    run             [[argv...], ...] extra commands, run in the working dir
    stderr          text written to stderr
    raw             text written to stdout before any event (malformed
                    lines, unknown event shapes)
    sleep           seconds to sleep before exiting
    exit            exit code (default 0)

Each call appends one JSON line to the log: the tool, argv, cwd, the names
(never the values) of the environment, and stdin.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_ITEM = re.compile(r"^(\s*[-*] \[)([ xX])(\] \[(T\d+)\] .*)$")


def load_scenario():
    raw = os.environ.get("BOTTEGA_FAKE_SCENARIO", "")
    if not raw:
        return {}
    if raw.lstrip().startswith("{"):
        return json.loads(raw)
    with open(raw, encoding="utf-8") as stream:
        return json.load(stream)


def log_path(scenario):
    value = scenario.get("log") or os.environ.get("BOTTEGA_FAKE_LOG")
    return Path(value) if value else None


def next_call(scenario, log):
    """(call number starting at 1, step) with a locked counter beside the log."""
    calls = scenario.get("calls") or []
    if log is None:
        number = 1
    else:
        log.parent.mkdir(parents=True, exist_ok=True)
        counter = Path(str(log) + ".count")
        with open(counter, "a+", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.seek(0)
            text = stream.read().strip()
            number = int(text or "0") + 1
            stream.seek(0)
            stream.truncate()
            stream.write(str(number))
    if number <= len(calls):
        return number, calls[number - 1]
    if "default" in scenario:
        return number, scenario["default"]
    if not calls:
        return number, {}
    sys.stderr.write("fake: no scenario step for call %d\n" % number)
    sys.exit(99)


def record(log, tool, argv, cwd, stdin, number):
    if log is None:
        return
    entry = {
        "call": number,
        "tool": tool,
        "argv": argv,
        "cwd": str(cwd),
        "env_names": sorted(os.environ),
        "stdin": stdin,
    }
    with open(log, "a", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(entry) + "\n")


def option(argv, *names):
    """The value after the last occurrence of any of `names`, else None."""
    value = None
    for index, arg in enumerate(argv):
        if arg in names and index + 1 < len(argv):
            value = argv[index + 1]
        for name in names:
            if name.startswith("--") and arg.startswith(name + "="):
                value = arg.split("=", 1)[1]
    return value


def _set_boxes(path, ids, mark):
    lines = Path(path).read_text(encoding="utf-8").split("\n")
    for index, line in enumerate(lines):
        match = _ITEM.match(line)
        if match and match.group(4) in ids:
            lines[index] = match.group(1) + mark + match.group(3)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def act(step, cwd, add_dir, scenario):
    """Perform the step's side effects in order: writes, boxes, commands, signal."""
    for rel, content in (step.get("writes") or {}).items():
        target = Path(cwd) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    doc = step.get("task_doc") or (str(Path(add_dir) / "task.md") if add_dir else None)
    if step.get("tick"):
        _set_boxes(doc, set(step["tick"]), "x")
    if step.get("untick"):
        _set_boxes(doc, set(step["untick"]), " ")
    # Child output goes to stderr: a real CLI keeps tool output out of the
    # event stream on stdout.
    for argv in step.get("run") or []:
        subprocess.run(argv, cwd=str(cwd), check=False, stdout=sys.stderr)
    if step.get("signal") is not None:
        bottega = os.environ.get("BOTTEGA_FAKE_BOTTEGA", "bottega")
        task = step.get("task") or scenario.get("task") or ""
        subprocess.run(
            [bottega, "signal", task, *step["signal"]], cwd=str(cwd), stdout=sys.stderr
        )
    if step.get("stderr"):
        sys.stderr.write(step["stderr"])


def finish(step):
    if step.get("sleep"):
        time.sleep(float(step["sleep"]))
    sys.stdout.flush()
    sys.exit(int(step.get("exit", 0)))


def emit(event):
    sys.stdout.write(json.dumps(event) + "\n")


def usage():
    return {
        "input_tokens": 120,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 40,
    }


def claude_main(argv):
    if "--version" in argv:
        print("2.1.302 (Claude Code)")
        return 0
    scenario = load_scenario()
    log = log_path(scenario)
    stdin = sys.stdin.read() if not sys.stdin.isatty() else ""
    number, step = next_call(scenario, log)
    cwd = Path.cwd()
    record(log, "claude", argv, cwd, stdin, number)
    act(step, cwd, option(argv, "--add-dir"), scenario)
    requested = option(argv, "--model") or "fake-model"
    claude_stream(step, number, requested, cwd, argv)
    finish(step)
    return 0


def task_dir_of(prompt_file):
    """The task directory, from a prompt at <task dir>/runs/<run>/prompt.md."""
    return str(Path(prompt_file).parent.parent.parent) if prompt_file else None


def grok_main(argv):
    """`grok --prompt-file <run dir>/prompt.md`: Claude Code's stream shape."""
    if "--version" in argv or "-v" in argv:
        print("grok 1.0.62 (fake) [stable]")
        return 0
    prompt_file = option(argv, "--prompt-file")
    if not prompt_file or not Path(prompt_file).read_text(encoding="utf-8"):
        sys.stderr.write("Error: empty prompt\n")
        return 1
    scenario = load_scenario()
    log = log_path(scenario)
    number, step = next_call(scenario, log)
    cwd = Path.cwd()
    record(log, "grok", argv, cwd, "", number)
    act(step, cwd, task_dir_of(prompt_file), scenario)
    claude_stream(
        step, number, option(argv, "-m", "--model") or "fake-model", cwd, argv
    )
    finish(step)
    return 0


def claude_stream(step, number, requested, cwd, argv):
    """The stream-json events of one Claude Code (or Grok Build) run."""
    model = step.get("model", requested)
    final = None if step.get("no_final") else step.get("final", "fake final message")
    started = time.time()
    sys.stdout.write(step.get("raw", ""))
    emit(
        {
            "type": "system",
            "subtype": "init",
            "session_id": "fake-session-%d" % number,
            "cwd": str(cwd),
            "model": model,
            "tools": [],
            "permissionMode": option(argv, "--permission-mode") or "default",
        }
    )
    if final is not None:
        emit(
            {
                "type": "assistant",
                "session_id": "fake-session-%d" % number,
                "message": {
                    "id": "msg_fake_%d" % number,
                    "type": "message",
                    "role": "assistant",
                    "model": step.get("assistant_model", model),
                    "content": [{"type": "text", "text": final}],
                    "usage": usage(),
                },
            }
        )
    for event in step.get("events") or []:
        emit(event)
    model_usage = {
        name: {"inputTokens": 10, "outputTokens": 5, "costUSD": 0.0001}
        for name in step.get("usage_extra") or []
    }
    model_usage[step.get("usage_model", model)] = {
        "inputTokens": 120,
        "outputTokens": 40,
        "costUSD": 0.0123,
    }
    result = {
        "type": "result",
        "subtype": "error_during_execution" if step.get("is_error") else "success",
        "is_error": bool(step.get("is_error")),
        "duration_ms": int((time.time() - started) * 1000),
        "num_turns": 1,
        "session_id": "fake-session-%d" % number,
        "total_cost_usd": 0.0123,
        "usage": usage(),
        "modelUsage": model_usage,
    }
    if final is not None:
        result["result"] = final
    emit(result)


def kimi_main(argv):
    """`kimi -p <prompt>`, in the shapes Kimi Code 2.3.1 printed on 2026-10-23:
    stream-json messages on stdout, and a session log with the requested
    model, the effort and the tokens under $KIMI_CODE_HOME/sessions."""
    if "--version" in argv or "-V" in argv:
        print("2.3.1")
        return 0
    prompt = option(argv, "-p", "--prompt")
    if not prompt:
        sys.stderr.write("Error: Prompt cannot be empty.\n")
        return 1
    scenario = load_scenario()
    log = log_path(scenario)
    number, step = next_call(scenario, log)
    cwd = Path.cwd()
    record(log, "kimi", argv, cwd, "", number)
    act(step, cwd, option(argv, "--add-dir"), scenario)
    final = None if step.get("no_final") else step.get("final", "fake final message")
    session = "session_fake-%d" % number
    sys.stdout.write(step.get("raw", ""))
    emit({"role": "meta", "type": "system.version", "version": "2.3.1"})
    for event in step.get("events") or []:
        emit(event)
    if final is not None:
        emit({"role": "assistant", "content": final})
    emit(
        {
            "role": "meta",
            "type": "session.resume_hint",
            "session_id": session,
            "command": "kimi -r " + session,
        }
    )
    home = Path(os.environ.get("KIMI_CODE_HOME") or Path.home() / ".kimi-code")
    wire = home / "sessions" / "wd_fake" / session / "agents" / "main" / "wire.jsonl"
    wire.parent.mkdir(parents=True, exist_ok=True)
    alias = option(argv, "-m", "--model") or "fake-model"
    lines = [
        {
            "type": "llm.request",
            "agentId": "main",
            "model": alias.split("/")[-1],
            "modelAlias": alias,
            "thinkingEffort": os.environ.get("KIMI_MODEL_THINKING_EFFORT"),
        },
        {
            "type": "usage.record",
            "agentId": "main",
            "model": alias,
            "usage": {
                "inputOther": 300,
                "output": 60,
                "inputCacheRead": 1200,
                "inputCacheCreation": 0,
            },
        },
        {
            "type": "turn.ended",
            "agentId": "main",
            "reason": "completed",
            "durationMs": 7,
        },
    ]
    if not step.get("no_session_log"):
        wire.write_text("".join(json.dumps(line) + "\n" for line in lines))
    finish(step)
    return 0


def codex_main(argv):
    if "--version" in argv:
        print("codex-cli 0.163.0")
        return 0
    if not argv or argv[0] != "exec":
        sys.stderr.write("fake codex: only `codex exec` is supported\n")
        return 2
    scenario = load_scenario()
    log = log_path(scenario)
    stdin = sys.stdin.read() if argv[-1] == "-" else ""
    number, step = next_call(scenario, log)
    cwd = Path(option(argv, "-C", "--cd") or Path.cwd())
    record(log, "codex", argv, cwd, stdin, number)
    act(step, cwd, option(argv, "--add-dir"), scenario)
    requested = option(argv, "-m", "--model") or "fake-model"
    model = step.get("model", requested)
    final = None if step.get("no_final") else step.get("final", "fake final message")
    sys.stdout.write(step.get("raw", ""))
    emit(
        {
            "type": "thread.started",
            "thread_id": "fake-thread-%d" % number,
            "model": model,
        }
    )
    emit({"type": "turn.started"})
    for event in step.get("events") or []:
        emit(event)
    if final is not None:
        emit(
            {
                "type": "item.completed",
                "item": {"id": "item_0", "type": "agent_message", "text": final},
            }
        )
        out = option(argv, "-o", "--output-last-message")
        if out:
            Path(out).write_text(final, encoding="utf-8")
    emit(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 200,
                "cached_input_tokens": 0,
                "output_tokens": 50,
            },
        }
    )
    finish(step)
    return 0


def gemini_main(argv):
    """`gemini` with the prompt on stdin: the stream-json shape of Gemini CLI
    0.65.0 (init, message deltas, tool_use/tool_result, result with stats)."""
    if "--version" in argv or "-v" in argv:
        print("0.65.0")
        return 0
    stdin = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not stdin.strip():
        sys.stderr.write("No input provided via stdin.\n")
        return 42
    scenario = load_scenario()
    log = log_path(scenario)
    number, step = next_call(scenario, log)
    cwd = Path.cwd()
    record(log, "gemini", argv, cwd, stdin, number)
    act(step, cwd, option(argv, "--include-directories"), scenario)
    requested = option(argv, "-m", "--model") or "fake-model"
    model = step.get("model", requested)
    final = None if step.get("no_final") else step.get("final", "fake final message")
    session = "fake-gemini-session-%d" % number
    sys.stdout.write(step.get("raw", ""))
    emit({"type": "init", "session_id": session, "model": requested})
    emit({"type": "message", "role": "user", "content": stdin})
    for event in step.get("events") or []:
        emit(event)
    if final is not None:
        half = len(final) // 2
        for chunk in (final[:half], final[half:]):
            emit(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": chunk,
                    "delta": True,
                }
            )
    models = {model: {"total_tokens": 160, "input_tokens": 120, "output_tokens": 40}}
    for name in step.get("usage_extra") or []:
        models[name] = {"total_tokens": 15, "input_tokens": 10, "output_tokens": 5}
    result = {
        "type": "result",
        "status": "error" if step.get("is_error") else "success",
        "stats": {
            "total_tokens": sum(m["total_tokens"] for m in models.values()),
            "input_tokens": sum(m["input_tokens"] for m in models.values()),
            "output_tokens": sum(m["output_tokens"] for m in models.values()),
            "duration_ms": 9,
            "tool_calls": 0,
            "models": models,
        },
    }
    if step.get("is_error"):
        result["error"] = {"type": "FatalError", "message": "fake failure"}
    emit(result)
    finish(step)
    return 0


def muse_record(number, sequence, kind, payload):
    return {
        "schema_version": 1,
        "stream": {"kind": "session", "id": "fake-muse-session-%d" % number},
        "sequence": sequence,
        "payload_type": kind,
        "payload": payload,
    }


def muse_main(argv):
    """`muse exec --json --prompt-file <run dir>/prompt.md`: the record shape
    of Muse Code 1.4.12 (payload kinds run_output_delta, run_usage,
    run_terminal)."""
    if "--version" in argv or "-V" in argv:
        print("Muse Code 1.4.12 (fake)")
        return 0
    if not argv or argv[0] != "exec":
        sys.stderr.write("fake muse: only `muse exec` is supported\n")
        return 2
    prompt_file = option(argv, "--prompt-file")
    if not prompt_file or not Path(prompt_file).read_text(encoding="utf-8"):
        sys.stderr.write("muse: empty prompt\n")
        return 64
    scenario = load_scenario()
    log = log_path(scenario)
    number, step = next_call(scenario, log)
    cwd = Path.cwd()
    record(log, "muse", argv, cwd, "", number)
    act(step, cwd, task_dir_of(prompt_file), scenario)
    requested = option(argv, "--model") or "fake-model"
    model = step.get("model", requested)
    final = None if step.get("no_final") else step.get("final", "fake final message")
    sys.stdout.write(step.get("raw", ""))
    seq = 0
    for event in step.get("events") or []:
        seq += 1
        emit(muse_record(number, seq, "event", event))
    if final is not None:
        seq += 1
        emit(
            muse_record(
                number,
                seq,
                "run.output.delta",
                {"kind": "run_output_delta", "text": final},
            )
        )
    usage = {
        "kind": "run_usage",
        "models": [
            {
                "model": model,
                "input_tokens": 300,
                "cached_tokens": 1200,
                "output_tokens": 60,
                "reasoning_tokens": 20,
                "calls": 2,
            }
        ],
        "calls": 2,
        "allowance": None,
    }
    seq += 1
    emit(muse_record(number, seq, "run.usage", usage))
    terminal = "failed" if step.get("is_error") else "completed"
    seq += 1
    emit(
        muse_record(
            number,
            seq,
            "run.terminal." + terminal,
            {
                "kind": "run_terminal",
                "terminal": terminal,
                "text": final if terminal == "completed" else None,
                "reason": "fake failure" if terminal == "failed" else None,
            },
        )
    )
    finish(step)
    return 0
