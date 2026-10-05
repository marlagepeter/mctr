# MCTR Input Fields — Visual Reference & Matrix

## Phase-by-Phase Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1: Feature Calculation                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  INPUT:                       PROCESSING:              OUTPUT:               │
│  ┌──────────────────┐        ┌──────────────────┐     ┌──────────────────┐  │
│  │ Stock OHLCV      │───────▶│ Position %tiles  │────▶│ 60/120/250/500d  │  │
│  │ (date indexed)   │        │ 60/120/250/500d  │     │ percentiles      │  │
│  └──────────────────┘        └──────────────────┘     └──────────────────┘  │
│         △                                                        │            │
│         │                                                        ▼            │
│  ┌──────────────────┐        ┌──────────────────┐     ┌──────────────────┐  │
│  │ (no special data)│───────▶│ MACD + Histogram │────▶│ macd             │  │
│  │                  │        │ KDJ              │     │ histogram_slope  │  │
│  │                  │        │ Price-Volume     │     │ kdj_k, kdj_d     │  │
│  │                  │        │ Trend Features   │     │ price_velocity   │  │
│  │                  │        │                  │     │ volume_exhaustion│  │
│  │                  │        │                  │     │ price_efficiency │  │
│  └──────────────────┘        └──────────────────┘     └──────────────────┘  │
│                                                               │              │
│                                                               ▼              │
│                                                     ┌──────────────────┐     │
│                                                     │ Trend State      │     │
│                                                     │ (T0 - T6)        │     │
│                                                     └──────────────────┘     │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 2: Chip Profile Calculation                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  INPUT:                       PROCESSING:              OUTPUT:               │
│  ┌──────────────────┐        ┌──────────────────┐     ┌──────────────────┐  │
│  │ Free-Float Data  │───────▶│ Activity Ratio   │────▶│ ETC              │  │
│  │ (symbol, date,   │        │ Calculation      │     │ active_ratio     │  │
│  │  free_float$)    │        │                  │     │ confidence       │  │
│  └──────────────────┘        └──────────────────┘     └──────────────────┘  │
│         △                                                        │            │
│  ┌──────────────────┐                                            ▼            │
│  │ Shareholder Data │───────────────────────────────┐  ┌──────────────────┐  │
│  │ (effective_date, │                               │  │ Chip Density     │  │
│  │  symbol,         │                               └─▶│ distribution     │  │
│  │  shareholder_id, │                                  │ (price-level)    │  │
│  │  shares,         │                                  │                  │  │
│  │  holder_type,    │                                  │ concentration    │  │
│  │  activity_weight)│        ┌──────────────────┐     │ core_*           │  │
│  └──────────────────┘───────▶│ Build Density    │────▶│ peak_*           │  │
│         △                    │ from OHLCV       │     │ support_density  │  │
│         │                    │ + ETC Migration  │     │ resistance_density   │
│  ┌──────────────────┐        │ Turnover = vol/FF│     │ migration_*      │  │
│  │ OHLCV History    │───────▶│                  │     │ divergence_*     │  │
│  │ (for turnover)   │        └──────────────────┘     └──────────────────┘  │
│  └──────────────────┘                                                        │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 3: Regime & Resonance Calculation                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  INPUT (Market Layer):        ┌──────────────────┐     OUTPUT:               │
│  ┌──────────────────┐         │ Calculate        │     ┌──────────────────┐  │
│  │ Market Index     │────────▶│ Position %tiles  │────▶│ Market Regime    │  │
│  │ OHLCV            │         │ MACD, KDJ, Trend │     │ (M0-M8)          │  │
│  └──────────────────┘         │ + Market Gate    │     │ market_strength  │  │
│         △                     │                  │     │ market_gate      │  │
│  ┌──────────────────┐         └──────────────────┘     └──────────────────┘  │
│  │ Breadth Data     │────────────────────────────────────────┐                │
│  │ (optional)       │                                        │                │
│  └──────────────────┘                                        ▼                │
│                                                     ┌──────────────────┐      │
│  INPUT (Sector Layer):                              │ Cycle Alignment  │      │
│  ┌──────────────────┐         ┌──────────────────┐  │ Calculation      │      │
│  │ Sector Index     │────────▶│ Position, MACD,  │  │ (Market→Sector   │      │
│  │ OHLCV            │         │ KDJ, Trend,      │──▶│  →Stock)         │      │
│  └──────────────────┘         │ Rel.Strength     │  │                  │      │
│         △                     │ + Market Ref     │  │ → Resonance      │      │
│  ┌──────────────────┐         └──────────────────┘  │ Profile          │      │
│  │ Market Close     │─────────────────┐             └──────────────────┘      │
│  │ (for RS calc)    │                 ▼                      △                │
│  └──────────────────┘         ┌──────────────────┐           │                │
│                               │ Sector Regime    │───────────┘                │
│                               │ (S1-S8)          │                            │
│  INPUT (Stock Layer):         │ sector_strength  │                            │
│  ┌──────────────────┐         │ cycle_state      │                            │
│  │ Phase 1 Features │────────▶│                  │                            │
│  │ (position, mom,  │         └──────────────────┘                            │
│  │  trend, etc)     │                 △                                       │
│  │ + Chip Profile   │                 │                                       │
│  └──────────────────┘        ┌──────────────────┐                            │
│                               │ Stock Regime     │                            │
│                               │ (from Phase 1 +  │                            │
│                               │  Chip)           │                            │
│                               │ → stock_strength │                            │
│                               │ → stock_cycle    │                            │
│                               └──────────────────┘                            │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 4: Bottom Engine Scoring                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│ INPUTS (All Phase 1-3 outputs):                                             │
│ ┌─ Position %tiles (60/120/250/500) ──────┐                                 │
│ ├─ Chip Profile (concentration, support, resistance, migration, divergence)│
│ ├─ Momentum Features (MACD, KDJ, price-volume tanh-bounded)                │
│ ├─ Exhaustion Features (volume, price, efficiency, momentum)               │
│ ├─ Trend State (T0-T6) ──────────────────────────────────────────────┐    │
│ ├─ Market Regime (M0-M8, market_strength, market_gate) ──────────┐   │    │
│ ├─ Sector Regime (S1-S8, sector_strength, relative_strength)──────┤   │    │
│ └─ Resonance Profile (resonance_strength, resonance_grade) ───────┤   │    │
│                                                                     │   │    │
│   ┌──────────────────────────────────────────────────────────┐    │   │    │
│   │           SCORE AGGREGATION & GATING                      │    │   │    │
│   ├──────────────────────────────────────────────────────────┤    │   │    │
│   │                                                            │    │   │    │
│   │ Position Score:                                           │    │   │    │
│   │   1 - geom_mean(pos60, pos120, pos250, pos500)            │    │   │    │
│   │   weights: 20%, 25%, 25%, 30%                             │    │   │    │
│   │   (low price = favorable)                                 │    │   │    │
│   │                                                            │    │   │    │
│   │ Chip Score:                                               │    │   │    │
│   │   geom_mean(stability, support, pressure)                 │    │   │    │
│   │   weights: 40%, 35%, 25%                                  │    │   │    │
│   │   stability = concentration × exp(-width / price_window)  │    │   │    │
│   │                                                            │    │   │    │
│   │ Exhaustion Score:                                         │    │   │    │
│   │   geom_mean(volume, price, efficiency, momentum)          │    │   │    │
│   │   weights: 25% each                                       │    │   │    │
│   │                                                            │    │   │    │
│   │ Momentum Reversal Score:                                  │    │   │    │
│   │   geom_mean(tanh-bounded features)                        │    │   │    │
│   │   weights: histogram 25%, slope 20%, divergence 20%,      │    │   │    │
│   │            velocity 20%, KDJ 15%                          │    │   │    │
│   │                                                            │    │   │    │
│   │ Trend Transition Score: T0-T6 prior                       │    │   │    │
│   │   priors: T0=10%, T1=55%, T2=80%, T3=70%, T4=65%,         │    │   │    │
│   │           T5=20%, T6=5%                                   │    │   │    │
│   │                                                            │    │   │    │
│   │ Resonance Score: resonance_strength (Phase 3)             │    │   │    │
│   │                                                            │    │   │    │
│   │ STRUCTURAL BOTTOM SCORE:                                  │    │   │    │
│   │   geom_mean(position, chip, exhaustion, momentum, resonance)   │    │    │
│   │   weights: 25%, 25%, 20%, 10%, 20%                        │    │   │    │
│   │                                                            │    │   │    │
│   │ CONFIRMATION FACTOR: momentum × trend agreement           │    │   │    │
│   │   agreement = 1 - |momentum - trend|                      │    │   │    │
│   │   weights: 60% momentum, 40% trend                        │    │   │    │
│   │                                                            │    │   │    │
│   │ CONTRADICTION FACTOR:◄─────────────────────────────────────┤   │    │
│   │   Penalize cheap+bearish: position high + momentum low    │   │    │
│   │   Penalize weak chips, bearish market/sector             │   │    │
│   │                                                            │   │    │
│   │ RISK OVERRIDE (R0-R3):◄───────────────────────────────────┤   │    │
│   │   R3 (0.05x): M0/M8 or T6_TREND_BROKEN + bearish factors │   │    │
│   │   R2 (0.30x): Multiple risk factors present              │   │    │
│   │   R1 (0.70x): Single risk factor (chip migration, volume) │   │    │
│   │   R0 (1.00x): No risk overrides                          │   │    │
│   │                                                            │   │    │
│   │ BOTTOM PROBABILITY:◄──────────────────────────────────────┤   │    │
│   │   structural × confirmation × contradiction × risk_factor │   │    │
│   │                                                            │   │    │
│   │ BOTTOM LEVEL: L1, L2, L3, L4, NONE◄──────────────────────┘   │    │
│   │   Based on probability + component thresholds                 │    │
│   │                                                                │    │
│   │ RISK/REWARD ZONES:                                            │    │
│   │   Entry: current_price                                        │    │
│   │   Downside: support_density level                             │    │
│   │   Target1: core_upper or peak_price                           │    │
│   │   Target2: historical high > Target1                          │    │
│   │   Ratios: (target - entry) / (entry - risk)                   │    │
│   │                                                                │    │
│   └────────────────────────────────────────────────────────────┘    │    │
│                                                                      │    │
│ OUTPUTS:                                                             │    │
│ ┌─ Bottom Probability: [0, 1]                                       │    │
│ ├─ Bottom Level: L1, L2, L3, L4, NONE                              │    │
│ ├─ Risk Override State: R0, R1, R2, R3                             │    │
│ ├─ Component Scores: position, chip, exhaustion, momentum, trend   │    │
│ ├─ Risk/Reward Zones: entry, downside, targets, ratios            │    │
│ ├─ Explanation Dict: reasons for each component                    │    │
│ └─ Confidence: high, medium, low                                   │    │
│                                                                      │    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Type Matrix: What Each Phase Needs

