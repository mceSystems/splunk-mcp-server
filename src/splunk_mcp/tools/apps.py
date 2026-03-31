from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_apps(count: int = 100) -> str:
        """List installed Splunk apps.

        Args:
            count: Maximum number of apps to return (default 100)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_apps(count=count)
            entries = data.get("entry", [])
            if not entries:
                return "No apps found."
            lines = [f"Found {len(entries)} app(s):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                label = content.get("label", name)
                version = content.get("version", "unknown")
                disabled = content.get("disabled", False)
                visible = content.get("visible", True)
                author = content.get("author", "unknown")
                status = "disabled" if disabled else ("hidden" if not visible else "enabled")
                lines.append(f"\n  {name} (v{version}) [{status}]")
                if label != name:
                    lines.append(f"    Label: {label}")
                lines.append(f"    Author: {author}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)
