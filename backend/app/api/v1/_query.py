from fastapi import HTTPException, status


def build_sort_stage(
    value: str | None,
    allowed_fields: set[str],
    default_field: str,
    default_direction: int = 1,
) -> dict[str, int]:
    if not value:
        return {default_field: default_direction}
    descending = value.startswith("-")
    field = value[1:] if descending else value
    if field not in allowed_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Trường sắp xếp không hợp lệ: {field}",
        )
    return {field: -1 if descending else 1}


def validate_date_range(from_date, to_date) -> None:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Khoảng ngày không hợp lệ",
        )
