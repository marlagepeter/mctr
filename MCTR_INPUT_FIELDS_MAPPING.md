# MCTR Phases 1-4 Complete Input Fields Mapping

## Executive Summary

This document provides a **comprehensive mapping of all required input fields** for MCTR Phases 1-4 algorithms. Each field is classified as Required/Optional, with explicit data types, constraints, and usage details for every Phase.

**Key Organization**:
- 20 sections covering each data category
- Input/output flow across phases
- Validation constraints and confidence levels
- Config defaults and critical invariants

---

## 1. OHLCV DATA (Primary Input Across All Phases)

### Base OHLCV Fields (Required)

| Field | Type | Constraint | Phase Usage |
|-------|------|-----------|------------|
| **open** | float | open >= 0 | 1-4: Price position, trend analysis, MACD/KDJ |
| **high** | float | high >= close, high >= low | 1-4: Range, position percentile, support |
| **low** | float | low <= close, low <= high | 1-4: Range, price position, support |
| **close** | float | low <= close <= high | 1-4: Position (60/120/250/500d), MACD, KDJ, trend |
| **volume** | float | volume >= 0 | 1-4: ETC turnover, chip migration, momentum, participation |

### Optional OHLCV Fields

| Field | Type | Phase Usage | Impact if Missing |
|-------|------|------------|-------------------|
| **amount** | float | 3: Market volume profile | Degraded confidence only |

### OHLCV Index/Date

| Field | Format | Constraint | Impact |
|-------|--------|-----------|--------|
| **date** | DatetimeIndex or date column | Must be pd.Timestamp, monotonic increasing | No gaps/duplicates for single symbol |

---

## 2. STOCK DATA (Single or Multi-Symbol)

### Input Container

```python
class StockDataBundle:
    frame: pd.DataFrame  # columns: (date, symbol, open, high, low, close, volume)
                        # uniqueness: (symbol, date)
```

### Fields

| Field | Type | Constraint | Phase Usage |
|-------|------|-----------|------------|
| **symbol** | string | Any format (e.g., "000001.SZ", "AAPL") | 2-4: Free-float lookup, shareholder filtering |
| **date** | Timestamp | See OHLCV Index above | 1-4: Time anchor |
| **open, high, low, close, volume** | float | See OHLCV Fields | 1-4: All phases |

### Validation Rules

- ✓ Multi-symbol DataFrames allow date reordering (auto-sorted internally)
- ✓ (symbol, date) pairs must be unique
- ✓ OHLCV relationships always enforced
- ✓ No forward fill or missing value fabrication

**Example Usage**:
```python
# User provides data from multiple stocks, dates may be out of order
from mctr.data.validators import validate_stock

df = pd.DataFrame({
    'symbol': ['AAPL', 'MSFT', 'AAPL', 'MSFT'],
    'date': ['2024-01-02', '2024-01-01', '2024-01-01', '2024-01-02'],
    'open': [...], 'high': [...], 'low': [...], 'close': [...], 'volume': [...]
})

result = validate_stock(df)  # ✓ Accepts, auto-sorts by date, checks (symbol, date) unique
```

---

## 3. MARKET DATA

### Input Container: MarketDataBundle

```python
@dataclass(frozen=True)
class MarketDataBundle:
    indices: dict[str, pd.DataFrame]  # e.g., {'SSE': df, 'CSI300': df}
    breadth: pd.DataFrame | None = None  # optional
```

### Market Index Fields (Required per index)

Each index DataFrame contains standard OHLCV columns:
- **date, open, high, low, close, volume**
- Index name implied by dict key: "SSE", "CSI300", "Shanghai", etc.

### Market Breadth Fields (Optional, enhances Phase 3)

When breadth DataFrame provided (calculated from all stock closes):

**Cross-sectional counts:**
- **advance_count** (int): Stocks with close > prior close
- **decline_count** (int): Stocks with close < prior close
- **unchanged_count** (int): Stocks with close == prior close
- **new_high_count** (int): New 250-day highs
- **new_low_count** (int): New 250-day lows

**Moving average participation ratios:**
- **above_ma20_ratio** (float): [0, 1] % stocks > 20-day MA
- **above_ma60_ratio** (float): [0, 1] % stocks > 60-day MA
- **above_ma120_ratio** (float): [0, 1] % stocks > 120-day MA
- **above_ma250_ratio** (float): [0, 1] % stocks > 250-day MA

**Aggregate volume:**
- **total_turnover** (float): Market-wide turnover (optional)

### Phase Usage

| Phase | Input/Output | Usage |
|-------|-------------|-------|
| 1 | Output | Position percentiles (60/120/250/500), MACD, KDJ, trend state |
| 3 | Input | Market Regime: position state, momentum, trend, breadth_state, volume_state |
| 4 | Input | Market gate (0.0 for M0/M8), market_strength for resonance, contradiction checks |

---

## 4. SECTOR DATA

### Input Container: SectorDataBundle

```python
class SectorDataBundle:
    frame: pd.DataFrame  # columns: (date, sector, open, high, low, close, volume)
                        # uniqueness: (sector, date)
```

### Fields

