"""task.md: sections, checkbox items, [T<n>] ids, and the plan hash (plan §4.3).

A section is a level-2 heading (`## Title`) and every line up to the next
level-1 or level-2 heading. Headings and checkboxes inside fenced code blocks
are ignored.
"""

import hashlib
import re

from .util import Refused

REQUEST = "Original Request"
TODO = "To-Do List"
FINDINGS = "Review Findings"
VERDICT = "Verdict"

_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_HEADING = re.compile(r"^(#{1,2}) +(.+?)\s*#*\s*$")
_ITEM = re.compile(r"^(\s*[-*] \[)([ xX])(\] )(?:\[(T\d+)\] )?(.*)$")
_CHECKED = re.compile(r"^(\s*[-*] )\[[xX]\]")
ITEM_ID = re.compile(r"^T[1-9][0-9]*$")


class TaskDocError(Refused):
    """task.md cannot be used as asked (exit 2)."""


def normalise_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _lines(text):
    return normalise_newlines(text).split("\n")


def _outside_fences(lines):
    """Yield (index, line) for the lines that are not inside a code fence."""
    fenced = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield index, line


def sections(text):
    """[(title, heading_index, end_index)] for every level-2 section."""
    lines = _lines(text)
    headings = []
    for index, line in _outside_fences(lines):
        match = _HEADING.match(line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2)))
    found = []
    for position, (index, level, title) in enumerate(headings):
        if level != 2:
            continue
        if position + 1 < len(headings):
            end = headings[position + 1][0]
        else:
            end = len(lines)
        found.append((title, index, end))
    return found


def _find(text, title):
    for name, start, end in sections(text):
        if name == title:
            return start, end
    return None


def has_section(text, title):
    return _find(text, title) is not None


def get_section(text, title):
    """The body of section `title` without its heading, stripped; None if absent."""
    span = _find(text, title)
    if span is None:
        return None
    start, end = span
    return "\n".join(_lines(text)[start + 1 : end]).strip("\n")


def replace_section(text, title, body, before=None):
    """Replace the body of section `title` (never append to it).

    A missing section is inserted before section `before` when that exists,
    else at the end of the document.
    """
    lines = _lines(text)
    block = ["## " + title, ""]
    body = normalise_newlines(body).strip("\n")
    if body:
        block += body.split("\n") + [""]
    span = _find(text, title)
    if span is not None:
        start, end = span
        tail = lines[end:]
        new = lines[:start] + block + tail
    else:
        anchor = _find(text, before) if before else None
        if anchor is not None:
            new = lines[: anchor[0]] + block + lines[anchor[0] :]
        else:
            head = lines[:]
            while head and head[-1] == "":
                head.pop()
            new = head + [""] + block
    result = "\n".join(new).rstrip("\n") + "\n"
    return result


def set_title(text, title):
    """Set the level-1 `# Task <title>` heading (the first H1)."""
    lines = _lines(text)
    for index, line in _outside_fences(lines):
        if line.startswith("# "):
            lines[index] = "# Task " + title
            return "\n".join(lines)
    return "# Task " + title + "\n\n" + "\n".join(lines)


def blockquote(text):
    """`text` as a Markdown blockquote, line by line, verbatim."""
    quoted = []
    for line in normalise_newlines(text).strip("\n").split("\n"):
        quoted.append("> " + line if line else ">")
    return "\n".join(quoted)


def seed(template, title, request):
    """A new task.md: the template with the title and the verbatim request."""
    text = set_title(normalise_newlines(template), title)
    return replace_section(text, REQUEST, blockquote(request))


class Item:
    __slots__ = ("index", "checked", "id", "text")

    def __init__(self, index, checked, item_id, text):
        self.index = index
        self.checked = checked
        self.id = item_id
        self.text = text

    def as_dict(self):
        return {"id": self.id, "checked": self.checked, "text": self.text}


def todo_items(text):
    """The checkbox items of the To-Do List section, in document order."""
    span = _find(text, TODO)
    if span is None:
        return []
    start, end = span
    lines = _lines(text)
    items = []
    for index, line in _outside_fences(lines):
        if not start < index < end:
            continue
        match = _ITEM.match(line)
        if match:
            items.append(
                Item(index, match.group(2) != " ", match.group(4), match.group(5))
            )
    return items


def item_ids(text):
    return [item.id for item in todo_items(text) if item.id]


def duplicate_ids(text):
    seen, duplicates = set(), []
    for item_id in item_ids(text):
        if item_id in seen and item_id not in duplicates:
            duplicates.append(item_id)
        seen.add(item_id)
    return duplicates


def assign_ids(text):
    """Give every To-Do item without an id the next free `[T<n>]`.

    Existing ids are kept, so a re-approval after an edit never renumbers.
    Returns (new_text, [assigned ids]).
    """
    duplicates = duplicate_ids(text)
    if duplicates:
        raise TaskDocError("duplicate to-do id(s): " + ", ".join(duplicates))
    items = todo_items(text)
    used = [int(item.id[1:]) for item in items if item.id]
    next_id = max(used, default=0) + 1
    lines = _lines(text)
    assigned = []
    for item in items:
        if item.id:
            continue
        match = _ITEM.match(lines[item.index])
        item_id = "T%d" % next_id
        next_id += 1
        lines[item.index] = "%s%s%s[%s] %s" % (
            match.group(1),
            match.group(2),
            match.group(3),
            item_id,
            match.group(5),
        )
        assigned.append(item_id)
    return "\n".join(lines), assigned


def set_checked(text, ids, checked):
    """Tick or untick the To-Do items with these ids; unknown ids raise."""
    wanted = list(ids)
    by_id = {item.id: item for item in todo_items(text) if item.id}
    unknown = [item_id for item_id in wanted if item_id not in by_id]
    if unknown:
        raise TaskDocError("no to-do item with id: " + ", ".join(unknown))
    lines = _lines(text)
    mark = "x" if checked else " "
    for item_id in wanted:
        index = by_id[item_id].index
        match = _ITEM.match(lines[index])
        lines[index] = match.group(1) + mark + lines[index][len(match.group(1)) + 1 :]
    return "\n".join(lines)


def plan_region(text):
    """Everything above `## Review Findings`, normalised for hashing.

    Checked boxes become unchecked, trailing whitespace goes, line endings
    become `\\n`. The hash of this text survives ticking and re-reviewing and
    breaks on any edit to the plan itself.
    """
    lines = _lines(text)
    cut = len(lines)
    for title in (FINDINGS, VERDICT):
        span = _find(text, title)
        if span is not None:
            cut = span[0]
            break
    region = [_CHECKED.sub(r"\1[ ]", line).rstrip() for line in lines[:cut]]
    return "\n".join(region).strip("\n") + "\n"


def plan_sha256(text):
    return hashlib.sha256(plan_region(text).encode("utf-8")).hexdigest()
