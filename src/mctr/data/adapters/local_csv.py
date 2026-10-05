"""Local CSV adapter for loading raw historical data."""

from typing import Optional

from pathlib import Path

import pandas as pd

from .base import DataAdapter, AdapterConfig

class LocalCSVAdapter(DataAdapter):
    """Load raw data from local CSV files.
    
    Expected directory structure:
        data/raw/
        ├── ohlcv/
        │   └── stocks_ohlcv.csv
        ├── market/
        │   ├── market_index.csv
        │   └── market_breadth.csv (optional)
        ├── sector/
        │   └── sector_index.csv
        ├── fundamental/
        │   ├── free_float.csv (optional)
        │   └── shareholders.csv (optional)
    """

    def __init__(self, config: AdapterConfig = AdapterConfig()):
        """Initialize CSV adapter.
        
        Args:
            config: AdapterConfig with data_dir and parsing options
        """
        super().__init__(config)
        self._validate_data_dir()

    def _validate_data_dir(self) -> None:
        """Ensure data directory exists."""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

    def _load_csv(self, relative_path: str) -> pd.DataFrame:
        """Load a CSV file with configured options.
        
        Args:
            relative_path: Path relative to data_dir (e.g., "ohlcv/stocks_ohlcv.csv")
            
        Returns:
            Loaded DataFrame
            
        Raises:
            FileNotFoundError: If file does not exist
        """
        file_path = self.data_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        # Read CSV with configured options
        df = pd.read_csv(
            file_path,
            encoding=self.config.encoding,
        )
        
        # Parse dates if configured (flexible: parse whatever date columns exist)
        if self.config.parse_dates:
            for col in ["date", "effective_date"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])
        
        return df

    def load_ohlcv(self) -> pd.DataFrame:
        """Load multi-symbol OHLCV data.
        
        Expected columns: date, symbol, open, high, low, close, volume
        
        Returns:
            DataFrame with DatetimeIndex (date), columns: symbol, open, high, low, close, volume
        """
        df = self._load_csv("ohlcv/stocks_ohlcv.csv")
        df = self._ensure_date_index(df, "date")
        
        # Ensure symbol column exists
        if "symbol" not in df.columns:
            raise ValueError("OHLCV must include 'symbol' column")
        
        return df

    def load_market_index(self) -> pd.DataFrame:
        """Load market index OHLCV.
        
        Expected columns: date, open, high, low, close, volume
        
        Returns:
            DataFrame with DatetimeIndex (date), columns: open, high, low, close, volume
        """
        df = self._load_csv("market/market_index.csv")
        df = self._ensure_date_index(df, "date")
        return df

    def load_market_breadth(self) -> Optional[pd.DataFrame]:
        """Load optional market breadth data.
        
        Expected columns: date, advance_count, decline_count, etc.
        
        Returns:
            DataFrame or None if file does not exist
        """
        try:
            df = self._load_csv("market/market_breadth.csv")
            df = self._ensure_date_index(df, "date")
            return df
        except FileNotFoundError:
            return None

    def load_sector_index(self) -> pd.DataFrame:
        """Load sector indices OHLCV.
        
        Expected columns: date, sector, open, high, low, close, volume
        
        Returns:
            DataFrame with DatetimeIndex (date), columns: sector, open, high, low, close, volume
        """
        df = self._load_csv("sector/sector_index.csv")
        df = self._ensure_date_index(df, "date")
        
        # Ensure sector column exists
        if "sector" not in df.columns:
            raise ValueError("Sector index must include 'sector' column")
        
        return df

    def load_free_float(self) -> Optional[pd.DataFrame]:
        """Load free-float shares data.
        
        Expected columns: effective_date, symbol, free_float_shares
        
        Returns:
            DataFrame or None if file does not exist
        """
        try:
            df = self._load_csv("fundamental/free_float.csv")
            df = self._ensure_date_index(df, "effective_date")
            return df
        except FileNotFoundError:
            return None

    def load_shareholders(self) -> Optional[pd.DataFrame]:
        """Load shareholder activity data.
        
        Expected columns: effective_date, symbol, shareholder_id, shares, holder_type, activity_weight
        
        Returns:
            DataFrame or None if file does not exist
        """
        try:
            df = self._load_csv("fundamental/shareholders.csv")
            df = self._ensure_date_index(df, "effective_date")
            return df
        except FileNotFoundError:
            return None
