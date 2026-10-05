# MCTR Input Fields — Quick Reference Guide

## 1. Single-Symbol Stock OHLCV (Most Common)

```python
# Minimum required input structure:
import pandas as pd
from mctr.data.validators import validate_ohlcv

# Create DataFrame with date index
stock_data = pd.DataFrame({
    'open': [100.0, 101.0, 102.0, ...],
    'high': [102.0, 103.0, 104.0, ...],
    'low': [99.0, 100.5, 101.5, ...],
    'close': [101.0, 102.0, 103.0, ...],
    'volume': [1000000, 1100000, 1050000, ...],
}, index=pd.DatetimeIndex(['2024-01-01', '2024-01-02', '2024-01-03', ...]))

# Validate
clean_data = validate_ohlcv(stock_data)

# Phase 1 uses this to calculate:
# - Position percentiles (60/120/250/500d)
# - MACD, KDJ
# - Price-volume features
# - Trend state (T0-T6)
```

**Constraints**:
- ✓ DatetimeIndex must be sorted ascending
- ✓ high >= close, high >= low, low <= close
- ✓ volume >= 0
- ✓ No duplicate dates

---

## 2. Multi-Symbol Stock Bundle

```python
from mctr.data.validators import validate_stock

stock_data = pd.DataFrame({
    'symbol': ['AAPL', 'MSFT', 'AAPL', 'MSFT', ...],
    'date': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02', ...],
    'open': [100.0, 200.0, 101.0, 201.0, ...],
    'high': [102.0, 202.0, 103.0, 203.0, ...],
    'low': [99.0, 199.0, 100.5, 200.5, ...],
    'close': [101.0, 201.0, 102.0, 202.0, ...],
    'volume': [1000000, 2000000, 1100000, 2100000, ...],
})

# Validates (symbol, date) uniqueness and auto-sorts if needed
clean_data = validate_stock(stock_data)
```

**Key difference**: Allows date reordering (auto-sorted), requires symbol column

---

## 3. Market Index Data

```python
from mctr.data.validators import validate_market
from mctr.data.models import MarketDataBundle

# Create dict of indices
indices = {
    'SSE': pd.DataFrame({  # Shanghai Stock Exchange
        'date': ['2024-01-01', '2024-01-02', ...],
        'open': [2800.0, 2810.0, ...],
        'high': [2820.0, 2830.0, ...],
        'low': [2795.0, 2805.0, ...],
        'close': [2815.0, 2825.0, ...],
        'volume': [100000000, 105000000, ...],
    }, index='date').set_index(pd.DatetimeIndex(...)),
    
    'CSI300': pd.DataFrame({  # CSI 300 Index
        # ... same OHLCV structure
    }, index='date').set_index(pd.DatetimeIndex(...)),
}

# Optional: Market breadth data (all stocks' closes)
breadth_data = pd.DataFrame({
    'AAPL': [100.0, 101.0, ...],
    'MSFT': [200.0, 201.0, ...],
    'GOOG': [140.0, 141.0, ...],
    # ... all stock closes in columns
}, index=pd.DatetimeIndex([...]))

# Bundle them
market = MarketDataBundle(
    indices=indices,
    breadth=breadth_data  # optional
)

# Phase 3 calculates market regime and breadth profiles
```

---

## 4. Free-Float & Shareholder Data (Phase 2 Critical)

```python
from mctr.data.validators import validate_free_float, validate_shareholder

# Free-float data
free_float = pd.DataFrame({
    'symbol': ['AAPL', 'AAPL', 'MSFT', 'MSFT', ...],
    'date': ['2024-01-01', '2024-06-01', '2024-01-01', '2024-06-01', ...],
    'free_float_shares': [1000000000, 1010000000, 500000000, 505000000, ...],
})
clean_ff = validate_free_float(free_float)

# Shareholder data (more detailed)
shareholders = pd.DataFrame({
    'effective_date': ['2023-12-31', '2023-12-31', '2023-12-31', ...],
    'symbol': ['AAPL', 'AAPL', 'AAPL', ...],
    'shareholder_id': ['SH0001', 'SH0002', 'SH0003', ...],
    'shares': [100000000, 50000000, 25000000, ...],
    'holder_type': ['institution', 'fund', 'retail', ...],
    'activity_weight': [0.45, 0.55, 0.85, ...],  # or None to use type default
})
clean_sh = validate_shareholder(shareholders)

# Phase 2 calculates:
# 1. active_ratio = sum(shares * activity_weight) / free_float
# 2. ETC = free_float * active_ratio
# 3. Chip density from historical OHLCV + ETC
```

