"""Data contracts for effective tradable chips and chip density."""

from typing import Optional, Protocol, Union

from dataclasses import dataclass
from datetime import date
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass

import pandas as pd

class ShareholderType(StrEnum):
    """Configurable holder categories used to resolve activity priors."""

    RETAIL = "retail"
    INSTITUTION = "institution"
    FUND = "fund"
    INSURANCE = "insurance"
    SOCIAL_SECURITY = "social_security"
    COMPANY = "company"
    CONTROLLER = "controller"
    EXECUTIVE = "executive"
    STRATEGIC = "strategic"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class HolderActivity:
    """Configurable activity weight for a holder category."""

    category: str
    active_ratio: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.active_ratio <= 1.0:
            raise ValueError("active_ratio must be between 0 and 1")

@dataclass(frozen=True)
class ShareholderHolding:
    """A point-in-time holder record inside the free-float universe."""

    holder_name: str
    shares: float
    ownership_ratio: float
    shareholder_type: ShareholderType = ShareholderType.UNKNOWN
    is_top10_tradable: bool = False
    is_controller_related: bool = False
    is_executive_related: bool = False
    is_strategic: bool = False
    activity_weight: Optional[float] = None
    effective_date: Optional[Union[pd.Timestamp, date]] = None

    def __post_init__(self) -> None:
        if self.shares < 0.0:
            raise ValueError("shares must be non-negative")
        if not 0.0 <= self.ownership_ratio <= 1.0:
            raise ValueError("ownership_ratio must be between 0 and 1")
        if self.activity_weight is not None and not 0.0 <= self.activity_weight <= 1.0:
            raise ValueError("activity_weight must be between 0 and 1")

    @property
    def effective_shares(self) -> float:
        """Shares after the explicitly supplied activity weight."""
        if self.activity_weight is None:
            raise ValueError("activity_weight must be resolved before reading effective_shares")
        return self.shares * self.activity_weight

@dataclass(frozen=True)
class RestrictedShare:
    """A dated restriction record; it is never subtracted from free float again."""

    shares: float
    unlock_date: Union[pd.Timestamp, date]
    holder_type: ShareholderType = ShareholderType.UNKNOWN
    source_date: Optional[Union[pd.Timestamp, date]] = None

    def __post_init__(self) -> None:
        if self.shares < 0.0:
            raise ValueError("shares must be non-negative")

@dataclass(frozen=True)
class ActiveRatioResult:
    """Auditable active-ratio result with confidence and fallback metadata."""

    active_ratio: float
    confidence: str
    fallback_used: bool
    covered_shares: float

@dataclass(frozen=True)
class EffectiveTradableChips:
    """ETC inputs based on free float and activity, avoiding double subtraction."""

    free_float: float
    active_ratio: float

    @property
    def value(self) -> float:
        """Effective tradable chips."""
        return self.free_float * self.active_ratio

@dataclass(frozen=True)
class EffectiveTradableChipsResult:
    """Complete ETC output required by the research layer."""

    free_float: float
    active_ratio: float
    effective_tradable_chips: float
    confidence: str
    fallback_used: bool

@dataclass(frozen=True)
class ChipProfile:
    """Point-in-time raw chip features for one as-of trading date."""

    as_of_date: pd.Timestamp
    free_float: float
    active_ratio: float
    effective_tradable_chips: float
    confidence: str
    fallback_used: bool
    peak_price: Optional[float]
    peak_density: Optional[float]
    core_lower: Optional[float]
    core_upper: Optional[float]
    core_coverage: Optional[float]
    concentration: Optional[float]
    support_density: Optional[float]
    resistance_density: Optional[float]
    migration_5d: Optional[float]
    migration_20d: Optional[float]
    migration_60d: Optional[float]
    migration_velocity_5d: Optional[float]
    migration_velocity_20d: Optional[float]
    migration_velocity_60d: Optional[float]
    divergence_20d: Optional[float]
    divergence_60d: Optional[float]
    density: pd.Series
    normalized_density: pd.Series

@dataclass(frozen=True)
class ChipSnapshot:
    """Future daily chip density output contract."""

    density: pd.Series
    main_peak: Optional[float] = None
    core_range: Optional[tuple[float, float]] = None
    concentration: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    migration: Optional[float] = None
    price_divergence: Optional[float] = None

class ChipDensityEngine(Protocol):
    """Protocol for a point-in-time chip density implementation."""

    def update(self, history: pd.DataFrame, etc: EffectiveTradableChips) -> ChipSnapshot:
        """Update density from history through the current observation only."""
