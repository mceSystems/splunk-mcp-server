from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient

# Maps friendly object type names to REST path templates.
_OBJECT_ENDPOINTS: dict[str, str] = {
    "dashboard":    "/servicesNS/-/{app}/data/ui/views/{name}",
    "saved_search": "/servicesNS/-/{app}/saved/searches/{name}",
    "macro":        "/servicesNS/-/{app}/configs/conf-macros/{name}",
    "lookup":       "/servicesNS/-/{app}/data/transforms/lookups/{name}",
    "eventtype":    "/servicesNS/-/{app}/saved/eventtypes/{name}",
    "report":       "/servicesNS/-/{app}/saved/searches/{name}",
    "app":          "/services/apps/local/{name}",
    "index":        "/services/data/indexes/{name}",
}


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_get_object_acl(
        object_type: str,
        name: str,
        app: str = "search",
    ) -> str:
        """Get the ACL (owner, sharing, read/write roles) for a named Splunk object.

        Args:
            object_type: One of: dashboard, saved_search, report (alias for saved_search), macro, lookup, eventtype, app, index
            name: Object name
            app: App context (ignored for object_type='app' or 'index')
        """
        client: SplunkClient = get_client()
        key = object_type.lower().replace("-", "_").replace(" ", "_")
        if key not in _OBJECT_ENDPOINTS:
            valid = ", ".join(sorted(_OBJECT_ENDPOINTS))
            return f"Unknown object_type '{object_type}'. Valid types: {valid}"
        path = _OBJECT_ENDPOINTS[key].format(app=app, name=name)
        try:
            data = await client.get_raw(path)
            entry = data.get("entry", [{}])[0]
            acl = entry.get("acl", {})
            if not acl:
                return f"No ACL data found for {object_type} '{name}' in app '{app}'."
            perms = acl.get("perms", {}) or {}
            read_roles = perms.get("read", []) or []
            write_roles = perms.get("write", []) or []
            return (
                f"ACL for {object_type} '{name}':\n"
                f"  Owner:   {acl.get('owner', 'nobody')}\n"
                f"  App:     {acl.get('app', 'unknown')}\n"
                f"  Sharing: {acl.get('sharing', 'unknown')}\n"
                f"  Read:    {', '.join(read_roles) if read_roles else '(none)'}\n"
                f"  Write:   {', '.join(write_roles) if write_roles else '(none)'}\n"
                f"  Can change perms: {acl.get('can_change_perms', False)}  |  "
                f"Removable: {acl.get('removable', False)}"
            )
        except SplunkAPIError as e:
            return str(e)
