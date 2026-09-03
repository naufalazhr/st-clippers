"""Token, config and bearer check for the local MCP server.

The listener binds 127.0.0.1 only, so the trust boundary is "any process running
as this OS user". The bearer token exists so that boundary is explicit and
revocable, not because loopback is hostile.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import stat
from dataclasses import asdict, dataclass
from pathlib import Path

# 32 random bytes -> 64 hex characters, matching the playbook's token shape.
TOKEN_BYTES = 32

# Default port for the MCP listener. Deliberately not the API port: several MCP
# hosts commonly run at once, so this one is expected to move and is persisted.
DEFAULT_MCP_PORT = 8765

# How many consecutive ports to try before asking the OS for any free one.
PORT_SCAN_RANGE = 20


@dataclass
class McpConfig:
    enabled: bool = False
    port: int = DEFAULT_MCP_PORT


def token_path(data_dir: Path) -> Path:
    return data_dir / "mcp-token"


def config_path(data_dir: Path) -> Path:
    return data_dir / "mcp.json"


def _write_new_token(path: Path) -> str:
    token = secrets.token_hex(TOKEN_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        # Owner read/write only. No-op on Windows, which has no POSIX mode.
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return token


def get_or_create_token(data_dir: Path) -> str:
    path = token_path(data_dir)
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    if existing:
        return existing
    return _write_new_token(path)


def regenerate_token(data_dir: Path) -> str:
    """Replace the token. The only remediation if it leaks."""
    return _write_new_token(token_path(data_dir))


def load_config(data_dir: Path) -> McpConfig:
    try:
        raw = json.loads(config_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return McpConfig()
    if not isinstance(raw, dict):
        return McpConfig()
    port = raw.get("port", DEFAULT_MCP_PORT)
    return McpConfig(
        enabled=bool(raw.get("enabled", False)),
        port=int(port) if isinstance(port, int) and 0 < port < 65536 else DEFAULT_MCP_PORT,
    )


def save_config(data_dir: Path, config: McpConfig) -> None:
    path = config_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")


def check_bearer(expected_token: str, authorization_header: str | None) -> bool:
    """Constant-time bearer check.

    Compared with compare_digest so a wrong token cannot be discovered one byte
    at a time by timing the responses. The scheme is case-sensitive and a
    correct prefix is not enough.
    """
    if not expected_token or not authorization_header:
        return False
    prefix = "Bearer "
    if not authorization_header.startswith(prefix):
        return False
    presented = authorization_header[len(prefix):]
    return hmac.compare_digest(presented.encode("utf-8"), expected_token.encode("utf-8"))
