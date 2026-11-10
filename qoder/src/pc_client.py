"""Async client for PowerContext HTTP API."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from .config import PowerContextConfig

logger = logging.getLogger(__name__)


class PowerContextError(Exception):
    pass


class PowerContextClient:
    def __init__(self, config: PowerContextConfig):
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Content-Type": "application/json"}
            if self._config.api_token:
                headers["Authorization"] = f"Bearer {self._config.api_token}"
            self._client = httpx.AsyncClient(
                base_url=self._config.server_url,
                headers=headers,
                timeout=self._config.timeout,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _post(self, path: str, json: dict | None = None) -> dict:
        client = await self._ensure_client()
        try:
            resp = await client.post(path, json=json or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500]
            logger.error("PowerContext API %s failed: %s %s", path, e.response.status_code, body)
            raise PowerContextError(f"{path} -> {e.response.status_code}: {body}") from e
        except httpx.ConnectError as e:
            logger.error("Cannot connect to PowerContext at %s", self._config.server_url)
            raise PowerContextError(f"Connection failed: {e}") from e

    async def _get(self, path: str) -> dict:
        client = await self._ensure_client()
        try:
            resp = await client.get(path)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise PowerContextError(f"{path} -> {e.response.status_code}") from e
        except httpx.ConnectError as e:
            raise PowerContextError(f"Connection failed: {e}") from e

    async def health_check(self) -> bool:
        try:
            result = await self._get("/health/live")
            return result.get("status") == "ok"
        except PowerContextError:
            return False

    # ── Scope ──

    async def create_scope(
        self, title: str, summary: str, idempotency_key: str,
        parent_scope_id: Optional[str] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "title": title,
            "summary": summary,
            "idempotency_key": idempotency_key,
        }
        if parent_scope_id:
            payload["parent_scope_id"] = parent_scope_id
        return await self._post("/v1/scopes", payload)

    async def get_scope(self, scope_id: str) -> dict:
        return await self._get(f"/v1/scopes/{scope_id}")

    async def list_scopes(self, query: Optional[str] = None) -> list[dict]:
        params = {}
        if query:
            params["query"] = query
        client = await self._ensure_client()
        resp = await client.get("/v1/scopes", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("scopes", data.get("items", []))

    # ── Scope Bindings ──

    async def set_scope_binding(
        self, scope_id: str, integration: str, kind: str, external_id: str,
    ) -> dict:
        return await self._post("/v1/scope-bindings", {
            "key": {
                "integration": integration,
                "kind": kind,
                "external_id": external_id,
            },
            "scope_id": scope_id,
        })

    async def resolve_scope_binding(
        self, integration: str, kind: str, external_id: str,
    ) -> Optional[str]:
        try:
            result = await self._post("/v1/scope-bindings/resolve", {
                "integration": integration,
                "kind": kind,
                "external_id": external_id,
            })
            return result.get("scope_id")
        except PowerContextError:
            return None

    # ── Memory ──

    async def remember_memory(
        self, scope_id: str, kind: str, text: str,
        description: Optional[str] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "scope_id": scope_id,
            "kind": kind,
            "text": text[:8192],
        }
        if description:
            payload["description"] = description[:200]
        return await self._post("/v1/memory/remember", payload)

    async def search_memory(
        self, scope_id: str, query: str, limit: int = 10,
    ) -> list[dict]:
        try:
            result = await self._post("/v1/memory/search", {
                "scope_id": scope_id,
                "query": query,
                "limit": limit,
            })
            return result if isinstance(result, list) else result.get("entries", result.get("items", []))
        except PowerContextError:
            return []

    async def list_memory_entries(
        self, scope_id: str, limit: int = 50,
    ) -> list[dict]:
        try:
            result = await self._post("/v1/memory/entries/list", {
                "scope_id": scope_id,
                "limit": limit,
            })
            return result if isinstance(result, list) else result.get("entries", result.get("items", []))
        except PowerContextError:
            return []

    async def revise_memory_entry(
        self, scope_id: str, entry_id: str, text: str,
    ) -> dict:
        return await self._post("/v1/memory/entries/revise", {
            "scope_id": scope_id,
            "entry_id": entry_id,
            "text": text[:8192],
        })

    # ── Atomic Memory ──

    async def search_atomic_memory(
        self, scope_id: str, query: str, limit: int = 10,
    ) -> list[dict]:
        try:
            result = await self._post("/v1/atomic-memory/search", {
                "scope_id": scope_id,
                "query": query,
                "limit": limit,
            })
            return result if isinstance(result, list) else result.get("items", [])
        except PowerContextError:
            return []

    async def list_atomic_memories(self, scope_id: str) -> list[dict]:
        try:
            result = await self._post("/v1/atomic-memory/list", {
                "scope_id": scope_id,
            })
            return result if isinstance(result, list) else result.get("items", [])
        except PowerContextError:
            return []

    # ── Prepared Context ──

    async def prepare_context(
        self,
        scope_id: str,
        query: str,
        max_bytes: Optional[int] = None,
        memory_limit: int = 6,
        experience_limit: int = 2,
    ) -> Optional[str]:
        payload: dict[str, Any] = {
            "scope_id": scope_id,
            "query": query,
            "max_bytes": max_bytes or self._config.default_max_bytes,
            "assembly": {
                "format": "markdown",
                "sections": [
                    {"family": "memory", "limit": memory_limit},
                    {"family": "experience", "limit": experience_limit},
                ],
            },
        }
        try:
            result = await self._post("/v1/context/prepare", payload)
            if result.get("status") == "ready":
                return result.get("content", "")
            return None
        except PowerContextError:
            return None

    # ── Experience ──

    async def generate_experience(
        self, scope_id: str, reason: str,
        source_ids: Optional[list[str]] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "scope_id": scope_id,
            "reason": reason,
        }
        if source_ids:
            payload["sources"] = [
                {"source_type": "content", "source_id": sid} for sid in source_ids
            ]
        return await self._post("/v1/experience/generate", payload)

    async def propose_experience(
        self,
        scope_id: str,
        situation: str, action: str, outcome: str, lesson: str,
        source_ids: Optional[list[str]] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "scope_id": scope_id,
            "proposal": {
                "situation": situation[:8000],
                "action": action[:8000],
                "outcome": outcome[:8000],
                "lesson": lesson[:8000],
            },
        }
        if source_ids:
            payload["sources"] = [
                {"source_type": "content", "source_id": sid} for sid in source_ids
            ]
        return await self._post("/v1/experience/propose", payload)

    # ── Source Capture ──

    async def capture_source(
        self, scope_id: str, source_id: str, content: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "scope_id": scope_id,
            "source_id": source_id,
            "content": content,
        }
        if metadata:
            payload["metadata"] = metadata
        return await self._post("/v1/sources/content", payload)

    # ── Handoff ──

    async def handoff_activate(self, scope_id: str, source_id: str) -> dict:
        return await self._post("/v1/handoff/activate", {
            "scope_id": scope_id,
            "source_id": source_id,
        })

    async def handoff_prepare(
        self, scope_id: str, objective: str, max_bytes: int = 8000,
    ) -> dict:
        return await self._post("/v1/handoff/prepare", {
            "scope_id": scope_id,
            "objective": objective[:8192],
            "max_bytes": max_bytes,
        })

    async def handoff_finalize(self, scope_id: str, draft: dict) -> dict:
        return await self._post("/v1/handoff/finalize", {
            "scope_id": scope_id,
            "draft": draft,
        })

    async def handoff_commit(self, scope_id: str, prepared: dict) -> dict:
        return await self._post("/v1/handoff/commit", {
            "scope_id": scope_id,
            "prepared": prepared,
        })

    async def handoff_continue(self, scope_id: str) -> dict:
        return await self._post("/v1/handoff/continue", {
            "scope_id": scope_id,
        })

    async def handoff_hint(self, scope_id: str, max_bytes: int = 2000) -> Optional[str]:
        try:
            result = await self._post("/v1/handoff/hint", {
                "scope_id": scope_id,
                "max_bytes": max_bytes,
            })
            return result.get("content") or result.get("hint")
        except PowerContextError:
            return None

    # ── Skill ──

    async def generate_skill(
        self, scope_id: str, reason: str,
        source_ids: Optional[list[str]] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "scope_id": scope_id,
            "reason": reason,
        }
        if source_ids:
            payload["sources"] = [
                {"source_type": "content", "source_id": sid} for sid in source_ids
            ]
        return await self._post("/v1/skill/generate", payload)

    async def list_skills(self, scope_id: str) -> list[dict]:
        try:
            result = await self._post("/v1/skill/library", {
                "scope_id": scope_id,
            })
            return result if isinstance(result, list) else result.get("skills", result.get("items", []))
        except PowerContextError:
            return []
