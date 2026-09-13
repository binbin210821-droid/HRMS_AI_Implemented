import base64
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from jose import jwt
from jose.exceptions import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.http_contract import ApiError, get_request_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class IdempotencyClaim:
    state: str
    owner: str | None = None
    response: StoredResponse | None = None


@dataclass
class IdempotencyContext:
    """Claim information carried from the dependency to the route handler."""

    scope: str
    key: str
    owner: str
    request_hash: str
    store: "IdempotencyStore"
    ttl_seconds: int
    completed: bool = False


class IdempotencyReplay(Exception):
    def __init__(self, response: StoredResponse) -> None:
        self.response = response


class IdempotencyStore(Protocol):
    async def claim(self, key: str, request_hash: str, ttl_seconds: int) -> IdempotencyClaim:
        ...

    async def complete(
        self,
        key: str,
        owner: str,
        request_hash: str,
        response: StoredResponse,
        ttl_seconds: int,
    ) -> None:
        ...

    async def release(self, key: str, owner: str, request_hash: str) -> None:
        ...


class UnavailableIdempotencyStore:
    async def claim(self, key: str, request_hash: str, ttl_seconds: int) -> IdempotencyClaim:
        del key, request_hash, ttl_seconds
        raise RuntimeError("Idempotency store chưa sẵn sàng")

    async def complete(
        self,
        key: str,
        owner: str,
        request_hash: str,
        response: StoredResponse,
        ttl_seconds: int,
    ) -> None:
        del key, owner, request_hash, response, ttl_seconds
        raise RuntimeError("Idempotency store chưa sẵn sàng")

    async def release(self, key: str, owner: str, request_hash: str) -> None:
        del key, owner, request_hash
        raise RuntimeError("Idempotency store chưa sẵn sàng")


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[str, dict] = {}

    async def claim(self, key: str, request_hash: str, ttl_seconds: int) -> IdempotencyClaim:
        now = time.time()
        record = self._records.get(key)
        if record and record["expires_at"] <= now:
            self._records.pop(key, None)
            record = None
        if record is None:
            owner = uuid4().hex
            self._records[key] = {
                "request_hash": request_hash,
                "owner": owner,
                "expires_at": now + ttl_seconds,
            }
            return IdempotencyClaim("claimed", owner=owner)
        if record["request_hash"] != request_hash:
            return IdempotencyClaim("conflict")
        if "response" in record:
            return IdempotencyClaim("replay", response=record["response"])
        return IdempotencyClaim("in_progress")

    async def complete(
        self,
        key: str,
        owner: str,
        request_hash: str,
        response: StoredResponse,
        ttl_seconds: int,
    ) -> None:
        record = self._records.get(key)
        if record and record["owner"] == owner and record["request_hash"] == request_hash:
            record["response"] = response
            record["expires_at"] = time.time() + ttl_seconds

    async def release(self, key: str, owner: str, request_hash: str) -> None:
        record = self._records.get(key)
        if record and record["owner"] == owner and record["request_hash"] == request_hash:
            self._records.pop(key, None)


class RedisIdempotencyStore:
    _CLAIM_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if not current then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2], 'NX')
  return {1, ARGV[1]}
end
return {0, current}
"""
    _COMPLETE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
  return 1
end
return 0
"""
    _RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""

    def __init__(self, redis_url: str, client: Any | None = None) -> None:
        self._owns_client = client is None
        if client is None:
            try:
                from redis.asyncio import Redis
            except ImportError as error:
                raise RuntimeError("Redis client chưa được cài đặt") from error
            client = Redis.from_url(redis_url, decode_responses=False)
        self.client = client

    async def claim(self, key: str, request_hash: str, ttl_seconds: int) -> IdempotencyClaim:
        owner = uuid4().hex
        pending = json.dumps({"state": "pending", "owner": owner, "request_hash": request_hash})
        created, stored = await self.client.eval(
            self._CLAIM_SCRIPT,
            1,
            key,
            pending,
            ttl_seconds,
        )
        payload = json.loads(stored)
        if int(created) == 1:
            return IdempotencyClaim("claimed", owner=owner)
        if payload.get("request_hash") != request_hash:
            return IdempotencyClaim("conflict")
        if payload.get("state") == "complete":
            return IdempotencyClaim("replay", response=_deserialize_response(payload))
        return IdempotencyClaim("in_progress")

    async def complete(
        self,
        key: str,
        owner: str,
        request_hash: str,
        response: StoredResponse,
        ttl_seconds: int,
    ) -> None:
        pending = json.dumps({"state": "pending", "owner": owner, "request_hash": request_hash})
        complete = json.dumps(
            {
                "state": "complete",
                "owner": owner,
                "request_hash": request_hash,
                "status_code": response.status_code,
                "headers": response.headers,
                "body": base64.b64encode(response.body).decode("ascii"),
            }
        )
        await self.client.eval(self._COMPLETE_SCRIPT, 1, key, pending, complete, ttl_seconds)

    async def release(self, key: str, owner: str, request_hash: str) -> None:
        pending = json.dumps({"state": "pending", "owner": owner, "request_hash": request_hash})
        await self.client.eval(self._RELEASE_SCRIPT, 1, key, pending)

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()


