"""A small Model Context Protocol server over stdio: JSON-RPC 2.0, one message per line, standard library only.

It implements what tool servers need: ``initialize``, ``ping``, ``tools/list`` and ``tools/call``. Arguments are
checked against each tool's input schema before the handler runs. A tool that fails with :class:`ToolError` returns
``isError: true`` with the message (the model can read it and correct itself); anything unexpected returns a short
error without a traceback. Nothing is written to stdout except protocol messages.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import IO, Any

from dex_trove import __version__
from dex_trove.mcp.common import Context, ToolError, redact

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_LINE = 8 * 1024 * 1024

Handler = Callable[[Context, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict[str, dict[str, Any]]
    handler: Handler
    required: tuple[str, ...] = ()
    action: bool = False  # changes something outside this machine
    writes: bool = False  # writes files under the project (evidence, state)

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": self.properties,
            "required": list(self.required),
            "additionalProperties": False,
        }

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.schema(),
            "annotations": {
                "readOnlyHint": not (self.action or self.writes),
                "destructiveHint": self.action,
                "idempotentHint": not self.action,
                "openWorldHint": self.action,
            },
        }


_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


def check_args(tool: Tool, args: object) -> dict[str, Any]:
    """Validates arguments against the tool's schema (types, required, enums, no extra keys)."""
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ToolError("arguments must be an object")
    unknown = sorted(set(args) - set(tool.properties))
    if unknown:
        raise ToolError(
            f"{tool.name}: unknown argument(s) {', '.join(unknown)}; expected {', '.join(tool.properties)}"
        )
    missing = [name for name in tool.required if args.get(name) in (None, "")]
    if missing:
        raise ToolError(f"{tool.name}: missing required argument(s) {', '.join(missing)}")
    for name, value in args.items():
        spec = tool.properties[name]
        expected = spec.get("type")
        if value is None or not isinstance(expected, str):
            continue
        ok = isinstance(value, _TYPES[expected]) and not (
            expected in {"integer", "number"} and isinstance(value, bool)
        )
        if not ok:
            raise ToolError(f"{tool.name}: {name} must be {expected}")
        if "enum" in spec and value not in spec["enum"]:
            raise ToolError(f"{tool.name}: {name} must be one of {', '.join(map(str, spec['enum']))}")
        if (
            expected == "array"
            and spec.get("items", {}).get("type") == "string"
            and not all(isinstance(v, str) for v in value)
        ):
            raise ToolError(f"{tool.name}: {name} must be a list of strings")
    return args


@dataclass
class Server:
    name: str
    instructions: str
    tools: list[Tool]
    ctx: Context
    _by_name: dict[str, Tool] = field(init=False)

    def __post_init__(self) -> None:
        self._by_name = {t.name: t for t in self.tools}

    def call(self, name: str, args: object) -> dict[str, Any]:
        """Runs a tool in-process and returns its result, raising :class:`ToolError` (used by ``dex mcp call``)."""
        tool = self._by_name.get(name)
        if tool is None:
            raise ToolError(f"no tool {name!r}; this server has {', '.join(self._by_name)}")
        return tool.handler(self.ctx, check_args(tool, args))

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        try:
            out = self.call(str(name), params.get("arguments"))
        except ToolError as exc:
            return {"content": [{"type": "text", "text": redact(str(exc))}], "isError": True}
        except Exception as exc:  # noqa: BLE001 - a tool bug must not kill the server
            return {
                "content": [{"type": "text", "text": f"internal error in {name}: {type(exc).__name__}"}],
                "isError": True,
            }
        return {
            "content": [{"type": "text", "text": json.dumps(out, indent=1, ensure_ascii=False)}],
            "structuredContent": out,
        }

    def handle(self, msg: object) -> dict[str, Any] | None:
        """One JSON-RPC message in, one response out (``None`` for notifications)."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
        method, mid = msg["method"], msg.get("id")
        params = msg.get("params") or {}
        if "id" not in msg:  # a notification: never answered
            return None
        if not isinstance(params, dict):
            return _error(mid, -32602, "params must be an object")
        if method == "initialize":
            asked = params.get("protocolVersion")
            return _ok(
                mid,
                {
                    "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": f"dex-{self.name}", "version": __version__},
                    "instructions": self.instructions,
                },
            )
        if method == "ping":
            return _ok(mid, {})
        if method == "tools/list":
            return _ok(mid, {"tools": [t.describe() for t in self.tools]})
        if method == "tools/call":
            return _ok(mid, self._tools_call(params))
        return _error(mid, -32601, f"method not found: {method}")

    def serve(self, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> None:
        source, sink = stdin or sys.stdin, stdout or sys.stdout
        for line in source:
            if not line.strip():
                continue
            if len(line) > MAX_LINE:
                reply: dict[str, Any] | None = _error(None, -32600, "message too large")
            else:
                try:
                    reply = self.handle(json.loads(line))
                except ValueError:
                    reply = _error(None, -32700, "parse error")
            if reply is not None:
                sink.write(json.dumps(reply, ensure_ascii=False) + "\n")
                sink.flush()


def _ok(mid: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}
