# MCTR Phase Three

本阶段只实现 Market Regime、Sector Regime、Stock Regime Integration 和 Market -> Sector -> Stock 三层 Resonance。当前参数属于 Model Prior，尚未经过历史 walk-forward 校准，不代表任何 A/B/C/D 等级的收益保证。

重要边界：`Strength != Cycle Position != Bottom Probability`。Strength 表示结构有效程度；Cycle Position 表示所处周期阶段；Resonance 表示三层结构和周期的相容程度；Bottom Probability 与 Top Probability 属于后续 Phase。

## Market Regime

每个指数复用 Phase 1 的 Position、MACD、KDJ 和 Trend Engine。Position 使用配置的 60/120/250/500 日窗口；Trend 依赖趋势结构、方向效率和 MACD Histogram Slope，不使用均线金叉/死叉。

Market Breadth 直接接受日期 x 股票的收盘价横截面。每日计算上涨、下跌、平盘数量，250 日新高/新低数量，以及站上 20/60/120/250 日均线股票数除以当日有效股票数。任何日期只使用该日及之前的横截面。

Market Volume 保留总成交量/成交额和既有量价特征的趋势、变化、加速度字段。缺少 breadth 或 volume 时字段标记为 `missing`，confidence 降低，不静默填充。

Market Cycle State 由 Trend 主结构、Position 周期位置、Momentum 方向变化、Breadth 内部广度和 Volume 参与度共同解释，输出 M0 Extreme Bear、M1 Bear / Decline、M2 Decline Exhaustion、M3 Bottom Transition、M4 Recovery、M5 Bull Trend、M6 Acceleration、M7 Bull Exhaustion 或 M8 Breakdown 的状态文本。当前基线规则保守地优先识别下降、过渡、恢复和趋势状态。

## Market Strength

保留四个维度：`structural_strength`、`momentum_strength`、`breadth_strength`、`participation_strength`。最终强度不是算术平均，而是加权几何聚合：

`G = product(x_i ** w_i)`

权重由 `MarketConfig.strength_weights` 注入。严重缺失时 confidence 降低，缺失维度不会偷偷变成真实观测。

## Sector Strength

Sector Strength 不把 Cycle Position 作为重复乘数。四个连续结构分量为：Position、Momentum、Trend、Relative Strength：

`S_strength = (PositionStrength**wp * MomentumStrength**wm * TrendStrength**wt * RelativeStrengthStrength**wr) ** (1 / (wp + wm + wt + wr))`

PositionStrength 是 Position profile 与中性位置中心的连续距离；MomentumStrength 来自既有 MACD Histogram、Histogram Slope、Price/Volume Velocity、Volume Exhaustion 和 Price Efficiency 的连续变换；TrendStrength 使用配置化 T0-T6 非序数先验；RelativeStrengthStrength 来自相对强弱特征。权重由 `MarketConfig.sector_strength_weights` 配置。

低 Position 是 Cycle Position 信息，不会自动等于低 Strength；缺失分量会降低 confidence。

## Sector Regime

Sector 复用 Position、MACD、KDJ、量价已有定义和 Trend Engine，并额外计算相对大盘关系特征。行业周期状态输出 S0 Extreme Weak、S1 Weak、S2 Weakening / Exhaustion、S3 Bottom Transition、S4 Recovery、S5 Strong Trend、S6 Acceleration、S7 Exhaustion 或 S8 Breakdown 的状态文本；状态解释包含 Position、Momentum、Trend 和 Relative Strength。

## Relative Strength

对 N 日窗口：

`sector_return_N = sector_price_t / sector_price_(t-N) - 1`

`market_return_N = market_benchmark_t / market_benchmark_(t-N) - 1`

`relative_strength_N = sector_return_N - market_return_N`

默认支持 20d、60d、120d，所有输入先按 `as_of_date` 截断。

## Stock Regime Integration

Stock 只读取既有 Position、Momentum、Trend 和 Phase 2 `ChipProfile`。四个连续结构分量为：

`T_strength = PositionStrength**wp * MomentumStrength**wm * TrendStrength**wt * ChipStructuralStrength**wc`

其中权重由 `MarketConfig.stock_strength_weights` 配置，实际通过加权几何聚合。ChipStructuralStrength 只使用 Phase 2 的 Concentration、Support、Resistance、Migration 和 Chip-Price Divergence；没有重新发明筹码指标。只有旧状态标签时，使用 `stock_state_priors` / `chip_state_priors` 的透明 Model Prior，并降低 confidence。

输出 StockRegimeProfile，不产生 Bottom Probability、Top Probability、Buy Score 或 Sell Score。

## Three-Layer Resonance

令 `M`、`S`、`T` 分别为 Market、Sector、Stock Strength，均在 [0, 1]：

Structural Resonance：

`R_structural = M**wm * S**ws * T**wt * SectorAlignment * StockAlignment`

Cycle Alignment 独立计算 Market、Sector、Stock 的周期类别兼容性。低位 -> 过渡、过渡 -> 上升等相邻阶段使用配置化兼容分数，并以几何方式合并；它不等同于 Strength。

最终 Resonance：

`R = R_structural * CycleAlignment * MarketGate * WeakestLinkFactor`

其中权重由 `MarketConfig.resonance_weights` 配置且和为 1。该结构不是三者平均，也不是没有解释的直接乘积。底部过渡链可以在趋势强度尚不高时得到较高的 Cycle Alignment；这不代表 Bottom Probability。

相邻层 Alignment 分别计算 Market/Sector 与 Sector/Stock 的方向一致性；Stock 自身 alignment 读取已有 StockRegime 结构。输出每个因子及原因。

## Weakest-Link Constraint

最低层 strength 经过可配置非线性变换：

`WeakestLinkFactor = min(M, S, T) ** exponent`

指数由 `MarketConfig.weakest_link_exponent` 配置。它让任一层很弱时显著限制结果，而不是简单把最低值直接当最终得分。

## Market Gate and Grades

M0 Extreme Bear 和 M8 Breakdown 的 `MarketGate = 0`，因此不能产生任何共振等级；M2/M7 等耗竭状态的 Gate 上限为 `min(MarketStrength, 0.5)`；M1/M3/M4/M5/M6 使用 `max(market_gate_floor, min(1, MarketStrength))`。Gate 只限制系统性环境，不判断 Bottom。

等级阈值由 `MarketConfig` 配置：A 要求配置允许的底部过渡或强趋势 Market/Sector 状态、周期对齐和方向一致；B 表示较强但不完整的上层/下层组合；C 表示中性市场下行业与个股的局部结构；D 表示高位/风险市场中的个股局部结构，不代表战略买入；其余为 NONE。

## Point-in-Time and Scope

Market、Sector、Stock、Resonance 的输入均在 `as_of_date` 截断。不得使用未来指数、行业、成分股、股东或筹码数据；源码和测试禁止 `shift(-n)`、`bfill`、`backfill`。本阶段没有参数优化、实时 API、数据库、爬虫、券商、自动交易、回测策略、Bottom/Top Engine、Risk Override 或 UI。
