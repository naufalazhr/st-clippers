"""Guards for the two failures desktop users hit when reaching an LLM endpoint."""
from __future__ import annotations

import codecs
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from api import ClipJobRequest, app

client = TestClient(app)


class _StubLLM(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": [{"id": "model-a"}, {"id": "model-b"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stub_llm():
    server = HTTPServer(("127.0.0.1", 0), _StubLLM)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_localhost_endpoint_is_reachable_outside_docker(stub_llm, monkeypatch, host):
    # api.py rewrote localhost -> host.docker.internal unconditionally, so every
    # desktop model lookup failed to resolve ("getaddrinfo failed", or
    # "unknown encoding: idna" in a frozen build missing that codec).
    monkeypatch.delenv("IN_DOCKER", raising=False)
    response = client.post(
        "/api/models", json={"base_url": f"http://{host}:{stub_llm}/v1", "api_key": ""}
    )
    assert response.status_code == 200, response.json()
    assert response.json() == {"models": ["model-a", "model-b"]}


def test_docker_rewrite_still_applies_inside_docker(monkeypatch):
    monkeypatch.setenv("IN_DOCKER", "1")
    response = client.post(
        "/api/models", json={"base_url": "http://localhost:20128/v1", "api_key": ""}
    )
    # No such host outside Docker: proves the rewrite still fires when IN_DOCKER.
    assert response.status_code == 502
    assert "host.docker.internal" not in response.json()["detail"]  # host is hidden
    assert "Failed to reach LLM endpoint" in response.json()["detail"]


def test_idna_codec_is_available():
    # socket.getaddrinfo() encodes every hostname with this codec; a frozen build
    # missing it fails every network call with "unknown encoding: idna".
    assert codecs.lookup("idna") is not None
    assert codecs.lookup("punycode") is not None
    socket.getaddrinfo("localhost", 80)


def test_entry_point_imports_the_network_codecs():
    source = (__import__("pathlib").Path(__file__).parent.parent / "main.py").read_text(
        encoding="utf-8"
    )
    assert "import encodings.idna" in source
    assert "import encodings.punycode" in source


def test_spec_bundles_the_network_codecs():
    spec = (
        __import__("pathlib").Path(__file__).parent.parent / "sultanclip.spec"
    ).read_text(encoding="utf-8")
    assert "encodings.idna" in spec
    assert "encodings.punycode" in spec


def test_health_exposes_the_build_it_is_serving():
    # A stale backend holding the port is otherwise invisible: this is what makes
    # an old crop_mode enum diagnosable instead of a mystery 422.
    payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert "app_version" in payload
    assert payload["crop_modes"] == list(
        __import__("typing").get_args(
            ClipJobRequest.model_fields["crop_mode"].annotation
        )
    )


@pytest.mark.parametrize(
    "mode", ["center", "person", "streamer", "pillarbox", "split"]
)
def test_every_advertised_crop_mode_validates(mode):
    assert ClipJobRequest(url="https://x", crop_mode=mode).crop_mode == mode
