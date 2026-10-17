"""The prompt templates and their strict `{{var}}` engine (plan §2.15, §4.6, §9).

Only `{{name}}` with a `\\w+` name is a variable. A spaced marker such as
`{{ phase title }}` is guidance text and stays as it is. Rendering is one
pass: a value that itself contains `{{x}}` (a task.md snapshot, say) is
never expanded again. A variable the template names but the caller does not
supply raises; an override template naming a variable bottega-kit does not
know is refused before it is ever rendered.

Templates ship in `<kit>/prompts/<name>.md`; a file at
`~/.config/bottega-kit/prompts/<name>.md` wins on presence.
"""

import re
import zlib
from pathlib import Path

from . import KIT_ROOT, xdg
from .util import Refused

VARIABLE = re.compile(r"\{\{(\w+)\}\}")

PROMPTS_DIR = KIT_ROOT / "prompts"
TEMPLATE_FILE = KIT_ROOT / "templates" / "task.md"
NAMES = ("planner", "implementer", "reviewer", "judge")

# Every variable a role prompt may use (plan §2.15).
PROMPT_VARIABLES = (
    "task_doc",
    "task_doc_content",
    "task_id",
    "task_title",
    "worktree",
    "base_branch",
    "signal_cmd",
    "test_cmd",
    "round",
    "rounds",
    "scratch_dir",
    "port",
    "plan_template",
)
# The variables of templates/task.md (plan §9).
TEMPLATE_VARIABLES = ("task_title", "original_request")

PORT_BASE = 3100
PORT_SPAN = 900


class PromptError(Refused):
    """A template cannot be rendered (exit 2): nothing is dispatched."""


def names_in(text):
    """The `\\w+` variable names a template uses, in first-use order."""
    return list(dict.fromkeys(VARIABLE.findall(text)))


def render(text, values, where="template"):
    """Replace every `{{name}}` in one pass; a missing value raises PromptError."""
    missing = [name for name in names_in(text) if name not in values]
    if missing:
        raise PromptError(
            "%s uses variable(s) with no value: %s" % (where, ", ".join(missing))
        )
    return VARIABLE.sub(lambda match: str(values[match.group(1)]), text)


def unknown_names(text, known=PROMPT_VARIABLES):
    return [name for name in names_in(text) if name not in known]


def override_path(name):
    return xdg.prompts_override_dir() / (name + ".md")


def shipped_path(name):
    return PROMPTS_DIR / (name + ".md")


def load(name):
    """(template text, path) for role prompt `name`; an override wins.

    An override is validated for unknown variables before it is used.
    """
    if name not in NAMES:
        raise PromptError("unknown prompt %r (prompts: %s)" % (name, ", ".join(NAMES)))
    override = override_path(name)
    path = override if override.is_file() else shipped_path(name)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PromptError("cannot read prompt %s: %s" % (path, error)) from None
    if path == override:
        unknown = unknown_names(text)
        if unknown:
            raise PromptError(
                "%s uses unknown variable(s): %s (known: %s)"
                % (path, ", ".join(unknown), ", ".join(PROMPT_VARIABLES))
            )
    return text, path


def port(task_id):
    """bottega's per-task dev-server port, so parallel tasks do not collide."""
    return PORT_BASE + zlib.crc32(task_id.encode("utf-8")) % PORT_SPAN


def plan_template(template_text=None):
    """The part of templates/task.md the planner writes: `## Overview` up to,
    not including, `## Review Findings`. Title, request, findings and verdict
    are bottega-kit's to keep."""
    if template_text is None:
        template_text = TEMPLATE_FILE.read_text(encoding="utf-8")
    lines = template_text.replace("\r\n", "\n").split("\n")
    start = next(
        (i for i, line in enumerate(lines) if line.strip() == "## Overview"), 0
    )
    end = next(
        (
            i
            for i, line in enumerate(lines)
            if i > start and line.strip() == "## Review Findings"
        ),
        len(lines),
    )
    return "\n".join(lines[start:end]).strip("\n")


def values(st, task_dir, run_dir, role, rounds, test_cmd, bottega):
    """The full variable set for one dispatch (plan §2.15)."""
    task_doc = Path(task_dir) / "task.md"
    result = {
        "task_doc": str(task_doc),
        "task_doc_content": task_doc.read_text(encoding="utf-8"),
        "task_id": st["task"],
        "task_title": st["title"],
        "worktree": st["worktree"],
        "base_branch": st["base"],
        "signal_cmd": "%s signal %s" % (bottega, st["task"]),
        "test_cmd": test_cmd or "",
        "round": str(st.get("round") or 0),
        "rounds": str(rounds),
        "scratch_dir": str(Path(run_dir) / "scratch"),
        "port": str(port(st["task"])),
    }
    if role == "planner":
        result["plan_template"] = plan_template()
    return result
