"""Standard historical data contracts for MCTR input preparation."""

from typing import Any, Optional, Union

from dataclasses import dataclass

import pandas as pd

@dataclass(frozen=True)
class DataQualityReport:
    """Auditable data quality findings; validation never silently repairs data."""

    symbol: Optional[str]
    date_range: Optional[tuple[pd.Timestamp, pd.Timestamp]]
    row_count: int
    missing_dates: tuple[pd.Timestamp, ...]
    duplicate_dates: tuple[pd.Timestamp, ...]
    missing_columns: tuple[str, ...]
    invalid_rows: tuple[int, ...]
    future_rows: tuple[int, ...]
    chip_data_available: bool
    market_data_available: bool
    sector_data_available: bool

@dataclass(frozen=True)
class MarketDataBundle:
    """Market indices and optional breadth input tables."""

    indices: dict[str, pd.DataFrame]
    breadth: Optional[pd.DataFrame] = None

@dataclass(frozen=True)
class HistoricalChipInput:
    """Historical free-float and shareholder records for Phase 2 consumption."""

    free_float: Optional[pd.DataFrame]
    shareholders: Optional[pd.DataFrame]
    chip_data_available: bool

@dataclass(frozen=True)
class HistoricalDataSnapshot:
    """All inputs observable for one symbol at one as-of date."""

    as_of_date: pd.Timestamp
    symbol: str
    stock_ohlcv: Optional[pd.DataFrame]
    market_data: Optional[MarketDataBundle]
    sector_data: Optional[pd.DataFrame]
    breadth: Optional[pd.DataFrame]
    free_float: Optional[pd.DataFrame]
    shareholders: Optional[pd.DataFrame]
    chip_input: Optional[HistoricalChipInput]
    chip_data_available: bool
    market_data_available: bool
    sector_data_available: bool

@dataclass(frozen=True)
class StockDataBundle:
    """Validated multi-symbol stock table wrapper."""

    frame: pd.DataFrame

@dataclass(frozen=True)
class SectorDataBundle:
    """Validated multi-sector table wrapper."""

    frame: pd.DataFrame
