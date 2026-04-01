from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from ..client import SplunkAPIError, SplunkTimeoutError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_indexes(
        count: int = 100,
        include_internal: bool = False,
        time_window: str = "-7d",
    ) -> str:
        """List Splunk indexes that had events within the given time window.

        Uses SPL-based discovery (index=* | stats by index) rather than the REST
        /services/data/indexes endpoint, which only returns indexes the user owns.
        Note: indexes that exist but have no events in the time window will not appear.
        Enriches results with REST metadata (size, retention, status) where accessible.

        Args:
            count: Maximum number of indexes to return, sorted by event volume (default 100)
            include_internal: Include internal indexes like _internal, _audit (default False)
            time_window: Lookback window for SPL discovery, e.g. '-7d', '-24h', '-30d' (default '-7d')
        """
        client: SplunkClient = get_client()
        try:
            count = max(1, int(count))
            index_filter = "index=*" if include_internal else "index=* NOT (index=_*)"
            spl = (
                f"{index_filter} "
                f"| stats count as event_count by index "
                f"| sort - event_count "
                f"| head {count}"
            )
            result = await client.search_and_wait(
                query=spl,
                earliest_time=time_window,
                latest_time="now",
                max_count=count,
            )
            rows = result.get("results", [])
            if not rows:
                return (
                    f"No indexes with events in the last {time_window} were found. "
                    "Indexes may exist but have no data in this window, or may be "
                    "excluded by the current filters (e.g. internal indexes)."
                )

            # Best-effort REST enrichment for metadata (size, retention, status)
            meta: dict[str, dict[str, Any]] = {}
            try:
                # Use count=0 (unlimited) so REST metadata covers all discovered indexes
                # regardless of how REST sorts its results vs SPL event volume ordering
                rest_data = await client.list_indexes(count=0, include_internal=include_internal)
                for entry in rest_data.get("entry", []):
                    name = entry.get("name", "")
                    c = entry.get("content", {})
                    frozen_secs = c.get("frozenTimePeriodInSecs", 0)
                    meta[name] = {
                        "disabled": c.get("disabled", False),
                        "current_size_mb": c.get("currentDBSizeMB", "unknown"),
                        "max_size_mb": c.get("maxTotalDataSizeMB", "unknown"),
                        "retention_days": int(frozen_secs) // 86400 if isinstance(frozen_secs, (int, float)) else "unknown",
                    }
            except (SplunkAPIError, SplunkTimeoutError, httpx.HTTPError):
                pass

            lines = [f"Found {len(rows)} index(es) with events in the last {time_window} (sorted by volume):"]
            for row in rows:
                name = row.get("index", "unknown")
                event_count = row.get("event_count", "unknown")
                m = meta.get(name, {})

                try:
                    event_count_fmt = f"{int(event_count):,}"
                except (ValueError, TypeError):
                    event_count_fmt = str(event_count)

                disabled = m.get("disabled", False)
                lines.append(f"\n  {name}" + (" [disabled]" if disabled else ""))
                lines.append(f"    Events ({time_window}): {event_count_fmt}")
                size = m.get("current_size_mb", "unknown")
                max_size = m.get("max_size_mb", "unknown")
                retention = m.get("retention_days", "unknown")
                if size != "unknown":
                    lines.append(f"    Size: {size} MB / {max_size} MB max")
                if retention != "unknown":
                    lines.append(f"    Retention: {retention} days")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)
        except SplunkTimeoutError as e:
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
