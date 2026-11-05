"""Relevance criteria and their registry (spec disruption-assessment, design D3). OCP.

A criterion reads per-segment impact facts and returns the reasons it matches. Its
parameters and tier come from the versioned rule set, validated by the criterion's own
``Params`` model. A new rule is a new class here plus a row in the database; neither the
solver nor the schema changes. Any unknown key or invalid params makes the whole rule set
invalid, so the assessment fails closed.
"""

from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from companion.schemas.assessment import (
    ConnectionStatus,
    CriterionConfig,
    Reason,
    SegmentImpact,
    SegmentStatus,
    Tier,
)


class InvalidRuleSet(Exception):
    """The rule set cannot be used: unknown criterion key or invalid parameters."""


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Criterion(Protocol):
    key: ClassVar[str]

    def evaluate(self, impacts: list[SegmentImpact]) -> list[Reason]: ...


class CancellationCriterion:
    key: ClassVar[str] = "CANCELLATION"

    class Params(_Params):
        pass

    def __init__(self, params: Params) -> None:
        self.params = params

    def evaluate(self, impacts: list[SegmentImpact]) -> list[Reason]:
        return [
            Reason(code=self.key, segment_ids=[i.segment_id], event_ids=i.evidence)
            for i in impacts
            if i.status is SegmentStatus.CANCELLED
        ]


class MissedConnectionCriterion:
    key: ClassVar[str] = "MISSED_CONNECTION"

    class Params(_Params):
        default_mct_minutes: int = Field(ge=0)
        mct_by_airport: dict[str, int] = Field(default_factory=dict)

        def mct_for(self, airport: str) -> int:
            return self.mct_by_airport.get(airport, self.default_mct_minutes)

    def __init__(self, params: Params) -> None:
        self.params = params

    def evaluate(self, impacts: list[SegmentImpact]) -> list[Reason]:
        return [
            Reason(
                code=self.key,
                segment_ids=[i.segment_id, i.connection.to_segment_id],
                event_ids=i.evidence,
            )
            for i in impacts
            if i.connection is not None and i.connection.status is ConnectionStatus.MISSED
        ]


class _DelayAtLeast:
    key: ClassVar[str]

    class Params(_Params):
        min_delay_minutes: int = Field(gt=0)

    def __init__(self, params: Params) -> None:
        self.params = params

    def evaluate(self, impacts: list[SegmentImpact]) -> list[Reason]:
        return [
            Reason(code=self.key, segment_ids=[i.segment_id], event_ids=i.evidence)
            for i in impacts
            if i.status is SegmentStatus.DELAYED
            and i.delay_minutes is not None
            and i.delay_minutes >= self.params.min_delay_minutes
        ]


class LongDelayCriterion(_DelayAtLeast):
    key: ClassVar[str] = "LONG_DELAY"


class MinorDelayCriterion(_DelayAtLeast):
    key: ClassVar[str] = "MINOR_DELAY"


class GateChangeCriterion:
    key: ClassVar[str] = "GATE_CHANGE"

    class Params(_Params):
        pass

    def __init__(self, params: Params) -> None:
        self.params = params

    def evaluate(self, impacts: list[SegmentImpact]) -> list[Reason]:
        return [
            Reason(
                code=self.key,
                segment_ids=[i.segment_id],
                event_ids=[i.gate_event_id] if i.gate_event_id else [],
            )
            for i in impacts
            if i.gate is not None
        ]


REGISTRY: dict[str, type] = {
    cls.key: cls
    for cls in (
        CancellationCriterion,
        MissedConnectionCriterion,
        LongDelayCriterion,
        MinorDelayCriterion,
        GateChangeCriterion,
    )
}


def _instantiate(config: CriterionConfig) -> Criterion:
    cls = REGISTRY.get(config.key)
    if cls is None:
        raise InvalidRuleSet(f"unknown criterion {config.key!r}")
    try:
        params = cls.Params.model_validate(config.params)
    except ValidationError as exc:
        raise InvalidRuleSet(f"invalid params for {config.key!r}") from exc
    return cls(params)


def build_criteria(configs: list[CriterionConfig]) -> list[tuple[Tier, Criterion]]:
    """Validate every criterion (enabled or not) and return the enabled ones."""
    built = [(config, _instantiate(config)) for config in configs]
    return [(config.tier, criterion) for config, criterion in built if config.enabled]


def missed_connection_params(configs: list[CriterionConfig]) -> MissedConnectionCriterion.Params:
    """MCTs for computing connection facts, whether or not the criterion is enabled."""
    for config in configs:
        if config.key == MissedConnectionCriterion.key:
            criterion = _instantiate(config)
            return criterion.params  # type: ignore[attr-defined]
    raise InvalidRuleSet("rule set has no MISSED_CONNECTION parameters (MCT)")
