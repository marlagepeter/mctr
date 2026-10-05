"""Integration tests for data adapters and pipeline (demonstration phase)."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from mctr.data.adapters import LocalCSVAdapter, LocalParquetAdapter, AdapterConfig
from mctr.data.pipeline import DataPipeline
from mctr.data.test_data_generator import (
    generate_sample_ohlcv,
    generate_sample_market_index,
    generate_sample_sector_index,
    generate_sample_free_float,
    generate_sample_shareholders,
)


@pytest.fixture
def temp_data_dir():
    """Create temporary directory with sample data (DEMO ONLY)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        
        # Create subdirectories
        (base_path / "ohlcv").mkdir()
        (base_path / "market").mkdir()
        (base_path / "sector").mkdir()
        (base_path / "fundamental").mkdir()
        
        # Generate and save demo data (CSV only for now)
        symbols = [f"{600000 + i:06d}" for i in range(10)]
        
        ohlcv_df = generate_sample_ohlcv(num_symbols=10, num_days=250)
        ohlcv_df.to_csv(base_path / "ohlcv" / "stocks_ohlcv.csv")
        
        market_df = generate_sample_market_index(num_days=250)
        market_df.to_csv(base_path / "market" / "market_index.csv")
        
        sector_df = generate_sample_sector_index(num_days=250)
        sector_df.to_csv(base_path / "sector" / "sector_index.csv")
        
        ff_df = generate_sample_free_float(symbols)
        ff_df.to_csv(base_path / "fundamental" / "free_float.csv")
        
        sh_df = generate_sample_shareholders(symbols)
        sh_df.to_csv(base_path / "fundamental" / "shareholders.csv")
        
        # Try to save Parquet versions but skip if pyarrow unavailable
        try:
            ohlcv_df.to_parquet(base_path / "ohlcv" / "stocks_ohlcv.parquet")
            market_df.to_parquet(base_path / "market" / "market_index.parquet")
            sector_df.to_parquet(base_path / "sector" / "sector_index.parquet")
            ff_df.to_parquet(base_path / "fundamental" / "free_float.parquet")
            sh_df.to_parquet(base_path / "fundamental" / "shareholders.parquet")
        except ImportError:
            pass  # Skip Parquet if pyarrow not available
        
        yield base_path


class TestLocalCSVAdapter:
    """Test CSV data adapter."""

    def test_load_ohlcv(self, temp_data_dir):
        """Test loading OHLCV data from CSV."""
        adapter = LocalCSVAdapter(AdapterConfig(data_dir=temp_data_dir))
        df = adapter.load_ohlcv()
        
        assert df is not None
        assert "symbol" in df.columns
        assert "open" in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)
        assert len(df) > 0

    def test_load_market_index(self, temp_data_dir):
        """Test loading market index from CSV."""
        adapter = LocalCSVAdapter(AdapterConfig(data_dir=temp_data_dir))
        df = adapter.load_market_index()
        
        assert df is not None
        assert "open" in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_load_sector_index(self, temp_data_dir):
        """Test loading sector index from CSV."""
        adapter = LocalCSVAdapter(AdapterConfig(data_dir=temp_data_dir))
        df = adapter.load_sector_index()
        
        assert df is not None
        assert "sector" in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_load_free_float(self, temp_data_dir):
        """Test loading free-float data from CSV."""
        adapter = LocalCSVAdapter(AdapterConfig(data_dir=temp_data_dir))
        df = adapter.load_free_float()
        
        assert df is not None
        assert "free_float_shares" in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_load_shareholders(self, temp_data_dir):
        """Test loading shareholder data from CSV."""
        adapter = LocalCSVAdapter(AdapterConfig(data_dir=temp_data_dir))
        df = adapter.load_shareholders()
        
        assert df is not None
        assert "shareholder_id" in df.columns
        assert "activity_weight" in df.columns

    def test_missing_directory_raises(self):
        """Test that missing data directory raises error."""
        with pytest.raises(FileNotFoundError):
            adapter = LocalCSVAdapter(AdapterConfig(data_dir="/nonexistent"))


class TestLocalParquetAdapter:
    """Test Parquet data adapter."""

    @pytest.mark.skip(reason="Requires pyarrow (optional dependency)")
    def test_load_ohlcv(self, temp_data_dir):
        """Test loading OHLCV data from Parquet."""
        adapter = LocalParquetAdapter(AdapterConfig(data_dir=temp_data_dir))
        df = adapter.load_ohlcv()
        
        assert df is not None
        assert "symbol" in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)

    @pytest.mark.skip(reason="Requires pyarrow (optional dependency)")
    def test_load_market_index(self, temp_data_dir):
        """Test loading market index from Parquet."""
        adapter = LocalParquetAdapter(AdapterConfig(data_dir=temp_data_dir))
        df = adapter.load_market_index()
        
        assert df is not None
        assert "open" in df.columns

    @pytest.mark.skip(reason="Requires pyarrow (optional dependency)")
    def test_parity_with_csv(self, temp_data_dir):
        """Test that Parquet and CSV produce identical results."""
        csv_adapter = LocalCSVAdapter(AdapterConfig(data_dir=temp_data_dir))
        parquet_adapter = LocalParquetAdapter(AdapterConfig(data_dir=temp_data_dir))
        
        csv_ohlcv = csv_adapter.load_ohlcv()
        parquet_ohlcv = parquet_adapter.load_ohlcv()
        
        # Compare (note: floating point may have slight differences)
        pd.testing.assert_frame_equal(
            csv_ohlcv.sort_index(),
            parquet_ohlcv.sort_index(),
            atol=1e-6
        )