| Field | Type | Constraint | Usage |
|-------|------|-----------|-------|
| **sector** | string | Any string (e.g., "Technology", "Healthcare", "S1000610") | 3-4: Regime ID, relative strength |
| **date, open, high, low, close, volume** | float | Standard OHLCV | 3-4: Trend, momentum, position |

### Phase Usage

| Phase | Role |
|-------|------|
| 3 | Input: Sector regime (position, momentum, trend), relative strength vs market |
| 4 | Input: Sector relative strength for risk override, resonance validation |

---

## 5. FREE-FLOAT DATA

### Input Container

```python
# DataFrame with columns: (symbol, date/effective_date, free_float_shares)
# Uniqueness: (symbol, date) or (symbol, effective_date)
```

### Fields

| Field | Type | Constraint | Phase Usage |
|-------|------|-----------|------------|
| **symbol** | string | Stock identifier | 2-4: ETC lookup key |
| **date** or **effective_date** | Timestamp | pd.Timestamp convertible | 2: Base for ETC, point-in-time filtering (<=as_of_date) |
| **free_float_shares** | float | **Must be > 0** (strictly positive) | 2: ETC = free_float × active_ratio, chip density scaling |

### Validation Rules

- ✓ (symbol, date) pairs must be unique
- ✓ free_float_shares > 0 strictly (no zeros or negatives)
- ✓ Date ordering optional (auto-sorted in validators)
- ✓ No future free_float data allowed in snapshots (cutoff by as_of_date)

### Phase 2 Usage: ETC Calculation

**Algorithm**:
1. Get all shareholders with effective_date <= as_of_date
2. covered_shares = sum(shareholder.shares)
3. weighted_shares = sum(shareholder.shares × activity_weight_i)
4. uncovered = free_float - covered_shares
5. weighted_shares += uncovered × config.unknown_activity_weight (default 0.35)
6. active_ratio = weighted_shares / free_float
7. ETC = free_float × active_ratio
8. confidence: "high" if covered >= 80% else "medium"

### Key Invariant
- **Forbidden**: Subtracting restricted shares from free_float again
  - free_float is authoritative; restriction records retained for dated future updates only
  - Phase 2 never double-counts restricted shares

---

## 6. SHAREHOLDER DATA

### Input Container

```python
# DataFrame with columns: (effective_date, symbol, shareholder_id, shares, holder_type, activity_weight)
# Uniqueness: (effective_date, symbol, shareholder_id)
# Sorted ascending by effective_date
```

### Fields

| Field | Type | Constraint | Phase 2 Usage |
|-------|------|-----------|--------------|
| **effective_date** | Timestamp | pd.Timestamp convertible | Point-in-time filtering: records where effective_date <= as_of_date |
| **symbol** | string | Stock ID | Shareholder→stock link |
| **shareholder_id** | string/int | Unique within (effective_date, symbol) | Deduplication key |
| **shares** | float | shares >= 0 (non-negative) | Active ratio calculation (weighted component) |
| **holder_type** | string | Enum: retail, institution, fund, insurance, social_security, company, controller, executive, strategic, unknown | Activity weight resolution (type prior) |
| **activity_weight** | float | 0.0 <= activity_weight <= 1.0 | Explicit override; if None → type prior from config |

### Activity Weight Defaults (When not explicit)

These are the configured priors for each holder_type:

```python
DEFAULT_ACTIVITY_WEIGHTS = {
    "retail":           0.85,    # High activity (liquid)
    "institution":      0.45,    # Moderate activity
    "fund":             0.55,    # Moderate-high activity
    "insurance":        0.25,    # Low activity (long-term holder)
    "social_security":  0.20,    # Very low activity
    "company":          0.20,    # Very low activity
    "controller":       0.10,    # Most restricted (insider)
    "executive":        0.15,    # Restricted (insider)
    "strategic":        0.10,    # Restricted
    "unknown":          0.35,    # Fallback for uncovered shares
}
```

### Phase 2 ETC Calculation Detail

```python
def calculate_effective_tradable_chips(
    free_float: float,
    holdings: Sequence[ShareholderHolding] | None = None,
    activity_weights: Mapping[str, float] | None = None,
    config: ChipConfig = ChipConfig(),
    as_of_date: date | object | None = None,
) -> EffectiveTradableChipsResult:
    """
    1. Filter holdings to effective_date <= as_of_date
    2. If no holdings → return (active_ratio=config.unknown_activity_weight, confidence="low")
    3. Otherwise:
       covered_shares = sum(holding.shares)
       weighted = sum(holding.shares * resolved_weight(holding))
       uncovered = free_float - covered_shares
       weighted += uncovered * config.unknown_activity_weight
       active_ratio = weighted / free_float
       confidence = "high" if covered >= free_float * 0.80 else "medium"
    """
    ...
```

### Key Rules
- ✓ Must sort by effective_date before use
- ✓ (effective_date, symbol, shareholder_id) uniqueness enforced
- ✓ shares >= 0 but activity_weight explicit overrides type prior when provided
- ✓ activity_weight must be in [0, 1] or None

---

## 7. CHIP PROFILE DATA (Phase 2 Output → Phase 3-4 Input)