**Key rules**:
- ✓ free_float_shares must be > 0 (strictly positive)
- ✓ shares >= 0 (non-negative)
- ✓ activity_weight in [0, 1] or None
- ✓ (effective_date, symbol, shareholder_id) must be unique
- ✓ For as_of_date, use only shareholders where effective_date <= as_of_date

---

## 5. Phase 2 Chip Profile Output → Phase 3-4 Input

```python
# After Phase 2 processes free-float + shareholder + history OHLCV:
from mctr.chips.models import ChipProfile

chip_profile = ChipProfile(
    as_of_date=pd.Timestamp('2024-01-15'),
    
    # ETC metrics
    free_float=1000000000,
    active_ratio=0.52,  # 52% of free-float is active
    effective_tradable_chips=520000000,
    confidence='high',  # >=80% shareholder coverage
    fallback_used=False,
    
    # Chip density peaks and ranges
    peak_price=102.5,
    peak_density=50000000,  # 50M shares at price 102.5
    core_lower=100.0,
    core_upper=105.0,
    core_coverage=0.70,  # 70% of chips in core range
    concentration=0.65,  # Core density concentration metric
    
    # Support/Resistance (±10% window around current price ~102)
    support_density=0.45,  # 45% of chips below current price
    resistance_density=0.35,  # 35% of chips above current price
    
    # Migration (price-level shift)
    migration_5d=-0.02,  # -2% peak shift in 5d
    migration_20d=-0.05,  # -5% peak shift in 20d
    migration_60d=0.01,  # +1% peak shift in 60d
    
    # Divergence (price vs peak)
    divergence_20d=0.03,  # Current price 3% above historical peak
    divergence_60d=-0.01,
    
    # Distribution series
    density=pd.Series({
        98.5: 10000000,
        100.0: 20000000,
        102.5: 50000000,  # Peak
        105.0: 15000000,
        107.5: 5000000,
    }),
    normalized_density=pd.Series({  # Sum to 1.0
        98.5: 0.10,
        100.0: 0.20,
        102.5: 0.50,
        105.0: 0.15,
        107.5: 0.05,
    }),
)

# Phase 4 uses these fields for:
# - Chip stability (concentration × migration decay)
# - Support score (support_density within window)
# - Pressure score (1.0 - resistance_density)
# - Risk/reward zones (core_upper, peak_price, historical highs)
```

---

## 6. Market Regime Profile (Phase 3 → Phase 4)

```python
from mctr.market.models import MarketRegimeProfile

market_regime = MarketRegimeProfile(
    as_of_date=pd.Timestamp('2024-01-15'),
    
    # Primary Phase 4 inputs
    market_cycle_state='M5 Bull Trend',  # or M0, M1, M2, M3, M4, M6, M7, M8
    market_strength=0.72,  # [0,1] composite: 35% structural + 25% momentum + 20% breadth + 20% participation
    
    # Component states (for auditing)
    position_state='high',  # ('low', 'neutral', 'high')
    momentum_state='improving',  # ('improving', 'weakening')
    trend_state='trend',  # ('decline', 'transition', 'trend')
    breadth_state='strong',  # ('weak', 'neutral', 'strong')
    volume_state='expanding',  # ('expanding', 'contracting', 'missing')
    
    # Component strengths
    structural_strength=0.75,  # Position percentile average
    momentum_strength=0.68,  # % indices with positive histogram slope
    breadth_strength=0.80,  # Average above_ma ratio
    participation_strength=0.65,  # Volume trend
    
    market_cycle_state='M5 Bull Trend',
    confidence='high',  # All 4 components available
    explanation='trend=trend; position=high; momentum=improving; breadth=strong; volume=expanding'
)

# Phase 4 usage:
# market_gate = 0.0 if M0/M8 (systemic crisis)
#             = min(market_strength, 0.5) if M2/M7 (exhaustion, capped)
#             = max(0.15, market_strength) otherwise (floor-bounded)
```

---

## 7. Sector Regime Profile (Phase 3 → Phase 4)