class TestDataPipeline:
    """Test end-to-end data pipeline."""

    def test_pipeline_from_csv(self, temp_data_dir):
        """Test pipeline creation from CSV."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        data = pipeline.load(validate=False)
        
        assert data["ohlcv"] is not None
        assert data["market_index"] is not None
        assert data["sector_index"] is not None

    @pytest.mark.skip(reason="Requires pyarrow (optional dependency)")
    def test_pipeline_from_parquet(self, temp_data_dir):
        """Test pipeline creation from Parquet."""
        pipeline = DataPipeline.from_parquet(temp_data_dir)
        data = pipeline.load(validate=False)
        
        assert data["ohlcv"] is not None
        assert data["market_index"] is not None

    def test_pipeline_validate(self, temp_data_dir):
        """Test validation step."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        validated = pipeline.validate()
        
        assert validated["ohlcv"] is not None
        assert validated["market_index"] is not None

    def test_pipeline_quality_reports(self, temp_data_dir):
        """Test quality report generation."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        reports = pipeline.get_quality_reports()
        assert "ohlcv" in reports
        assert reports["ohlcv"].row_count > 0

    def test_build_snapshot(self, temp_data_dir):
        """Test snapshot building."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        # Get first available symbol
        ohlcv = pipeline._validated_data["ohlcv"]
        symbol = ohlcv["symbol"].unique()[0]
        
        snapshot = pipeline.build_snapshot(symbol, "2024-01-01")
        
        assert snapshot.symbol == symbol
        assert snapshot.stock_ohlcv is not None
        assert len(snapshot.stock_ohlcv) > 0

    def test_pit_filtering(self, temp_data_dir):
        """Test point-in-time filtering."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        symbol = pipeline._validated_data["ohlcv"]["symbol"].unique()[0]
        
        # Build snapshot as of specific date
        as_of_date = pd.Timestamp("2023-06-30")
        snapshot = pipeline.build_snapshot(symbol, as_of_date)
        
        # Verify no data beyond as_of_date
        if snapshot.stock_ohlcv is not None:
            assert snapshot.stock_ohlcv.index.max() <= as_of_date

    def test_multi_symbol_snapshot(self, temp_data_dir):
        """Test building snapshots for multiple symbols."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        as_of_date = pd.Timestamp("2024-01-01")
        snapshots = pipeline.build_snapshots_for_date(as_of_date)
        
        assert len(snapshots) > 0
        assert all(isinstance(s, type(snapshots[list(snapshots.keys())[0]])) for s in snapshots.values())


class TestDataIntegrity:
    """Test data integrity and point-in-time properties."""

    def test_no_future_data_in_snapshot(self, temp_data_dir):
        """Test that snapshots don't contain future data."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        symbol = pipeline._validated_data["ohlcv"]["symbol"].unique()[0]
        as_of_date = pd.Timestamp("2023-12-31")
        
        snapshot = pipeline.build_snapshot(symbol, as_of_date)
        
        if snapshot.stock_ohlcv is not None and not snapshot.stock_ohlcv.empty:
            assert (snapshot.stock_ohlcv.index <= as_of_date).all()

    def test_ohlcv_relationships(self, temp_data_dir):
        """Test OHLCV relationship integrity."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        ohlcv = pipeline._validated_data["ohlcv"]
        
        # Verify high >= close >= low
        assert (ohlcv["high"] >= ohlcv["close"]).all()
        assert (ohlcv["close"] >= ohlcv["low"]).all()
        assert (ohlcv["high"] >= ohlcv["low"]).all()
        
        # Verify volume >= 0
        assert (ohlcv["volume"] >= 0).all()

    def test_free_float_positive(self, temp_data_dir):
        """Test that free-float shares are positive."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        if pipeline._validated_data["free_float"] is not None:
            ff = pipeline._validated_data["free_float"]
            assert (ff["free_float_shares"] > 0).all()

    def test_activity_weight_range(self, temp_data_dir):
        """Test that activity weights are in [0, 1]."""
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        if pipeline._validated_data["shareholders"] is not None:
            sh = pipeline._validated_data["shareholders"]
            weights = sh["activity_weight"].dropna()
            if len(weights) > 0:
                assert (weights >= 0).all()
                assert (weights <= 1).all()


class TestRealRunner:
    """Test real data runner (Phase 1-4 execution)."""

    def test_runner_initialization(self, temp_data_dir):
        """Test RealRunner can be initialized."""
        from mctr.validation.real_runner import RealRunner
        
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        runner = RealRunner(pipeline)
        assert runner is not None
        assert runner.pipeline == pipeline

    def test_run_symbol_date(self, temp_data_dir):
        """Test running Phase 1-4 for one symbol on one date."""
        from mctr.validation.real_runner import RealRunner
        
        pipeline = DataPipeline.from_csv(temp_data_dir)
        pipeline.load()
        pipeline.validate()
        
        runner = RealRunner(pipeline)
        symbol = pipeline._validated_data["ohlcv"]["symbol"].unique()[0]
        as_of_date = pd.Timestamp("2024-01-01")
        
        result = runner.run_symbol_date(symbol, as_of_date)
        
        assert result is not None
        assert result.symbol == symbol
        assert result.as_of_date == as_of_date
        assert result.bottom_probability is not None
        assert result.bottom_level is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