### Input Container: ChipProfile (frozen dataclass)

Generated by Phase 2; consumed by Phase 3-4. Central to identifying price-level chips distribution.

### Core ETC Fields (Required for all phases)

| Field | Type | Range | Phase Usage |
|-------|------|-------|------------|
| **effective_tradable_chips** | float | >= 0 | Phase 3-4: Baseline for resonance and bottom probability |
| **free_float** | float | > 0 | Phase 2-4: Base shares, turnover denominator |
| **active_ratio** | float | [0, 1] | Phase 2-4: Coverage of actively-held shares |
| **confidence** | string | "high"/"medium"/"low" | 3-4: Data quality assessment |
| **fallback_used** | bool | - | 3-4: Audit: whether unknown_activity_weight was applied |

### Density Distribution Fields (Required for Phase 4 Bottom scoring)

| Field | Type | Constraint | Phase 4 Bottom Usage |
|-------|------|-----------|-------------------|
| **concentration** | float | [0, 1] | Chip stability: exp(-width / price_window_pct) × concentration |
| **core_lower** | float | Price level | Price window width for stability |
| **core_upper** | float | Price level | Price window width for stability |
| **peak_price** | float | >= 0 | Overhead resistance, price window reference |
| **peak_density** | float | >= 0 | Density at peak_price |
| **core_coverage** | float | [0, 1] | Fraction of chips in core range (target ~0.70) |
| **support_density** | float | [0, 1] | Normalized chips below current price (±10% window) |
| **resistance_density** | float | [0, 1] | Normalized chips above current price (±10% window) |

### Migration Fields (Optional, Phase 4 risk override)

| Field | Type | Phase 4 Usage |
|-------|------|--------------|
| **migration_5d** | float | % density shift over 5d (optional) |
| **migration_20d** | float | % density shift over 20d → chip stability component, risk override |
| **migration_60d** | float | % density shift over 60d (optional) |
| **migration_velocity_5d** | float | Rate of migration |
| **migration_velocity_20d** | float | Rate of migration |
| **migration_velocity_60d** | float | Rate of migration |

### Divergence Fields (Optional, Phase 4)

| Field | Type | Phase 4 Usage |
|-------|------|--------------|
| **divergence_20d** | float | Price vs density peak divergence (momentum input) |
| **divergence_60d** | float | Price vs density peak divergence (optional) |

### Distribution Series

| Field | Type | Phase 4 Usage |
|-------|------|--------------|
| **density** | pd.Series | Raw chip distribution (price levels → shares) |
| **normalized_density** | pd.Series | density / density.sum() for weighted calculations |

### Chip Profile as a Snapshot

```python
@dataclass(frozen=True)
class ChipProfile:
    as_of_date: pd.Timestamp
    free_float: float
    active_ratio: float
    effective_tradable_chips: float
    confidence: str
    fallback_used: bool
    # Density peaks and ranges
    peak_price: float | None
    peak_density: float | None
    core_lower: float | None
    core_upper: float | None
    core_coverage: float | None
    concentration: float | None
    support_density: float | None
    resistance_density: float | None
    # Migration
    migration_5d: float | None
    migration_20d: float | None
    migration_60d: float | None
    migration_velocity_5d: float | None
    migration_velocity_20d: float | None
    migration_velocity_60d: float | None
    # Divergence
    divergence_20d: float | None
    divergence_60d: float | None
    # Distribution
    density: pd.Series
    normalized_density: pd.Series
```

---

## 8. MARKET REGIME (Phase 3 Output → Phase 4 Input)

### Input Container: MarketRegimeProfile

Composite market state calculated from indices, breadth, and volume. Used by Phase 4 for gates and risk overrides.

### Core Fields (Required for Phase 4)

| Field | Type | Values | Phase 4 Usage |
|-------|------|--------|--------------|
| **market_cycle_state** | string | M0, M1, M2, M3, M4, M5, M6, M7, M8 | Risk gate, contradiction checks |
| **market_strength** | float | [0, 1] | Resonance aggregation, market_gate calculation |

**Market Cycle States**:
- `M0 Extreme Bear`: Systemic crisis (gate=0.0)
- `M1 Bear / Decline`: Downtrend continuation
- `M2 Decline Exhaustion`: Downtrend ending
- `M3 Bottom Transition`: Transition up (grade A eligible)
- `M4 Recovery`: Early uptrend
- `M5 Bull Trend`: Strong uptrend (grade A eligible)
- `M6 Acceleration`: Uptrend accelerating (grade A eligible)
- `M7 Bull Exhaustion`: Uptrend exhausting (gate capped at 0.5)
- `M8 Breakdown`: Systemic breakdown (gate=0.0)

### Market Strength Components (Optional but informative)

| Component | Type | Weight | Calculation |
|-----------|------|--------|------------|
| **structural_strength** | float | 35% | Mean of position percentiles (60/120/250/500) |
| **momentum_strength** | float | 25% | % of indices with improving histogram slope |
| **breadth_strength** | float | 20% | Mean of above_ma20/60/120/250 ratios |
| **participation_strength** | float | 20% | Volume trend (1.0 if expanding, 0.0 if contracting) |

