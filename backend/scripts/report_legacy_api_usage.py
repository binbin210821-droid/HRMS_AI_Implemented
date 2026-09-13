"""Tổng hợp log legacy API do LegacyApiUsageMiddleware ghi ra."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_PATTERN = re.compile(r"legacy_api_call\s+(\{.*\})\s*$")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Thời gian phải có múi giờ, ví dụ 2026-09-09T00:00:00+00:00")
    return parsed


def _parse_events(
    lines: Iterable[str], since: datetime | None, until: datetime | None
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in lines:
        match = LOG_PATTERN.search(line)
        if not match:
            continue
        try:
            event = json.loads(match.group(1))
            logged_at = _parse_datetime(event.get("logged_at"))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if logged_at is not None and (since is not None and logged_at < since):
            continue
        if logged_at is not None and (until is not None and logged_at > until):
            continue
        events.append(event)
    return events


def _read_events(log_file: Path, since: datetime | None, until: datetime | None) -> list[dict[str, Any]]:
    return _parse_events(log_file.read_text(encoding="utf-8").splitlines(), since, until)


def build_report(events: list[dict[str, Any]]) -> str:
    paths = Counter(str(event.get("path") or "(không rõ path)") for event in events)
    agents = Counter(str(event.get("user_agent") or "(không có User-Agent)") for event in events)
    lines = [f"Tổng request API cũ: {len(events)}", "", "Path | Số lần", "--- | ---"]
    lines.extend(f"{path} | {count}" for path, count in paths.most_common())
    lines.extend(["", "User-Agent phổ biến | Số lần", "--- | ---"])
    lines.extend(f"{agent} | {count}" for agent, count in agents.most_common())
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Báo cáo mức sử dụng API /api cũ")
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--since", help="ISO-8601 có múi giờ")
    parser.add_argument("--until", help="ISO-8601 có múi giờ")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(build_report(_read_events(args.log_file, _parse_datetime(args.since), _parse_datetime(args.until))))


if __name__ == "__main__":
    main()
