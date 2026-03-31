from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..client import SplunkAPIError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from ..client import SplunkClient


def register(mcp: "FastMCP", get_client: Any) -> None:

    @mcp.tool()
    async def splunk_list_kvstore_collections(app: str = "search") -> str:
        """List KV Store collections in a Splunk app.

        Args:
            app: App name (default 'search')
        """
        client: SplunkClient = get_client()
        try:
            data = await client.list_kvstore_collections(app=app)
            entries = data.get("entry", [])
            if not entries:
                return f"No KV Store collections found in app '{app}'."
            lines = [f"Found {len(entries)} KV Store collection(s) in '{app}':"]
            for entry in entries:
                name = entry.get("name", "unknown")
                content = entry.get("content", {})
                # Extract field definitions
                fields = {k: v for k, v in content.items() if k.startswith("field.")}
                accelerated = content.get("accelerated_fields", {})
                lines.append(f"\n  {name}")
                if fields:
                    lines.append(f"    Fields: {', '.join(k[6:] for k in fields)}")
                if accelerated:
                    lines.append(f"    Accelerated fields: {', '.join(accelerated.keys())}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)

    @mcp.tool()
    async def splunk_query_kvstore(
        app: str,
        collection: str,
        query_filter: str = "{}",
        count: int = 100,
    ) -> str:
        """Query records from a Splunk KV Store collection.

        Args:
            app: App name containing the collection
            collection: Collection name to query
            query_filter: MongoDB-style JSON filter (default '{}' returns all records)
            count: Maximum number of records to return (default 100)
        """
        client: SplunkClient = get_client()
        try:
            # Validate JSON filter
            try:
                json.loads(query_filter)
            except json.JSONDecodeError as e:
                return f"Invalid query_filter JSON: {e}"

            records = await client.query_kvstore(
                app=app,
                collection=collection,
                query_filter=query_filter,
                count=count,
            )
            if not records:
                return f"No records found in '{collection}' matching filter: {query_filter}"
            lines = [f"Found {len(records)} record(s) in '{app}/{collection}':"]
            for i, record in enumerate(records[:count], 1):
                lines.append(f"\n--- Record {i} ---")
                for k, v in record.items():
                    lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        except SplunkAPIError as e:
            return str(e)
