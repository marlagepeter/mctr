"""Effective tradable chip calculations from dated holder information."""

from datetime import date
from typing import Mapping, Protocol, Sequence

import pandas as pd

from mctr.chips.models import (
    ActiveRatioResult,
    EffectiveTradableChipsResult,
    RestrictedShare,
    ShareholderHolding,
    ShareholderType,
)
from mctr.config import ChipConfig


def _as_timestamp(value: date | object) -> pd.Timestamp:
    """Normalize date-like values without accepting an invalid timestamp."""
    return pd.Timestamp(value)


def effective_free_float(
    free_float: float,
    restricted_shares: Sequence[RestrictedShare] = (),
    as_of_date: date | object | None = None,
) -> float:
    """Return the supplied as-of free float without subtracting restrictions again.

    ``free_float`` is the authoritative tradable-share universe. Restricted-share
    records are retained for dated future updates, but are deliberately never
    subtracted from it because the source definitions may overlap.
    """
    if free_float < 0.0:
        raise ValueError("free_float must be non-negative")
    if as_of_date is not None:
        cutoff = _as_timestamp(as_of_date)
        for record in restricted_shares:
            if record.source_date is not None and _as_timestamp(record.source_date) > cutoff:
                continue
            _as_timestamp(record.unlock_date)
    return float(free_float)


def _resolved_weight(
    holding: ShareholderHolding,
    weights: Mapping[ShareholderType, float],
    unknown_weight: float,
) -> float:
    """Resolve explicit holder weight first, then the configured type prior."""
    if holding.activity_weight is not None:
        return holding.activity_weight
    try:
        holder_type = ShareholderType(holding.shareholder_type)
    except ValueError:
        holder_type = ShareholderType.UNKNOWN
    return weights.get(holder_type, unknown_weight)


def calculate_active_ratio(
    free_float: float,
    holdings: Sequence[ShareholderHolding] | None = None,
    activity_weights: Mapping[ShareholderType, float] | None = None,
    config: ChipConfig = ChipConfig(),
    as_of_date: date | object | None = None,
) -> ActiveRatioResult:
    """Calculate active shares divided by free float.

    Known holdings are weighted by explicit values or configured type priors. Any
    uncovered portion of free float receives the configured unknown prior, so a
    partial shareholder list cannot silently imply zero activity. With no holdings,
    the result is an explicit low-confidence fallback.
    """
    free_float = effective_free_float(free_float, as_of_date=as_of_date)
    if free_float <= 0.0:
        raise ValueError("free_float must be positive")
    weights = activity_weights or config.activity_weights
    records = list(holdings or ())
    if as_of_date is not None:
        cutoff = _as_timestamp(as_of_date)
        records = [
            record for record in records
            if record.effective_date is None or _as_timestamp(record.effective_date) <= cutoff
        ]
    if not records:
        return ActiveRatioResult(
            active_ratio=config.unknown_activity_weight,
            confidence="low",
            fallback_used=True,
            covered_shares=0.0,
        )
    covered_shares = sum(record.shares for record in records)
    if covered_shares > free_float + 1e-9:
        raise ValueError("shareholder holdings cannot exceed free_float")
    weighted_shares = sum(
        record.shares * _resolved_weight(record, weights, config.unknown_activity_weight)
        for record in records
    )
    uncovered = free_float - covered_shares
    weighted_shares += uncovered * config.unknown_activity_weight
    ratio = weighted_shares / free_float
    return ActiveRatioResult(
        active_ratio=min(max(ratio, 0.0), 1.0),
        confidence=(
            "high"
            if covered_shares >= free_float * config.known_coverage_confidence_threshold
            else "medium"
        ),
        fallback_used=False,
        covered_shares=covered_shares,
    )


def calculate_effective_tradable_chips(
    free_float: float,
    holdings: Sequence[ShareholderHolding] | None = None,
    activity_weights: Mapping[ShareholderType, float] | None = None,
    config: ChipConfig = ChipConfig(),
    as_of_date: date | object | None = None,
) -> EffectiveTradableChipsResult:
    """Return ``ETC = free_float * active_ratio`` with audit metadata."""
    active = calculate_active_ratio(
        free_float, holdings, activity_weights, config, as_of_date,
    )
    return EffectiveTradableChipsResult(
        free_float=float(free_float),
        active_ratio=active.active_ratio,
        effective_tradable_chips=float(free_float) * active.active_ratio,
        confidence=active.confidence,
        fallback_used=active.fallback_used,
    )


class ActivityCalibrator(Protocol):
    """Future interface for fitting activity priors from historical observations."""

    def fit(self, observations: object) -> Mapping[ShareholderType, float]:
        """Fit weights without changing the V1 prior defaults."""
