import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.core.config import get_settings
from app.core.database import database_lifespan, get_mongo_database
from app.core.time import BusinessClock
from app.events.event_bus import OVERLOAD_DETECTED, PERFORMANCE_METRIC_CREATED, event_bus
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


def database_provider():
    return get_mongo_database().get_database()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with database_lifespan(settings):
        stop_event = asyncio.Event()
        clock = BusinessClock()
        event_bus.subscribe(
            PERFORMANCE_METRIC_CREATED,
            create_metric_event_handler(database_provider, clock=clock),
        )
        event_bus.subscribe(
            PERFORMANCE_METRIC_CREATED,
            create_overload_metric_event_handler(database_provider, clock=clock),
        )
        event_bus.subscribe(
            OVERLOAD_DETECTED,
            create_overload_alert_event_handler(database_provider, clock=clock),
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


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(alerts_router)
app.include_router(attachments_router)
app.include_router(ai_router)
app.include_router(departments_router)
app.include_router(department_evaluations_router)
app.include_router(coordination_router)
app.include_router(dashboard_router)
app.include_router(employees_router)
app.include_router(performance_router)
app.include_router(overload_router)
app.include_router(thresholds_router)
app.include_router(tasks_router)
app.include_router(realtime_router)
