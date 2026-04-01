from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError, SplunkTimeoutError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_indexes(
        count: int = 100,
        include_internal: bool = False,
    ) -> str:
        """List Splunk indexes searchable by the current user.

        Uses SPL-based discovery (index=* | stats by index) over the last 7 days,
        which reliably returns all indexes the user can search — unlike the REST
        /services/data/indexes endpoint, which only returns indexes the user owns.

        Results include event count from the past 7 days plus available REST metadata
        (size, retention, enabled status) where accessible.

        Args:
            count: Maximum number of indexes to return, sorted by event volume (default 100)
            include_internal: Include internal Splunk indexes like _internal, _audit (default False)
        """
        client: SplunkClient = get_client()
        try:
            index_filter = "index=*" if include_internal else "index=* NOT (index=_*)"
            spl = (
                f"{index_filter} earliest=-7d latest=now "
                f"| stats count as event_count_7d by index "
                f"| sort - event_count_7d "
                f"| head {count}"
            )
            result = await client.search_and_wait(
                query=spl,
                earliest_time="-7d",
                latest_time="now",
                max_count=count,
            )
            rows = result.get("results", [])
            if not rows:
                return "No indexes found."

            # Phase 2: best-effort REST enrichment for metadata (size, retention, status)
            meta: dict[str, dict[str, Any]] = {}
            try:
                rest_data = await client.list_indexes(count=500, include_internal=include_internal)
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
            except Exception:
                pass  # mcp_user may not have REST metadata access — that's fine

            lines = [f"Found {len(rows)} index(es) (sorted by 7-day event volume):"]
            for row in rows:
                name = row.get("index", "unknown")
                event_count = row.get("event_count_7d", "unknown")
                m = meta.get(name, {})
                disabled = m.get("disabled", False)
                status = "disabled" if disabled else "enabled"
                size = m.get("current_size_mb", "unknown")
                max_size = m.get("max_size_mb", "unknown")
                retention = m.get("retention_days", "unknown")

                try:
                    event_count_fmt = f"{int(event_count):,}"
                except (ValueError, TypeError):
                    event_count_fmt = str(event_count)

                lines.append(f"\n  {name}" + (f" [{status}]" if disabled else ""))
                lines.append(f"    Events (7d): {event_count_fmt}")
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
    async def splunk_count_indexes(time_window: str = "-7d") -> str:
        """Return the total count of distinct indexes searchable by the current user.

        Faster than splunk_list_indexes when only the count is needed.

        Args:
            time_window: Lookback window for SPL discovery (default '-7d')
        """
        client: SplunkClient = get_client()
        try:
            spl = f"index=* earliest={time_window} latest=now | stats dc(index) as total_indexes"
            result = await client.search_and_wait(
                query=spl,
                earliest_time=time_window,
                latest_time="now",
                max_count=1,
            )
            rows = result.get("results", [])
            if not rows:
                return "Could not determine index count."
            total = rows[0].get("total_indexes", 0)
            return f"Total searchable indexes: {total} (discovered over {time_window} window)"
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