```python
from mctr.sector.models import SectorRegimeProfile

sector_regime = SectorRegimeProfile(
    sector_name='Technology',
    as_of_date=pd.Timestamp('2024-01-15'),
    
    # Primary Phase 4 inputs
    cycle_state='S5 Strong Trend',  # or S1-S8
    sector_strength=0.68,  # [0,1] composite
    
    # Position percentiles
    position={60: 0.75, 120: 0.72, 250: 0.65, 500: 0.60},
    
    # Component states
    position_state='high',
    momentum_state='improving',
    trend_label='trend',  # ('decline', 'transition', 'trend')
    trend_state=3,  # TrendState.T3_UPTREND
    
    # Relative strength vs market
    relative_strength={20: 0.05, 60: 0.08, 120: 0.02},  # Sector returns - market returns
    
    # Component strengths
    position_strength=0.75,
    momentum_strength=0.70,
    trend_strength=0.75,
    relative_strength_strength=0.60,
    
    confidence='high',
    explanation='...'
)

# Phase 4 usage:
# - Sector-level risk overrides (weak relative strength)
# - Resonance calculation (sector→stock alignment)
```

---

## 8. Resonance Profile (Phase 3 → Phase 4)

```python
from mctr.resonance.models import ResonanceProfile

resonance = ResonanceProfile(
    as_of_date=pd.Timestamp('2024-01-15'),
    
    # States at each layer
    market_state='M5 Bull Trend',
    sector_state='S5 Strong Trend',
    stock_state='recovery',
    
    # Primary Phase 4 inputs
    resonance_strength=0.65,  # Composite three-layer alignment
    resonance_grade='B',  # ('A', 'B', 'C', 'D', 'NONE')
    market_gate=0.72,  # Gates out systemic crises (M0/M8)
    
    # Component alignments
    structural_resonance=0.70,  # Base agreement before gating
    cycle_alignment=0.80,  # Adjacent phase compatibility
    sector_alignment=0.85,  # Market→sector directional match
    stock_alignment=0.75,  # Sector→stock directional match
    weakest_link_factor=0.68,  # min(market, sector, stock)^0.75
    
    confidence='high',
    explanation='...',
)

# Grade criteria:
# A: cycle_alignment >= 0.70 AND resonance >= 0.65 AND in grade-A states
# B: resonance >= 0.52
# C: resonance >= 0.10
# D: exhaustion/breakdown states
# NONE: market_gate = 0.0 (systemic crisis)

# Phase 4 usage:
# - Resonance score = 20% of structural bottom score
# - Grade filtering (optional)
```

---

## 9. Position Percentiles (Phase 1 → Phase 3-4)

```python
# Calculated for windows: 60, 120, 250, 500 days

position_percentiles = {
    60: 0.35,    # Price at 35th percentile within 60-day range
    120: 0.40,   # Price at 40th percentile within 120-day range
    250: 0.45,   # Price at 45th percentile within 250-day range
    500: 0.50,   # Price at 50th percentile within 500-day range (middle)
}

# Interpretation:
# - 0.0 = price at lowest point in window (very low position, favorable for bottom)
# - 0.5 = price at midpoint
# - 1.0 = price at highest point (very high position, unfavorable for bottom)

# Phase 4 aggregation:
# position_score = 1.0 - weighted_geometric_mean(0.35, 0.40, 0.45, 0.50)
#                = 1.0 - geometric_mean  # Low position (0.35-0.45) → high score
```

---

## 10. Phase 4 Bottom Engine Input Snapshot

```python
from mctr.models.states import TrendState
from mctr.scoring.bottom import calculate_bottom_engine

# All Phase 4 inputs consolidated:
result = calculate_bottom_engine(
    as_of_date=pd.Timestamp('2024-01-15'),
    
    # Price position (Phase 1)
    position_percentiles={60: 0.35, 120: 0.40, 250: 0.45, 500: 0.50},
    
    # Chip profile (Phase 2)
    chip_profile=chip_profile,  # See section 5
    
    # Momentum/exhaustion features (Phase 1)
    exhaustion_features={
        'volume': 1.15,  # volume_exhaustion
        'price': 0.68,   # price_efficiency
        'efficiency': 0.68,
        'momentum': 0.62,  # tanh-bounded momentum
    },
    momentum_features={
        'histogram': 0.15,  # MACD histogram
        'slope': 0.05,  # MACD histogram slope
        'divergence': 0.10,  # Price vs peak divergence
        'velocity': 0.02,  # Price velocity
        'kdj': 0.55,  # KDJ K-value
    },
    
    # Trend (Phase 1)
    trend_state='T3_UPTREND',
    
    # Resonance (Phase 3)
    resonance=resonance,  # See section 8
    
    # Current market/sector data
    current_price=102.5,
    market_state='M5 Bull Trend',
    sector_relative_strength=0.05,  # Sector - market return
    volume_ratio=1.2,  # Current volume / average
    
    # Historical data (for support/resistance zones)
    history=stock_data_ohlcv,  # All prior data through as_of_date
    
    # Config (optional)
    config=BottomConfig(),
)

# Output:
print(f"Bottom probability: {result.bottom_probability:.2%}")  # e.g., 68%
print(f"Bottom level: {result.bottom_level}")  # L1, L2, L3, L4, or NONE
print(f"Risk override: {result.risk_override_state}")  # R0, R1, R2, R3
```

