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
        validated_item = {
            "app": require_text(item.get("app"), f"items[{index}].app"),
            "host": require_text(item.get("host"), f"items[{index}].host"),
        }
        changes = item.get("changes", [])
        if not isinstance(changes, list):
            raise ValueError(f"items[{index}].changes must be an array")
        validated_item["changes"] = []
        for change_index, change in enumerate(changes):
            if not isinstance(change, dict):
                raise ValueError(f"items[{index}].changes[{change_index}] must be an object")
            before = change.get("before")
            after = change.get("after")
            if not isinstance(before, dict):
                raise ValueError(f"items[{index}].changes[{change_index}].before must be an object")
            if not isinstance(after, dict):
                raise ValueError(f"items[{index}].changes[{change_index}].after must be an object")
            validated_item["changes"].append(
                {
                    "service": require_text(
                        change.get("service"), f"items[{index}].changes[{change_index}].service"
                    ),
                    "image": require_text(
                        change.get("image"), f"items[{index}].changes[{change_index}].image"
                    ),
                    "before": validate_image(before, f"items[{index}].changes[{change_index}].before"),
                    "after": validate_image(after, f"items[{index}].changes[{change_index}].after"),
                }
            )
        validated.append(validated_item)
    return validated


def validate_image(image, name):
    image_id = require_text(image.get("id"), f"{name}.id")
    version = image.get("version")
    if version is not None and (not isinstance(version, str) or not version):
        raise ValueError(f"{name}.version must be a non-empty string or null")
    return {"id": image_id, "version": version}


def short_image_id(image_id):
    return image_id.removeprefix("sha256:")[:8]


def format_versions(before, after):
    before_version = before["version"]
    after_version = after["version"]
    if before_version and after_version and before_version != after_version:
        return before_version, after_version
    if before_version and after_version:
        return (
            f"{before_version} (sha:{short_image_id(before['id'])})",
            f"{after_version} (sha:{short_image_id(after['id'])})",
        )
    return (
        before_version or f"sha:{short_image_id(before['id'])}",
        after_version or f"sha:{short_image_id(after['id'])}",
    )


def format_app(item, change=None):
    app = escape_markdown(item["app"])
    if change is None:
        return f"• {app}"
    previous, current = format_versions(change["before"], change["after"])
    service = escape_markdown(change["service"])
    return f"• {app} • {service}: {escape_markdown(previous)} → {escape_markdown(current)}"


def flatten_items(items):
    entries = []
    for item in items:
        changes = item["changes"]
        entries.extend((item, change) for change in changes)
        if not changes:
            entries.append((item, None))
    return entries


def format_entries(entries):
    groups = OrderedDict()
    for item, change in entries:
        groups.setdefault(item["host"], []).append((item, change))

    sections = []
    for host, host_entries in groups.items():
        lines = [f"*{escape_markdown(host)}*"]
        lines.extend(format_app(item, change) for item, change in host_entries)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def format_message(repository, operation, target, run_url, items=None):
    repository = require_text(repository, "repository")
    operation = require_text(operation, "operation")
    target = require_text(target, "target")
    run_url = require_text(run_url, "run-url")
    items = validate_items([] if items is None else items)
    header = (
        f"*{escape_markdown(repository)}* • "
        f"[{escape_markdown(operation)}]({escape_link_url(run_url)}) completed • "
        f"*{escape_markdown(target)}*"
    )
    if not items:
        return header

    entries = flatten_items(items)
    message = f"{header}\n{format_entries(entries)}"
    if len(message) <= TELEGRAM_MESSAGE_LIMIT:
        return message

    for visible_count in range(len(entries) - 1, -1, -1):
        remaining = len(entries) - visible_count
        suffix = escape_markdown(f"…and {remaining} more services")
        body = format_entries(entries[:visible_count])
        candidate = f"{header}\n{body}\n\n{suffix}" if body else f"{header}\n{suffix}"
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
