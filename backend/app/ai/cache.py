from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from app.models.ai_proposal import AiAlertProposalResponse
from app.models.alert import AlertDocument
from app.models.overload import WorkloadCandidateResponse


class AiProposalCache:
    """Best-effort proposal cache; cache failures never block AI requests."""

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_entries: int = 256,
        redis_client: Any | None = None,
    ) -> None:
        self.ttl_seconds = max(0, ttl_seconds)
        self.max_entries = max(1, max_entries)
        self.redis_client = redis_client
        self._entries: OrderedDict[str, tuple[float, AiAlertProposalResponse]] = OrderedDict()

    @staticmethod
    def build_key(
        alert: AlertDocument,
        candidates: list[WorkloadCandidateResponse],
    ) -> str:
        payload = {
            "alert_id": str(alert.id),
            "alert_updated_at": alert.updated_at.isoformat(),
            "department_id": str(alert.department_id),
            "candidates": [
                {
                    "employee_id": candidate.employee_id,
                    "tasks_completed": candidate.tasks_completed,
                    "quality_score": candidate.quality_score,
                    "active_task_count": candidate.active_task_count,
                    "reserved_coordination_count": candidate.reserved_coordination_count,
                    "workload_count": candidate.workload_count,
                    "available_capacity": candidate.available_capacity,
                }
                for candidate in candidates
            ],
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        return f"ai:alert-proposal:{digest}"

    async def get(self, key: str) -> AiAlertProposalResponse | None:
        if self.ttl_seconds == 0:
            return None
        now = time.monotonic()
        entry = self._entries.get(key)
        if entry is not None:
            expires_at, response = entry
            if expires_at > now:
                self._entries.move_to_end(key)
                return response.model_copy(deep=True)
            self._entries.pop(key, None)

        if self.redis_client is None:
            return None
        try:
            raw = await self.redis_client.get(key)
            if raw:
                response = AiAlertProposalResponse.model_validate_json(raw)
                self._remember(key, response, now)
                return response.model_copy(deep=True)
        except Exception:
            return None
        return None

    async def set(self, key: str, response: AiAlertProposalResponse) -> None:
        if self.ttl_seconds == 0:
            return
        self._remember(key, response, time.monotonic())
        if self.redis_client is None:
            return
        try:
            await self.redis_client.set(
                key,
                response.model_dump_json(),
                ex=self.ttl_seconds,
            )
        except Exception:
            return

    def _remember(
        self,
        key: str,
        response: AiAlertProposalResponse,
        now: float,
    ) -> None:
        self._entries[key] = (now + self.ttl_seconds, response.model_copy(deep=True))
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)


class AiSummaryCache:
    """Short-lived summary cache with local single-flight request coalescing."""

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_entries: int = 256,
        redis_client: Any | None = None,
    ) -> None:
        self.ttl_seconds = max(0, ttl_seconds)
        self.max_entries = max(1, max_entries)
        self.redis_client = redis_client
        self._entries: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._inflight: dict[str, asyncio.Task[str]] = {}

    @staticmethod
    def build_key(actor_id: str, scope: Any, day: str) -> str:
        payload = {
            "actor_id": actor_id,
            "scope": str(scope) if scope is not None else "all",
            "day": day,
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        return f"ai:summary:{digest}"

    async def get(self, key: str) -> str | None:
        if self.ttl_seconds == 0:
            return None
        now = time.monotonic()
        entry = self._entries.get(key)
        if entry is not None:
            expires_at, value = entry
            if expires_at > now:
                self._entries.move_to_end(key)
                return value
            self._entries.pop(key, None)
        if self.redis_client is None:
            return None
        try:
            raw = await self.redis_client.get(key)
            if raw:
                value = raw.decode() if isinstance(raw, bytes) else str(raw)
                self._remember(key, value, now)
                return value
        except Exception:
            return None
        return None

    async def set(self, key: str, value: str) -> None:
        if self.ttl_seconds == 0 or not value.strip():
            return
        self._remember(key, value, time.monotonic())
        if self.redis_client is None:
            return
        try:
            await self.redis_client.set(key, value, ex=self.ttl_seconds)
        except Exception:
            return

    async def get_or_create(
        self,
        key: str,
        producer: Callable[[], Awaitable[str]],
        *,
        force_refresh: bool = False,
    ) -> str:
        if not force_refresh:
            cached = await self.get(key)
            if cached is not None:
                return cached
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(producer())
            self._inflight[key] = task
        try:
            value = await asyncio.shield(task)
            if value.strip():
                await self.set(key, value)
            return value
        finally:
            if task.done() and self._inflight.get(key) is task:
                self._inflight.pop(key, None)

    def _remember(self, key: str, value: str, now: float) -> None:
        self._entries[key] = (now + self.ttl_seconds, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