### Sub-component Profiles (Optional refinement)

| Field | Type | Content |
|-------|------|---------|
| **index_profiles** | dict[str, MarketIndexProfile] | Per-index breakdown (position, MACD, KDJ, trend_state, confidence) |
| **position_state** | string | "low" / "neutral" / "high" |
| **momentum_state** | string | "improving" / "weakening" |
| **trend_state** | string | "decline" / "transition" / "trend" |
| **breadth_state** | string | "weak" / "neutral" / "strong" |
| **volume_state** | string | "expanding" / "contracting" / "missing" |

### Market Gate Calculation (Phase 4)

```python
def market_gate(market_state: str, market_strength: float, floor: float = 0.15) -> float:
    if market_state in {"M0 Extreme Bear", "M8 Breakdown"}:
        return 0.0  # Hard gate: no resonance in systemic crisis
    if market_state in {"M7 Bull Exhaustion", "M2 Decline Exhaustion"}:
        return min(market_strength, 0.5)  # Capped participation
    return max(floor, min(1.0, market_strength))  # Floor-bounded, default 0.15
```

---

## 9. SECTOR REGIME (Phase 3 Output → Phase 4 Input)

### Input Container: SectorRegimeProfile

Point-in-time sector state aggregated from position, momentum, trend, and relative strength.

### Core Fields (Required for Phase 4)

| Field | Type | Values | Phase 4 Usage |
|-------|------|--------|--------------|
| **cycle_state** | string | S1, S2, S3, S4, S5, S6, S7, S8 | Resonance cycle alignment, risk override |
| **sector_strength** | float | [0, 1] | Resonance aggregation, directional alignment |

**Sector Cycle States**:
- `S1 Weak`: Downtrend, low position
- `S2 Weakening / Exhaustion`: Downtrend, exhausted momentum
- `S3 Bottom Transition`: Reversal up (grade A eligible)
- `S4 Recovery`: Early uptrend
- `S5 Strong Trend`: Strong uptrend with positive relative strength (grade A eligible)
- `S6 Acceleration`: Uptrend accelerating (grade A eligible)
- `S7 Exhaustion`: Uptrend exhausted
- `S8 Breakdown`: Trend broken

### Sub-components

| Field | Type | Phase 4 Usage |
|-------|------|--------------|
| **sector_name** | string | Identifier |
| **position** | dict[int, float] | Position percentiles (60/120/250/500d) |
| **position_state** | string | "low" / "neutral" / "high" |
| **momentum_state** | string | "improving" / "weakening" / "missing" |
| **trend_state** | int or None | TrendState enum (T0-T6) |
| **trend_label** | string | "decline" / "transition" / "trend" |
| **relative_strength** | dict[int, float] | Returns: sector_return - market_return for 20d/60d/120d |
| **position_strength** | float | [0, 1] Distance from neutral |
| **momentum_strength** | float | [0, 1] Geom. mean of momentum components |
| **trend_strength** | float | [0, 1] Config prior for trend_state |
| **relative_strength_strength** | float | [0, 1] Tanh-bounded relative_strength |

---

## 10. STOCK REGIME (Phase 3 Output → Phase 4 Input)

### Input Container: StockRegimeProfile

Integration of stock position, momentum, trend, and chip features into a unified stock state.

### Core Fields (Required for Phase 4)

| Field | Type | Values | Phase 4 Usage |
|-------|------|--------|--------------|
| **stock_cycle_state** | string | "recovery" / "low-observation" / "neutral" | Resonance cycle alignment |
| **stock_strength** | float | [0, 1] | Resonance aggregation |

### Sub-components

| Field | Type | Range | Phase 4 Usage |
|-------|------|-------|--------------|
| **position_state** | string | "low" / "neutral" / "high" | Cycle classification |
| **momentum_state** | string | "improving" / "weakening" | Cycle classification |
| **trend_state** | string | Lowercase TrendState name (t0_main_decline, ..., t6_trend_broken) | Cycle classification |
| **chip_state** | string | "supportive" / "resistant" / "missing" | Chip quality assessment |
| **position_strength** | float | [0, 1] | Distance from price position neutral |
| **momentum_strength** | float | [0, 1] | Geometric mean of momentum components |
| **trend_strength** | float | [0, 1] | Config prior for trend_state |
| **chip_structural_strength** | float | [0, 1] | Geometric mean of chip components |

---

## 11. RESONANCE PROFILE (Phase 3 Output → Phase 4 Input)

### Input Container: ResonanceProfile

Explainable three-layer (Market → Sector → Stock) resonance alignment.

### Core Fields (Required for Phase 4)

| Field | Type | Range | Phase 4 Usage |
|-------|------|-------|--------------|
| **resonance_strength** | float | [0, 1] | Structural Bottom Score component (20% weight) |
| **resonance_grade** | string | "A", "B", "C", "D", "NONE" | Auditing, acceptance filtering |
| **market_gate** | float | [0, 1] | Calculated from market_cycle_state; 0.0 for M0/M8 |

