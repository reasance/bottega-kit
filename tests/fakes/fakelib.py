"""Shared engine for the fake `claude` and `codex` executables.

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
    assistant_model / usage_model   claude only: report a different name there
    final           the final message (default "fake final message")
    no_final        true: produce no final message
    is_error        claude only: the result event says is_error
    writes          {relative path: content} written under the working dir
    tick / untick   to-do ids to tick or untick in task.md
    task_doc        task.md path (default: <--add-dir>/task.md)
    signal          ["needs-work", "reason", "--uncheck", "T2"]: runs
                    `bottega signal <task> ...` (bottega from PATH, or
                    BOTTEGA_FAKE_BOTTEGA)
    run             [[argv...], ...] extra commands, run in the working dir
    stderr          text written to stderr
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
    model = step.get("model", requested)
    final = None if step.get("no_final") else step.get("final", "fake final message")
    started = time.time()
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
    result = {
        "type": "result",
        "subtype": "error_during_execution" if step.get("is_error") else "success",
        "is_error": bool(step.get("is_error")),
        "duration_ms": int((time.time() - started) * 1000),
        "num_turns": 1,
        "session_id": "fake-session-%d" % number,
        "total_cost_usd": 0.0123,
        "usage": usage(),
        "modelUsage": {
            step.get("usage_model", model): {
                "inputTokens": 120,
                "outputTokens": 40,
                "costUSD": 0.0123,
            }
        },
    }
    if final is not None:
        result["result"] = final
    emit(result)
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
    emit(
        {
            "type": "thread.started",
            "thread_id": "fake-thread-%d" % number,
            "model": model,
        }
    )
    emit({"type": "turn.started"})
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
