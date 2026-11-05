import datetime as dt


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)
