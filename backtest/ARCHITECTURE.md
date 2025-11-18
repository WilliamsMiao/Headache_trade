# 生产级回测系统架构说明

## 系统概述

本回测系统采用低耦合、高内聚的架构设计，各组件职责单一，通过标准接口交互。

## 核心组件

### 1. DataManager (数据管理器)
**文件**: `trading_bots/data_manager.py`

**职责**:
- 统一管理历史数据获取
- 智能缓存机制
- 自动重试和错误处理

**主要方法**:
- `fetch_data()` - 获取历史数据（自动使用缓存）
- `list_cached_data()` - 查看缓存清单
- `clear_cache()` - 清理缓存

**设计原则**:
- 纯数据层，不依赖任何策略或回测逻辑
- 缓存策略：每日更新，失败时使用旧缓存
- 数据格式标准化：统一返回 DataFrame

```python
# 使用示例
dm = DataManager()
df = dm.fetch_data('binance', 'BTC/USDT', '15m', 90)
# 第二次调用自动使用缓存，速度快
```

### 2. ReportGenerator (报告生成器)
**文件**: `trading_bots/report_generator.py`

**职责**:
- 生成标准化回测报告
- 支持多种输出格式（文本、JSON）
- 策略评级系统

**主要方法**:
- `generate_report()` - 生成单策略报告
- `compare_strategies()` - 生成对比报告
- `_calculate_rating()` - 计算策略评级 (A-F)

**设计原则**:
- 只处理结果数据，不参与回测执行
- 输出格式统一，无emoji（生产环境友好）
- 评级算法透明，基于5项核心指标

**评级标准**:
| 指标 | 权重 | 说明 |
|------|------|------|
| 总收益率 | 30% | 盈利能力 |
| 胜率 | 20% | 稳定性 |
| 盈亏比 | 20% | 风险回报比 |
| 夏普比率 | 15% | 风险调整后收益 |
| 最大回撤 | 15% | 风险控制 |

```python
# 使用示例
rg = ReportGenerator()
report_text = rg.generate_report(
    strategy_name='Momentum',
    results=backtest_results,
    params={'rsi_period': 14},
    data_info={'symbol': 'BTC/USDT', 'days': 90}
)
```

### 3. BacktestEngine (回测引擎)
**文件**: `trading_bots/backtest_engine.py`

**职责**:
- 逐K线模拟交易
- 仓位管理和资金计算
- 止损止盈执行
- 性能指标计算

**主要方法**:
- `run_backtest()` - 运行完整回测
- `_open_position()` - 开仓逻辑
- `_close_position()` - 平仓逻辑
- `_calculate_metrics()` - 计算回测指标

**设计原则**:
- 忠实模拟真实交易环境
- 考虑手续费、滑点等实际成本
- 完整的权益曲线记录

**重要参数**:
- `commission_rate`: 手续费率 (默认 0.1%)
- `slippage_rate`: 滑点率 (默认 0.05%)
- `initial_capital`: 初始资金 (默认 $10,000)

### 4. BacktestSystem (回测系统)
**文件**: `backtest/backtest_system.py`

**职责**:
- 协调所有组件
- 提供统一的入口点
- 策略注册和管理
- 参数优化框架

**主要方法**:
- `run_strategy()` - 运行单个策略
- `compare_strategies()` - 对比多个策略
- `optimize_parameters()` - 参数优化
- `list_strategies()` - 列出可用策略

**设计原则**:
- Facade模式，简化复杂交互
- 策略注册表，易于扩展
- 标准化的工作流程

## 组件交互流程

```
用户请求
   |
   v
BacktestSystem (协调层)
   |
   |-- DataManager.fetch_data()  --> 获取历史数据
   |
   |-- Strategy.generate_signal() --> 生成交易信号
   |        |
   |        v
   |-- BacktestEngine.run_backtest() --> 执行回测
   |        |
   |        v
   |-- ReportGenerator.generate_report() --> 生成报告
   |
   v
返回结果 (Dict + Report)
```

## 策略接口标准

所有策略必须继承 `BaseStrategy` 并实现：

```python
class YourStrategy(BaseStrategy):
    def generate_signal(self, price_data: pd.DataFrame, 
                       current_position: Optional[Dict]) -> Optional[TradingSignal]:
        """
        生成交易信号
        
        Args:
            price_data: 历史价格数据
            current_position: 当前持仓（None表示无持仓）
        
        Returns:
            TradingSignal 或 None
        """
        pass
    
    def should_exit(self, price_data: pd.DataFrame, 
                   entry_price: float, side: str) -> bool:
        """
        判断是否应该退出持仓
        
        Args:
            price_data: 历史价格数据
            entry_price: 入场价格
            side: 持仓方向 ('long' 或 'short')
        
        Returns:
            True = 退出, False = 继续持有
        """
        pass
```

**TradingSignal 结构**:
```python
TradingSignal(
    signal_type=SignalType.LONG,  # LONG 或 SHORT
    entry_price=100000.0,          # 入场价格
    stop_loss=98000.0,             # 止损价
    take_profit=104000.0,          # 止盈价
    position_size=0.3,             # 仓位大小 (0-1)
    metadata={'reason': '...'}     # 额外信息
)
```

## 数据流

### 输入
- 交易对: 如 'BTC/USDT'
- 时间周期: 1m, 5m, 15m, 1h, 4h, 1d
- 回测天数: 任意正整数
- 策略参数: 字典格式

### 中间数据
- 价格数据: DataFrame (timestamp, open, high, low, close, volume)
- 交易信号: TradingSignal对象
- 持仓记录: Dict (entry_time, entry_price, size, side, etc.)

