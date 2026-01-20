# Dashboard模块

这是重构后的Dashboard后端服务模块，采用分层架构设计。

## 目录结构

```
dashboard/
├── __init__.py
├── __main__.py              # 模块入口，允许 python -m dashboard 运行
├── app.py                   # Flask应用入口
├── config.py                # 应用配置和常量
├── models/                  # 数据模型（预留）
├── repositories/            # 数据访问层
│   ├── dashboard_repository.py
│   ├── chart_repository.py
│   └── config_repository.py
├── services/                # 业务逻辑层
│   ├── dashboard_service.py
│   ├── price_service.py
│   ├── config_service.py
│   ├── backtest_service.py
│   └── log_service.py
├── routes/                  # API路由层
│   ├── dashboard_routes.py
│   ├── config_routes.py
│   ├── backtest_routes.py
│   ├── log_routes.py
│   └── auth_routes.py
└── utils/                   # 工具函数
    └── file_lock.py
```

## 架构说明

### 分层架构

1. **Repositories（数据访问层）**: 负责所有数据文件的读写操作
2. **Services（业务逻辑层）**: 包含业务逻辑处理和数据聚合
3. **Routes（API路由层）**: 定义Flask API端点，调用Services
4. **Utils（工具层）**: 提供通用工具函数（如文件锁）

### 设计原则

- **单一职责**: 每个模块只负责一个功能领域
- **依赖注入**: Services接收Repositories作为依赖
- **配置集中化**: 所有路径和常量集中在 `config.py`
- **向后兼容**: 保持所有API端点不变

## 启动方式

### 方式1: 作为模块运行（推荐）
```bash
python -m dashboard
```

### 方式2: 直接运行app.py
```bash
python dashboard/app.py
```

### 方式3: 使用启动脚本
```bash
./start_services.sh
```

## API端点

所有API端点保持不变，确保前端无需修改：

- `/api/dashboard` - 获取仪表板数据
- `/api/models` - 获取模型数据
- `/api/crypto-prices` - 获取加密货币价格
- `/api/positions` - 获取持仓信息
- `/api/trades` - 获取交易历史
- `/api/signals` - 获取交易信号
- `/api/chart-history` - 获取图表历史
- `/api/config/trading` - 交易配置CRUD
- `/api/backtest/run` - 运行回测
- `/api/logs` - 获取日志

完整列表请参考各路由文件。

## 迁移说明

注意：旧的 `trading_dashboard.py` 文件已被移除，现在使用模块化的 `dashboard/` 目录结构。