**Grade Criteria**:
- `A`: cycle_alignment >= 0.70 AND strength >= 0.65 AND market/sector in grade-A states
- `B`: strength >= 0.52
- `C`: strength >= 0.10
- `D`: Exhaustion or breakdown market states
- `NONE`: market_gate = 0.0 (gated out by systemic risk)

### Alignment Components

| Field | Type | Range | Definition |
|-------|------|-------|-----------|
| **structural_resonance** | float | [0, 1] | Base agreement before gating: market_strength^0.35 × sector_strength^0.30 × stock_strength^0.35 × sector_alignment × stock_alignment |
| **cycle_alignment** | float | [0, 1] | Geometric mean of adjacent phase compatibility scores |
| **market_gate** | float | [0, 1] | Caps resonance in M0/M8 (0.0) or exhaustion states (≤0.5) |
| **sector_alignment** | float | [0, 1] | Directional agreement: market_state → sector_state |
| **stock_alignment** | float | [0, 1] | Directional agreement: sector_state → stock_state |
| **weakest_link_factor** | float | [0, 1] | min(market, sector, stock)^0.75 |

### States (for audit trail)

| Field | Type | Content |
|-------|------|---------|
| **market_state** | string | market_cycle_state from Phase 3 |
| **sector_state** | string | sector cycle_state from Phase 3 |
| **stock_state** | string | stock_cycle_state from Phase 3 |

### Explanation Fields

| Field | Type | Content |
|-------|------|---------|
| **market_gate_reason** | string | Why market gate is set to current value |
| **sector_alignment_reason** | string | Why directional agreement scored as given |
| **stock_alignment_reason** | string | Why directional agreement scored as given |
| **weakest_link_reason** | string | Which component is weakest |
| **confidence** | string | "high" / "medium" / "low" |

---

## 12. POSITION PERCENTILES (Phase 1 Output → Phase 3-4 Input)

### Input Container: dict[int, float]

**Keys**: 60, 120, 250, 500 (day windows)
**Values**: [0, 1] percentile range

### Formula per window

```
position_N = (close - rolling_min_N) / (rolling_max_N - rolling_min_N)

where:
  rolling_min_N = close.rolling(N, min_periods=N).min()
  rolling_max_N = close.rolling(N, min_periods=N).max()
```

- 0.0 = price at lowest point in window
- 1.0 = price at highest point in window
- 0.5 = price at midpoint

### Phase Usage

| Phase | Role |
|-------|------|
| 1 | Output: Calculated from close OHLCV |
| 3 | Input: Market/Sector position_state classification |
| 4 | Input: Position score aggregation (weights: 60d 20%, 120d 25%, 250d 25%, 500d 30%) |

### Phase 4 Position Score

```python
def calculate_position_score(percentiles: dict[int, float], config: BottomConfig) -> float:
    """
    Returns P = 1 - weighted_geometric_mean(percentiles)
    
    Low position (close to 0.0) produces high P (favorable for bottom)
    High position (close to 1.0) produces low P (unfavorable)
    """
    # Clip values to [0, 1]
    # Compute weighted geometric mean: exp(sum(w_i * log(p_i)) / sum(w_i))
    # Return 1 - mean
```

---

## 13. MOMENTUM FEATURES (Phase 1 Output → Phase 3-4 Input)

All calculated from OHLCV without forward-looking data.

### MACD (12/26/9 parameters)

| Indicator | Calculation | Phase Usage |
|-----------|-----------|------------|
| **macd** | 12-EMA(close) - 26-EMA(close) | Trend direction |
| **macd_histogram** | macd - 9-EMA(macd) | Momentum strength |
| **macd_histogram_slope** | histogram.diff() | Momentum acceleration (→ Phase 4 momentum reversal) |
| **macd_signal** | 9-EMA(macd) | Not used directly in MCTR |

**Phase 4 Momentum Reversal Usage**:
- Tanh-bounded: 0.5 + 0.5 * tanh(histogram_slope / momentum_feature_scale)
- Weight: 20% of momentum_reversal_score

### KDJ (9-period, 3-smoothing)

| Indicator | Range | Phase Usage |
|-----------|-------|------------|
| **kdj_rsv** | [0, 100] | Raw stochastic |
| **kdj_k** | Implied [0, 100] | Smoothed stochastic (→ Phase 4 momentum) |
| **kdj_d** | Implied [0, 100] | K's EMA (signal line) |
| **kdj_j** | Unbounded | 3K - 2D (overshoot indicator) |

**Phase 4 KDJ Usage**:
- Tanh-bounded as momentum component
- Weight: 15% of momentum_reversal_score

### Price-Volume Features (20-day window)

| Feature | Calculation | Phase Usage |
|---------|-----------|------------|
| **price_velocity** | N-day average return = mean(pct_change(close)) | 3-4: Momentum state, trend classification |
| **volume_velocity** | N-day average volume change = mean(pct_change(volume)) | 4: Momentum component |
| **volume_exhaustion** | volume / N-day average volume | 4: Exhaustion score component |
| **price_efficiency** | N-day net move / N-day total path | 4: Exhaustion component, trend classification |

**Formula for efficiency**:
```
price_efficiency = abs(close[T] - close[T-N]) / sum(abs(close[i] - close[i-1]) for i in [T-N:T])
```

