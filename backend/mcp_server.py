"""Local MCP server (stateless Streamable HTTP) for Sultan Clip.

Architecture note
-----------------
The integration playbook puts the socket in Rust and the tool handlers in the
webview, because in that app the domain logic and session live in the webview.
Here they do not: jobs, clips and rendering all live in this Python backend, so
the handlers are plain functions and there is no bridge (playbook A.8, the
"native app, no webview" row). Everything else from the playbook applies as
written: bearer auth before parse, notifications answered 202, GET answered 405,
long-poll capped below the client's patience, and absolute file paths in results
so Telegram can send the file rather than a link.

Transport is a single ``POST /mcp`` with one JSON response per JSON-RPC request.
No SSE, no session ids.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import mcp_auth
import mcp_tools

SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
FALLBACK_PROTOCOL_VERSION = "2025-03-26"

SERVER_NAME = "sultan-clip"
SERVER_VERSION = "1.0.0"

# JSON-RPC error codes used here.
PARSE_ERROR = -32700
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603


@dataclass
class McpStatus:
    """What the settings screen renders. Per-install values, so the UI is the
    only correct documentation of them."""

    enabled: bool = False
    running: bool = False
    preferred_port: int = mcp_auth.DEFAULT_MCP_PORT
    bound_port: int | None = None
    # The port moved since last launch: an agent config written earlier now
    # points at nothing, and that failure is indistinguishable from "app not
    # running" unless the UI says so.
    port_changed: bool = False
    last_error: str | None = None
    token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "preferred_port": self.preferred_port,
            "bound_port": self.bound_port,
            "port_changed": self.port_changed,
            "last_error": self.last_error,
            "token": self.token,
            "url": f"http://127.0.0.1:{self.bound_port}/mcp" if self.bound_port else None,
        }


def bind_with_fallback(preferred: int) -> tuple[socket.socket, int]:
    """Bind 127.0.0.1 on the first free port at or after ``preferred``.

    Several MCP hosts commonly run at once, so a taken port is expected rather
    than exceptional. A working server on an odd port that the UI reports beats
    no server at all, hence the port-0 last resort.
    """
    last_error = ""
    for candidate in range(preferred, min(preferred + mcp_auth.PORT_SCAN_RANGE, 65536)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", candidate))
            return sock, candidate
        except OSError as exc:
            last_error = str(exc)
            sock.close()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))  # any free port
        return sock, sock.getsockname()[1]
    except OSError as exc:
        sock.close()
        raise OSError(
            f"could not bind any port on 127.0.0.1 starting at {preferred}: "
            f"{last_error}; {exc}"
        ) from exc


def rpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def negotiate_protocol_version(requested: Any) -> str:
    """Echo the client's version when supported, else offer our fallback."""
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return FALLBACK_PROTOCOL_VERSION