```
                    │ Phase 1 │ Phase 2 │ Phase 3 │ Phase 4 │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
OHLCV               │  INPUT  │ INPUT   │ INPUT   │ INPUT   │
Stock Symbol        │    -    │ INPUT   │ INPUT   │ INPUT   │
Market Index OHLCV  │    -    │    -    │ INPUT   │ INPUT   │
Market Breadth      │    -    │    -    │ INPUT   │ INPUT   │
Sector Index OHLCV  │    -    │    -    │ INPUT   │ INPUT   │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Free-Float          │    -    │ INPUT   │ OUTPUT  │ OUTPUT  │
Shareholder         │    -    │ INPUT   │ OUTPUT  │ OUTPUT  │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Position %tiles     │ OUTPUT  │ OUTPUT  │ INPUT   │ INPUT   │
MACD/Histogram      │ OUTPUT  │ OUTPUT  │ INPUT   │ INPUT   │
KDJ                 │ OUTPUT  │ OUTPUT  │ INPUT   │ INPUT   │
Price-Volume Feat   │ OUTPUT  │ OUTPUT  │ INPUT   │ INPUT   │
Trend State         │ OUTPUT  │ OUTPUT  │ INPUT   │ INPUT   │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Chip Profile        │    -    │ OUTPUT  │ INPUT   │ INPUT   │
ETC                 │    -    │ OUTPUT  │ OUTPUT  │ OUTPUT  │
Density Distribution│    -    │ OUTPUT  │ OUTPUT  │ INPUT   │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Market Regime       │    -    │    -    │ OUTPUT  │ INPUT   │
Sector Regime       │    -    │    -    │ OUTPUT  │ INPUT   │
Stock Regime        │    -    │    -    │ OUTPUT  │ INPUT   │
Resonance Profile   │    -    │    -    │ OUTPUT  │ INPUT   │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Bottom Probability  │    -    │    -    │    -    │ OUTPUT  │
Bottom Level        │    -    │    -    │    -    │ OUTPUT  │
Risk/Reward Zones   │    -    │    -    │    -    │ OUTPUT  │
```