### Phase 1-4 Usage Pipeline

```
Phase 1: Calculate MACD, KDJ, price_volume_features from OHLCV
    ↓
Phase 3: Use price_velocity for market/sector momentum_state, trend classification
    ↓
Phase 4: Aggregate all into momentum_reversal_score
         + exhaustion_score (volume_exhaustion, price_efficiency)
         + risk_override checks (bearish_momentum_threshold: histogram_slope < -0.50)
```

---

## 14. TREND STATE (Phase 1 Output → Phase 3-4 Input)

### Trend State Classification (T0-T6)

Calculated row-by-row from trend structure and MACD histogram slope.

### Input Features for Classification

| Feature | Calculation | Required |
|---------|-----------|----------|
| **trend_mean** | 20-day MA of close | ✓ |
| **trend_mean_slope** | trend_mean[T] - trend_mean[T-1] | ✓ |
| **trend_return** | pct_change(close, 20) | ✓ |
| **trend_efficiency** | efficiency from price_volume_features | ✓ |
| **macd_histogram_slope** | From MACD (Phase 1) | ✓ |

### State Transitions

| State | Label | Conditions | Favorability |
|-------|-------|-----------|-------------|
| **T0** | Main Decline | slope < 0 AND histogram_slope < 0 | Very Bearish |
| **T1** | Decline Stopped | slope < 0 AND histogram_slope >= 0 | Moderately Bearish |
| **T2** | Reversal Confirmed | slope >= 0 AND return <= 0 | Neutral/Positive |
| **T3** | Uptrend | slope >= 0 AND return > 0 AND efficiency < 0.7 | Bullish |
| **T4** | Acceleration | slope >= 0 AND return > 0 AND efficiency >= 0.7 AND histogram_slope > 0 | Very Bullish |
| **T5** | Rally Exhaustion | slope >= 0 AND return > 0 AND efficiency >= 0.7 AND histogram_slope <= 0 | Moderately Bullish |
| **T6** | Trend Broken | slope < 0 AND return > 0 | Warning: Reversal Risk |

### Phase 3-4 Usage

| Phase | Usage | Impact |
|-------|-------|--------|
| 3 | Market/Sector trend_label ("decline", "transition", "trend") | Cycle state classification |
| 4 | Trend transition score prior (T0: 0.10, T1: 0.55, T2: 0.80, T3: 0.70, T4: 0.65, T5: 0.20, T6: 0.05) | 10% weight in structural bottom score |
| 4 | Risk override: T6_TREND_BROKEN → R2 (30% risk factor) | Downside risk activation |
| 4 | Contradiction check (T6 presence) | Bearish veto |

---

## 15. EXHAUSTION FEATURES (Phase 4 Specific Input)

### Exhaustion Component Aggregation

Phase 4 aggregates multiple exhaustion signals geometrically:

```python
def calculate_exhaustion_score(features: dict[str, float], config: BottomConfig) -> float:
    """
    Components:
    - volume (float): volume_exhaustion
    - price (float): price_efficiency
    - efficiency (float): derived from path calculation
    - momentum (float): momentum component
    
    Aggregation: geometric_mean(volume, price, efficiency, momentum)
    All values clipped to [0, 1] before aggregation
    Weights: each 25% (uniform)
    """
```

### Field Mapping

| Phase 4 Component | Source | Calculation | Meaning |
|-----------------|--------|------------|---------|
| **volume** | price_volume_features | volume / 20-day avg | High exhaustion (>1.0) suggests cycle end |
| **price** | price_volume_features | efficiency ratio | High efficiency (>0.7) suggests trending, low exhaustion |
| **efficiency** | price_volume_features | Same as price | Price-move directional quality |
| **momentum** | Momentum features | Tanh-bounded sum of MACD/KDJ | Momentum reversal strength |

### Exhaustion Score Interpretation

- **Low exhaustion** (0.0-0.35): Fresh move, not ready to turn
- **Medium exhaustion** (0.35-0.65): Normal cycle progression
- **High exhaustion** (0.65-1.0): Cycle near turning point

### Phase 4 Usage

Exhaustion score = 20% of structural bottom score (weights: position 25%, chip 25%, exhaustion 20%, momentum 10%, resonance 20%)

Low exhaustion by itself does not prevent bottom probability; other components (position, resonance) may be strong.

---

## 16. DATA FLOW SUMMARY TABLE

This table shows which phases produce/consume each data category:

| Category | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|----------|---------|---------|---------|---------|
| **OHLCV** | Input ✓ | Input ✓ | Input ✓ | Input ✓ |
| **Stock Symbol** | - | Input ✓ | Input ✓ | Input ✓ |
| **Free-Float** | - | Input ✓ | Output (via Chip) | Input (via Chip) |
| **Shareholder** | - | Input ✓ | Output (via Chip) | Input (via Chip) |
| **Chip Density** | - | Output ✓ | Input ✓ | Input ✓ |
| **Position %** | Output ✓ | Output (via Chip) | Input ✓ | Input ✓ |
| **Momentum** | Output ✓ | Output (via Chip) | Input ✓ | Input ✓ |
| **Trend State** | Output ✓ | Output (optional) | Input ✓ | Input ✓ |
| **Market Index** | - | Output (via Market) | Input ✓ | Input ✓ |
| **Market Breadth** | - | - | Input ✓ | Input ✓ |
| **Sector Index** | - | - | Input ✓ | Input ✓ |
| **Market Regime** | - | - | Output ✓ | Input ✓ |
| **Sector Regime** | - | - | Output ✓ | Input ✓ |
| **Stock Regime** | - | - | Output ✓ | Input (via Resonance) |
| **Resonance** | - | - | Output ✓ | Input ✓ |

