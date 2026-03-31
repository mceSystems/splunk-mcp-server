from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError, SplunkTimeoutError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_get_server_info() -> str:
        """Get Splunk server information including version, build, and license details."""
        client: SplunkClient = get_client()
        try:
            data = await client.get_server_info()
            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})
            return (
                f"Splunk Version: {content.get('version', 'unknown')}\n"
                f"Build: {content.get('build', 'unknown')}\n"
                f"Product: {content.get('product_type', 'unknown')}\n"
                f"Server Name: {content.get('serverName', 'unknown')}\n"
                f"OS: {content.get('os_name', 'unknown')} {content.get('os_version', '')}\n"
                f"CPU Arch: {content.get('cpu_arch', 'unknown')}\n"
                f"GUID: {content.get('guid', 'unknown')}\n"
                f"License: {content.get('activeLicenseGroup', 'unknown')}"
            )
        except SplunkAPIError as e:
            return str(e)
        except SplunkTimeoutError as e:
            return str(e)
