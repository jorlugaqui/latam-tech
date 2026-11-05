"""Policy rule conditions with the Interpreter pattern (spec recommendation, design D2).

Grammar (whitespace-separated, case-sensitive):

    condition := clause ( " AND " clause )*
    clause    := FACT [ OP LITERAL ]          # a bare FACT means FACT == true
    FACT      := [a-z_][a-z0-9_]*
    OP        := >= | <= | == | > | <
    LITERAL   := -?[0-9]+ | true | false

A condition is parsed into a small AST and evaluated with three-valued (Kleene) logic.
Nothing is ever executed: anything outside the grammar parses to ``None`` and evaluates
to UNKNOWN, which never grants an entitlement.
"""

import operator
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

FactValue = int | bool | None

_CLAUSE = re.compile(
    r"^(?P<fact>[a-z_][a-z0-9_]*)(?: (?P<op>>=|<=|==|>|<) (?P<literal>-?[0-9]+|true|false))?$"
)
_OPS: dict[str, Callable[[int, int], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    ">": operator.gt,
    "<": operator.lt,
}
_MAX_CLAUSES = 8


class Tri(Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Comparison:
    fact: str
    op: str
    literal: int | bool

    def evaluate(self, facts: Mapping[str, FactValue]) -> Tri:
        value = facts.get(self.fact)
        if value is None:
            return Tri.UNKNOWN
        # bool is a subclass of int in Python: compare kinds explicitly.
        if isinstance(value, bool) != isinstance(self.literal, bool):
            return Tri.UNKNOWN
        if isinstance(value, bool) and self.op != "==":
            return Tri.UNKNOWN
        return Tri.TRUE if _OPS[self.op](value, self.literal) else Tri.FALSE


@dataclass(frozen=True)
class And:
    clauses: tuple[Comparison, ...]

    def evaluate(self, facts: Mapping[str, FactValue]) -> Tri:
        results = [clause.evaluate(facts) for clause in self.clauses]
        if Tri.FALSE in results:
            return Tri.FALSE
        if Tri.UNKNOWN in results:
            return Tri.UNKNOWN
        return Tri.TRUE


def _literal(text: str) -> int | bool:
    if text == "true":
        return True
    if text == "false":
        return False
    return int(text)


def parse(condition: str) -> And | None:
    parts = condition.split(" AND ")
    if not condition or len(parts) > _MAX_CLAUSES:
        return None
    clauses: list[Comparison] = []
    for part in parts:
        match = _CLAUSE.match(part)
        if match is None:
            return None
        if match["op"] is None:
            clauses.append(Comparison(match["fact"], "==", True))
        else:
            clauses.append(Comparison(match["fact"], match["op"], _literal(match["literal"])))
    return And(tuple(clauses))


def evaluate(condition: str, facts: Mapping[str, FactValue]) -> Tri:
    tree = parse(condition)
    return Tri.UNKNOWN if tree is None else tree.evaluate(facts)
