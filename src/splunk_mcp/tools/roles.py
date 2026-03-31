from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_roles(count: int = 100) -> str:
        """List Splunk authorization roles.

        Args:
            count: Maximum number of roles to return (default 100)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_roles(count=count)
            entries = data.get("entry", [])
            if not entries:
                return "No roles found."
            lines = [f"Found {len(entries)} role(s):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                inherited = content.get("imported_roles", [])
                capabilities = content.get("capabilities", [])
                srch_indexes_allowed = content.get("srchIndexesAllowed", [])
                srch_indexes_default = content.get("srchIndexesDefault", [])
                srch_disk_quota = content.get("srchDiskQuota", "unknown")
                srch_jobs_quota = content.get("srchJobsQuota", "unknown")
                lines.append(f"\n  {name}")
                if inherited:
                    lines.append(f"    Inherits: {', '.join(inherited)}")
                if srch_indexes_allowed:
                    lines.append(f"    Indexes (allowed): {', '.join(srch_indexes_allowed)}")
                if srch_indexes_default:
                    lines.append(f"    Indexes (default): {', '.join(srch_indexes_default)}")
                lines.append(f"    Disk Quota: {srch_disk_quota} MB  |  Job Quota: {srch_jobs_quota}")
                if capabilities:
                    lines.append(f"    Capabilities ({len(capabilities)}): {', '.join(capabilities[:8])}" +
                                 (" ..." if len(capabilities) > 8 else ""))
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_role(name: str) -> str:
        """Get full details for a specific Splunk role including all capabilities.

        Args:
            name: Role name (e.g. 'admin', 'power', 'user')
        """
        client: SplunkClient = get_client()
        try:
            data = await client.get_role(name=name)
            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})
            capabilities = content.get("capabilities", [])
            imported_roles = content.get("imported_roles", [])
            imported_capabilities = content.get("imported_capabilities", [])
            srch_indexes_allowed = content.get("srchIndexesAllowed", [])
            srch_indexes_default = content.get("srchIndexesDefault", [])
            lines = [
                f"Role: {name}",
                f"Inherited Roles: {', '.join(imported_roles) if imported_roles else '(none)'}",
                f"Search Indexes (allowed): {', '.join(srch_indexes_allowed) if srch_indexes_allowed else '(none)'}",
                f"Search Indexes (default): {', '.join(srch_indexes_default) if srch_indexes_default else '(none)'}",
                f"Search Disk Quota: {content.get('srchDiskQuota', 'unknown')} MB",
                f"Search Job Quota: {content.get('srchJobsQuota', 'unknown')}",
                f"Real-time Search Job Quota: {content.get('rtSrchJobsQuota', 'unknown')}",
                f"Search Filter: {content.get('srchFilter', '(none)')}",
                f"Search Time Win: {content.get('srchTimeWin', 'unlimited')} s",
                f"\nCapabilities ({len(capabilities)}):",
            ]
            for cap in sorted(capabilities):
                lines.append(f"  + {cap}")
            if imported_capabilities:
                lines.append(f"\nInherited Capabilities ({len(imported_capabilities)}):")
                for cap in sorted(imported_capabilities):
                    lines.append(f"  ~ {cap}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)
