# MCTR Phase Four: Bottom Engine

本阶段只实现研究计算核心、数据模型和测试，不实现 Top Engine、正式回测、自动交易、API、数据库或 UI。所有默认配置都是 Model Prior，尚未经过历史校准。

## 重要边界

- `Low Price != Bottom`
- `Strength != Bottom Probability`
- `Exhaustion != Reversal`
- `Probability != Risk/Reward`

## Components

### Position Score

使用 Phase 1 的 60/120/250/500 日 Price Percentile，令 `q_N` 为对应分位：

`P = 1 - (q_60**w60 * q_120**w120 * q_250**w250 * q_500**w500) ** (1 / sum(w))`

权重由 `BottomConfig.position_weights` 配置。P 高只表示历史价格低位，不表示已经筑底。

### Chip Score

完全复用 Phase 2 `ChipProfile`，不重新发明筹码指标。三个子组件为：

- `C_stability`：Concentration、Core Chip Range 宽度和 Main Chip Peak Migration
- `C_support`：Support Density
- `C_pressure`：基于上方筹码距离衰减后的逆压力

Core range 稳定度采用连续指数衰减：

`C_stability = concentration * exp(-range_width / configured_price_window)`

距离加权压力为：

`distance_i = (price_i - current_price) / current_price`

`decay_i = exp(-abs(distance_i) / chip_distance_scale)`

`ResistancePressure = sum(normalized_density_i * decay_i)`（仅上方价格）

`C_pressure = clip(1 - ResistancePressure, 0, 1)`

下方 Support 同样使用距离衰减，因此近距离高密度筹码比远距离筹码更重要。`chip_distance_scale` 是 Model Prior，由 `BottomConfig` 配置。

最终：

`C = C_stability**ws * C_support**wp * C_pressure**wr`

### Exhaustion

使用已有 Volume Exhaustion、Price Velocity、Price Efficiency 和 MACD Histogram Slope 等连续特征，通过配置权重几何聚合：

`E = E_volume**wv * E_price**wp * E_efficiency**we * E_momentum**wm`

Exhaustion 表示下跌推进能力减弱，不表示已经反转。

### Momentum Reversal

使用已有 MACD Histogram、Histogram Slope、Divergence、Price/Volume Velocity 和 KDJ 相关连续特征。原始有符号特征先经：

`z_i = feature_i / momentum_feature_scale_i`

`x_i = 0.5 + 0.5 * tanh(z_i)`

每个特征的 scale 由 `BottomConfig.momentum_feature_scales` 配置，当前为 Model Prior，未经过历史校准。

再按 `BottomConfig.momentum_weights` 几何聚合。它独立于 Exhaustion，表示动量开始改善。

### Trend Transition

直接使用 Phase 3 Trend 状态映射，不使用 `state / 6`。Phase 4 状态先验为：

- T0 0.10
- T1 0.55
- T2 0.80
- T3 0.70
- T4 0.65
- T5 0.20
- T6 0.05

T0 不会直接否决底部；T6 至少触发 R2 风险。

## Structural Bottom Score

Trend Transition 不进入主体结构分数，避免大底在弱趋势阶段被硬否决：

`Bs = P**wp * C**wc * E**we * M**wm * R**wr`

权重由 `BottomConfig.structural_weights` 配置，且使用加权几何聚合。

## Confirmation Factor

Momentum 已进入 Bs，但 Confirmation 只表达从底部向反转的过渡确认，避免重复放大：

`Agreement = 1 - abs(M - T)`

`Confirmation = (M**wm * T**wt) * Agreement`

权重由 `BottomConfig.confirmation_weights` 配置。

Momentum 在 Bs 中表示动量证据，在 Confirmation 中只通过改善方向及其与 Trend Transition 的一致性参与，避免同一含义的重复放大。

## Contradiction Factor

为了避免“越跌越像底”，以下矛盾会降低因子：低位但动量恶化、筹码压力高、M0/M8、行业持续弱于市场。最终：

`B_adjusted = Bs * ContradictionFactor`

## Risk Override

风险独立于普通 Bottom Score：

- R0 Normal：`RiskFactor = 1.0`
- R1 Warning：配置的部分惩罚
- R2 Strong Risk：强惩罚，禁止 L4
- R3 Systemic Risk：极强惩罚，禁止 L4

M0/M8 直接 R3；T6 至少 R2。检查依据只使用现有 Phase 1/2/3 特征。

## Final Bottom Probability

`FinalBottomProbability = Bs * ConfirmationFactor * ContradictionFactor * RiskFactor`

依赖链：`Position -> P -> Bs`；`Chip -> C -> Bs`；`Exhaustion -> E -> Bs`；`Momentum -> M -> Bs + Confirmation 的方向一致性`；`Trend -> Confirmation`；`Phase 3 Resonance -> R -> Bs`；`Risk conditions -> RiskOverride -> RiskFactor`。Risk 不进入 Bs；Risk/Reward 不进入 Probability；Resonance 只读取 Phase 3 最终输出，不重新计算 Market/Sector/Stock。

不能等价为 `Bs * 100`，也不能由概率单独决定 L4。

## L1-L4

- L1 Price Low：Position 高，但 Chip/Exhaustion 证据不足。便宜不等于底。
- L2 Structural Low：Position、Chip Structure、Exhaustion 形成。
- L3 Cycle Bottom Candidate：L2 加 Momentum Reversal、Trend Transition 和最低 Resonance。
- L4 Strategic Bottom：L3 加高 Resonance、R0 Risk Override 和 RR1 达标。

状态条件、概率门槛和风险收益条件共同决定等级。

## Risk/Reward

Risk/Reward 与 Bottom Probability 分离。目标为区域而非精确价格：

- Target 1：当前可观察的 Core Range 上沿、主峰或阻力区
- Target 2：历史高点/更高的已观察阻力区
- Extreme Target：历史可观察极值区域

`RR_N = (Target_N - Entry) / (Entry - Risk)`

所有区域只使用当前及以前已知的 ChipProfile 和历史高点；不预测未来一定触达。

## Point-in-Time

Bottom Engine 接受的所有输入都必须是 `as_of_date` 快照。Risk/Reward 只读取截至该日期的历史。不得使用负向 shift、bfill、backfill、未来价格、未来成交量、未来筹码、未来市场、未来行业或未来股东信息。

## Current Scope

当前没有 Bottom 参数优化、walk-forward 校准、Top Engine、Risk Override 之外的交易执行逻辑、仓位、止盈止损、回测策略、API、数据库、自动交易或 UI。
