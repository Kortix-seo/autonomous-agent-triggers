#!/usr/bin/env python3
"""Refuse a trigger file that would start sessions nobody can bound.

Reads a kortix.yaml (or any file with a top-level `triggers:` list) with the
standard library only, and reports per trigger:

  * the cron expression's field count (six expected: second, minute, hour,
    day of month, month, weekday)
  * max_runs_per_hour and max_runs_per_day, absent or below 1
  * a webhook trigger with no secret_env
  * an overlap value other than skip or allow

Exit code 0 when every trigger passes, 1 when at least one does not.

The parser is deliberately small: it understands the block shape this
repository documents (a top-level `triggers:` list of mappings, scalar
values, quoted or not) and refuses anything it cannot read rather than
guessing. It is a lint, not an implementation of the platform.

Usage:
    python3 check_triggers.py kortix.example.yaml
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCALAR = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*)\s*:\s*(?P<value>.*)$")
LIST_ITEM = re.compile(r"^-\s*(?P<rest>.*)$")

CRON_FIELDS = 6
REQUIRED_CAPS = ("max_runs_per_hour", "max_runs_per_day")
VALID_TYPES = {"cron", "webhook", "event", "monitor"}
VALID_OVERLAP = {"skip", "allow"}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    # drop a trailing comment that follows a space, but never inside quotes
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


@dataclass
class Trigger:
    slug: str = ""
    type: str = ""
    values: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def parse_triggers(text: str) -> tuple[list[Trigger], list[str]]:
    """Return the triggers found and any file-level parse problems."""
    triggers: list[Trigger] = []
    problems: list[str] = []
    in_triggers = False
    current: Trigger | None = None
    seen_triggers_key = False

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()

        if not line.startswith((" ", "\t")):
            key = SCALAR.match(stripped)
            if key and key.group("key") == "triggers":
                in_triggers = True
                seen_triggers_key = True
                continue
            if in_triggers:
                # a new top-level key ends the triggers block
                in_triggers = False
            continue

        if not in_triggers:
            continue

        item = LIST_ITEM.match(stripped)
        if item:
            current = Trigger()
            triggers.append(current)
            rest = item.group("rest").strip()
            if rest:
                pair = SCALAR.match(rest)
                if pair:
                    _assign(current, pair.group("key"), pair.group("value"))
                else:
                    problems.append(f"line {number}: cannot read list item: {stripped!r}")
            continue

        if current is None:
            problems.append(f"line {number}: indented line outside a trigger: {stripped!r}")
            continue

        pair = SCALAR.match(stripped)
        if not pair:
            problems.append(f"line {number}: cannot read: {stripped!r}")
            continue
        _assign(current, pair.group("key"), pair.group("value"))

    if not seen_triggers_key:
        problems.append("no top-level `triggers:` key")
    if not triggers and seen_triggers_key:
        problems.append("`triggers:` is present but empty")
    return triggers, problems


def _assign(trigger: Trigger, key: str, raw_value: str) -> None:
    value = _unquote(raw_value)
    trigger.values[key] = value
    if key == "slug":
        trigger.slug = value
    elif key == "type":
        trigger.type = value


def check(trigger: Trigger) -> None:
    values = trigger.values
    where = trigger.slug or "(no slug)"

    if not trigger.slug:
        trigger.problems.append("has no slug")
    if not trigger.type:
        trigger.problems.append("has no type")
    elif trigger.type not in VALID_TYPES:
        trigger.problems.append(
            f"type {trigger.type!r} is not one of {sorted(VALID_TYPES)}"
        )

    if trigger.type == "cron":
        expression = values.get("cron", "")
        if not expression:
            trigger.problems.append("is a cron trigger with no cron expression")
        else:
            fields = expression.split()
            if len(fields) != CRON_FIELDS:
                trigger.problems.append(
                    f"cron expression has {len(fields)} fields, expected {CRON_FIELDS} "
                    "(second, minute, hour, day of month, month, weekday)"
                )
        if not values.get("timezone"):
            trigger.problems.append(
                "is a cron trigger with no timezone, so the expression is read in the server's zone"
            )

    if trigger.type == "webhook" and not values.get("secret_env"):
        trigger.problems.append(
            "is a webhook trigger with no secret_env: every webhook trigger needs a "
            "signing secret, there is no unsigned webhook"
        )

    for cap in REQUIRED_CAPS:
        if cap not in values:
            trigger.problems.append(f"sets no {cap}")
            continue
        raw = values[cap]
        if raw.lower() in {"", "none", "null"}:
            if cap == "max_runs_per_hour":
                trigger.problems.append(
                    "sets max_runs_per_hour to no value; the platform falls back to 60 an hour"
                )
            continue
        if not raw.isdigit() or int(raw) < 1:
            trigger.problems.append(f"{cap} is {raw!r}, which is not a whole number of at least 1")

    overlap = values.get("overlap")
    if overlap and overlap not in VALID_OVERLAP:
        trigger.problems.append(
            f"overlap is {overlap!r}, which is not one of {sorted(VALID_OVERLAP)}"
        )

    # a cron trigger with no overlap inherits skip, which is fine; report it as a note
    if overlap is None and trigger.type == "cron":
        trigger.values.setdefault("_note", "no overlap set; the cron default is skip")

    del where  # only used in earlier versions of the messages


def report(path: Path, triggers: list[Trigger], problems: list[str]) -> int:
    failed = bool(problems)
    print(f"{path}: {len(triggers)} trigger{'s' if len(triggers) != 1 else ''}")
    for trigger in triggers:
        caps = "  ".join(
            f"{cap}={trigger.values.get(cap, '-')}" for cap in REQUIRED_CAPS
        )
        state = "ok" if not trigger.problems else "FAIL"
        print(f"  {trigger.slug or '(no slug)':<17} {trigger.type or '-':<8} {caps:<44} {state}")
        for problem in trigger.problems:
            print(f"      - {problem}")
        if trigger.values.get("_note"):
            print(f"      note: {trigger.values['_note']}")
        failed = failed or bool(trigger.problems)

    for problem in problems:
        print(f"  file: {problem}")
    return 1 if failed or problems else 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"not a file: {path}")
        return 2
    triggers, problems = parse_triggers(path.read_text(encoding="utf-8"))
    for trigger in triggers:
        check(trigger)
    return report(path, triggers, problems)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
