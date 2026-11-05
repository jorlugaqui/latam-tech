import datetime as dt
from typing import Protocol


class Clock(Protocol):
    def now(self) -> dt.datetime:
        """The current time, timezone-aware in UTC."""
        ...
