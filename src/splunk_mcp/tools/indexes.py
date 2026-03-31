from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_indexes(
        count: int = 100,
        include_internal: bool = False,
    ) -> str:
        """List all Splunk indexes.

        Args:
            count: Maximum number of indexes to return (default 100)
            include_internal: Include internal Splunk indexes like _internal, _audit (default False)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_indexes(count=count, include_internal=include_internal)
            entries = data.get("entry", [])
            if not entries:
                return "No indexes found."
            lines = [f"Found {len(entries)} index(es):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                total_event_count = content.get("totalEventCount", "unknown")
                current_db_size_mb = content.get("currentDBSizeMB", "unknown")
                max_total_data_size_mb = content.get("maxTotalDataSizeMB", "unknown")
                frozen_time_period = content.get("frozenTimePeriodInSecs", "unknown")
                disabled = content.get("disabled", False)
                status = "disabled" if disabled else "enabled"
                lines.append(
                    f"\n  {name} [{status}]\n"
                    f"    Events: {total_event_count:,}" if isinstance(total_event_count, int)
                    else f"\n  {name} [{status}]\n"
                    f"    Events: {total_event_count}"
                )
                lines.append(f"    Size: {current_db_size_mb} MB / {max_total_data_size_mb} MB max")
                if isinstance(frozen_time_period, int):
                    days = frozen_time_period // 86400
                    lines.append(f"    Retention: {days} days")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_index_info(name: str) -> str:
        """Get detailed information about a specific Splunk index.

        Args:
            name: Index name (e.g. 'main', 'security', '_internal')
        """
        client: SplunkClient = get_client()
        try:
            data = await client.get_index(name)
            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})
            frozen_secs = content.get("frozenTimePeriodInSecs", 0)
            retention_days = int(frozen_secs) // 86400 if isinstance(frozen_secs, (int, float)) else "unknown"
            return (
                f"Index: {name}\n"
                f"Enabled: {not content.get('disabled', False)}\n"
                f"Events: {content.get('totalEventCount', 'unknown')}\n"
                f"Current Size: {content.get('currentDBSizeMB', 'unknown')} MB\n"
                f"Max Size: {content.get('maxTotalDataSizeMB', 'unknown')} MB\n"
                f"Retention: {retention_days} days\n"
                f"Home Path: {content.get('homePath', 'unknown')}\n"
                f"Cold Path: {content.get('coldPath', 'unknown')}\n"
                f"Thawed Path: {content.get('thawedPath', 'unknown')}\n"
                f"Replicated: {content.get('isReady', 'unknown')}"
            )
        except SplunkAPIError as e:
            return str(e)
