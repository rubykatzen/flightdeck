#!/usr/bin/env python3
import json
import os
import uuid
from collections import OrderedDict

MARKDOWN_V2_SPECIAL_CHARACTERS = frozenset("_*[]()~`>#+-=|{}.!\\")
TELEGRAM_MESSAGE_LIMIT = 4096


def escape_markdown(value):
    return "".join(
        f"\\{character}" if character in MARKDOWN_V2_SPECIAL_CHARACTERS else character for character in str(value)
    )


def escape_link_url(value):
    return str(value).replace("\\", "\\\\").replace(")", "\\)")


def require_text(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def validate_items(items):
    if not isinstance(items, list):
        raise ValueError("items must be a JSON array")

    validated = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"items[{index}] must be an object")
        validated.append(
            {
                "app": require_text(item.get("app"), f"items[{index}].app"),
                "host": require_text(item.get("host"), f"items[{index}].host"),
            }
        )
    return validated


def format_items(items):
    groups = OrderedDict()
    for item in items:
        groups.setdefault(item["host"], []).append(item["app"])

    sections = []
    for host, apps in groups.items():
        lines = [f"*{escape_markdown(host)}*"]
        lines.extend(f"• {escape_markdown(app)}" for app in apps)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def format_message(repository, operation, target, run_url, items=None):
    repository = require_text(repository, "repository")
    operation = require_text(operation, "operation")
    target = require_text(target, "target")
    run_url = require_text(run_url, "run-url")
    items = validate_items([] if items is None else items)
    header = (
        f"*{escape_markdown(repository)}* · "
        f"[{escape_markdown(operation)}]({escape_link_url(run_url)}) completed · "
        f"*{escape_markdown(target)}*"
    )
    if not items:
        return header

    message = f"{header}\n\n{format_items(items)}"
    if len(message) <= TELEGRAM_MESSAGE_LIMIT:
        return message

    for visible_count in range(len(items) - 1, -1, -1):
        remaining = len(items) - visible_count
        suffix = escape_markdown(f"…and {remaining} more")
        body = format_items(items[:visible_count])
        candidate = f"{header}\n\n{body}\n\n{suffix}" if body else f"{header}\n\n{suffix}"
        if len(candidate) <= TELEGRAM_MESSAGE_LIMIT:
            return candidate
    raise ValueError("operation notification header exceeds Telegram's message limit")


def write_output(message):
    delimiter = f"ghdelim_{uuid.uuid4().hex}"
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print(f"message<<{delimiter}", file=output)
        print(message, file=output)
        print(delimiter, file=output)


def main():
    items = json.loads(os.environ.get("ITEMS") or "[]")
    message = format_message(
        repository=os.environ["REPOSITORY"],
        operation=os.environ["OPERATION"],
        target=os.environ["TARGET"],
        run_url=os.environ["RUN_URL"],
        items=items,
    )
    write_output(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
