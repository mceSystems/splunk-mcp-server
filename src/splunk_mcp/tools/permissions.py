from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient

# Maps friendly object type names to REST path templates.
# {app} and {name} are substituted at call time.
_OBJECT_ENDPOINTS: dict[str, str] = {
    "dashboard":     "/servicesNS/-/{app}/data/ui/views/{name}",
    "saved_search":  "/servicesNS/-/{app}/saved/searches/{name}",
    "macro":         "/servicesNS/-/{app}/configs/conf-macros/{name}",
    "lookup":        "/servicesNS/-/{app}/data/transforms/lookups/{name}",
    "eventtype":     "/servicesNS/-/{app}/saved/eventtypes/{name}",
    "report":        "/servicesNS/-/{app}/saved/searches/{name}",  # alias
    "app":           "/services/apps/local/{name}",
    "index":         "/services/data/indexes/{name}",
}


def _acl_summary(acl: dict[str, Any]) -> str:
    owner = acl.get("owner", "nobody")
    app = acl.get("app", "unknown")
    sharing = acl.get("sharing", "unknown")
    perms = acl.get("perms", {}) or {}
    read_roles = perms.get("read", []) or []
    write_roles = perms.get("write", []) or []
    removable = acl.get("removable", False)
    modifiable = acl.get("can_change_perms", False)

    lines = [
        f"  Owner:   {owner}",
        f"  App:     {app}",
        f"  Sharing: {sharing}",
        f"  Read:    {', '.join(read_roles) if read_roles else '(none)'}",
        f"  Write:   {', '.join(write_roles) if write_roles else '(none)'}",
        f"  Can change perms: {modifiable}  |  Removable: {removable}",
    ]
    return "\n".join(lines)


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_get_object_acl(
        object_type: str,
        name: str,
        app: str = "search",
    ) -> str:
        """Get the ACL (owner, sharing, read/write roles) for a named Splunk object.

        Args:
            object_type: One of: dashboard, saved_search, macro, lookup, eventtype, app, index
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
            return f"ACL for {object_type} '{name}':\n{_acl_summary(acl)}"
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_check_user_permissions(username: str) -> str:
        """Show a user's effective permissions: roles, capabilities, and index access.

        Flattens all roles (including inherited) to give a complete picture of what
        the user can actually do.

        Args:
            username: Splunk username
        """
        client: SplunkClient = get_client()
        try:
            user_data = await client.get_user(username)
            user_entry = user_data.get("entry", [{}])[0]
            user_content = user_entry.get("content", {})
            roles = user_content.get("roles", [])

            if not roles:
                return f"User '{username}' has no roles assigned."

            # Fetch each role to collect capabilities and index access
            all_capabilities: set[str] = set()
            all_indexes_allowed: set[str] = set()
            all_indexes_default: set[str] = set()
            role_details: list[str] = []

            for role_name in roles:
                try:
                    role_data = await client.get_role(role_name)
                    role_entry = role_data.get("entry", [{}])[0]
                    rc = role_entry.get("content", {})
                    caps = set(rc.get("capabilities", []))
                    imported_caps = set(rc.get("imported_capabilities", []))
                    idx_allowed = set(rc.get("srchIndexesAllowed", []))
                    idx_default = set(rc.get("srchIndexesDefault", []))
                    all_capabilities |= caps | imported_caps
                    all_indexes_allowed |= idx_allowed
                    all_indexes_default |= idx_default
                    role_details.append(
                        f"  {role_name}: {len(caps)} direct + {len(imported_caps)} inherited caps, "
                        f"indexes: {', '.join(sorted(idx_allowed)) or '(none)'}"
                    )
                except SplunkAPIError:
                    role_details.append(f"  {role_name}: (could not fetch role details)")

            lines = [
                f"User: {username}",
                f"Real Name: {user_content.get('realname', '(not set)')}",
                f"Email: {user_content.get('email', '(not set)')}",
                f"Locked: {user_content.get('locked-out', False)}",
                f"Default App: {user_content.get('defaultApp', '(not set)')}",
                f"\nAssigned Roles ({len(roles)}):",
            ]
            lines.extend(role_details)
            lines += [
                f"\nEffective Index Access:",
                f"  Allowed: {', '.join(sorted(all_indexes_allowed)) or '(none)'}",
                f"  Default: {', '.join(sorted(all_indexes_default)) or '(none)'}",
                f"\nEffective Capabilities ({len(all_capabilities)}):",
            ]
            for cap in sorted(all_capabilities):
                lines.append(f"  + {cap}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_diagnose_access(
        username: str,
        object_type: str,
        name: str,
        app: str = "search",
    ) -> str:
        """Diagnose whether a user can access a specific Splunk object and explain why.

        Checks sharing level, object ACL read/write roles, and whether the user's
        roles overlap with the allowed roles.

        Args:
            username: Splunk username to check
            object_type: One of: dashboard, saved_search, macro, lookup, eventtype, app, index
            name: Object name
            app: App context (ignored for object_type='app' or 'index')
        """
        client: SplunkClient = get_client()
        key = object_type.lower().replace("-", "_").replace(" ", "_")
        if key not in _OBJECT_ENDPOINTS:
            valid = ", ".join(sorted(_OBJECT_ENDPOINTS))
            return f"Unknown object_type '{object_type}'. Valid types: {valid}"

        try:
            # Fetch user
            user_data = await client.get_user(username)
            user_entry = user_data.get("entry", [{}])[0]
            user_content = user_entry.get("content", {})
            user_roles = set(user_content.get("roles", []))
            locked = user_content.get("locked-out", False)
        except SplunkAPIError as e:
            return f"Could not fetch user '{username}': {e}"

        # Fetch object ACL
        path = _OBJECT_ENDPOINTS[key].format(app=app, name=name)
        try:
            obj_data = await client.get_raw(path)
            entry = obj_data.get("entry", [{}])[0]
            acl = entry.get("acl", {}) or {}
        except SplunkAPIError as e:
            return f"Could not fetch {object_type} '{name}': {e}"

        owner = acl.get("owner", "nobody")
        sharing = acl.get("sharing", "user")
        perms = acl.get("perms", {}) or {}
        read_roles = set(perms.get("read", []) or [])
        write_roles = set(perms.get("write", []) or [])
        obj_app = acl.get("app", app)

        lines = [
            f"Access diagnosis: user='{username}'  {object_type}='{name}'  app='{obj_app}'",
            f"{'='*60}",
        ]

        # Locked check
        if locked:
            lines.append("BLOCKED: User account is locked out.")
            return "\n".join(lines)

        # Sharing check
        lines.append(f"\nObject sharing: {sharing}")
        if sharing == "user":
            if owner == username:
                lines.append("  Owner match — user owns this object (private).")
                can_read = True
            else:
                lines.append(f"  Private object owned by '{owner}'. Only the owner can access it.")
                can_read = False
            return "\n".join(lines + [f"\nVerdict: {'ALLOWED (owner)' if can_read else 'BLOCKED (private)'}"])

        if sharing == "app":
            lines.append(f"  App-scoped to '{obj_app}'. User must be in a role with access to this app.")
        elif sharing == "global":
            lines.append("  Global sharing — visible across all apps.")

        # Role overlap check
        lines.append(f"\nUser roles: {', '.join(sorted(user_roles)) or '(none)'}")
        lines.append(f"Object read roles: {', '.join(sorted(read_roles)) or '(none)'}")
        lines.append(f"Object write roles: {', '.join(sorted(write_roles)) or '(none)'}")

        wildcard_read = "*" in read_roles
        wildcard_write = "*" in write_roles
        read_overlap = user_roles & read_roles
        write_overlap = user_roles & write_roles
        is_owner = owner == username

        can_read = bool(wildcard_read or read_overlap or is_owner)
        can_write = bool(wildcard_write or write_overlap or is_owner)

        lines.append(f"\nOwner: {owner}  (user is owner: {is_owner})")

        lines.append("\nRead access:")
        if wildcard_read:
            lines.append("  ALLOWED — read is open to all roles (*)")
        elif is_owner:
            lines.append("  ALLOWED — user is the owner")
        elif read_overlap:
            lines.append(f"  ALLOWED — matching roles: {', '.join(sorted(read_overlap))}")
        else:
            lines.append("  BLOCKED — user has none of the required read roles")
            if read_roles:
                missing = read_roles - user_roles
                lines.append(f"  Missing roles: {', '.join(sorted(missing))}")

        lines.append("Write access:")
        if wildcard_write:
            lines.append("  ALLOWED — write is open to all roles (*)")
        elif is_owner:
            lines.append("  ALLOWED — user is the owner")
        elif write_overlap:
            lines.append(f"  ALLOWED — matching roles: {', '.join(sorted(write_overlap))}")
        else:
            lines.append("  BLOCKED — user has none of the required write roles")
            if write_roles:
                missing = write_roles - user_roles
                lines.append(f"  Missing roles: {', '.join(sorted(missing))}")

        verdict = []
        if can_read:
            verdict.append("READ: ALLOWED")
        else:
            verdict.append("READ: BLOCKED")
        if can_write:
            verdict.append("WRITE: ALLOWED")
        else:
            verdict.append("WRITE: BLOCKED")
        lines.append(f"\nVerdict: {' | '.join(verdict)}")

        return "\n".join(lines)

    @mcp.tool()
    async def splunk_list_app_permissions(count: int = 100) -> str:
        """List all apps with their sharing and permission settings.

        Useful for understanding which apps are globally shared vs app-scoped vs private.

        Args:
            count: Maximum number of apps to return (default 100)
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_apps(count=count)
            entries = data.get("entry", [])
            if not entries:
                return "No apps found."
            lines = [f"Found {len(entries)} app(s) with permissions:"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                acl = entry.get("acl", {}) or {}
                perms = acl.get("perms", {}) or {}
                sharing = acl.get("sharing", "unknown")
                owner = acl.get("owner", "unknown")
                read_roles = perms.get("read", []) or []
                write_roles = perms.get("write", []) or []
                label = content.get("label", name)
                disabled = content.get("disabled", False)
                status = "disabled" if disabled else "enabled"
                lines.append(f"\n  {name} [{status}]  sharing={sharing}  owner={owner}")
                if label != name:
                    lines.append(f"    Label: {label}")
                lines.append(f"    Read:  {', '.join(read_roles) if read_roles else '(none)'}")
                lines.append(f"    Write: {', '.join(write_roles) if write_roles else '(none)'}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)
