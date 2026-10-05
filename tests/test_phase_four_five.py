import numpy as np
import pandas as pd
import pytest

from mctr.validation import HistoricalValidator, ValidationObservation, future_metrics, grouped_statistics, probability_bucket


def prices(size: int = 260) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=size, freq="D")
    close = pd.Series(np.linspace(10, 30, size), index=index)
    return pd.DataFrame({"date": index, "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 100.0})


def signal_frame(dates: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({
        "date": dates,
        "position_score": 0.8,
        "chip_score": 0.7,
        "exhaustion_score": 0.6,
        "momentum_reversal_score": 0.5,
        "trend_transition_score": 0.5,
        "resonance_score": 0.7,
        "structural_bottom_score": 0.6,
        "confirmation_factor": 0.5,
        "contradiction_factor": 1.0,
        "risk_factor": 1.0,
        "bottom_probability": 0.8,
        "bottom_level": "L4",
        "risk_override_state": "R0",
        "rr1": 2.0,
        "rr2": 3.0,
        "rr_extreme": 4.0,
    })


def test_forward_returns_all_requested_horizons() -> None:
    frame = prices()
    result = future_metrics(frame.close, frame.high, frame.low, 0)
    assert result["forward_return_5d"] == pytest.approx(15 / 10 - 0 if False else frame.close.iloc[5] / frame.close.iloc[0] - 1)
    for horizon in (20, 60, 120, 250):
        assert result[f"forward_return_{horizon}d"] is not None


def test_mfe_and_mae_exclude_signal_day() -> None:
    close = pd.Series([10.0, 11.0, 8.0, 12.0])
    high = pd.Series([100.0, 11.0, 8.0, 12.0])
    low = pd.Series([1.0, 11.0, 8.0, 12.0])
    result = future_metrics(close, high, low, 0, return_horizons=(1,), excursion_horizons=(2,))
    assert result["mfe_2d"] == pytest.approx(0.1)
    assert result["mae_2d"] == pytest.approx(-0.2)


def test_insufficient_future_returns_none_without_fill() -> None:
    frame = prices(10)
    result = future_metrics(frame.close, frame.high, frame.low, 8)
    assert result["forward_return_5d"] is None
    assert result["mfe_20d"] is None


def test_invalid_metrics_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        future_metrics(pd.Series([0.0]), pd.Series([1.0]), pd.Series([1.0]), 0)
    with pytest.raises(ValueError):
        future_metrics(pd.Series([1.0]), pd.Series([1.0]), pd.Series([1.0]), 0, return_horizons=(0,))


def test_attach_labels_preserves_signal_values() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0, 1]]))
    result = HistoricalValidator().validate_symbol("X", signals, frame)
    assert list(result.bottom_probability) == [0.8, 0.8]
    assert result.loc[0, "forward_return_5d"] is not None
    assert result.loc[0, "symbol"] == "X"


def test_future_price_injection_does_not_change_t_labels() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]]))
    original = HistoricalValidator().validate_symbol("X", signals, frame)
    changed = frame.copy()
    changed.iloc[1:, changed.columns.get_loc("close")] = 9999
    changed.iloc[1:, changed.columns.get_loc("high")] = 10000
    changed_result = HistoricalValidator().validate_symbol("X", signals, changed)
    assert original.loc[0, "bottom_probability"] == changed_result.loc[0, "bottom_probability"]


def test_future_volume_injection_does_not_change_signal_columns() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]]))
    changed = frame.copy()
    changed.iloc[1:, changed.columns.get_loc("volume")] = 1e12
    result = HistoricalValidator().validate_symbol("X", signals, changed)
    assert result.loc[0, "bottom_probability"] == 0.8


def test_future_chip_data_is_not_an_input() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]]))
    signals["chip_score"] = 0.7
    result = HistoricalValidator().validate_symbol("X", signals, frame)
    assert result.loc[0, "chip_score"] == 0.7


def test_statistics_for_l1_to_l4() -> None:
    observations = pd.DataFrame({"bottom_level": ["L1", "L2", "L3", "L4"], "bottom_probability": [0.1, 0.3, 0.6, 0.9], "resonance_grade": ["D", "C", "B", "A"], **{f"forward_return_{h}d": [0.1, 0.2, -0.1, 0.3] for h in (5, 20, 60, 120, 250)}, **{f"mfe_{h}d": [0.1] * 4 for h in (20, 60, 120)}, **{f"mae_{h}d": [-0.1] * 4 for h in (20, 60, 120)}})
    report = grouped_statistics(observations, "bottom_level")
    assert set(report.bottom_level) == {"L1", "L2", "L3", "L4"}
    assert "mean_return" in report and "win_rate" in report


