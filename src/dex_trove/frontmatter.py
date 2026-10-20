"""Tolerant YAML frontmatter parsing for upstream Markdown (which is often not valid YAML)."""

from __future__ import annotations

import re
from typing import Any

import yaml

_FM = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


def split(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter, body)``. Invalid YAML falls back to naive ``key: value`` lines."""
    m = _FM.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), text[m.end() :]
    try:
        data = yaml.safe_load(raw)
        if isinstance(data, dict):
            return {str(k): v for k, v in data.items()}, body
    except yaml.YAMLError:
        pass
    naive: dict[str, Any] = {}
    for line in raw.splitlines():
        km = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if km:
            naive[km.group(1)] = km.group(2).strip().strip("'\"")
    return naive, body


def first_heading(body: str) -> str | None:
    m = re.search(r"^#\s+(.+?)\s*#*\s*$", body, re.MULTILINE)
    return m.group(1).strip() if m else None


def as_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = re.split(r"[,\s]+", value.strip("[]"))
    elif isinstance(value, (list, tuple)):
        items = [str(v) for v in value]
    else:
        return []
    out = []
    for item in items:
        tag = re.sub(r"[^a-z0-9.-]+", "-", item.strip().strip("'\"").lower()).strip("-")
        if tag:
            out.append(tag)
    return sorted(set(out))
