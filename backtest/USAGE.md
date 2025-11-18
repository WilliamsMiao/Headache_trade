# 回测系统使用指南

## 快速开始

### 1. 查看所有可用策略
```bash
python backtest/run.py --list
```

### 2. 运行单个策略回测
```bash
# 基础用法
python backtest/run.py --strategy momentum --days 90

# 指定时间周期和交易对
python backtest/run.py --strategy mean_reversion --days 30 --timeframe 1h --symbol BTC/USDT

# 指定初始资金
python backtest/run.py --strategy breakout --days 60 --capital 20000
```

### 3. 对比多个策略
```bash
# 对比2个策略
python backtest/run.py --compare momentum mean_reversion --days 90

# 对比所有策略
python backtest/run.py --all --days 90
```

## 参数说明

| 参数 | 说明 | 默认值 | 可选值 |
|------|------|--------|--------|
| `--list` | 列出所有策略 | - | - |
| `--strategy` | 运行单个策略 | - | momentum, mean_reversion, breakout, grid, trend |
| `--compare` | 对比多个策略 | - | 空格分隔的策略名 |
| `--all` | 对比所有策略 | - | - |
| `--days` | 回测天数 | 90 | 任意正整数 |
| `--timeframe` | 时间周期 | 15m | 1m, 5m, 15m, 1h, 4h, 1d |
| `--symbol` | 交易对 | BTC/USDT | 任意交易对 |
| `--capital` | 初始资金 | 10000 | 任意正数 |

## 策略列表

### 1. Momentum (动量策略)
- **原理**: 捕捉强势趋势中的动量行情
- **适用**: 单边上涨/下跌行情
- **关键指标**: RSI, ADX, 成交量

### 2. Mean Reversion (均值回归)
- **原理**: 在超买超卖区域寻找反转机会
- **适用**: 震荡市场
- **关键指标**: RSI, 布林带, 成交量萎缩

### 3. Breakout (突破策略)
- **原理**: 突破关键价位时跟随
- **适用**: 区间突破行情
- **关键指标**: 价格突破, 成交量放大

### 4. Grid (网格交易)
- **原理**: 在价格区间内反复高抛低吸
- **适用**: 横盘震荡市
- **关键指标**: 网格间距, 回归均值

### 5. Trend Following (趋势跟踪)
- **原理**: 识别并跟随中长期趋势
- **适用**: 明确趋势行情
- **关键指标**: 均线, MACD, ADX

## 输出文件

回测完成后，会在 `backtest_results/` 目录生成以下文件：

- `{策略名}_{时间戳}.txt` - 文本格式报告
- `{策略名}_{时间戳}.json` - JSON格式数据
- `comparison_{时间戳}.txt` - 策略对比报告（对比模式）

## 评级标准

策略会根据以下指标获得 A-F 评级（满分100分）：

| 指标 | 权重 | 评分标准 |
|------|------|----------|
| 总收益率 | 30% | >20%=30分, >10%=25分, >5%=20分, >0%=15分 |
| 胜率 | 20% | >60%=20分, >50%=15分, >40%=10分 |
| 盈亏比 | 20% | >2.0=20分, >1.5=15分, >1.0=10分 |
| 夏普比率 | 15% | >2.0=15分, >1.0=10分, >0.5=5分 |
| 最大回撤 | 15% | <5%=15分, <10%=10分, <20%=5分 |

**评级等级**:
- A (80-100): 优秀
- B (60-79): 良好
- C (40-59): 一般
- D (20-39): 较差
- F (0-19): 失败

## Python API 使用

```python
from backtest_system import BacktestSystem

# 创建回测系统
system = BacktestSystem()

# 运行单个策略
result = system.run_strategy(
    strategy_key='momentum',
    days=90,
    timeframe='15m',
    initial_capital=10000,
    custom_params={'rsi_period': 14}
)

# 对比多个策略
results = system.compare_strategies(
    strategy_keys=['momentum', 'mean_reversion', 'breakout'],
    days=90
)

# 参数优化
best = system.optimize_parameters(
    strategy_key='mean_reversion',
    param_grid={
        'rsi_oversold': [30, 35, 40],
        'rsi_overbought': [60, 65, 70],
        'stop_loss': [0.01, 0.015, 0.02]
    },
    days=90,
    metric='total_return'
)
print(f"最佳参数: {best['best_params']}")
print(f"最佳收益: {best['best_score']:.2f}%")
```

## 注意事项

1. **数据缓存**: 首次下载数据会较慢，后续会使用缓存
2. **数据更新**: 缓存每天自动更新，可手动清除缓存重新下载
3. **Windows编码**: 如遇中文乱码，在命令行前添加 `$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
4. **内存使用**: 大数据量回测（>180天 + 1分钟级）可能占用较多内存
5. **CPU使用**: 参数优化会测试大量组合，建议使用较短时间周期

## 故障排除

### 问题：ImportError
```bash
# 解决方案：确保在项目根目录运行
cd c:\Users\cair1\Desktop\HT\Headache_trade
python backtest/run.py --list
```

### 问题：数据下载失败
```bash
# 解决方案：检查网络连接，或使用现有缓存
python backtest/run.py --strategy momentum --days 30  # 使用更短时间
```

### 问题：回测速度慢
```bash
# 解决方案：减少数据量或提高时间周期
python backtest/run.py --strategy momentum --days 30 --timeframe 1h  # 30天+1小时
```

## 示例场景

### 场景1：测试策略在近期行情表现
```bash
python backtest/run.py --strategy momentum --days 30 --timeframe 15m
```

### 场景2：寻找最佳策略
```bash
python backtest/run.py --all --days 90 --timeframe 1h
```

### 场景3：优化策略参数（Python代码）
```python
from backtest_system import BacktestSystem

system = BacktestSystem()
best = system.optimize_parameters(
    strategy_key='momentum',
    param_grid={
        'atr_multiplier': [1.5, 2.0, 2.5],
        'risk_reward': [1.5, 2.0, 2.5],
        'position_size': [0.2, 0.3, 0.4]
    },
    days=90,
    metric='total_return'
)
```

### 场景4：不同时间周期对比
```bash
# 短周期
python backtest/run.py --strategy momentum --days 90 --timeframe 15m

# 中周期  
python backtest/run.py --strategy momentum --days 90 --timeframe 1h

# 长周期
python backtest/run.py --strategy momentum --days 90 --timeframe 4h
```
