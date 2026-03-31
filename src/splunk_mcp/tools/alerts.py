from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_fired_alerts(count: int = 50) -> str:
        """List recently fired Splunk alerts.

        Args:
            count: Maximum number of fired alerts to return (default 50)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_fired_alerts(count=count)
            entries = data.get("entry", [])
            if not entries:
                return "No fired alerts found."
            lines = [f"Found {len(entries)} fired alert(s):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                triggered_alerts = content.get("triggered_alert_count", 0)
                lines.append(f"\n  Alert: {name}")
                lines.append(f"    Triggered Count: {triggered_alerts}")
                # Try to get sub-entries (individual triggers)
                triggered = content.get("triggered_alerts", [])
                if isinstance(triggered, list):
                    for t in triggered[:5]:
                        trigger_time = t.get("trigger_time_rendered", t.get("trigger_time", "unknown"))
                        severity = t.get("severity", "unknown")
                        lines.append(f"    - Fired at: {trigger_time} (severity: {severity})")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)
