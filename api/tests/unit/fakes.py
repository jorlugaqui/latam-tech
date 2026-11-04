"""Test doubles for ports. Each must be substitutable for the real adapter (LSP)."""

from dataclasses import dataclass


@dataclass
class FakeDatabaseProbe:
    reachable: bool = True

    def is_reachable(self) -> bool:
        return self.reachable
