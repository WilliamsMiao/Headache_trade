@echo off
echo ============================================================
echo 🚀 AI增强型多策略交易系统 - 快速启动
echo ============================================================
echo.

REM 检查Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python未安装，请先安装Python 3.8+
    pause
    exit /b 1
)

echo ✅ Python已安装
echo.

REM 检查依赖
echo 📦 检查依赖包...
pip show ccxt >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  依赖包未安装
    echo 📦 正在安装依赖包...
    pip install -r requirements.txt
)

echo ✅ 依赖包已安装
echo.

REM 检查配置文件
if not exist "config.json" (
    echo ⚠️  配置文件不存在
    echo 📝 正在创建配置文件...
    copy config_example.json config.json
    echo.
    echo ⚠️ 请编辑 config.json 文件，填入以下信息：
    echo    1. Binance API密钥 (api_key, api_secret)
    echo    2. DeepSeek API密钥 (ai.deepseek_api_key) [可选]
    echo    3. 交易对设置 (symbol)
    echo.
    echo 按任意键编辑配置文件...
    pause >nul
    notepad config.json
    echo.
    echo 配置完成后按任意键继续...
    pause >nul
)

echo ✅ 配置文件已存在
echo.

REM 运行测试
echo 🧪 运行系统测试...
cd trading_bots
python test_ai_integration.py
echo.

REM 询问是否启动
echo ============================================================
echo 准备启动交易系统
echo ============================================================
echo.
echo ⚠️  警告：
echo    - 确保已正确配置API密钥
echo    - 建议先用小资金测试
echo    - 随时可以按 Ctrl+C 停止
echo.
set /p start="是否启动交易系统？(y/n): "

if /i "%start%"=="y" (
    echo.
    echo 🚀 启动交易系统...
    echo ============================================================
    python multi_strategy_bot.py
) else (
    echo.
    echo ⏸️  已取消启动
    echo.
    echo 💡 提示：
    echo    - 查看文档: README_FULL.md
    echo    - AI指南: AI_INTEGRATION_GUIDE.md
    echo    - 策略指南: MULTI_STRATEGY_GUIDE.md
    echo.
)

cd ..
pause
