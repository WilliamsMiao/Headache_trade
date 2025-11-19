# 配置文件说明

## 文件列表

### 主配置文件
- **config.yaml** - 生产环境主配置文件（默认）
- **config.test.yaml** - 测试环境配置（覆盖主配置的部分设置）
- **config.example.yaml** - 配置示例文件（包含所有可用配置项的说明）

### 环境配置
- **.env.example** - 环境变量示例文件

## 配置文件格式

项目现在使用 **YAML** 格式作为标准配置格式，替代之前的JSON格式。

### YAML优势
- ✅ 更易读、更简洁
- ✅ 支持注释
- ✅ 支持环境变量替换
- ✅ 支持配置继承

## 使用方法

### 1. 基础使用

```python
from headache_trade.utils.config_loader import load_config, get_config

# 加载配置
config = load_config('config/config.yaml')

# 获取配置值（支持点号路径）
symbol = get_config('trading.symbol')
max_risk = get_config('risk_management.max_risk_pct')
```

### 2. 环境变量替换

在YAML配置中可以使用环境变量：

```yaml
exchange:
  api_key: ${EXCHANGE_API_KEY}           # 使用环境变量
  api_secret: ${EXCHANGE_API_SECRET:default}  # 带默认值
```

### 3. 多环境配置

```python
# 加载测试环境配置（自动继承主配置并覆盖）
config = load_config('config/config.yaml', environment='test')
```

### 4. 配置热更新

配置加载器会自动检测文件变化并重新加载：

```python
# 自动检测配置变化（每5秒检查一次）
value = get_config('trading.symbol')
```

## 配置迁移

如果你有旧的JSON配置文件，可以使用迁移工具转换：

```bash
python scripts/migrate_config.py old_config.json -o new_config.yaml --backup
```

## 配置项说明

详见 `config.example.yaml` 文件，包含所有可用配置项及其说明。

主要配置节：
- **exchange**: 交易所配置
- **trading**: 交易参数
- **ai**: AI模型配置
- **risk_management**: 风险管理
- **scheduler**: 策略调度
- **strategies**: 各策略参数
- **indicators**: 技术指标参数
- **logging**: 日志配置
- **performance**: 性能优化
- **notifications**: 通知配置
- **web**: Web界面配置
- **backtest**: 回测配置
- **development**: 开发模式配置

## 兼容性说明

- ✅ 新版本使用 `config_loader.py` 加载YAML配置
- ⚠️ 旧版本的 `config.py` 仍然支持，但建议迁移到新版本
- ✅ 同时支持YAML和JSON格式（推荐YAML）

## 依赖项

```bash
pip install pyyaml
```

如果不安装PyYAML，系统会回退到仅支持JSON格式。
