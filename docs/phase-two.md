# MCTR Phase Two

第二阶段只实现 ETC 与筹码密度原始特征，不实现 Bottom/Top Score、Market Regime、Sector Regime、Resonance、Risk Override 或回测策略。

## ETC

自由流通股是交易股份基础，不再从中重复扣除限售股或十大流通股东：

`ETC = Free Float * Active Ratio`

股东明细的有效股份为：

`effective_shares = shares * activity_weight`

已知股东加权股份与自由流通股中未覆盖部分的 unknown 先验相加，再除以 Free Float 得到 Active Ratio。没有股东明细时返回低置信度、`fallback_used=True` 的显式 fallback。V1 权重是模型先验，尚未历史校准；`ActivityCalibrator` 是后续校准接口。

## Density and Migration

OHLCV 条件下的成交价格重心近似为：

`center = (high + low + 2 * close) / 4`

它不是逐笔或分钟数据的替代品。每日有效换手为：

`turnover = clip(volume / FreeFloat, 0, 1)`

逐日迁移为：

`old_chip = previous_chip * (1 - turnover)`

`new_chip = turnover * ETC`

`raw_chip = old_chip + new_chip_at_center`

每日迁移后，如果 `raw_total > 0`，重新缩放到当前 ETC：

`scale_factor = ETC_today / raw_total`

`chip_today = raw_chip * scale_factor`

因此每日筹码总量等于当前日 ETC。`raw_total = 0` 时保留零密度，不执行除法。

内部同时保留 shares 版本和归一化版本。归一化密度的总和为 1（非空时）。

## Peak, Core Range, Support, Resistance

主峰是密度最大的价格 level。核心区间是在排序价格 level 上，使归一化密度覆盖目标比例的最窄连续区间；目标比例由 `ChipConfig.core_coverage_target` 配置。

支撑是当前价格以下、`support_resistance_window_pct` 窗口内的筹码；阻力是当前价格以上同窗口内的筹码。两者都输出最近价格、归一化密度和密度加权价格。

## Migration and Divergence

`migration_Nd = current_peak - peak_N_trading_days_ago`

`migration_velocity_Nd = migration_Nd / N`

`divergence_Nd = price_return_Nd - chip_peak_return_Nd`

其中 `price_return_Nd = close_today / close_N_days_ago - 1`，`chip_peak_return_Nd` 使用同样的主峰价格定义。历史不足时返回 `None`。

## Point-in-Time

任何 profile 先将 OHLCV 截断到 `as_of_date`。股东记录只接受 `effective_date <= as_of_date`，限售股记录的 `source_date > as_of_date` 不参与当前日期的数据边界。限售股不会从已经给定的 Free Float 中再次扣除。