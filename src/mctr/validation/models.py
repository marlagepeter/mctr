"""Data contracts for post-hoc historical signal validation."""

from typing import Any, Optional, Union

from dataclasses import dataclass

@dataclass(frozen=True)
class ValidationObservation:
    """One signal snapshot plus strictly future-only validation labels."""

    date: Any
    symbol: str
    position_score: Optional[float] = None
    chip_score: Optional[float] = None
    exhaustion_score: Optional[float] = None
    momentum_reversal_score: Optional[float] = None
    trend_transition_score: Optional[float] = None
    resonance_score: Optional[float] = None
    structural_bottom_score: Optional[float] = None
    confirmation_factor: Optional[float] = None
    contradiction_factor: Optional[float] = None
    risk_factor: Optional[float] = None
    bottom_probability: Optional[float] = None
    bottom_level: Optional[str] = None
    risk_override_state: Optional[str] = None
    rr1: Optional[float] = None
    rr2: Optional[float] = None
    rr_extreme: Optional[float] = None
    forward_return_5d: Optional[float] = None
    forward_return_20d: Optional[float] = None
    forward_return_60d: Optional[float] = None
    forward_return_120d: Optional[float] = None
    forward_return_250d: Optional[float] = None
    mfe_20d: Optional[float] = None
    mfe_60d: Optional[float] = None
    mfe_120d: Optional[float] = None
    mae_20d: Optional[float] = None
    mae_60d: Optional[float] = None
    mae_120d: Optional[float] = None

@dataclass(frozen=True)
class CaseStudyResult:
    """Transparent result for a named reference case."""

    symbol: str
    reference_date: Any
    available: bool
    validation_data_incomplete: bool
    observation: Optional[ValidationObservation]
    first_l2_date: Optional[Any] = None
    first_l3_date: Optional[Any] = None
    first_l4_date: Optional[Any] = None
    note: str = ""
