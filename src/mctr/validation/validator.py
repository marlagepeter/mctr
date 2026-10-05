"""DataFrame-driven historical validation orchestration."""

from typing import Optional, Union

from collections.abc import Mapping

import pandas as pd

from .metrics import attach_future_labels, grouped_statistics, probability_bucket
from .models import CaseStudyResult

class HistoricalValidator:
    """Validate frozen signal snapshots without recalculating Phase 1-4."""

    def validate_symbol(
        self,
        symbol: str,
        signals: pd.DataFrame,
        ohlcv: pd.DataFrame,
        date_column: str = "date",
    ) -> pd.DataFrame:
        """Attach future labels to already-computed signal rows."""
        return attach_future_labels(signals, ohlcv, symbol, date_column)

    def validate_universe(
        self,
        signals_by_symbol: Mapping[str, pd.DataFrame],
        ohlcv_by_symbol: Mapping[str, pd.DataFrame],
        date_column: str = "date",
    ) -> pd.DataFrame:
        """Validate each symbol and concatenate observations without imputation."""
        frames = [
            self.validate_symbol(symbol, signals, ohlcv_by_symbol[symbol], date_column)
            for symbol, signals in signals_by_symbol.items()
            if symbol in ohlcv_by_symbol
        ]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def statistics(self, observations: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Return fixed level, probability-bucket and resonance reports."""
        frame = observations.copy()
        if "bottom_probability" in frame:
            frame["probability_bucket"] = frame["bottom_probability"].map(probability_bucket)
        reports: dict[str, pd.DataFrame] = {}
        if "bottom_level" in frame:
            reports["bottom_level"] = grouped_statistics(frame, "bottom_level")
        if "probability_bucket" in frame:
            reports["probability_bucket"] = grouped_statistics(frame, "probability_bucket")
        if "resonance_grade" in frame:
            reports["resonance_grade"] = grouped_statistics(frame, "resonance_grade")
        return reports

    def case_study(
        self,
        symbol: str,
        reference_date: object,
        signals: Optional[pd.DataFrame],
        ohlcv: Optional[pd.DataFrame],
        date_column: str = "date",
    ) -> CaseStudyResult:
        """Analyze a named reference window, or explicitly report unavailable data."""
        if signals is None or ohlcv is None or signals.empty or ohlcv.empty:
            return CaseStudyResult(symbol, reference_date, False, True, None, note="validation_data_incomplete")
        frame = self.validate_symbol(symbol, signals, ohlcv, date_column)
        dates = pd.to_datetime(frame[date_column])
        target = pd.Timestamp(reference_date)
        candidates = frame.loc[dates == target]
        if candidates.empty:
            return CaseStudyResult(symbol, reference_date, False, True, None, note="reference_date_unavailable")
        row = candidates.iloc[0].to_dict()
        row["date"] = row.pop(date_column)
        fields = {field: row.get(field) for field in CaseStudyResult.__annotations__ if field in row}
        from .models import ValidationObservation

        observation = ValidationObservation(**{field: row.get(field) for field in ValidationObservation.__annotations__})
        window = frame.loc[(dates >= target - pd.Timedelta(days=45)) & (dates <= target + pd.Timedelta(days=45))]
        def first(level: str):
            matching = window.loc[window.get("bottom_level") == level]
            return matching[date_column].iloc[0] if not matching.empty else None
        return CaseStudyResult(symbol, reference_date, True, False, observation, first("L2"), first("L3"), first("L4"))
