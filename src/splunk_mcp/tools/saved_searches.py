from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_saved_searches(
        count: int = 50,
        offset: int = 0,
        app: str = "",
    ) -> str:
        """List saved searches in Splunk.

        Args:
            count: Maximum number of saved searches to return (default 50)
            offset: Offset for pagination (default 0)
            app: Filter by app name (e.g. 'search', 'splunk_security_essentials'). Empty returns all.
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_saved_searches(count=count, offset=offset, app=app)
            entries = data.get("entry", [])
            if not entries:
                return "No saved searches found."
            lines = [f"Found {len(entries)} saved search(es):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                app_name = entry.get("acl", {}).get("app", "unknown")
                search = content.get("search", "")
                cron = content.get("cron_schedule", "")
                alert_type = content.get("alert_type", "")
                lines.append(f"\n  [{app_name}] {name}")
                if search:
                    short_search = search[:120] + "..." if len(search) > 120 else search
                    lines.append(f"    Search: {short_search}")
                if cron:
                    lines.append(f"    Schedule: {cron}")
                if alert_type and alert_type != "always":
                    lines.append(f"    Alert: {alert_type}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_saved_search(name: str, app: str = "search") -> str:
        """Get details of a specific saved search.

        Args:
            name: Name of the saved search
            app: App context (default 'search')
        """
        client: SplunkClient = get_client()
        try:
            data = await client.get_saved_search(name=name, app=app)
            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})
            return (
                f"Name: {name}\n"
                f"App: {entry.get('acl', {}).get('app', app)}\n"
                f"Owner: {entry.get('acl', {}).get('owner', 'unknown')}\n"
                f"Search: {content.get('search', 'unknown')}\n"
                f"Earliest: {content.get('dispatch.earliest_time', 'not set')}\n"
                f"Latest: {content.get('dispatch.latest_time', 'not set')}\n"
                f"Schedule: {content.get('cron_schedule', 'not scheduled')}\n"
                f"Alert Type: {content.get('alert_type', 'none')}\n"
                f"Alert Condition: {content.get('alert_condition', 'none')}\n"
                f"Actions: {content.get('actions', 'none')}"
            )
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_run_saved_search(
        name: str,
        app: str = "search",
        earliest_time: str = "",
        latest_time: str = "",
    ) -> str:
        """Dispatch (run) a saved search and return the job SID.

        Args:
            name: Name of the saved search to run
            app: App context (default 'search')
            earliest_time: Override earliest time (e.g. '-24h'). Empty uses saved search default.
            latest_time: Override latest time (e.g. 'now'). Empty uses saved search default.
        """
        client: SplunkClient = get_client()
        try:
            data = await client.dispatch_saved_search(
                name=name, app=app, earliest_time=earliest_time, latest_time=latest_time
            )
            sid = data.get("sid", "unknown")
            return (
                f"Saved search '{name}' dispatched successfully.\n"
                f"Job SID: {sid}\n"
                f"Use splunk_get_job_status(sid='{sid}') to check progress.\n"
                f"Use splunk_get_job_results(sid='{sid}') to fetch results when done."
            )
        except SplunkAPIError as e:
            return str(e)