---

## 17. VALIDATION CONSTRAINTS CHECKLIST

### Type Constraints
- ✓ DatetimeIndex: All dates must be `pd.Timestamp`, monotonic increasing (no gaps for single symbol)
- ✓ Float columns: Enforced by `pd.api.types.is_numeric_dtype()`
- ✓ OHLCV: `low <= close <= high`, `high >= low`, `volume >= 0`
- ✓ Weights/Ratios: All in [0, 1] range
- ✓ Shares: >= 0 (non-negative)
- ✓ Free-float: > 0 (strictly positive)

### Uniqueness Constraints
- ✓ Single-symbol OHLCV: No duplicate dates
- ✓ Multi-symbol: (symbol, date) must be unique
- ✓ Multi-sector: (sector, date) must be unique
- ✓ Shareholder: (effective_date, symbol, shareholder_id) must be unique

### Point-in-Time Filtering
- ✓ All historical data filtered to `date <= as_of_date`
- ✓ No forward-fill or future data usage
- ✓ Snapshots preserve data state as-of their cutoff date
- ✓ Shareholder records: use only those with `effective_date <= as_of_date`

### Quality Indicators
- ✓ Confidence levels reported as "high", "medium", "low"
- ✓ Phase 2 ETC: "high" confidence when covered >= 80% of free_float
- ✓ Phase 4 Bottom: "high" confidence when chip data + all exhaustion features present

---

## 18. CRITICAL DATA FLOW INVARIANTS

1. **No Circular Dependencies**: Each phase output becomes next phase input (Phase 1 → 2 → 3 → 4)
2. **No Backfilling**: Missing values remain `NaN`; system respects data gaps gracefully
3. **Causality Preservation**: T-day features never use T+1 or later data
4. **Immutability**: All data processing non-mutating; quality reports never modify inputs
5. **Auditability**: Every field traced to source with explicit metadata
6. **Reproducibility**: Identical inputs → identical outputs (deterministic algorithms)
7. **Graceful Degradation**: Confidence levels reflect actual data quality; system continues with reduced confidence rather than failing

---

## 19. CONFIG DEFAULTS (Customizable)

All default values can be overridden by passing custom config objects.

### ChipConfig (Phase 2)

```python
@dataclass(frozen=True)
class ChipConfig:
    activity_weights: dict = {
        "retail": 0.85, "institution": 0.45, "fund": 0.55,
        "insurance": 0.25, "social_security": 0.20, "company": 0.20,
        "controller": 0.10, "executive": 0.15, "strategic": 0.10,
        "unknown": 0.35,
    }
    unknown_activity_weight: float = 0.35
    known_coverage_confidence_threshold: float = 0.80  # >=80% covered = "high"
    core_coverage_target: float = 0.70  # Target chip density core
    support_resistance_window_pct: float = 0.10  # ±10% around current price
    migration_windows: tuple = (5, 20, 60)
    divergence_windows: tuple = (20, 60)
```

### IndicatorConfig (Phase 1)

```python
@dataclass(frozen=True)
class IndicatorConfig:
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    kdj_period: int = 9
    kdj_smoothing: int = 3
    position_windows: tuple = (60, 120, 250, 500)
```

### MarketConfig (Phase 3)

```python
@dataclass(frozen=True)
class MarketConfig:
    position_windows: tuple = (60, 120, 250, 500)
    relative_strength_windows: tuple = (20, 60, 120)
    breadth_ma_windows: tuple = (20, 60, 120, 250)
    strength_weights: dict = {
        "structural": 0.35, "momentum": 0.25,
        "breadth": 0.20, "participation": 0.20,
    }
    sector_strength_weights: dict = {
        "position": 0.25, "momentum": 0.25,
        "trend": 0.25, "relative_strength": 0.25,
    }
    stock_strength_weights: dict = {
        "position": 0.25, "momentum": 0.25,
        "trend": 0.25, "chip": 0.25,
    }
    position_neutral_center: float = 0.50
    momentum_scale: float = 1.0
    chip_divergence_scale: float = 0.10
    market_gate_floor: float = 0.15
    cycle_alignment_threshold: float = 0.70
    grade_c_threshold: float = 0.10
    grade_b_threshold: float = 0.52
    grade_a_threshold: float = 0.65
```

### BottomConfig (Phase 4)

