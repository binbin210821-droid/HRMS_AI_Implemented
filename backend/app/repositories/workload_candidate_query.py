from datetime import date as Date
from datetime import datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId

from app.core.workload_policy import DAILY_WORKLOAD_CAPACITY, MIN_STABLE_QUALITY_SCORE


def build_rebalance_candidate_pipeline(
    department_id: ObjectId,
    metric_date: Date,
    excluded_employee_id: ObjectId | None = None,
    *,
    offset: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Build a candidate query that includes daily and multi-day workload.

    ``performance_metrics.tasks_completed`` is the completed volume for the
    alert date. A task contributes on every day after creation until its
    completion timestamp; unfinished tasks continue to contribute after their
    due date. Coordination plans already reserved for that employee/date are
    added before the capacity filter.
    """

    start = datetime.combine(metric_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    metric_match: dict[str, Any] = {
        "date": {"$gte": start, "$lt": end},
        "quality_score": {"$gte": MIN_STABLE_QUALITY_SCORE},
    }
    if excluded_employee_id is not None:
        metric_match["employee_id"] = {"$ne": excluded_employee_id}

    pipeline: list[dict[str, Any]] = [
        {"$match": metric_match},
        {
            "$lookup": {
                "from": "tasks",
                "let": {"candidate_employee_id": "$employee_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$employee_id", "$$candidate_employee_id"]},
                                    {
                                        "$lt": [
                                            "$created_at",
                                            end,
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$gte": ["$due_date", start]},
                                            {"$eq": ["$completed_at", None]},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {"$eq": ["$completed_at", None]},
                                            {"$gte": ["$completed_at", end]},
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    {"$project": {"_id": 0, "title": 1}},
                ],
                "as": "active_tasks",
            }
        },
        {
            "$lookup": {
                "from": "coordination_plans",
                "let": {"candidate_employee_id": "$employee_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {
                                        "$eq": [
                                            "$target_employee_id",
                                            "$$candidate_employee_id",
                                        ]
                                    },
                                    {"$eq": ["$alert_date", start]},
                                ]
                            }
                        }
                    },
                    {"$project": {"_id": 0, "tasks_to_transfer": 1}},
                ],
                "as": "reserved_plans",
            }
        },
        {
            "$set": {
                "active_task_count": {"$size": "$active_tasks"},
                "active_task_titles": {
                    "$map": {
                        "input": "$active_tasks",
                        "as": "task",
                        "in": "$$task.title",
                    }
                },
                "reserved_coordination_count": {"$sum": "$reserved_plans.tasks_to_transfer"},
            }
        },
        {
            "$set": {
                "workload_count": {
                    "$add": [
                        "$tasks_completed",
                        "$active_task_count",
                        "$reserved_coordination_count",
                    ]
                }
            }
        },
        {
            "$set": {
                "available_capacity": {
                    "$max": [0, {"$subtract": [DAILY_WORKLOAD_CAPACITY, "$workload_count"]}]
                }
            }
        },
        {"$match": {"workload_count": {"$lt": DAILY_WORKLOAD_CAPACITY}}},
        {
            "$lookup": {
                "from": "employees",
                "localField": "employee_id",
                "foreignField": "_id",
                "as": "employee",
            }
        },
        {"$unwind": "$employee"},
        {
            "$match": {
                "employee.department_id": department_id,
                "employee.is_active": True,
            }
        },
        {
            "$project": {
                "_id": 0,
                "employee_id": {"$toString": "$employee_id"},
                "employee_code": "$employee.employee_code",
                "employee_name": "$employee.full_name",
                "tasks_completed": 1,
                "quality_score": 1,
                "active_task_count": 1,
                "active_task_titles": 1,
                "reserved_coordination_count": 1,
                "workload_count": 1,
                "available_capacity": 1,
            }
        },
        {"$sort": {"workload_count": 1, "quality_score": -1, "employee_code": 1}},
    ]
    if offset is not None and limit is not None:
        pipeline.append(
            {
                "$facet": {
                    "metadata": [{"$count": "total"}],
                    "items": [{"$skip": offset}, {"$limit": limit}],
                }
            }
        )
    return pipeline


__all__ = ["build_rebalance_candidate_pipeline"]
