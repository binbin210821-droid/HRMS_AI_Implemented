from datetime import datetime

from app.core.time import BusinessClock


class FixedBusinessClock(BusinessClock):
    def __init__(self, value: datetime) -> None:
        super().__init__("Asia/Ho_Chi_Minh")
        self._value = value

    def now(self) -> datetime:
        return self._value
