from types import SimpleNamespace

import pytest

from herpeakgem.services.mcp.config import MCPConfig, MCPServerConfig
from herpeakgem.services.mcp.pageindex_server import (
    PAGEINDEX_SERVER_NAME,
    builtin_pageindex_server,
    with_builtin_servers,
)


class _Cfg(SimpleNamespace):
    """Small config stub with attribute-style API."""


def test_builtin_pageindex_server_requires_key(monkeypatch):
    monkeypatch.setattr(
        "herpeakgem.services.rag.pipelines.pageindex.config.get_pageindex_config",
        lambda require_key=True: _Cfg(api_key="", api_base_url="https://api.pageindex.ai"),
    )
    assert builtin_pageindex_server() is None


def test_with_builtin_servers_appends_pageindex(monkeypatch):
    monkeypatch.setattr(
        "herpeakgem.services.rag.pipelines.pageindex.config.get_pageindex_config",
        lambda require_key=False: _Cfg(api_key="sekret", api_base_url="https://api.pageindex.ai"),
    )
    merged = with_builtin_servers(MCPConfig())
    assert PAGEINDEX_SERVER_NAME in merged.servers
    inserted = merged.servers[PAGEINDEX_SERVER_NAME]
    assert inserted.url == "https://api.pageindex.ai/mcp"
    assert inserted.headers["Authorization"] == "Bearer sekret"
    assert inserted.type == "streamableHttp"


def test_with_builtin_servers_preserves_user_pageindex(monkeypatch):
    monkeypatch.setattr(
        "herpeakgem.services.rag.pipelines.pageindex.config.get_pageindex_config",
        lambda require_key=False: _Cfg(api_key="sekret", api_base_url="https://api.pageindex.ai"),
    )
    custom = MCPServerConfig(
        type="stdio",
        command="python",
        args=["-m", "custom"],
    )
    original = MCPConfig(servers={PAGEINDEX_SERVER_NAME: custom})
    merged = with_builtin_servers(original)

    assert merged.servers[PAGEINDEX_SERVER_NAME] is custom
    assert merged.servers[PAGEINDEX_SERVER_NAME].type == "stdio"
