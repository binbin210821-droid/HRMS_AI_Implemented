from datetime import date, datetime, timezone

from bson import ObjectId

from app.core.workload_policy import DAILY_WORKLOAD_CAPACITY
from app.repositories.workload_candidate_query import build_rebalance_candidate_pipeline


def test_rebalance_query_adds_active_tasks_and_reserved_plans_before_capacity_filter():
    pipeline = build_rebalance_candidate_pipeline(ObjectId(), date(2026, 9, 17))

    lookups = {stage["$lookup"]["from"]: stage["$lookup"] for stage in pipeline if "$lookup" in stage}
    assert {"tasks", "coordination_plans", "employees"} <= lookups.keys()

    task_match = lookups["tasks"]["pipeline"][0]["$match"]["$expr"]["$and"]
    assert {"$eq": ["$completed_at", None]} in task_match[3]["$or"]
    assert {
        "$gte": ["$completed_at", datetime(2026, 9, 18, tzinfo=timezone.utc)]
    } in task_match[3]["$or"]
    assert {
        "$lt": [
            "$created_at",
            datetime(2026, 9, 18, tzinfo=timezone.utc),
        ]
    } in task_match
    assert {
        "$gte": ["$due_date", datetime(2026, 9, 17, tzinfo=timezone.utc)]
    } in task_match[2]["$or"]

    workload_stage = next(
        stage for stage in pipeline if stage.get("$match", {}).get("workload_count")
    )
    assert workload_stage["$match"]["workload_count"] == {"$lt": DAILY_WORKLOAD_CAPACITY}

    projection = next(stage["$project"] for stage in pipeline if "$project" in stage)
    assert projection["active_task_count"] == 1
    assert projection["active_task_titles"] == 1
    assert projection["reserved_coordination_count"] == 1
    assert projection["workload_count"] == 1
    assert projection["available_capacity"] == 1


def test_rebalance_query_page_uses_same_capacity_filter_before_facet():
    pipeline = build_rebalance_candidate_pipeline(
        ObjectId(), date(2026, 9, 17), offset=20, limit=10
    )

    workload_index = next(
        index
        for index, stage in enumerate(pipeline)
        if stage.get("$match", {}).get("workload_count")
    )
    facet_index = next(index for index, stage in enumerate(pipeline) if "$facet" in stage)
    assert workload_index < facet_index
    assert pipeline[-1]["$facet"]["items"] == [{"$skip": 20}, {"$limit": 10}]
