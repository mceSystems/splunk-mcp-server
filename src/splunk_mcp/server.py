"""Splunk MCP Server — entry point."""
from __future__ import annotations


import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from .client import SplunkClient
from .config import get_settings
from .tools import alerts, apps, dashboards, indexes, kvstore, macros, permissions, roles, saved_searches, search, server_info, users

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_client: SplunkClient | None = None


def get_client() -> SplunkClient:
    if _client is None:
        raise RuntimeError("SplunkClient not initialized")
    return _client


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    global _client
    settings = get_settings()
    logger.info(
        "Connecting to Splunk at %s:%s (SSL verify=%s)",
        settings.splunk_host,
        settings.splunk_port,
        settings.splunk_verify_ssl,
    )
    _client = SplunkClient(settings)
    try:
        yield
    finally:
        await _client.aclose()
        _client = None
        logger.info("Splunk client closed")


mcp = FastMCP("splunk-mcp", lifespan=lifespan)

# Register all tool modules
server_info.register(mcp, get_client)
search.register(mcp, get_client)
indexes.register(mcp, get_client)
apps.register(mcp, get_client)
saved_searches.register(mcp, get_client)
alerts.register(mcp, get_client)
dashboards.register(mcp, get_client)
kvstore.register(mcp, get_client)
macros.register(mcp, get_client)
users.register(mcp, get_client)
roles.register(mcp, get_client)
permissions.register(mcp, get_client)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
