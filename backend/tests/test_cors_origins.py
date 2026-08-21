import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

# macOS uses tauri://localhost, Windows/Linux use http(s)://tauri.localhost.
WEBVIEW_ORIGINS = [
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
]


@pytest.mark.parametrize("origin", WEBVIEW_ORIGINS)
def test_simple_request_is_allowed(origin):
    response = client.get("/api/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", WEBVIEW_ORIGINS)
def test_json_post_preflight_is_allowed(origin):
    response = client.options(
        "/api/jobs",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_foreign_origin_is_still_rejected():
    response = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert response.headers.get("access-control-allow-origin") is None