---

## 11. Critical Validation Checklist

| Category | Validation |
|----------|-----------|
| **Dates** | ✓ DatetimeIndex, sorted ascending (no duplicates for single symbol) |
| **OHLCV** | ✓ high >= close, high >= low, low <= close, volume >= 0 |
| **Free-float** | ✓ free_float_shares > 0 (strictly positive) |
| **Shares** | ✓ shares >= 0 (non-negative) |
| **Weights** | ✓ All in [0, 1]: activity_weight, position %, strength scores |
| **Uniqueness** | ✓ Single-symbol: no duplicate dates; Multi-symbol: (symbol, date); Shareholders: (effective_date, symbol, shareholder_id) |
| **Point-in-time** | ✓ as_of_date filtering: use data <= as_of_date only |

---

## 12. Field Dependency Graph

```
OHLCV (Phase 1 Input)
├─ Position %tiles (60/120/250/500)
├─ MACD (histogram, slope)
├─ KDJ (k, d, rsv, j)
├─ Price-Volume Features (velocity, exhaustion, efficiency)
└─ Trend State (T0-T6)

Free-Float (Phase 2 Input) + Shareholder (Phase 2 Input)
├─ Active Ratio (weighted coverage)
└─ ETC = free_float × active_ratio

ETC + OHLCV History (Phase 2 Input)
├─ Chip Density (price-level distribution)
├─ Core Range (concentration, coverage)
├─ Peak Price & Density
├─ Support/Resistance (±10% window)
└─ Migration & Divergence

Market Index OHLCV (Phase 3 Input)
├─ Market Regime (position, momentum, trend, breadth, volume)
└─ Market Gate (0.0 for M0/M8, capped for M2/M7)

Sector Index OHLCV (Phase 3 Input) + Market Index
├─ Sector Regime (position, momentum, trend, relative_strength)
└─ Relative Strength (sector - market returns)

Position %tiles + Momentum + Trend + Chip Profile (Phase 3 Input)
├─ Stock Regime
└─ Resonance (Market → Sector → Stock alignment)

All Phase 1-3 Outputs (Phase 4 Input)
├─ Position Score
├─ Chip Score (stability, support, pressure)
├─ Exhaustion Score (volume, price, efficiency, momentum)
├─ Momentum Reversal Score (MACD, KDJ, features)
├─ Trend Transition Score (T0-T6 prior)
├─ Resonance Score (20% of structural)
├─ Structural Bottom Score (geometric mean of above)
├─ Confirmation Factor (momentum × trend agreement)
├─ Contradiction Factor (bearish veto)
├─ Risk Override (R0-R3)
└─ Bottom Probability & Level (L1-L4, NONE)
```

---

## 13. Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `ValueError: dates must be sorted ascending` | OHLCV data out of order | Use `allow_reorder=False` for single symbol or manually sort by date |
| `ValueError: duplicate dates are not allowed` | Same date appears twice | Merge duplicates or keep first/last occurrence |
| `ValueError: free_float_shares must be positive` | Free-float contains zero or negative | Filter out invalid rows: `ff[ff > 0]` |
| `ValueError: activity_weight must be between 0 and 1` | Weight outside [0, 1] | Clamp: `min(max(w, 0.0), 1.0)` or set None for type prior |
| `ValueError: (symbol, date) duplicate key` | Two rows for same symbol-date | Keep one, consolidate if from different sources |
| `ValueError: missing columns` | Required column not present | Check column names (case-sensitive): open, high, low, close, volume |
| Confidence drops to "low" in Phase 2 | Shareholder coverage < 20% of free-float | Collect more shareholder data or use fallback activity weight |
| Confidence drops to "low" in Phase 4 | Missing chip data or exhaustion features | Verify Phase 2 completed, check feature calculations |

---

## 14. Data Flow Example: Single Stock Analysis

