"""A fake HTTP service on 127.0.0.1 for the MCP server tests: routes are set per test, requests are recorded."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

Reply = tuple[int, dict[str, str], bytes]
Route = Callable[["Seen"], Reply]


@dataclass
class Seen:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class Fake:
    base: str = ""
    routes: dict[tuple[str, str], Route | list[Route]] = field(default_factory=dict)
    seen: list[Seen] = field(default_factory=list)
    require: dict[str, str] = field(default_factory=dict)  # header -> value every request must carry

    def json(
        self, method: str, path: str, data: Any, status: int = 200, headers: dict[str, str] | None = None
    ) -> None:
        body = json.dumps(data).encode()
        self.routes[(method, path)] = lambda _s: (
            status,
            {"Content-Type": "application/json", **(headers or {})},
            body,
        )

    def sequence(self, method: str, path: str, items: list[Any]) -> None:
        self.routes[(method, path)] = [
            (lambda _s, d=d: (200, {"Content-Type": "application/json"}, json.dumps(d).encode()))
            for d in items
        ]


@contextmanager
def serve() -> Iterator[Fake]:
    fake = Fake()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:  # quiet
            return

        def _any(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            seen = Seen(self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, body)
            fake.seen.append(seen)
            for key, value in fake.require.items():
                if seen.headers.get(key.lower()) != value:
                    self._reply(401, {}, b"unauthenticated")
                    return
            route = fake.routes.get((self.command, self.path))
            if isinstance(route, list):
                route = route.pop(0) if len(route) > 1 else route[0]
            if route is None:
                self._reply(404, {}, b"not found")
                return
            self._reply(*route(seen))

        def _reply(self, status: int, headers: dict[str, str], body: bytes) -> None:
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = do_DELETE = _any

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fake.base = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield fake
    finally:
        server.shutdown()
        server.server_close()