### 输出
- 回测结果: Dict (包含所有性能指标)
- 文本报告: 格式化的性能报告
- JSON数据: 机器可读的完整数据

## 扩展性

### 添加新策略
1. 在 `trading_bots/strategies/` 创建新策略文件
2. 继承 `BaseStrategy`
3. 实现 `generate_signal()` 和 `should_exit()`
4. 在 `BacktestSystem.STRATEGIES` 注册

### 添加新指标
1. 在策略类中添加计算方法
2. 在 `_calculate_indicators()` 中集成
3. 在 `generate_signal()` 中使用

### 添加新数据源
1. 在 `DataManager` 中添加新的交易所支持
2. 实现数据格式转换
3. 更新缓存逻辑

## 性能优化

### 已实现
- 数据缓存：避免重复下载
- 矢量化计算：使用pandas/numpy加速
- 增量更新：只下载新数据

### 未来可优化
- 多进程参数优化
- C扩展关键路径
- 数据库替代文件缓存
- 实时数据流支持

## 测试建议

### 单元测试
```python
# 测试数据管理器
def test_data_manager():
    dm = DataManager()
    df = dm.fetch_data('binance', 'BTC/USDT', '1h', 7)
    assert len(df) > 0
    assert 'close' in df.columns

# 测试策略信号
def test_strategy_signal():
    strategy = MomentumStrategy()
    df = load_test_data()
    signal = strategy.generate_signal(df, None)
    assert signal is None or isinstance(signal, TradingSignal)
```

### 集成测试
```python
def test_full_backtest():
    system = BacktestSystem()
    result = system.run_strategy('momentum', days=30, timeframe='1h')
    assert 'results' in result
    assert 'report' in result
    assert result['results']['total_trades'] >= 0
```

### 回归测试
- 固定数据集上的结果一致性
- 性能指标计算准确性
- 边界条件处理

## 命令行接口

### 基础用法
```bash
# 列出策略
python backtest/run_clean.py --list

# 单策略回测
python backtest/run_clean.py --strategy momentum --days 90

# 对比策略
python backtest/run_clean.py --compare momentum mean_reversion --days 90

# 全部对比
python backtest/run_clean.py --all --days 90
```

### 高级用法
```bash
# 指定参数
python backtest/run_clean.py --strategy momentum \
  --days 90 \
  --timeframe 15m \
  --symbol BTC/USDT \
  --capital 20000

# 静默模式
python backtest/run_clean.py --strategy momentum --quiet
```

## Python API

### 基础用法
```python
from backtest.backtest_system import BacktestSystem

system = BacktestSystem()

# 运行回测
result = system.run_strategy('momentum', days=90)
print(result['report'])

# 对比策略
results = system.compare_strategies(['momentum', 'mean_reversion'], days=90)
```

### 参数优化
```python
best = system.optimize_parameters(
    strategy_key='momentum',
    param_grid={
        'atr_multiplier': [1.5, 2.0, 2.5],
        'risk_reward': [1.5, 2.0, 2.5]
    },
    days=90,
    metric='total_return'
)
print(f"Best params: {best['best_params']}")
print(f"Best return: {best['best_score']:.2f}%")
```

### 自定义参数
```python
result = system.run_strategy(
    strategy_key='momentum',
    days=90,
    custom_params={
        'rsi_period': 14,
        'atr_multiplier': 2.5,
        'position_size': 0.35
    }
)
```

## 故障排除

### 常见问题

**Q: UnicodeEncodeError (emoji问题)**
A: 使用 `run_clean.py` 代替 `run.py`

**Q: 数据下载失败**
A: 检查网络，或减少天数/使用缓存

**Q: 回测速度慢**
A: 提高时间周期(15m→1h)，减少天数(90→30)

**Q: 内存不足**
A: 减少数据量，避免 1m + 180天 这种组合

**Q: 策略无交易**
A: 参数可能过严，尝试放宽条件

## 最佳实践

### 回测周期选择
- **短周期测试**: 30天 + 1小时 (快速验证)
- **标准测试**: 90天 + 15分钟 (全面评估)
- **长周期测试**: 180天 + 4小时 (稳定性验证)

### 策略开发
1. 先用短周期快速迭代 (30天 1h)
2. 参数稳定后用标准测试 (90天 15m)
3. 最后用长周期验证稳定性 (180天 4h)

### 参数优化
1. 不要过度优化（避免过拟合）
2. 验证集测试（训练/测试分离）
3. 保留一定参数冗余度

### 生产部署
1. 使用90天以上数据验证
2. 检查最大回撤是否可接受
3. 确保胜率 > 40% 或 盈亏比 > 1.5
4. 夏普比率 > 0.5
5. 实盘前先模拟盘运行

## 下一步优化方向

### 功能增强
- [ ] Walk-forward分析
- [ ] Monte Carlo模拟
- [ ] 多资产组合回测
- [ ] 实时信号推送
- [ ] Web可视化界面

### 性能优化
- [ ] 多进程并行回测
- [ ] GPU加速指标计算
- [ ] 数据库存储替代文件
- [ ] 增量回测支持

### 质量提升
- [ ] 完善单元测试覆盖率
- [ ] 添加集成测试
- [ ] CI/CD自动化
- [ ] 代码质量检查

## 架构优势

✅ **低耦合**: 各组件独立，易于测试和维护
✅ **高内聚**: 每个组件职责单一清晰
✅ **可扩展**: 新增策略只需实现接口
✅ **标准化**: 统一的输入输出格式
✅ **生产就绪**: 考虑了实际交易成本和限制
✅ **易用性**: CLI和API两种使用方式
✅ **可靠性**: 完善的错误处理和缓存机制
