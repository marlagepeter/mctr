"""Bottom, top, risk, and risk/reward engine extension points."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResistanceZone:
    """A target area rather than a falsely precise target price."""

    lower: float
    upper: float
    label: str
    confidence: float | None = None


@dataclass(frozen=True)
class RiskReward:
    """Risk/reward contract using resistance zones."""

    entry: float
    downside: float
    first_target: ResistanceZone
    second_target: ResistanceZone | None = None
    extreme_target: ResistanceZone | None = None
    ratio: float | None = None


# TODO: implement calibrated nonlinear Bottom/Top engines and Risk Override.