```python
import pandas as pd
from mctr.data.validators import validate_ohlcv, validate_free_float, validate_shareholder
from mctr.chips.activity import calculate_effective_tradable_chips
from mctr.chips.density import build_chip_density
from mctr.market.regime import calculate_market_regime
from mctr.sector.regime import calculate_sector_regime
from mctr.resonance.engine import build_stock_regime, calculate_resonance
from mctr.scoring.bottom import calculate_bottom_engine

# Step 1: Load & validate stock OHLCV
stock_data = pd.read_csv('stock.csv', index_col='date', parse_dates=True)
stock_data = validate_ohlcv(stock_data)

# Step 2: Calculate Phase 1 features (position, MACD, KDJ, trend)
# [Phase 1 calculates automatically in Phase 2-4 usage]

# Step 3: Load & validate free-float and shareholder data
free_float_data = pd.read_csv('free_float.csv', parse_dates=['date'])
free_float_data = validate_free_float(free_float_data)

shareholder_data = pd.read_csv('shareholders.csv', parse_dates=['effective_date'])
shareholder_data = validate_shareholder(shareholder_data)

# Step 4: Calculate Phase 2 ETC and chip profile
as_of_date = pd.Timestamp('2024-01-15')
ff_row = free_float_data[free_float_data['date'] <= as_of_date].iloc[-1]
sh_rows = shareholder_data[shareholder_data['effective_date'] <= as_of_date]

etc = calculate_effective_tradable_chips(
    free_float=ff_row['free_float_shares'],
    holdings=[...],  # Convert shareholder rows to ShareholderHolding objects
    as_of_date=as_of_date,
)

chip_profile = ChipProfile(
    free_float=etc.free_float,
    active_ratio=etc.active_ratio,
    effective_tradable_chips=etc.effective_tradable_chips,
    # ... other fields from density calculation
)

# Step 5: Load & validate market and sector data
market_data = pd.read_csv('market_index.csv', index_col='date', parse_dates=True)
market_data = validate_market(market_data)

sector_data = pd.read_csv('sector_index.csv', index_col='date', parse_dates=True)
sector_data = validate_sector(sector_data)

# Step 6: Calculate Phase 3 regimes
market_regime = calculate_market_regime(
    indices={'SSE': market_data},
    breadth_closes=pd.DataFrame({...}),  # All stock closes
    as_of_date=as_of_date,
)

sector_regime = calculate_sector_regime(
    sector_name='Technology',
    sector_frame=sector_data,
    market_close=market_data['close'],
    as_of_date=as_of_date,
)

stock_regime = build_stock_regime(
    as_of_date=as_of_date,
    position_state='low',  # From Phase 1
    momentum_state='improving',  # From Phase 1
    trend_state=TrendState.T3_UPTREND,  # From Phase 1
    chip_profile=chip_profile,
)

resonance = calculate_resonance(market_regime, sector_regime, stock_regime)

# Step 7: Calculate Phase 4 Bottom Engine
bottom_result = calculate_bottom_engine(
    as_of_date=as_of_date,
    position_percentiles={60: 0.35, 120: 0.40, 250: 0.45, 500: 0.50},
    chip_profile=chip_profile,
    exhaustion_features={'volume': 1.15, 'price': 0.68, 'efficiency': 0.68, 'momentum': 0.62},
    momentum_features={'histogram': 0.15, 'slope': 0.05, 'divergence': 0.10, 'velocity': 0.02, 'kdj': 0.55},
    trend_state='T3_UPTREND',
    resonance=resonance,
    current_price=102.5,
    history=stock_data,
)

print(f"Bottom Probability: {bottom_result.bottom_probability:.2%}")
print(f"Bottom Level: {bottom_result.bottom_level}")
print(f"Confidence: {bottom_result.confidence}")
```

---

## Quick Field Checklist

### For Phase 2 (Chip Calculation)
- [ ] Free-float (symbol, date, free_float_shares > 0)
- [ ] Shareholders (effective_date, symbol, shareholder_id, shares >= 0, holder_type, activity_weight ∈ [0,1])
- [ ] OHLCV history (for chip density)

### For Phase 3 (Regime Calculation)
- [ ] Market indices OHLCV
- [ ] Sector indices OHLCV
- [ ] Breadth data (optional, all stock closes)
- [ ] Chip profile from Phase 2

### For Phase 4 (Bottom Engine)
- [ ] Current price
- [ ] Position percentiles (60/120/250/500)
- [ ] Chip profile (all fields: concentration, core_*, peak_*, support, resistance)
- [ ] Momentum features (MACD, KDJ, price-volume)
- [ ] Exhaustion features (volume, price, efficiency, momentum)
- [ ] Trend state (T0-T6)
- [ ] Market regime (market_cycle_state, market_strength)
- [ ] Sector relative strength
- [ ] Resonance profile
- [ ] Historical OHLCV (for support/resistance zones)

---

**Reference**: For complete details, see [MCTR_INPUT_FIELDS_MAPPING.md](MCTR_INPUT_FIELDS_MAPPING.md)

