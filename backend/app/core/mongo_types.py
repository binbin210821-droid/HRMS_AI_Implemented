"""Helpers that keep Python temporal values compatible with BSON."""

from datetime import date, datetime, time, timezone
from typing import Any


def to_mongo_datetime(value: date | datetime) -> datetime:
    """Convert date/datetime values to timezone-aware UTC datetimes for MongoDB."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def normalize_mongo_value(value: Any) -> Any:
    """Normalize nested write payloads before PyMongo serializes them to BSON."""
    if isinstance(value, (date, datetime)):
        return to_mongo_datetime(value)
    if isinstance(value, dict):
        return {key: normalize_mongo_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_mongo_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_mongo_value(item) for item in value)
    return value


__all__ = ["normalize_mongo_value", "to_mongo_datetime"]
