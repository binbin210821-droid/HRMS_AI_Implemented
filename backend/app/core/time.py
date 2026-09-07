from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings

UTC = timezone.utc


class BusinessClock:
    """Một nguồn duy nhất cho giờ nghiệp vụ và ranh giới ngày của hệ thống."""

    def __init__(self, timezone_name: str | None = None) -> None:
        self.timezone = ZoneInfo(timezone_name or get_settings().business_timezone)

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().astimezone(self.timezone).date()

    def start_of_day(self, value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=self.timezone).astimezone(UTC)

    def end_of_day(self, value: date) -> datetime:
        return self.start_of_day(value + timedelta(days=1))

    def date_range(self, start: date, end: date) -> tuple[datetime, datetime]:
        """Trả về khoảng [start, end + 1 ngày) ở UTC để truy vấn MongoDB."""
        return self.start_of_day(start), self.end_of_day(end)

    def localize(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Datetime nghiệp vụ phải có múi giờ")
        return value.astimezone(self.timezone)

    @staticmethod
    def as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Datetime nghiệp vụ phải có múi giờ")
        return value.astimezone(UTC)


business_clock = BusinessClock()


__all__ = ["UTC", "BusinessClock", "business_clock"]
