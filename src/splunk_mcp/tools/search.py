from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError, SplunkTimeoutError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def _format_results(data: dict[str, Any], max_results: int) -> str:
    results = data.get("results", [])
    if not results:
        return "No results found."
    count = len(results)
    lines = [f"Found {count} result(s) (showing up to {max_results}):"]
    for i, row in enumerate(results[:max_results], 1):
        lines.append(f"\n--- Result {i} ---")
        for k, v in row.items():
            if not k.startswith("__"):
                lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_search(
        query: str,
        earliest_time: str = "-24h",
        latest_time: str = "now",
        max_results: int = 100,
    ) -> str:
        """Run a Splunk search query and wait for results.

        Args:
            query: SPL search query (e.g. 'index=main error | stats count by host')
            earliest_time: Start of time range (e.g. '-24h', '-7d', '2024-01-01T00:00:00')
            latest_time: End of time range (e.g. 'now', '-1h', '2024-01-02T00:00:00')
            max_results: Maximum number of results to return (default 100)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.search_and_wait(
                query=query,
                earliest_time=earliest_time,
                latest_time=latest_time,
                max_count=max_results,
            )
            return _format_results(data, max_results)
        except SplunkAPIError as e:
            return str(e)
        except SplunkTimeoutError as e:
            return str(e)

    @mcp.tool()
    async def splunk_search_export(
        query: str,
        earliest_time: str = "-24h",
        latest_time: str = "now",
        max_results: int = 1000,
    ) -> str:
        """Run a Splunk search using the streaming export endpoint (better for large result sets).

        Args:
            query: SPL search query
            earliest_time: Start of time range
            latest_time: End of time range
            max_results: Maximum number of results to return (default 1000)
        """
        client: SplunkClient = get_client()
        try:
            results = await client.search_export(
                query=query,
                earliest_time=earliest_time,
                latest_time=latest_time,
                max_count=max_results,
            )
            if not results:
                return "No results found."
            lines = [f"Found {len(results)} result(s):"]
            for i, row in enumerate(results[:max_results], 1):
                lines.append(f"\n--- Result {i} ---")
                for k, v in row.items():
                    if not k.startswith("__"):
                        lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)
        except SplunkTimeoutError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_job_status(sid: str) -> str:
        """Get the status of a Splunk search job by its SID.

        Args:
            sid: Search job ID returned by a previous search call
        """
        client: SplunkClient = get_client()
        try:
            content = await client.get_job_status(sid)
            return (
                f"SID: {sid}\n"
                f"State: {content.get('dispatchState', 'unknown')}\n"
                f"Progress: {float(content.get('doneProgress', 0)) * 100:.1f}%\n"
                f"Event Count: {content.get('eventCount', 0)}\n"
                f"Result Count: {content.get('resultCount', 0)}\n"
                f"Scan Count: {content.get('scanCount', 0)}"
            )
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_job_results(
        sid: str,
        count: int = 100,
        offset: int = 0,
    ) -> str:
        """Fetch results from a completed Splunk search job.

        Args:
            sid: Search job ID
            count: Number of results to fetch (default 100)
            offset: Result offset for pagination (default 0)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.get_job_results(sid, count=count, offset=offset)
            return _format_results(data, count)
        except SplunkAPIError as e:
            return str(e)
