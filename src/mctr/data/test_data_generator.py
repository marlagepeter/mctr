"""Test data generation utilities for demonstration (NOT real data)."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_sample_ohlcv(
    num_symbols: int = 10,
    num_days: int = 250,
    start_date: str = "2023-01-01",
) -> pd.DataFrame:
    """Generate sample OHLCV data for testing (DEMO ONLY - NOT REAL).
    
    Args:
        num_symbols: Number of stock symbols
        num_days: Number of trading days
        start_date: Start date
        
    Returns:
        DataFrame with columns: date, symbol, open, high, low, close, volume
    """
    np.random.seed(42)
    start = pd.Timestamp(start_date)
    dates = pd.bdate_range(start=start, periods=num_days)
    
    data = []
    for symbol_idx in range(num_symbols):
        symbol = f"{600000 + symbol_idx:06d}"
        base_price = 10 + 5 * np.random.rand()
        
        for date in dates:
            # Generate random walk
            daily_return = np.random.normal(0.001, 0.02)
            base_price = base_price * (1 + daily_return)
            
            open_price = base_price * (1 + np.random.normal(0, 0.01))
            close_price = base_price * (1 + np.random.normal(0, 0.01))
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
            volume = int(1e6 * np.random.exponential(2))
            
            data.append({
                "date": date,
                "symbol": symbol,
                "open": max(0.01, open_price),
                "high": max(0.01, high_price),
                "low": max(0.01, low_price),
                "close": max(0.01, close_price),
                "volume": volume,
            })
    
    df = pd.DataFrame(data)
    return df.set_index("date")


def generate_sample_market_index(
    num_days: int = 250,
    start_date: str = "2023-01-01",
) -> pd.DataFrame:
    """Generate sample market index (DEMO ONLY - NOT REAL)."""
    np.random.seed(42)
    start = pd.Timestamp(start_date)
    dates = pd.bdate_range(start=start, periods=num_days)
    
    base_price = 3500
    data = []
    
    for date in dates:
        daily_return = np.random.normal(0.001, 0.015)
        base_price = base_price * (1 + daily_return)
        
        open_price = base_price * (1 + np.random.normal(0, 0.01))
        close_price = base_price * (1 + np.random.normal(0, 0.01))
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
        volume = int(1e7 * np.random.exponential(1))
        
        data.append({
            "date": date,
            "open": high_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
        })
    
    df = pd.DataFrame(data)
    return df.set_index("date")


def generate_sample_sector_index(
    num_days: int = 250,
    start_date: str = "2023-01-01",
) -> pd.DataFrame:
    """Generate sample sector indices (DEMO ONLY - NOT REAL)."""
    np.random.seed(42)
    start = pd.Timestamp(start_date)
    dates = pd.bdate_range(start=start, periods=num_days)
    
    sectors = ["制造业", "金融业", "信息技术", "能源业", "医疗健康"]
    data = []
    
    sector_bases = {sector: 2000 + i * 200 for i, sector in enumerate(sectors)}
    
    for date in dates:
        for sector in sectors:
            base_price = sector_bases[sector]
            daily_return = np.random.normal(0.001, 0.015)
            base_price = base_price * (1 + daily_return)
            sector_bases[sector] = base_price
            
            open_price = base_price * (1 + np.random.normal(0, 0.01))
            close_price = base_price * (1 + np.random.normal(0, 0.01))
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
            volume = int(1e6 * np.random.exponential(1))
            
            data.append({
                "date": date,
                "sector": sector,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            })
    
    df = pd.DataFrame(data)
    return df.set_index("date")


def generate_sample_free_float(
    symbols: list[str],
) -> pd.DataFrame:
    """Generate sample free-float data (DEMO ONLY - NOT REAL)."""
    np.random.seed(42)
    data = []
    
    for symbol in symbols:
        # 2-3 updates over the period
        dates = [
            pd.Timestamp("2023-01-15"),
            pd.Timestamp("2023-12-31"),
            pd.Timestamp("2024-06-30"),
        ]
        
        for date in dates:
            free_float = int(1e9 * np.random.exponential(3))
            data.append({
                "effective_date": date,
                "symbol": symbol,
                "free_float_shares": max(1e8, free_float),
            })
    
    df = pd.DataFrame(data)
    return df.set_index("effective_date")


def generate_sample_shareholders(
    symbols: list[str],
) -> pd.DataFrame:
    """Generate sample shareholder data (DEMO ONLY - NOT REAL)."""
    np.random.seed(42)
    holder_types = ["executive", "founder", "institutional", "employee", "other"]
    data = []
    
    for symbol in symbols:
        dates = [
            pd.Timestamp("2023-01-15"),
            pd.Timestamp("2023-12-31"),
            pd.Timestamp("2024-06-30"),
        ]
        
        for date in dates:
            # 3-5 shareholders per symbol per date
            for i in range(np.random.randint(3, 6)):
                holder_type = holder_types[i % len(holder_types)]
                shares = int(1e7 * np.random.exponential(1))
                activity_weight = np.random.rand() if holder_type != "other" else np.random.rand() * 0.3
                
                data.append({
                    "effective_date": date,
                    "symbol": symbol,
                    "shareholder_id": f"SH{i:03d}",
                    "shares": max(1e6, shares),
                    "holder_type": holder_type,
                    "activity_weight": min(1.0, activity_weight),
                })
    
    df = pd.DataFrame(data)
    return df.set_index("effective_date")
