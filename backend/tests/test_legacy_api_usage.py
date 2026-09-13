from datetime import datetime, timedelta, timezone

from scripts.report_legacy_api_usage import _parse_events, build_report


def test_legacy_usage_report_filters_time_and_groups_paths() -> None:
    start = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)
    events = _parse_events(
        (
        "INFO legacy_api_call "
        '{"event":"legacy_api_call","path":"/api/tasks","method":"GET",'
        '"user_agent":"Browser","logged_at":"2026-09-09T08:05:00+00:00"}\n'
        "INFO legacy_api_call "
        '{"event":"legacy_api_call","path":"/api/tasks","method":"GET",'
        '"user_agent":"Browser","logged_at":"2026-09-09T08:06:00+00:00"}\n'
        "INFO legacy_api_call "
        '{"event":"legacy_api_call","path":"/api/old","method":"POST",'
        '"user_agent":"Script","logged_at":"2026-09-09T09:00:00+00:00"}\n'
        "INFO legacy_api_call "
        '{"event":"legacy_api_call","path":"/api/outside","method":"GET",'
        '"user_agent":"Browser","logged_at":"2026-09-09T10:00:00+00:00"}\n'
        ).splitlines(),
        since=start,
        until=start + timedelta(hours=1),
    )

    assert len(events) == 3
    report = build_report(events)
    assert "/api/tasks | 2" in report
    assert "/api/old | 1" in report
    assert "Browser | 2" in report
    assert "Script | 1" in report
