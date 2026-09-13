import pytest
from fastapi import Depends, FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.core.pagination import (
    Page,
    PaginationParams,
    get_pagination,
    paginate_aggregate,
    paginate_v1,
)


class FakeAggregateCursor:
    def __init__(self, payload: list[dict]) -> None:
        self.payload = payload
        self.limit_calls: list[int] = []

    async def to_list(self, length: int):
        self.limit_calls.append(length)
        return self.payload


class FakeCollection:
    def __init__(self) -> None:
        self.pipelines: list[list[dict]] = []

    def aggregate(self, pipeline: list[dict]) -> FakeAggregateCursor:
        self.pipelines.append(pipeline)
        return FakeAggregateCursor(
            [{"data": [{"_id": "item-2"}], "total": [{"count": 3}]}]
        )


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/items")
    async def list_v1(
        request: Request,
        response: Response,
        pagination: PaginationParams = Depends(get_pagination),  # noqa: B008
    ) -> list[int]:
        return paginate_v1(request, response, list(range(5)), pagination)

    @app.get("/api/items")
    async def list_legacy(
        request: Request,
        response: Response,
        pagination: PaginationParams = Depends(get_pagination),  # noqa: B008
    ) -> list[int]:
        return paginate_v1(request, response, list(range(5)), pagination)

    return app


def test_v1_pagination_preserves_list_payload_and_emits_navigation_headers() -> None:
    response = TestClient(build_app()).get("/api/v1/items?offset=2&limit=2")

    assert response.json() == [2, 3]
    assert response.headers["X-Total-Count"] == "5"
    assert response.headers["X-Offset"] == "2"
    assert response.headers["X-Limit"] == "2"
    assert "offset=4" in response.headers["Link"]


def test_legacy_api_keeps_original_unpaged_payload() -> None:
    response = TestClient(build_app()).get("/api/items?offset=2&limit=2")

    assert response.json() == [0, 1, 2, 3, 4]
    assert "X-Total-Count" not in response.headers


def test_repository_page_uses_database_total_without_reslicing_items() -> None:
    app = FastAPI()

    @app.get("/api/v1/repository-page")
    async def repository_page(request: Request, response: Response) -> list[int]:
        pagination = PaginationParams(offset=2, limit=2)
        return paginate_v1(request, response, Page(items=[2, 3], total=5), pagination)

    response = TestClient(app).get("/api/v1/repository-page")

    assert response.json() == [2, 3]
    assert response.headers["X-Total-Count"] == "5"
    assert "offset=4" in response.headers["Link"]


@pytest.mark.asyncio
async def test_paginate_aggregate_uses_one_facet_pipeline() -> None:
    collection = FakeCollection()

    page = await paginate_aggregate(collection, {"status": "open"}, {"created_at": -1}, 2, 1)

    assert page.items == [{"_id": "item-2"}]
    assert page.total == 3
    assert len(collection.pipelines) == 1
    pipeline = collection.pipelines[0]
    assert pipeline[0] == {"$match": {"status": "open"}}
    assert pipeline[1] == {"$sort": {"created_at": -1}}
    assert pipeline[2]["$facet"]["data"] == [{"$skip": 1}, {"$limit": 1}]
    assert pipeline[2]["$facet"]["total"] == [{"$count": "count"}]
