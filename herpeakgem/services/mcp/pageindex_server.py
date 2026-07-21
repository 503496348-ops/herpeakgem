"""Built-in PageIndex MCP server entry.

When a PageIndex API key is configured in runtime settings, the MCP manager
injects a reserved ``pageindex`` server into the live registry. The registry is
never persisted to ``mcp.json`` so keys and endpoint details stay centralized in
the PageIndex settings and cannot be edited through the MCP admin UI.
"""

from __future__ import annotations

from herpeakgem.services.mcp.config import MCPConfig, MCPServerConfig

PAGEINDEX_SERVER_NAME = "pageindex"


def builtin_pageindex_server() -> MCPServerConfig | None:
    """Build the injected PageIndex MCP server, or ``None`` when unavailable."""
    from herpeakgem.services.rag.pipelines.pageindex.config import get_pageindex_config

    try:
        cfg = get_pageindex_config(require_key=False)
    except Exception:
        return None

    api_key = getattr(cfg, "api_key", "")
    if not api_key:
        return None

    return MCPServerConfig(
        type="streamableHttp",
        url=f"{cfg.api_base_url.rstrip('/')}" + "/mcp",
        headers={"Authorization": f"Bearer {api_key}"},
        tool_timeout=120,
        enabled_tools=["*"],
    )


def with_builtin_servers(config: MCPConfig) -> MCPConfig:
    """Overlay built-in MCP servers onto persisted config.

    User-edited entries always win; builtin entries are only injected when missing.
    """
    if PAGEINDEX_SERVER_NAME in config.servers:
        return config

    entry = builtin_pageindex_server()
    if entry is None:
        return config

    return MCPConfig(servers={**config.servers, PAGEINDEX_SERVER_NAME: entry})


__all__ = [
    "PAGEINDEX_SERVER_NAME",
    "builtin_pageindex_server",
    "with_builtin_servers",
]
