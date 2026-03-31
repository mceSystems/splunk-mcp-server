from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_macros(
        count: int = 100,
        offset: int = 0,
        app: str = "",
    ) -> str:
        """List Splunk search macros.

        Args:
            count: Maximum number of macros to return (default 100)
            offset: Offset for pagination (default 0)
            app: Filter by app name (e.g. 'search'). Empty returns all.
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_macros(count=count, offset=offset, app=app)
            entries = data.get("entry", [])
            if not entries:
                return "No macros found."
            lines = [f"Found {len(entries)} macro(s):"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                app_name = entry.get("acl", {}).get("app", "unknown")
                definition = content.get("definition", "")
                args = content.get("args", "")
                arg_count = content.get("iseval", "")
                lines.append(f"\n  [{app_name}] `{name}`")
                if args:
                    lines.append(f"    Args: {args}")
                if definition:
                    short = definition[:120] + "..." if len(definition) > 120 else definition
                    lines.append(f"    Definition: {short}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_get_macro(name: str, app: str = "search") -> str:
        """Get the definition of a specific Splunk search macro.

        Args:
            name: Macro name (without backticks). For argument macros include the arg count,
                  e.g. 'mymacro(2)' for a 2-argument macro.
            app: App context (default 'search')
        """
        client: SplunkClient = get_client()
        try:
            data = await client.get_macro(name=name, app=app)
            entry = data.get("entry", [{}])[0]
            content = entry.get("content", {})
            acl = entry.get("acl", {})
            return (
                f"Macro: `{name}`\n"
                f"App: {acl.get('app', app)}\n"
                f"Owner: {acl.get('owner', 'unknown')}\n"
                f"Sharing: {acl.get('sharing', 'unknown')}\n"
                f"Args: {content.get('args', '(none)')}\n"
                f"Is Eval: {content.get('iseval', False)}\n"
                f"Validation: {content.get('validation', '(none)')}\n"
                f"Error Msg: {content.get('errormsg', '(none)')}\n\n"
                f"Definition:\n{content.get('definition', '(empty)')}"
            )
        except SplunkAPIError as e:
            return str(e)
