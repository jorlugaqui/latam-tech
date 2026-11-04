from typing import Protocol


class DatabaseProbe(Protocol):
    """Answers whether the database can serve queries right now.

    Implementations must not raise: a failure is reported as ``False``.
    """

    def is_reachable(self) -> bool: ...
