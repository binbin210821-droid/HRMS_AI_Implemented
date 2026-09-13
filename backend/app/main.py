import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.ai.cache import AiProposalCache, AiSummaryCache
from app.api.ai import router as ai_router
from app.api.alerts import router as alerts_router
from app.api.attachments import router as attachments_router
from app.api.auth import router as auth_router
from app.api.coordination import router as coordination_router
from app.api.dashboard import router as dashboard_router
from app.api.department_evaluations import router as department_evaluations_router
from app.api.departments import router as departments_router
from app.api.employees import router as employees_router
from app.api.health import router as health_router
from app.api.overload import router as overload_router
from app.api.performance import router as performance_router
from app.api.tasks import router as tasks_router
from app.api.thresholds import router as thresholds_router
from app.api.v1 import api_v1_router
from app.core.api_deprecation import LegacyApiDeprecationMiddleware, LegacyApiUsageMiddleware
from app.core.config import get_settings
from app.core.csrf import CSRFMiddleware
from app.core.database import database_lifespan, get_mongo_database
from app.core.http_contract import RequestIdMiddleware, install_http_contract
from app.core.time import BusinessClock
from app.events.event_bus import OVERLOAD_DETECTED, PERFORMANCE_METRIC_CREATED, event_bus
from app.infrastructure.idempotency import (
    IdempotencyReplay,
    RedisIdempotencyStore,
    UnavailableIdempotencyStore,
    handle_idempotency_replay,
)
from app.infrastructure.rate_limit import (
    InMemoryRateLimiter,
    RateLimitKeyBuilder,
    RateLimitMiddleware,
    RateLimitPolicy,
    RedisRateLimiter,
    UnavailableRateLimiter,
)
from app.realtime.change_stream_worker import (
    create_alerts_worker,
    create_department_directives_worker,
    create_department_evaluations_worker,
    create_performance_metrics_worker,
    create_task_directives_worker,
    create_task_execution_reports_worker,
    create_tasks_worker,
)
from app.realtime.websocket import router as realtime_router
from app.services.alert_service import (
    create_metric_event_handler,
    create_overload_alert_event_handler,
)
from app.services.overload_service import create_overload_metric_event_handler

settings = get_settings()


def create_redis_client(settings: Any):
    if settings.rate_limit_backend != "redis" and not settings.idempotency_enabled:
        return None
    try:
        from redis.asyncio import Redis
    except ImportError:
        return None
    return Redis.from_url(settings.redis_url, decode_responses=False)


def create_rate_limiter(settings, redis_client=None):
    if settings.rate_limit_backend != "redis":
        return InMemoryRateLimiter()
    try:
        return RedisRateLimiter(settings.redis_url, client=redis_client)
    except RuntimeError:
        return UnavailableRateLimiter()


def create_idempotency_store(settings, redis_client=None):
    if not settings.idempotency_enabled:
        return UnavailableIdempotencyStore()
    try:
        return RedisIdempotencyStore(settings.redis_url, client=redis_client)
    except RuntimeError:
        return UnavailableIdempotencyStore()


redis_client = create_redis_client(settings)
rate_limiter = create_rate_limiter(settings, redis_client)
idempotency_store = create_idempotency_store(settings, redis_client)


def database_provider():
    return get_mongo_database().get_database()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with database_lifespan(settings):
        stop_event = asyncio.Event()
        clock = BusinessClock()
        metric_handler = create_metric_event_handler(database_provider, clock=clock)
        overload_metric_handler = create_overload_metric_event_handler(
            database_provider, clock=clock
        )
        overload_alert_handler = create_overload_alert_event_handler(
            database_provider, clock=clock
        )
        event_bus.subscribe(
            PERFORMANCE_METRIC_CREATED,
            metric_handler,
        )
        event_bus.subscribe(
            PERFORMANCE_METRIC_CREATED,
            overload_metric_handler,
        )
        event_bus.subscribe(
            OVERLOAD_DETECTED,
            overload_alert_handler,
        )

        worker_tasks = [
            asyncio.create_task(
                create_alerts_worker(database_provider).run(stop_event),
                name="alerts-change-stream",
            ),
            asyncio.create_task(
                create_performance_metrics_worker(database_provider).run(stop_event),
                name="performance-metrics-change-stream",
            ),
            asyncio.create_task(
                create_tasks_worker(database_provider).run(stop_event),
                name="tasks-change-stream",
            ),
            asyncio.create_task(
                create_department_directives_worker(database_provider).run(stop_event),
                name="department-directives-change-stream",
            ),
            asyncio.create_task(
                create_task_directives_worker(database_provider).run(stop_event),
                name="task-directives-change-stream",
            ),
            asyncio.create_task(
                create_task_execution_reports_worker(database_provider).run(stop_event),
                name="task-execution-reports-change-stream",
            ),
            asyncio.create_task(
                create_department_evaluations_worker(database_provider).run(stop_event),
                name="department-evaluations-change-stream",
            ),
        ]
        try:
            yield
        finally:
            stop_event.set()
            for worker_task in worker_tasks:
                worker_task.cancel()
            await asyncio.gather(*worker_tasks, return_exceptions=True)
            event_bus.unsubscribe(PERFORMANCE_METRIC_CREATED, metric_handler)
            event_bus.unsubscribe(PERFORMANCE_METRIC_CREATED, overload_metric_handler)
            event_bus.unsubscribe(OVERLOAD_DETECTED, overload_alert_handler)
            for backend in (rate_limiter, idempotency_store):
                close = getattr(backend, "aclose", None)
                if close is not None:
                    await close()
            if redis_client is not None:
                await redis_client.aclose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.state.settings = settings
app.state.rate_limiter = rate_limiter
app.state.rate_limit_policy = RateLimitPolicy(settings)
app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
app.state.idempotency_store = idempotency_store
app.state.ai_proposal_cache = AiProposalCache(
    ttl_seconds=settings.ai_proposal_cache_ttl_seconds,
    max_entries=settings.ai_proposal_cache_max_entries,
    redis_client=redis_client,
)
app.state.ai_summary_cache = AiSummaryCache(
    ttl_seconds=settings.ai_summary_cache_ttl_seconds,
    max_entries=settings.ai_summary_cache_max_entries,
    redis_client=redis_client,
)
# CORS bọc ngoài CSRF để response lỗi CSRF vẫn nhận được CORS headers.
app.add_middleware(LegacyApiDeprecationMiddleware, settings=settings)
app.add_middleware(LegacyApiUsageMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    limiter=rate_limiter,
    settings=settings,
)
app.add_middleware(CSRFMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Đăng ký sau CORS để Request-ID bao phủ cả response preflight và lỗi do CORS.
app.add_middleware(RequestIdMiddleware)
install_http_contract(app)
app.add_exception_handler(IdempotencyReplay, handle_idempotency_replay)


def _operation_id(prefix: str, route) -> str:
    normalized_prefix = prefix.strip("/").replace("/", "_") or "root"
    return f"{normalized_prefix}_{route.name}"


def _operation_id_factory(prefix: str) -> Callable[[APIRoute], str]:
    return lambda route: _operation_id(prefix, route)


api_routers = (
    health_router,
    auth_router,
    alerts_router,
    attachments_router,
    ai_router,
    departments_router,
    department_evaluations_router,
    coordination_router,
    dashboard_router,
    employees_router,
    performance_router,
    overload_router,
    thresholds_router,
    tasks_router,
)
for api_router in api_routers:
    app.include_router(
        api_router,
        prefix="/api",
        generate_unique_id_function=_operation_id_factory("/api"),
    )
app.include_router(api_v1_router)
app.include_router(realtime_router)
