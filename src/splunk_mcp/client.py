from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class SplunkAPIError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Splunk API error (HTTP {status_code}): {message}")


class SplunkTimeoutError(Exception):
    def __init__(self, max_wait: float, sid: str = ""):
        self.max_wait = max_wait
        self.sid = sid
        msg = f"Search timed out after {max_wait:.0f}s"
        if sid:
            msg += f". Job is still running — poll status with SID '{sid}'"
        super().__init__(msg)


class SplunkClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        base_url = f"https://{settings.splunk_host}:{settings.splunk_port}"
        if not settings.splunk_verify_ssl:
            logger.warning("SSL verification disabled — connections to Splunk are not verified")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {settings.splunk_token}",
            },
            params={"output_mode": "json"},
            verify=settings.splunk_verify_ssl,
            timeout=settings.splunk_timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "SplunkClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                body = response.json()
                messages = body.get("messages", [])
                text = "; ".join(m.get("text", "") for m in messages) if messages else response.text[:200]
            except Exception:
                text = response.text[:200]
            raise SplunkAPIError(response.status_code, text)

    # ── Search ──────────────────────────────────────────────────────────────

    async def create_search_job(
        self,
        query: str,
        earliest_time: str = "-24h",
        latest_time: str = "now",
    ) -> str:
        """Returns the search job SID."""
        # Generating commands (e.g. | tstats, | inputlookup) must be the first
        # command and must not be prefixed with "search".
        search_query = query if (query.startswith("search ") or query.startswith("|")) else f"search {query}"
        response = await self._client.post(
            "/services/search/jobs",
            data={
                "search": search_query,
                "earliest_time": earliest_time,
                "latest_time": latest_time,
            },
        )
        self._raise_for_status(response)
        return response.json()["sid"]

    async def get_job_status(self, sid: str) -> dict[str, Any]:
        response = await self._client.get(f"/services/search/jobs/{sid}")
        self._raise_for_status(response)
        entry = response.json()["entry"][0]
        return entry["content"]

    async def get_job_results(
        self, sid: str, count: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        response = await self._client.get(
            f"/services/search/jobs/{sid}/results",
            params={"count": count, "offset": offset},
        )
        self._raise_for_status(response)
        return response.json()

    async def delete_job(self, sid: str) -> None:
        try:
            response = await self._client.delete(f"/services/search/jobs/{sid}")
            self._raise_for_status(response)
        except Exception:
            logger.debug("Failed to delete search job %s", sid)

    async def search_and_wait(
        self,
        query: str,
        earliest_time: str = "-24h",
        latest_time: str = "now",
        max_count: int = 100,
        max_wait: float | None = None,
    ) -> dict[str, Any]:
        if max_wait is None:
            max_wait = self._settings.splunk_max_wait

        sid = await self.create_search_job(query, earliest_time, latest_time)
        elapsed = 0.0
        interval = 0.5
        max_interval = 5.0
        timed_out = False

        try:
            while elapsed < max_wait:
                await asyncio.sleep(interval)
                elapsed += interval
                interval = min(interval * 1.5, max_interval)

                status = await self.get_job_status(sid)
                dispatch_state = status.get("dispatchState", "")

                if dispatch_state in ("DONE", "FAILED", "FINALIZED"):
                    break
            else:
                timed_out = True
                raise SplunkTimeoutError(max_wait, sid)

            if dispatch_state in ("FAILED",):
                raise SplunkAPIError(500, f"Search job failed: {status.get('messages', '')}")

            return await self.get_job_results(sid, count=max_count)
        finally:
            if not timed_out:
                await self.delete_job(sid)

    async def search_export(
        self,
        query: str,
        earliest_time: str = "-24h",
        latest_time: str = "now",
        max_count: int = 1000,
    ) -> list[dict[str, Any]]:
        # Generating commands (e.g. | tstats, | inputlookup) must be the first
        # command and must not be prefixed with "search".
        search_query = query if (query.startswith("search ") or query.startswith("|")) else f"search {query}"
        response = await self._client.post(
            "/services/search/jobs/export",
            data={
                "search": search_query,
                "earliest_time": earliest_time,
                "latest_time": latest_time,
                "count": max_count,
            },
        )
        self._raise_for_status(response)
        results = []
        for line in response.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json
                obj = json.loads(line)
                if "result" in obj:
                    results.append(obj["result"])
            except Exception:
                pass
        return results

    # ── Saved Searches ───────────────────────────────────────────────────────

    async def list_saved_searches(
        self, count: int = 50, offset: int = 0, app: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"count": count, "offset": offset}
        if app:
            params["search"] = f"eai:acl.app={app}"
        response = await self._client.get("/servicesNS/-/-/saved/searches", params=params)
        self._raise_for_status(response)
        return response.json()

    async def get_saved_search(self, name: str, app: str = "search") -> dict[str, Any]:
        response = await self._client.get(f"/servicesNS/-/{app}/saved/searches/{name}")
        self._raise_for_status(response)
        return response.json()

    async def dispatch_saved_search(
        self,
        name: str,
        app: str = "search",
        earliest_time: str = "",
        latest_time: str = "",
    ) -> dict[str, Any]:
        data: dict[str, str] = {}
        if earliest_time:
            data["dispatch.earliest_time"] = earliest_time
        if latest_time:
            data["dispatch.latest_time"] = latest_time
        response = await self._client.post(
            f"/servicesNS/-/{app}/saved/searches/{name}/dispatch", data=data
        )
        self._raise_for_status(response)
        return response.json()

    # ── Indexes ──────────────────────────────────────────────────────────────

    async def list_indexes(
        self, count: int = 100, include_internal: bool = False
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"count": count}
        if not include_internal:
            params["search"] = "isInternal=false"
        response = await self._client.get("/services/data/indexes", params=params)
        self._raise_for_status(response)
        return response.json()

    async def get_index(self, name: str) -> dict[str, Any]:
        response = await self._client.get(f"/services/data/indexes/{name}")
        self._raise_for_status(response)
        return response.json()

    # ── Alerts ───────────────────────────────────────────────────────────────

    async def list_fired_alerts(self, count: int = 50) -> dict[str, Any]:
        response = await self._client.get(
            "/services/alerts/fired_alerts", params={"count": count}
        )
        self._raise_for_status(response)
        return response.json()

    # ── Dashboards ───────────────────────────────────────────────────────────

    async def list_dashboards(self, count: int = 50, app: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {"count": count}
        response = await self._client.get("/servicesNS/-/-/data/ui/views", params=params)
        self._raise_for_status(response)
        data = response.json()
        if app:
            data["entry"] = [
                e for e in data.get("entry", []) if e.get("acl", {}).get("app") == app
            ]
        return data

    async def get_dashboard(self, name: str, app: str = "search") -> dict[str, Any]:
        response = await self._client.get(f"/servicesNS/-/{app}/data/ui/views/{name}")
        self._raise_for_status(response)
        return response.json()

    # ── Server Info ──────────────────────────────────────────────────────────

    async def get_server_info(self) -> dict[str, Any]:
        response = await self._client.get("/services/server/info")
        self._raise_for_status(response)
        return response.json()

    # ── Apps ─────────────────────────────────────────────────────────────────

    async def list_apps(self, count: int = 100) -> dict[str, Any]:
        response = await self._client.get("/services/apps/local", params={"count": count})
        self._raise_for_status(response)
        return response.json()

    # ── KV Store ─────────────────────────────────────────────────────────────

    async def list_kvstore_collections(self, app: str = "search") -> dict[str, Any]:
        response = await self._client.get(
            f"/servicesNS/-/{app}/storage/collections/config"
        )
        self._raise_for_status(response)
        return response.json()

    async def query_kvstore(
        self,
        app: str,
        collection: str,
        query_filter: str = "{}",
        count: int = 100,
    ) -> list[dict[str, Any]]:
        response = await self._client.get(
            f"/servicesNS/nobody/{app}/storage/collections/data/{collection}",
            params={"query": query_filter, "limit": count},
        )
        self._raise_for_status(response)
        return response.json()

    # ── Generic ──────────────────────────────────────────────────────────────

    async def get_raw(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET any Splunk REST path and return the parsed JSON."""
        response = await self._client.get(path, params=params or {})
        self._raise_for_status(response)
        return response.json()

    # ── Macros ───────────────────────────────────────────────────────────────

    async def list_macros(
        self, count: int = 100, offset: int = 0, app: str = ""
    ) -> dict[str, Any]:
        ns = f"-/{app}" if app else "-/-"
        response = await self._client.get(
            f"/servicesNS/{ns}/configs/conf-macros",
            params={"count": count, "offset": offset},
        )
        self._raise_for_status(response)
        return response.json()

    async def get_macro(self, name: str, app: str = "search") -> dict[str, Any]:
        response = await self._client.get(
            f"/servicesNS/-/{app}/configs/conf-macros/{name}"
        )
        self._raise_for_status(response)
        return response.json()

    # ── Users ────────────────────────────────────────────────────────────────

    async def list_users(self, count: int = 100, offset: int = 0) -> dict[str, Any]:
        response = await self._client.get(
            "/services/authentication/users",
            params={"count": count, "offset": offset},
        )
        self._raise_for_status(response)
        return response.json()

    async def get_user(self, username: str) -> dict[str, Any]:
        response = await self._client.get(f"/services/authentication/users/{username}")
        self._raise_for_status(response)
        return response.json()

    # ── Roles ────────────────────────────────────────────────────────────────

    async def list_roles(self, count: int = 100) -> dict[str, Any]:
        response = await self._client.get(
            "/services/authorization/roles", params={"count": count}
        )
        self._raise_for_status(response)
        return response.json()

    async def get_role(self, name: str) -> dict[str, Any]:
        response = await self._client.get(f"/services/authorization/roles/{name}")
        self._raise_for_status(response)
        return response.json()
