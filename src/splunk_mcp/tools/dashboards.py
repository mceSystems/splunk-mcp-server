from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_dashboards(count: int = 50, app: str = "") -> str:
        """List Splunk dashboards.

        Args:
            count: Maximum number of dashboards to return (default 50)
            app: Filter by app name (e.g. 'search'). Empty returns all.
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_dashboards(count=count, app=app)
            entries = data.get("entry", [])
            if not entries:
                return "No dashboards found."
            lines = [f"Found {len(entries)} dashboard(s):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                acl = entry.get("acl", {})
                app_name = acl.get("app", "unknown")
                label = content.get("label", name)
                is_visible = content.get("isDashboard", True)
                sharing = acl.get("sharing", "unknown")
                lines.append(f"\n  [{app_name}] {name}")
                if label and label != name:
                    lines.append(f"    Label: {label}")
                lines.append(f"    Sharing: {sharing}")
                if not is_visible:
                    lines.append("    (not a dashboard view)")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_dashboard(name: str, app: str = "search") -> str:
        """Get the XML definition of a Splunk dashboard.

        Args:
            name: Dashboard name/ID
            app: App context (default 'search')
        """
        client: SplunkClient = get_client()
        try:
            data = await client.get_dashboard(name=name, app=app)
            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})
            acl = entry.get("acl", {})
            label = content.get("label", name)
            xml_data = content.get("eai:data", "(no XML data)")
            # Truncate very long dashboards
            if len(xml_data) > 3000:
                xml_data = xml_data[:3000] + "\n... (truncated)"
            return (
                f"Dashboard: {name}\n"
                f"Label: {label}\n"
                f"App: {acl.get('app', app)}\n"
                f"Owner: {acl.get('owner', 'unknown')}\n"
                f"Sharing: {acl.get('sharing', 'unknown')}\n\n"
                f"XML Definition:\n{xml_data}"
            )
        except SplunkAPIError as e:
            return str(e)