def _deserialize_response(payload: dict) -> StoredResponse:
    return StoredResponse(
        status_code=int(payload["status_code"]),
        headers=dict(payload.get("headers") or {}),
        body=base64.b64decode(payload.get("body", "")),
    )


def _client_ip(request: Request, settings: Settings) -> str:
    client_host = request.client.host if request.client else "unknown"
    trusted_proxies = {
        value.strip()
        for value in settings.rate_limit_trusted_proxy_ips.split(",")
        if value.strip()
    }
    if client_host in trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return client_host


def _idempotency_identity(request: Request, settings: Settings) -> str:
    token = request.cookies.get(settings.auth_access_cookie_name)
    if not token:
        authorization = request.headers.get("authorization", "")
        token = authorization.removeprefix("Bearer ").strip()
    if token:
        try:
            claims = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.algorithm],
            )
            role = claims.get("role")
            subject = claims.get("sub")
            if role in {"manager", "leadership"} and subject:
                subject_hash = hashlib.sha256(str(subject).encode("utf-8")).hexdigest()[:32]
                return f"{role}:user:{subject_hash}"
        except (JWTError, TypeError, ValueError):
            pass
        return f"invalid-token:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:32]}"
    return f"anonymous:{_client_ip(request, settings)}"


def _idempotency_key(
    request: Request,
    raw_key: str,
    body: bytes,
    settings: Settings,
) -> str:
    identity = _idempotency_identity(request, settings)
    del body
    scope = (
        f"{request.method.upper()}:{request.url.path}?{request.url.query}"
        f":{identity}:{raw_key}"
    )
    return f"idempotency:{hashlib.sha256(scope.encode('utf-8')).hexdigest()}"


def _scoped_idempotency_key(
    request: Request,
    scope: str,
    raw_key: str,
    settings: Settings,
) -> str:
    identity = _idempotency_identity(request, settings)
    material = (
        f"{request.method.upper()}:{request.url.path}?{request.url.query}:"
        f"{identity}:{raw_key}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"idem:{scope}:{digest}"


def _record_idempotency_header_usage(request: Request, scope: str, has_key: bool) -> None:
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    route_key = f"{request.method.upper()} {route_path}"
    state = "with_key" if has_key else "without_key"
    counters = getattr(request.app.state, "idempotency_counters", None)
    if counters is None:
        counters = {}
        request.app.state.idempotency_counters = counters
    scope_counters = counters.setdefault(scope, {})
    route_counters = scope_counters.setdefault(
        route_key,
        {"with_key": 0, "without_key": 0},
    )
    route_counters[state] += 1
    logger.info(
        "idempotency_request_observed",
        extra={
            "event": "idempotency_request",
            "scope": scope,
            "route": route_key,
            "has_idempotency_key": has_key,
            "header_state": state,
            "count": route_counters[state],
        },
    )


def idempotent(scope: str):
    """Optionally claim an Idempotency-Key for one route scope."""

    async def dependency(request: Request) -> AsyncIterator[IdempotencyContext | None]:
        settings: Settings = request.app.state.settings
        if not settings.idempotency_enabled:
            # Killswitch: khi tắt, tính năng phải biến mất hoàn toàn. Không
            # đọc header, không chạm Redis và không yêu cầu backend sẵn sàng.
            yield None
            return

        raw_key = request.headers.get("Idempotency-Key", "").strip()
        _record_idempotency_header_usage(request, scope, bool(raw_key))
        if not raw_key:
            # Header là opt-in để tránh breaking traffic cũ; client nào gửi
            # header vẫn nhận đầy đủ semantics claim/replay/conflict.
            yield None
            return

        if len(raw_key) > 255:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key không được dài quá 255 ký tự.",
            )
        store: IdempotencyStore | None = getattr(request.app.state, "idempotency_store", None)
        if store is None:
            raise HTTPException(
                status_code=503,
                detail="Hệ thống chống gửi lặp chưa sẵn sàng.",
            )

        body = await request.body()
        request_hash = hashlib.sha256(body).hexdigest()
        key = _scoped_idempotency_key(request, scope, raw_key, settings)
        try:
            claim = await store.claim(key, request_hash, 30)
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail="Hệ thống chống gửi lặp chưa sẵn sàng.",
            ) from error

        if claim.state == "replay" and claim.response is not None:
            raise IdempotencyReplay(claim.response)
        if claim.state == "conflict":
            raise HTTPException(
                status_code=409,
                detail="Khóa Idempotency-Key đã dùng cho 1 yêu cầu khác nội dung",
            )
        if claim.state == "in_progress":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Yêu cầu trước đó với cùng khóa đang được xử lý, "
                    "vui lòng thử lại sau ít giây"
                ),
            )
        if claim.state != "claimed" or claim.owner is None:
            raise HTTPException(
                status_code=503,
                detail="Không thể tạo trạng thái chống gửi lặp.",
            )

        context = IdempotencyContext(
            scope, key, claim.owner, request_hash, store, settings.idempotency_ttl_seconds
        )
        contexts = getattr(request.state, "idempotency_contexts", None)
        if contexts is None:
            contexts = {}
            request.state.idempotency_contexts = contexts
        contexts[scope] = context
        try:
            yield context
        finally:
            contexts.pop(scope, None)
            if not context.completed:
                try:
                    await store.release(key, claim.owner, request_hash)
                except Exception:
                    # Không che khuất exception nghiệp vụ gốc; TTL 30 giây
                    # vẫn giới hạn thời gian tồn tại của claim lỗi.
                    pass

    return dependency