---

## Required Fields by Data Category

```
OHLCV DATA (Mandatory for all phases)
├─ open: float >= 0
├─ high: float >= close, >= low
├─ low: float <= close, <= high
├─ close: float, low <= close <= high
├─ volume: float >= 0
├─ date: DatetimeIndex (sorted, unique for single symbol)
└─ amount: float (optional, Phase 3 only)

STOCK SYMBOL
├─ symbol: string (Phase 2-4)
└─ Requirement: (symbol, date) unique in multi-symbol DataFrames

MARKET DATA
├─ Market Index: standard OHLCV per index
│  └─ indexed by dict key: 'SSE', 'CSI300', etc.
└─ Breadth (optional, Phase 3):
   ├─ advance_count: int
   ├─ decline_count: int
   ├─ unchanged_count: int
   ├─ new_high_count: int
   ├─ new_low_count: int
   ├─ above_ma20_ratio: float [0,1]
   ├─ above_ma60_ratio: float [0,1]
   ├─ above_ma120_ratio: float [0,1]
   ├─ above_ma250_ratio: float [0,1]
   └─ total_turnover: float (optional)

SECTOR DATA
├─ sector: string (S1000610, Technology, etc.)
├─ OHLCV: standard fields
└─ Requirement: (sector, date) unique

FREE-FLOAT DATA (Phase 2 Critical)
├─ symbol: string
├─ date/effective_date: Timestamp
└─ free_float_shares: float > 0 (strictly positive)

SHAREHOLDER DATA (Phase 2 Critical)
├─ effective_date: Timestamp
├─ symbol: string
├─ shareholder_id: string/int
├─ shares: float >= 0 (non-negative)
├─ holder_type: string [retail, institution, fund, insurance, ...]
├─ activity_weight: float [0,1] or None
└─ Requirement: (effective_date, symbol, shareholder_id) unique

CHIP PROFILE (Phase 2 Output → Phase 3-4 Input)
├─ ETC metrics:
│  ├─ effective_tradable_chips: float
│  ├─ free_float: float > 0
│  ├─ active_ratio: float [0,1]
│  ├─ confidence: string (high/medium/low)
│  └─ fallback_used: bool
├─ Density fields:
│  ├─ concentration: float [0,1]
│  ├─ core_lower/upper: float
│  ├─ peak_price/density: float
│  ├─ support_density: float [0,1]
│  ├─ resistance_density: float [0,1]
│  ├─ migration_*: float
│  ├─ divergence_*: float
│  ├─ density: pd.Series (price → shares)
│  └─ normalized_density: pd.Series

MARKET REGIME (Phase 3 Output → Phase 4 Input)
├─ market_cycle_state: string (M0-M8)
├─ market_strength: float [0,1]
├─ market_gate: float [0,1] (calculated)
├─ position_state/momentum_state/trend_state/breadth_state: string
└─ (plus component strengths for refinement)

SECTOR REGIME (Phase 3 Output → Phase 4 Input)
├─ cycle_state: string (S1-S8)
├─ sector_strength: float [0,1]
├─ position/momentum_state/trend_label: string
├─ relative_strength: dict (20d/60d/120d returns)
└─ (plus component strengths)

RESONANCE PROFILE (Phase 3 Output → Phase 4 Input)
├─ resonance_strength: float [0,1]
├─ resonance_grade: string (A/B/C/D/NONE)
├─ market_state/sector_state/stock_state: string
├─ market_gate: float [0,1]
├─ cycle_alignment: float [0,1]
└─ (plus alignment components & explanations)

POSITION PERCENTILES (Phase 1 Output)
└─ dict: {60: 0.35, 120: 0.40, 250: 0.45, 500: 0.50}

MOMENTUM FEATURES (Phase 1 Output)
├─ macd: float
├─ macd_histogram: float
├─ macd_histogram_slope: float
├─ kdj_k: float
├─ kdj_d: float
├─ price_velocity: float
├─ volume_velocity: float
├─ volume_exhaustion: float
└─ price_efficiency: float

TREND STATE (Phase 1 Output)
└─ T0-T6: TrendState enum or int

EXHAUSTION FEATURES (Phase 4 Input)
├─ volume: float (volume_exhaustion)
├─ price: float (price_efficiency)
├─ efficiency: float
└─ momentum: float (tanh-bounded)
```