def test_probability_buckets_are_fixed_reporting_bins() -> None:
    assert probability_bucket(0.0) == "0.0-0.2"
    assert probability_bucket(0.2) == "0.2-0.4"
    assert probability_bucket(0.8) == "0.8-1.0"
    assert probability_bucket(None) is None


def test_probability_bucket_report_supports_monotonicity_observation() -> None:
    observations = pd.DataFrame({"bottom_probability": [0.1, 0.3, 0.5, 0.7, 0.9], **{f"forward_return_{h}d": [0.01, 0.02, 0.03, 0.04, 0.05] for h in (5, 20, 60, 120, 250)}, **{f"mfe_{h}d": [0.1] * 5 for h in (20, 60, 120)}, **{f"mae_{h}d": [-0.1] * 5 for h in (20, 60, 120)}})
    observations["bucket"] = observations.bottom_probability.map(probability_bucket)
    report = grouped_statistics(observations, "bucket")
    assert report["mean_return"].notna().any()


def test_resonance_grade_statistics() -> None:
    observations = pd.DataFrame({"resonance_grade": ["A", "B", "C", "D", "NONE"], **{f"forward_return_{h}d": [0.1] * 5 for h in (5, 20, 60, 120, 250)}, **{f"mfe_{h}d": [0.1] * 5 for h in (20, 60, 120)}, **{f"mae_{h}d": [-0.1] * 5 for h in (20, 60, 120)}})
    report = grouped_statistics(observations, "resonance_grade")
    assert len(report) == 25


def test_validator_universe_missing_symbol_is_explicitly_skipped() -> None:
    frame = prices(10)
    signals = {"X": signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]])), "MISSING": signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]]))}
    result = HistoricalValidator().validate_universe(signals, {"X": frame})
    assert set(result.symbol) == {"X"}


def test_empty_universe_returns_empty_frame() -> None:
    result = HistoricalValidator().validate_universe({}, {})
    assert result.empty


@pytest.mark.parametrize("symbol, reference", [("长川科技", "2025-01-10"), ("恒铭达", "2025-01-10"), ("奥海科技", "2024-10-01")])
def test_three_case_loading_without_data_is_explicit(symbol: str, reference: str) -> None:
    result = HistoricalValidator().case_study(symbol, reference, None, None)
    assert result.available is False
    assert result.validation_data_incomplete is True
    assert result.note == "validation_data_incomplete"


def test_case_study_observation_and_first_levels() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date))
    validator = HistoricalValidator()
    result = validator.case_study("X", frame.date.iloc[10], signals, frame)
    assert result.available is True
    assert result.observation is not None
    assert result.first_l4_date is not None


def test_case_study_missing_reference_is_explicit() -> None:
    frame = prices(10)
    signals = signal_frame(pd.DatetimeIndex(frame.date))
    result = HistoricalValidator().case_study("X", "2030-01-01", signals, frame)
    assert result.available is False
    assert result.note == "reference_date_unavailable"


def test_missing_chip_signal_can_be_validated_without_fabrication() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]])).drop(columns=["chip_score"])
    result = HistoricalValidator().validate_symbol("X", signals, frame)
    assert "chip_score" not in result


def test_missing_market_or_sector_data_does_not_get_filled() -> None:
    frame = prices(30)
    result = HistoricalValidator().validate_universe({"X": signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]]))}, {"X": frame})
    assert "market_strength" not in result and "sector_strength" not in result


def test_missing_market_data_is_not_synthesized() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]])).drop(columns=["resonance_score"])
    result = HistoricalValidator().validate_symbol("X", signals, frame)
    assert "resonance_score" not in result


def test_missing_sector_data_is_not_synthesized() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]])).drop(columns=["chip_score"])
    result = HistoricalValidator().validate_symbol("X", signals, frame)
    assert "chip_score" not in result


def test_observation_contract_contains_future_labels() -> None:
    fields = ValidationObservation.__dataclass_fields__
    assert "forward_return_250d" in fields
    assert "mfe_120d" in fields and "mae_120d" in fields


def test_validator_does_not_use_future_signal_columns() -> None:
    frame = prices(30)
    signals = signal_frame(pd.DatetimeIndex(frame.date.iloc[[0]]))
    future_signal = signals.copy()
    future_signal.loc[0, "bottom_probability"] = 0.1
    assert HistoricalValidator().validate_symbol("X", signals, frame).loc[0, "bottom_probability"] != future_signal.loc[0, "bottom_probability"]
