from datetime import date, datetime, timezone

from bson import BSON

from app.core.mongo_types import normalize_mongo_value, to_mongo_datetime


def test_date_is_converted_to_bson_compatible_utc_datetime():
    payload = normalize_mongo_value({"alert_date": date(2026, 8, 27)})

    assert payload["alert_date"] == datetime(2026, 8, 27, tzinfo=timezone.utc)
    BSON.encode(payload)


def test_nested_update_payload_normalizes_dates_without_changing_other_values():
    payload = normalize_mongo_value(
        {
            "$set": {"updated_at": datetime(2026, 8, 27, 12, tzinfo=timezone.utc)},
            "history": [date(2026, 8, 26), "kept"],
        }
    )

    assert payload["$set"]["updated_at"].hour == 12
    assert payload["history"][0] == datetime(2026, 8, 26, tzinfo=timezone.utc)
    assert payload["history"][1] == "kept"
    BSON.encode(payload)


def test_naive_datetime_is_explicitly_treated_as_utc():
    assert to_mongo_datetime(datetime(2026, 8, 27)).tzinfo == timezone.utc