---

## Confidence Level Definitions

```
PHASE 2 (ETC Calculation):
├─ "high": covered_shares >= 80% of free_float
├─ "medium": covered_shares < 80%
└─ "low": no shareholder records (fallback to unknown_activity_weight)

PHASE 3 (Market/Sector Regime):
├─ "high": all 4 components available (position, momentum, trend, breadth/RS)
├─ "medium": 2-3 components available
└─ "low": 0-1 components available

PHASE 4 (Bottom Engine):
├─ "high": chip data present + all exhaustion features + Phase 3 outputs
├─ "medium": chip data incomplete or missing some momentum features
└─ "low": critical gaps in chip/exhaustion/momentum
```

---

## Risk Override States (Phase 4)

```
R0 (1.00x risk factor):
  └─ No risk override triggered (baseline probability unmodified)

R1 (0.70x risk factor):
  ├─ Single risk factor present:
  │  ├─ Chip peak migrating downward rapidly (migration_20d < -price_window%)
  │  ├─ Volume at extreme levels with adverse price
  │  └─ Sector relative strength weak

R2 (0.30x risk factor):
  ├─ Multiple risk factors OR:
  ├─ Trend broken (T6_TREND_BROKEN)
  ├─ MACD histogram bearish acceleration
  └─ Systemic warnings (exhaustion states, volume extremes)

R3 (0.05x risk factor):
  ├─ Systemic crisis (M0 Extreme Bear OR M8 Breakdown)
  ├─ Multiple bearish factors converging
  └─ Extreme risk environment
```