```python
@dataclass(frozen=True)
class BottomConfig:
    # Component weights (all sum to 1.0)
    position_weights: dict = {"60": 0.20, "120": 0.25, "250": 0.25, "500": 0.30}
    chip_weights: dict = {"stability": 0.40, "support": 0.35, "pressure": 0.25}
    exhaustion_weights: dict = {
        "volume": 0.25, "price": 0.25, "efficiency": 0.25, "momentum": 0.25,
    }
    momentum_weights: dict = {
        "histogram": 0.25, "slope": 0.20, "divergence": 0.20,
        "velocity": 0.20, "kdj": 0.15,
    }
    structural_weights: dict = {
        "position": 0.25, "chip": 0.25, "exhaustion": 0.20,
        "momentum": 0.10, "resonance": 0.20,
    }
    confirmation_weights: dict = {"momentum": 0.60, "trend": 0.40}
    
    # Trend state priors
    trend_state_priors: dict = {
        "T0_MAIN_DECLINE": 0.10, "T1_DECLINE_STOPPED": 0.55,
        "T2_REVERSAL_CONFIRMED": 0.80, "T3_UPTREND": 0.70,
        "T4_ACCELERATION": 0.65, "T5_RALLY_EXHAUSTION": 0.20,
        "T6_TREND_BROKEN": 0.05,
    }
    
    # Thresholds
    l1_threshold: float = 0.40  # Weak bottom candidate
    l2_threshold: float = 0.50  # Structural bottom
    l3_threshold: float = 0.50  # Confirmed bottom
    l4_threshold: float = 0.75  # Strategic bottom (rare)
    resonance_minimum: float = 0.30  # Minimum resonance for consideration
    resonance_high: float = 0.65  # High resonance for L4
    rr1_minimum: float = 1.50  # Minimum risk/reward 1 for L4
    
    # Risk factors (R0=1.0, R1=0.70, R2=0.30, R3=0.05)
    risk_r1_factor: float = 0.70
    risk_r2_factor: float = 0.30
    risk_r3_factor: float = 0.05
    
    # Other
    price_window_pct: float = 0.10  # ±10% for support/resistance
    chip_distance_scale: float = 0.10
    bearish_momentum_threshold: float = -0.50  # MACD slope < -0.50 = bearish
    weak_sector_relative_strength: float = -0.10  # RS < -0.10 = weak
```

---

## 20. QUICK REFERENCE: FIELD BY PHASE

### Phase 1 Inputs (OHLCV)
- open, high, low, close, volume, date

### Phase 1 Outputs (Features)
- position_60/120/250/500, price_percentile
- MACD (macd, histogram, histogram_slope)
- KDJ (k, d, rsv, j)
- Price-volume features (velocity, exhaustion, efficiency)
- Trend state (T0-T6)

### Phase 2 Inputs
- Free-float data (symbol, date, free_float_shares)
- Shareholder data (effective_date, symbol, shareholder_id, shares, holder_type, activity_weight)
- OHLCV history (for chip density calculation)

### Phase 2 Outputs
- ETC (effective_tradable_chips, active_ratio, confidence, fallback_used)
- Chip Profile (concentration, core_range, peak_price, migration, divergence, density)

### Phase 3 Inputs
- OHLCV (market indices, sectors)
- Breadth data (optional)
- Stock position, momentum, trend
- Chip profile

### Phase 3 Outputs
- Market Regime (market_cycle_state, market_strength, market_gate)
- Sector Regime (cycle_state, sector_strength, relative_strength)
- Stock Regime (stock_cycle_state, stock_strength)
- Resonance Profile (resonance_strength, resonance_grade)

### Phase 4 Inputs
- Current price
- Position percentiles (60/120/250/500)
- Chip profile (all fields)
- Momentum features (MACD, KDJ, price-volume)
- Trend state
- Exhaustion features
- Market regime (market_cycle_state, market_strength, market_gate)
- Sector regime (cycle_state, sector_relative_strength)
- Resonance profile (resonance_strength)
- History (for support/resistance)

### Phase 4 Outputs
- Bottom probability (0.0-1.0)
- Bottom level (L1, L2, L3, L4, NONE)
- Risk override state (R0-R3)
- Risk/reward zones
- Component scores (position, chip, exhaustion, momentum, trend, resonance)

---

## Appendix: Reference Links

- Source: `/Users/paipai/Downloads/mctr/src/mctr/data/models.py` — Data contracts
- Source: `/Users/paipai/Downloads/mctr/src/mctr/data/validators.py` — Validation rules
- Source: `/Users/paipai/Downloads/mctr/src/mctr/chips/models.py` — Chip data structures
- Source: `/Users/paipai/Downloads/mctr/src/mctr/config.py` — All configurable defaults
- Source: `/Users/paipai/Downloads/mctr/src/mctr/scoring/bottom.py` — Phase 4 bottom engine
- Source: `/Users/paipai/Downloads/mctr/src/mctr/market/regime.py` — Phase 3 market regime
- Source: `/Users/paipai/Downloads/mctr/src/mctr/sector/regime.py` — Phase 3 sector regime
- Source: `/Users/paipai/Downloads/mctr/src/mctr/resonance/engine.py` — Phase 3 resonance

---

**Document Version**: 1.0  
**Last Updated**: 2026-09-01  
**Scope**: MCTR Phases 1-4 Input Fields Reference  
**Status**: Comprehensive mapping complete

