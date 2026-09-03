"""Protocol conformance and the tool surface, exercised over real HTTP."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import pytest

import mcp_auth
import mcp_server
import mcp_tools


@pytest.fixture
def server(tmp_path):
    """A listener on a real socket, with a known token."""
    mcp_auth.save_config(tmp_path, mcp_auth.McpConfig(enabled=True, port=0))
    srv = mcp_server.McpServer(data_dir=tmp_path)
    status = srv.start()
    assert status.running, status.last_error
    yield srv
    srv.stop()


def call(server, payload, token=None, method="POST", path="/mcp"):
    """Returns (status_code, parsed_body_or_None)."""
    url = f"http://127.0.0.1:{server.status.bound_port}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    tok = server.status.token if token is None else token
    if tok is not False:
        request.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, None


# --- transport --------------------------------------------------------------

def test_unauthenticated_request_is_refused(server):
    status, _ = call(server, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, token=False)
    assert status == 401


def test_a_wrong_token_is_refused(server):
    status, _ = call(server, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="deadbeef")
    assert status == 401


def test_get_is_405_because_there_is_no_sse(server):
    # A 200 with an empty body reads to clients as a broken stream.
    status, _ = call(server, None, method="GET")
    assert status == 405


def test_handshake_echoes_a_supported_version(server):
    _, body = call(server, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "0"}},
    })
    assert body["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in body["result"]["capabilities"]
    assert body["result"]["serverInfo"]["name"] == "sultan-clip"


def test_unknown_protocol_version_gets_the_fallback(server):
    _, body = call(server, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "1999-01-01"},
    })
    assert body["result"]["protocolVersion"] == mcp_server.FALLBACK_PROTOCOL_VERSION


def test_ping(server):
    _, body = call(server, {"jsonrpc": "2.0", "id": 7, "method": "ping"})
    assert body == {"jsonrpc": "2.0", "id": 7, "result": {}}


def test_notification_is_accepted_with_no_body(server):
    # notifications/initialized arrives right after the handshake; answering it
    # with a JSON-RPC response is a protocol error some clients reject.
    status, body = call(server, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert status == 202
    assert body is None


def test_unknown_method(server):
    _, body = call(server, {"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
    assert body["error"]["code"] == mcp_server.METHOD_NOT_FOUND


def test_malformed_json_is_a_parse_error_not_a_crash(server):
    url = f"http://127.0.0.1:{server.status.bound_port}/mcp"
    request = urllib.request.Request(url, data=b"{not json", method="POST")
    request.add_header("Authorization", f"Bearer {server.status.token}")
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read())
    assert body["error"]["code"] == mcp_server.PARSE_ERROR


def test_tools_list_over_http(server):
    _, body = call(server, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    names = [t["name"] for t in body["result"]["tools"]]
    assert "create_clip_job" in names and "list_jobs" in names


# --- port handling ----------------------------------------------------------

def test_port_fallback_when_the_preferred_port_is_taken(tmp_path):
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    taken = blocker.getsockname()[1]
    blocker.listen(1)
    try:
        sock, bound = mcp_server.bind_with_fallback(taken)
        sock.close()
        assert bound != taken  # moved to a free one rather than failing
    finally:
        blocker.close()


def test_the_bound_port_is_persisted_and_flagged_when_it_moves(tmp_path):
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    taken = blocker.getsockname()[1]
    blocker.listen(1)
    try:
        mcp_auth.save_config(tmp_path, mcp_auth.McpConfig(enabled=True, port=taken))
        srv = mcp_server.McpServer(data_dir=tmp_path)
        status = srv.start()
        try:
            assert status.running
            assert status.bound_port != taken
            # An agent config written earlier now points at nothing, and that
            # failure looks exactly like "the app isn't running".
            assert status.port_changed is True
            # Persisted, so a static agent config keeps working next launch.
            assert mcp_auth.load_config(tmp_path).port == status.bound_port
        finally:
            srv.stop()
    finally:
        blocker.close()


def test_regenerating_the_token_invalidates_the_old_one(server):
    old = server.status.token
    server.regenerate_token()
    assert server.status.token != old
    assert server.status.running  # came back up on the new token

    status, _ = call(server, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, token=old)
    assert status == 401
    status, _ = call(server, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert status == 200


def test_disabled_by_default(tmp_path):
    # Opening a local port is a decision, not a default.
    status = mcp_server.McpServer(data_dir=tmp_path).status
    assert status.enabled is False and status.running is False