---

## Bottom Level Classification (Phase 4)

```
L1: WEAK BOTTOM
  ├─ position >= 0.40 (low in 60-day range)
  ├─ chip < 0.50
  └─ exhaustion < 0.50

L2: STRUCTURAL BOTTOM
  ├─ position >= 0.40
  ├─ chip >= 0.50
  └─ exhaustion >= 0.50
  └─ momentum < 0.50 OR transition < 0.50

L3: CONFIRMED BOTTOM
  ├─ probability >= 0.50
  ├─ momentum >= 0.50
  ├─ transition >= 0.50
  └─ resonance >= 0.30

L4: STRATEGIC BOTTOM (Rare)
  ├─ probability >= 0.75
  ├─ resonance >= 0.65
  ├─ risk override = R0 (no risk factors)
  └─ risk_reward_1 >= 1.50

NONE: NOT A BOTTOM
  └─ Conditions for L1-L4 not met
```

---

## Common Data Shape Issues & Fixes

| Issue | Detection | Fix |
|-------|-----------|-----|
| Missing date index | index.name != 'date' or not DatetimeIndex | Set index: `df.set_index(pd.to_datetime(df['date'])) ` |
| Non-unique dates | date.duplicated().any() | Keep first/last: `df[~df.index.duplicated()]` |
| Date out of order | not df.index.is_monotonic_increasing | Sort: `df.sort_index()` |
| Missing columns | missing = [c for c in required if c not in df] | Rename or add: `df.rename(columns={...})` |
| Non-numeric OHLCV | df['close'].dtype != float64 | Convert: `df['close'] = pd.to_numeric(df['close'])` |
| Invalid OHLCV | (df['low'] > df['high']).any() | Filter or fix: `df = df[df['low'] <= df['high']]` |
| Negative volume | (df['volume'] < 0).any() | Filter: `df = df[df['volume'] >= 0]` |
| Zero free-float | (ff['free_float_shares'] == 0).any() | Filter: `ff = ff[ff['free_float_shares'] > 0]` |
| Activity weight out of range | ((activity_weight < 0) \| (activity_weight > 1)).any() | Clamp: `activity_weight.clip(0, 1)` or set None |

