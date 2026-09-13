from dataclasses import dataclass
from datetime import date
from typing import Any, Generic, TypeVar

from fastapi import Query, Request, Response
from pydantic import BaseModel


@dataclass(frozen=True)
class PaginationParams:
    offset: int = 0
    limit: int = 100


T = TypeVar("T")
_PAGE_QUERY = Query(default=1, ge=1)
_PAGE_SIZE_QUERY = Query(default=20, ge=1, le=100)
_SORT_QUERY = Query(default=None)
_FROM_DATE_QUERY = Query(default=None, alias="from")
_TO_DATE_QUERY = Query(default=None, alias="to")


class ListQueryParams:
    """Query contract chuẩn cho các endpoint list phân trang theo page."""

    def __init__(
        self,
        page: int = _PAGE_QUERY,
        page_size: int = _PAGE_SIZE_QUERY,
        sort: str | None = _SORT_QUERY,
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.sort = sort


class DateRangeParams:
    """Khoảng ngày dùng chung cho các endpoint list có bộ lọc thời gian."""

    def __init__(
        self,
        from_date: date | None = _FROM_DATE_QUERY,
        to_date: date | None = _TO_DATE_QUERY,
    ) -> None:
        self.from_date = from_date
        self.to_date = to_date


class PageResponse(BaseModel, Generic[T]):
    """Wrapper duy nhất cho list endpoint có phân trang theo page."""

    items: list[T]
    page: int
    page_size: int
    total: int
    has_next: bool


@dataclass(frozen=True)
class Page(Generic[T]):
    """Một trang đã được truy vấn ở tầng repository, kèm tổng số bản ghi."""

    items: list[T]
    total: int


async def paginate_aggregate(
    collection: Any,
    match_stage: dict[str, Any],
    sort_stage: dict[str, int],
    page: int,
    page_size: int,
) -> Page[dict[str, Any]]:
    """Lấy một trang và tổng số bản ghi bằng một pipeline `$facet`."""

    if page < 1 or page_size < 1:
        raise ValueError("page và page_size phải lớn hơn 0")
    pipeline = [
        {"$match": match_stage},
        {"$sort": sort_stage},
        {
            "$facet": {
                "data": [
                    {"$skip": (page - 1) * page_size},
                    {"$limit": page_size},
                ],
                "total": [{"$count": "count"}],
            }
        },
    ]
    result = await collection.aggregate(pipeline).to_list(length=1)
    payload = result[0] if result else {}
    total_rows = payload.get("total") or []
    total = int(total_rows[0]["count"]) if total_rows else 0
    return Page(items=payload.get("data") or [], total=total)


def get_pagination(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=100, ge=1, le=100),
) -> PaginationParams:
    return PaginationParams(offset=offset, limit=limit)


def paginate_v1[T](
    request: Request,
    response: Response,
    items: list[T] | Page[T],
    pagination: PaginationParams,
) -> list[T]:
    """Phân trang response v1; giữ nguyên payload list để client cũ không vỡ."""
    if not request.url.path.startswith("/api/v1/"):
        return items.items if isinstance(items, Page) else items

    if isinstance(items, Page):
        page_items = items.items
        total = items.total
        start = pagination.offset
        end = start + len(page_items)
    else:
        total = len(items)
        start = pagination.offset
        end = start + pagination.limit
        page_items = items[start:end]
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Offset"] = str(start)
    response.headers["X-Limit"] = str(pagination.limit)
    if end < total:
        next_url = str(request.url.include_query_params(offset=end, limit=pagination.limit))
        response.headers["Link"] = f'<{next_url}>; rel="next"'
    return page_items
