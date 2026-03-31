from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_users(count: int = 100, offset: int = 0) -> str:
        """List Splunk users.

        Args:
            count: Maximum number of users to return (default 100)
            offset: Offset for pagination (default 0)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_users(count=count, offset=offset)
            entries = data.get("entry", [])
            if not entries:
                return "No users found."
            lines = [f"Found {len(entries)} user(s):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                real_name = content.get("realname", "")
                email = content.get("email", "")
                roles = content.get("roles", [])
                default_app = content.get("defaultApp", "")
                locked = content.get("locked-out", False)
                status = " [LOCKED]" if locked else ""
                lines.append(f"\n  {name}{status}")
                if real_name:
                    lines.append(f"    Name: {real_name}")
                if email:
                    lines.append(f"    Email: {email}")
                if roles:
                    lines.append(f"    Roles: {', '.join(roles)}")
                if default_app:
                    lines.append(f"    Default App: {default_app}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_user(username: str) -> str:
        """Get details for a specific Splunk user.

        Args:
            username: Splunk username
        """
        client: SplunkClient = get_client()
        try:
            data = await client.get_user(username=username)
            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})
            roles = content.get("roles", [])
            capabilities = content.get("capabilities", [])
            return (
                f"Username: {username}\n"
                f"Real Name: {content.get('realname', '(not set)')}\n"
                f"Email: {content.get('email', '(not set)')}\n"
                f"Default App: {content.get('defaultApp', '(not set)')}\n"
                f"Timezone: {content.get('tz', '(not set)')}\n"
                f"Locked: {content.get('locked-out', False)}\n"
                f"Roles: {', '.join(roles) if roles else '(none)'}\n"
                f"Capabilities: {', '.join(capabilities) if capabilities else '(none)'}"
            )
        except SplunkAPIError as e:
            return str(e)