async def complete_idempotency(
    context: IdempotencyContext | None,
    payload: object,
    response: Response | None = None,
    status_code: int = 200,
) -> None:
    if not isinstance(context, IdempotencyContext):
        return
    headers = {"content-type": "application/json"}
    if response is not None and response.headers.get("location"):
        headers["location"] = response.headers["location"]
    body = json.dumps(
        jsonable_encoder(payload), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    stored = StoredResponse(status_code, headers, body)
    await context.store.complete(
        context.key,
        context.owner,
        context.request_hash,
        stored,
        context.ttl_seconds,
    )
    context.completed = True


async def handle_idempotency_replay(request: Request, exception: Exception) -> Response:
    if not isinstance(exception, IdempotencyReplay):
        return Response(status_code=500)
    response = IdempotencyMiddleware._response_from_stored(
        exception.response, get_request_id(request)
    )
    response.headers["Idempotency-Replayed"] = "true"
    return response


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, store: IdempotencyStore, settings: Settings) -> None:
        super().__init__(app)
        self.store = store
        self.settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        raw_key = request.headers.get("Idempotency-Key", "").strip()
        if len(raw_key) > 255:
            return self._error(
                request,
                400,
                "invalid_idempotency_key",
                "Idempotency-Key không được dài quá 255 ký tự.",
            )
        if (
            not self.settings.idempotency_enabled
            or not raw_key
            or request.method.upper() in {"GET", "HEAD", "OPTIONS"}
            or request.url.path.endswith("/auth/login")
            or request.headers.get("accept", "").startswith("text/event-stream")
        ):
            return await call_next(request)

        body = await request.body()
        key = _idempotency_key(
            request,
            raw_key,
            body,
            self.settings,
        )
        request_hash = hashlib.sha256(body).hexdigest()
        try:
            claim = await self.store.claim(key, request_hash, self.settings.idempotency_ttl_seconds)
        except Exception:
            return self._unavailable(request)
        if claim.state == "replay" and claim.response is not None:
            response = self._response_from_stored(claim.response, get_request_id(request))
            response.headers["Idempotency-Replayed"] = "true"
            return response
        if claim.state == "conflict":
            return self._error(
                request,
                409,
                "idempotency_key_conflict",
                "Idempotency-Key đã được dùng cho nội dung request khác.",
            )
        if claim.state == "in_progress":
            return self._error(
                request,
                409,
                "idempotency_request_in_progress",
                "Request cùng Idempotency-Key đang được xử lý.",
            )

        response = await call_next(request)
        if claim.owner is not None and 200 <= response.status_code < 500:
            stored = await self._materialize(response)
            try:
                await self.store.complete(
                    key,
                    claim.owner,
                    request_hash,
                    stored,
                    self.settings.idempotency_ttl_seconds,
                )
            except Exception:
                return self._unavailable(request)
            return self._response_from_stored(stored, get_request_id(request))
        if claim.owner is not None:
            try:
                await self.store.release(key, claim.owner, request_hash)
            except Exception:
                return self._unavailable(request)
        return response

    @staticmethod
    async def _materialize(response: Response) -> StoredResponse:
        body = b""
        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is not None:
            body = b"".join([chunk async for chunk in body_iterator])
        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower()
            not in {"content-length", "set-cookie", "transfer-encoding", "x-request-id"}
        }
        return StoredResponse(response.status_code, headers, body)

    @staticmethod
    def _response_from_stored(stored: StoredResponse, request_id: str | None = None) -> Response:
        headers = dict(stored.headers)
        if request_id:
            headers["X-Request-ID"] = request_id
        return Response(
            content=stored.body,
            status_code=stored.status_code,
            headers=headers,
            media_type=headers.get("content-type"),
        )

    @staticmethod
    def _error(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
        payload = ApiError(code=code, message=message, request_id=get_request_id(request))
        response = JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
        response.headers["X-Request-ID"] = payload.request_id
        return response

    @staticmethod
    def _unavailable(request: Request) -> JSONResponse:
        return IdempotencyMiddleware._error(
            request,
            503,
            "idempotency_unavailable",
            "Hệ thống chống gửi lặp chưa sẵn sàng. Vui lòng thử lại sau.",
        )