---

## Point-in-Time Snapshot Filtering

```python
# When creating a snapshot for as_of_date = 2024-01-15:

# OHLCV data: Keep all data <= 2024-01-15
stock_data_pit = stock_data[stock_data.index <= pd.Timestamp('2024-01-15')]

# Free-float: Last value <= 2024-01-15
ff_pit = free_float_data[free_float_data['date'] <= pd.Timestamp('2024-01-15')]

# Shareholder: All records where effective_date <= 2024-01-15
sh_pit = shareholder_data[shareholder_data['effective_date'] <= pd.Timestamp('2024-01-15')]

# Breadth: All data through 2024-01-15
breadth_pit = breadth_data[breadth_data.index <= pd.Timestamp('2024-01-15')]

# Result: Point-in-time snapshot with no future data leak
```

---

## Performance Optimization Hints

```
Phase 1 Calculation:
  └─ Vectorized (pandas rolling/ewm)
  └─ ~50-100k rows per stock: <100ms

Phase 2 Calculation:
  ├─ Shareholder aggregation: O(n shareholders)
  └─ Density building: O(n trading days) causal loop
  └─ ~500d history + 100 shareholders: <50ms

Phase 3 Calculation:
  ├─ Market regime: aggregate indices → O(n indices × n days)
  ├─ Sector regime: per-sector O(n days)
  ├─ Resonance: combine 3 layers → O(1) per date
  └─ ~5 indices × 250d: <100ms

Phase 4 Calculation:
  ├─ Geometric aggregations: O(1) per date (fixed components)
  ├─ Risk/reward zone search: O(n historical highs)
  └─ Single date: <10ms

Bottleneck: Phase 2 (shareholder iterations) and Phase 1 (if >10k rows)
Optimization: Vectorize shareholder weights, use rolling windows efficiently
```

---

## Field Uniqueness Requirements

```python
# Single-symbol OHLCV
assert not stock_ohlcv.index.duplicated().any()  # No duplicate dates

# Multi-symbol stock data
assert not stock_data.duplicated(['symbol', 'date']).any()  # (symbol, date) unique

# Multi-sector data
assert not sector_data.duplicated(['sector', 'date']).any()  # (sector, date) unique

# Free-float (historical)
assert not free_float.duplicated(['symbol', 'date']).any()  # (symbol, date) unique

# Shareholder (with effective_date)
assert not shareholders.duplicated(['effective_date', 'symbol', 'shareholder_id']).any()

# Market breadth (optional, single row per date)
assert not breadth.index.duplicated().any()

# Market indices (each dict entry)
for name, index_df in indices.items():
    assert not index_df.index.duplicated().any()
```

---

**Document Version**: 1.0  
**Format**: Visual Reference & Data Structure Matrix  
**Last Updated**: 2026-09-01