def handle_message(message: Any) -> dict[str, Any] | None:
    """Dispatch one JSON-RPC message. ``None`` means "acknowledge, no body"."""
    if not isinstance(message, dict):
        return rpc_error(None, PARSE_ERROR, "parse error")

    # Notifications carry no id: acknowledge and drop. Answering
    # notifications/initialized with a response is a protocol error some
    # clients reject outright.
    if "id" not in message:
        return None

    request_id = message.get("id")
    method = message.get("method") or ""
    params = message.get("params") or {}

    if method == "initialize":
        requested = params.get("protocolVersion") if isinstance(params, dict) else None
        return rpc_result(
            request_id,
            {
                "protocolVersion": negotiate_protocol_version(requested),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "ping":
        return rpc_result(request_id, {})

    if method in ("tools/list", "tools/call"):
        reply = mcp_tools.dispatch(method, params)
        if "error" in reply:
            return rpc_error(request_id, reply["error"]["code"], reply["error"]["message"])
        return rpc_result(request_id, reply["ok"])

    return rpc_error(request_id, METHOD_NOT_FOUND, f"method not found: {method}")


class _Handler(BaseHTTPRequestHandler):
    server_version = f"{SERVER_NAME}/{SERVER_VERSION}"
    token: str = ""

    def log_message(self, *args):  # noqa: D102 - quieten the default stderr spam
        pass

    def _send(self, status: int, payload: bytes = b"", content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def _send_json(self, status: int, body: Any):
        self._send(status, json.dumps(body).encode("utf-8"))

    def do_GET(self):  # noqa: N802
        # No SSE support, so the spec's answer for GET /mcp is 405. Returning
        # 200 with an empty body reads to clients as a broken stream.
        self._send(405, b"method not allowed", "text/plain")

    def do_POST(self):  # noqa: N802
        if self.path.rstrip("/") != "/mcp":
            self._send(404, b"not found", "text/plain")
            return

        # Auth before parse: an unauthenticated caller learns nothing about how
        # this server handles payloads.
        if not mcp_auth.check_bearer(self.token, self.headers.get("Authorization")):
            self._send(401, b"unauthorized", "text/plain")
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b""

        try:
            message = json.loads(raw or b"null")
        except json.JSONDecodeError:
            self._send_json(200, rpc_error(None, PARSE_ERROR, "parse error"))
            return

        # A batch is a list; answer each member that is a request.
        if isinstance(message, list):
            replies = [r for r in (handle_message(m) for m in message) if r is not None]
            if not replies:
                self._send(202)
                return
            self._send_json(200, replies)
            return

        try:
            reply = handle_message(message)
        except Exception as exc:  # a handler bug must not kill the connection
            self._send_json(200, rpc_error(message.get("id") if isinstance(message, dict) else None,
                                           INTERNAL_ERROR, str(exc)))
            return

        if reply is None:
            self._send(202)
            return
        self._send_json(200, reply)


@dataclass
class McpServer:
    """Owns the listener thread and the status the UI renders."""

    data_dir: Path
    status: McpStatus = field(default_factory=McpStatus)
    _httpd: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def refresh_from_disk(self) -> None:
        config = mcp_auth.load_config(self.data_dir)
        self.status.enabled = config.enabled
        self.status.preferred_port = config.port
        self.status.token = mcp_auth.get_or_create_token(self.data_dir)

    def start(self) -> McpStatus:
        with self._lock:
            if self._httpd is not None:
                return self.status

            config = mcp_auth.load_config(self.data_dir)
            preferred = config.port
            token = mcp_auth.get_or_create_token(self.data_dir)

            try:
                sock, bound = bind_with_fallback(preferred)
            except OSError as exc:
                self.status.running = False
                self.status.last_error = str(exc)
                self.status.token = token
                return self.status

            handler = type("_BoundHandler", (_Handler,), {"token": token})
            httpd = ThreadingHTTPServer(("127.0.0.1", bound), handler, bind_and_activate=False)
            httpd.socket.close()
            httpd.socket = sock
            httpd.server_activate()

            thread = threading.Thread(target=httpd.serve_forever, daemon=True,
                                      name="sultanclip-mcp")
            thread.start()

            self._httpd, self._thread = httpd, thread
            self.status.enabled = True
            self.status.running = True
            self.status.bound_port = bound
            self.status.port_changed = bound != preferred
            self.status.preferred_port = bound  # sticky: prefer it next launch
            self.status.last_error = None
            self.status.token = token

            # Persist what was actually bound, so a static agent config keeps
            # working across restarts.
            mcp_auth.save_config(self.data_dir, mcp_auth.McpConfig(enabled=True, port=bound))
            return self.status

    def stop(self) -> McpStatus:
        with self._lock:
            if self._httpd is not None:
                self._httpd.shutdown()
                self._httpd.server_close()
            self._httpd = None
            self._thread = None
            self.status.running = False
            self.status.bound_port = None
            self.status.port_changed = False
            return self.status

    def set_enabled(self, enabled: bool) -> McpStatus:
        if enabled:
            status = self.start()
        else:
            status = self.stop()
            status.enabled = False
            mcp_auth.save_config(
                self.data_dir,
                mcp_auth.McpConfig(enabled=False, port=self.status.preferred_port),
            )
        return status

    def regenerate_token(self) -> McpStatus:
        token = mcp_auth.regenerate_token(self.data_dir)
        self.status.token = token
        # The listener captured the old token in its handler class, so it has to
        # come back up for the new one to take effect.
        if self.status.running:
            self.stop()
            self.start()
        return self.status


_server: McpServer | None = None


def get_server(data_dir: Path) -> McpServer:
    global _server
    if _server is None:
        _server = McpServer(data_dir=data_dir)
        _server.refresh_from_disk()
    return _server


def init(data_dir: Path) -> McpStatus:
    """Start the listener only if the user previously enabled it.

    Opening a local port is a decision, not a default.
    """
    server = get_server(data_dir)
    config = mcp_auth.load_config(data_dir)
    if config.enabled:
        return server.start()
    server.refresh_from_disk()
    return server.status
