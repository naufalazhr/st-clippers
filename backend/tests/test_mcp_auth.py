"""The bearer check is the only thing between a local process and the tools."""
from __future__ import annotations

import json
import os
import stat
import sys

import pytest

from mcp_auth import (
    DEFAULT_MCP_PORT,
    McpConfig,
    check_bearer,
    get_or_create_token,
    load_config,
    regenerate_token,
    save_config,
    token_path,
)


# --- bearer check -----------------------------------------------------------

def test_rejects_missing_and_malformed_headers():
    assert not check_bearer("abc", None)
    assert not check_bearer("abc", "abc")          # no scheme
    assert not check_bearer("abc", "Basic abc")
    assert not check_bearer("abc", "bearer abc")   # scheme is case-sensitive
    assert not check_bearer("abc", "")
    assert not check_bearer("abc", "Bearer ")


def test_accepts_only_the_exact_token():
    assert check_bearer("abc", "Bearer abc")
    assert not check_bearer("abc", "Bearer abcd")  # a prefix is not enough
    assert not check_bearer("abc", "Bearer ab")
    assert not check_bearer("abc", "Bearer ABC")


def test_an_empty_expected_token_never_authorises():
    # A server that failed to load its token must not accept "Bearer ".
    assert not check_bearer("", "Bearer ")
    assert not check_bearer("", None)


# --- token file -------------------------------------------------------------

def test_token_is_created_once_and_reused(tmp_path):
    first = get_or_create_token(tmp_path)
    assert len(first) == 64  # 32 bytes, hex
    assert get_or_create_token(tmp_path) == first


def test_regenerate_replaces_the_token(tmp_path):
    first = get_or_create_token(tmp_path)
    second = regenerate_token(tmp_path)
    assert second != first
    assert get_or_create_token(tmp_path) == second


def test_a_blank_token_file_is_replaced(tmp_path):
    token_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    token_path(tmp_path).write_text("   \n", encoding="utf-8")
    assert len(get_or_create_token(tmp_path)) == 64


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes only")
def test_token_file_is_owner_only(tmp_path):
    get_or_create_token(tmp_path)
    mode = stat.S_IMODE(os.stat(token_path(tmp_path)).st_mode)
    assert mode == 0o600


# --- config -----------------------------------------------------------------

def test_config_defaults_to_disabled(tmp_path):
    config = load_config(tmp_path)
    assert config.enabled is False
    assert config.port == DEFAULT_MCP_PORT


def test_config_round_trips(tmp_path):
    save_config(tmp_path, McpConfig(enabled=True, port=45817))
    config = load_config(tmp_path)
    assert config.enabled is True
    assert config.port == 45817


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    (tmp_path / "mcp.json").write_text("{not json", encoding="utf-8")
    assert load_config(tmp_path) == McpConfig()


def test_nonsense_port_falls_back_to_the_default(tmp_path):
    (tmp_path / "mcp.json").write_text(
        json.dumps({"enabled": True, "port": 999999}), encoding="utf-8"
    )
    config = load_config(tmp_path)
    assert config.enabled is True
    assert config.port == DEFAULT_MCP_PORT
