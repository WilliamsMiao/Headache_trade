"""
回测执行脚本
获取历史数据、运行回测、生成报告
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import ccxt
from dotenv import load_dotenv

from trading_bots.guidance import load_guidance
from trading_bots.indicators import (
    calculate_technical_indicators,
    get_market_trend,
    get_support_resistance_levels,
)
from trading_bots.signals import generate_signal_with_guidance

class NumpyEncoder(json.JSONEncoder):
    """防止JSON序列化numpy类型报错"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super(NumpyEncoder, self).default(obj)

# Add project root so trading_bots can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from trading_bots.config import deepseek_client
from scripts.backtest_engine import BacktestEngine
from scripts.backtest_analyzer import BacktestAnalyzer

# 加载环境变量
load_dotenv()

# 数据文件路径
DATA_DIR = os.path.join(os.getcwd(), 'data', 'backtest', 'data')
REPORTS_DIR = os.path.join(os.getcwd(), 'data', 'backtest', 'reports')
CONFIGS_DIR = os.path.join(os.getcwd(), 'data', 'backtest', 'configs')


def extract_json_block(text: str) -> Optional[Dict]:
    """Extract first JSON object from text and return parsed dict."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def apply_ai_adjustments(base_config: Dict, ai_payload: Dict) -> Tuple[Dict, List[Dict]]:
    """Apply AI suggested adjustments onto base config with basic validation."""
    if not ai_payload:
        return base_config, []

    allowed_fields = {
        'initial_balance': {'type': float, 'min': 10, 'max': 10_000_000},
        'leverage': {'type': int, 'min': 1, 'max': 20},
        'fee_rate': {'type': float, 'min': 0.0, 'max': 0.01},
        'slippage': {'type': float, 'min': 0.0, 'max': 0.01},
        'dynamic_leverage': {'type': bool},
        'funding_rate': {'type': float, 'min': -0.01, 'max': 0.01},
        'atr_pct_min': {'type': float, 'min': 0.0, 'max': 0.1},
        'atr_pct_max': {'type': float, 'min': 0.0, 'max': 0.5},
        'funding_abs_max': {'type': float, 'min': 0.0, 'max': 0.01},
        'funding_long_min': {'type': float, 'min': -0.01, 'max': 0.01},
        'funding_long_max': {'type': float, 'min': -0.01, 'max': 0.01},
        'funding_short_min': {'type': float, 'min': -0.01, 'max': 0.01},
        'funding_short_max': {'type': float, 'min': -0.01, 'max': 0.01},
        'rsi_long_min': {'type': float, 'min': 0.0, 'max': 100.0},
        'rsi_long_max': {'type': float, 'min': 0.0, 'max': 100.0},
        'rsi_short_min': {'type': float, 'min': 0.0, 'max': 100.0},
        'rsi_short_max': {'type': float, 'min': 0.0, 'max': 100.0},
        'rsi_extreme_high': {'type': float, 'min': 0.0, 'max': 100.0},
        'rsi_extreme_low': {'type': float, 'min': 0.0, 'max': 100.0},
        'trend_score_entry': {'type': int, 'min': 0, 'max': 100},
        'near_level_threshold': {'type': float, 'min': 0.0, 'max': 0.02},
        'atr_high_threshold': {'type': float, 'min': 0.0, 'max': 0.2},
        'atr_mid_threshold': {'type': float, 'min': 0.0, 'max': 0.2},
        'sl_multiplier_high': {'type': float, 'min': 0.1, 'max': 10.0},
        'tp_multiplier_high': {'type': float, 'min': 0.1, 'max': 15.0},
        'sl_multiplier_mid': {'type': float, 'min': 0.1, 'max': 10.0},
        'tp_multiplier_mid': {'type': float, 'min': 0.1, 'max': 15.0},
        'sl_multiplier_low': {'type': float, 'min': 0.1, 'max': 10.0},
        'tp_multiplier_low': {'type': float, 'min': 0.1, 'max': 15.0},
    }

    updated = dict(base_config)
    applied_changes: List[Dict] = []

    adjustments = ai_payload.get('adjustments') or []
    fallback = ai_payload.get('fallback_config') or {}

    def coerce_value(field: str, value):
        spec = allowed_fields[field]
        expected = spec['type']
        if expected is bool:
            return bool(value)
        if expected is int:
            try:
                value = int(round(float(value)))
            except Exception:
                return None
        elif expected is float:
            try:
                value = float(value)
            except Exception:
                return None
        min_v = spec.get('min')
        max_v = spec.get('max')
        if min_v is not None:
            value = max(min_v, value)
        if max_v is not None:
            value = min(max_v, value)
        return value

    for adj in adjustments:
        field = adj.get('param')
        if field not in allowed_fields:
            continue
        target = adj.get('target')
        coerced = coerce_value(field, target)
        if coerced is None:
            continue
        updated[field] = coerced
        applied_changes.append({
            'param': field,
            'target': coerced,
            'reason': adj.get('reason', ''),
            'bounds': adj.get('bounds')
        })

    # If nothing applied, fall back to provided defaults
    if not applied_changes and fallback:
        for field, value in fallback.items():
            if field not in allowed_fields:
                continue
            coerced = coerce_value(field, value)
            if coerced is None:
                continue
            updated[field] = coerced
            applied_changes.append({
                'param': field,
                'target': coerced,
                'reason': 'fallback_config'
            })

    return updated, applied_changes


def fetch_historical_data(symbol: str = 'BTC/USDT:USDT', timeframe: str = '15m', 
                         days: int = 30, save_path: str = None) -> pd.DataFrame:
    """
    获取历史K线数据
    
    Args:
        symbol: 交易对
        timeframe: 时间周期
        days: 天数
        save_path: 保存路径
        
    Returns:
        DataFrame with OHLCV data
    """
    print(f"\n{'='*60}")
    print(f"📥 开始获取历史数据")
    print(f"{'='*60}")
    print(f"交易对: {symbol}")
    print(f"时间周期: {timeframe}")
    print(f"数据天数: {days}天")
    
    try:
        # 初始化交易所
        exchange = ccxt.okx({
            'options': {'defaultType': 'swap'},
            'apiKey': os.getenv('OKX_API_KEY'),
            'secret': os.getenv('OKX_SECRET'),
            'password': os.getenv('OKX_PASSWORD'),
        })
        
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        since = int(start_time.timestamp() * 1000)
        
        print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("正在获取数据...")
        
        # 获取K线数据（批量获取）
        all_ohlcv = []
        current_since = since
        limit = 300  # 每次获取300根K线
        
        while True:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
            if not ohlcv:
                break
            
            all_ohlcv.extend(ohlcv)
            
            # 更新since到最后一根K线的时间
            last_timestamp = ohlcv[-1][0]
            if last_timestamp >= int(end_time.timestamp() * 1000):
                break
            current_since = last_timestamp + 1
            
            print(f"已获取 {len(all_ohlcv)} 根K线...", end='\r')
        
        print(f"\n✅ 成功获取 {len(all_ohlcv)} 根K线数据")
        
        # 转换为DataFrame
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # 保存数据
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            df.to_json(save_path, orient='records', date_format='iso', indent=2)
            print(f"✅ 数据已保存至: {save_path}")
        
        return df
        
    except Exception as e:
        print(f"❌ 获取数据失败: {str(e)}")
        raise


def load_historical_data(filepath: str) -> pd.DataFrame:
    """加载历史数据"""
    print(f"📂 加载历史数据: {filepath}")
    df = pd.read_json(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"✅ 成功加载 {len(df)} 根K线数据")
    return df

def calculate_backtest_position(signal_data, price_data, current_balance,
                                current_position, performance_stats):
    """回测版智能仓位计算（与生产一致的风险/仓位模型）。"""
    stop_loss = signal_data.get('stop_loss', 0)
    current_price = price_data
    stop_loss_distance_pct = abs(stop_loss - current_price) / current_price if stop_loss > 0 else 0.01

    max_acceptable_loss = current_balance * 0.03
    max_safe_trade_amount = max_acceptable_loss / stop_loss_distance_pct

    contract_size = 0.01
    contract_value_per_unit = current_price * contract_size
    max_safe_contract_size = max_safe_trade_amount / contract_value_per_unit

    win_rate = performance_stats.get('win_rate', 0)
    if win_rate >= 0.5:
        dynamic_leverage = min(8 + int((win_rate - 0.5) * 10), 10)
    elif win_rate >= 0.4:
        dynamic_leverage = 6 + int((win_rate - 0.4) * 10)
    else:
        dynamic_leverage = max(3, int(win_rate * 10)) if win_rate > 0 else 3

    trend_score = signal_data.get('trend_score', 5)
    if trend_score >= 8:
        trend_multiplier = 1.5
    elif trend_score >= 6:
        trend_multiplier = 1.2
    elif trend_score >= 4:
        trend_multiplier = 1.0
    else:
        trend_multiplier = 0.5

    optimal_contract_size = max_safe_contract_size * trend_multiplier

    max_utilization = 0.60
    current_margin = (optimal_contract_size * contract_value_per_unit) / dynamic_leverage
    current_utilization = current_margin / current_balance if current_balance > 0 else 0
    if current_utilization > max_utilization:
        max_margin = current_balance * max_utilization
        optimal_contract_size = (max_margin * dynamic_leverage) / contract_value_per_unit

    optimal_contract_size = max(optimal_contract_size, 0.01)
    optimal_contract_size = round(optimal_contract_size, 2)

    return {
        'contract_size': optimal_contract_size,
        'optimal_leverage': dynamic_leverage,
        'trend_multiplier': trend_multiplier,
        'utilization': current_utilization
    }


def create_soldier_strategy(df_with_indicators: pd.DataFrame, guidance_state: Dict, config: Dict = None):
    """Use production soldier signal (generate_signal_with_guidance) in backtests."""
    signal_log: List[Dict] = []

    def strategy(index, df, position, current_balance, performance_stats):
        if index < 50:
            return None

        window = df_with_indicators.iloc[:index+1].copy()
        latest = window.iloc[-1]
        prev_close = window.iloc[-2]['close'] if len(window) > 1 else latest['close']
        price = float(latest['close'])
        price_change = ((price - prev_close) / prev_close * 100) if prev_close else 0.0

        technical_data = {
            'rsi': float(latest.get('rsi', 0.0) or 0.0),
            'atr': float(latest.get('atr', 0.0) or 0.0),
            'bb_position': float(latest.get('bb_position', 0.5) or 0.5),
        }

        price_data = {
            'price': price,
            'price_change': price_change,
            'timestamp': latest.get('timestamp', latest.name),
            'full_data': window,
            'technical_data': technical_data,
            'trend_analysis': get_market_trend(window),
            'levels_analysis': get_support_resistance_levels(window),
            'funding_rate': float(latest.get('funding_rate', 0.0) or 0.0),
        }

        signal = generate_signal_with_guidance(price_data, guidance=guidance_state, config=config)
        if signal.get('signal') not in ('BUY', 'SELL'):
            return None

        position_result = calculate_backtest_position(
            signal_data=signal,
            price_data=price,
            current_balance=current_balance,
            current_position=position,
            performance_stats=performance_stats
        )

        size = round(position_result['contract_size'], 2)
        action = 'BUY' if signal['signal'] == 'BUY' else 'SELL'
        signal_log.append({
            'ts': str(price_data['timestamp']),
            'price': price,
            'signal': signal.get('signal'),
            'confidence': signal.get('confidence'),
            'reason': signal.get('reason'),
            'guidance_bias': guidance_state.get('bias'),
        })

        return {
            'action': action,
            'size': size,
            'leverage': position_result['optimal_leverage'],
            'stop_loss': signal.get('stop_loss'),
            'take_profit': signal.get('take_profit'),
            'trend_multiplier': position_result['trend_multiplier'],
            'grade': signal.get('confidence'),
        }

    strategy.signal_log = signal_log
    return strategy


def run_backtest(df: pd.DataFrame, config: Dict = None) -> Dict:
    """
    运行回测
    
    Args:
        df: 历史K线数据
        config: 回测配置
        
    Returns:
        回测结果
    """
    if config is None:
        config = {
            'initial_balance': 100,
            'leverage': 6,
            'fee_rate': 0.001,
            'slippage': 0.0001,
            'funding_rate': 0.0001,  # 默认0.01%每8小时
            'guidance_path': 'data/guidance.json',
            'atr_pct_min': 0.005,
            'atr_pct_max': 0.030,
            'funding_abs_max': 0.0003,
            'funding_long_min': -0.0001,
            'funding_long_max': 0.0002,
            'funding_short_min': -0.0002,
            'funding_short_max': 0.0001,
            'rsi_long_min': 45,
            'rsi_long_max': 75,
            'rsi_short_min': 25,
            'rsi_short_max': 55,
            'rsi_extreme_high': 75,
            'rsi_extreme_low': 25,
            'trend_score_entry': 65,
            'near_level_threshold': 0.002,
            'atr_high_threshold': 0.020,
            'atr_mid_threshold': 0.015,
            'sl_multiplier_high': 2.5,
            'tp_multiplier_high': 3.0,
            'sl_multiplier_mid': 2.0,
            'tp_multiplier_mid': 2.5,
            'sl_multiplier_low': 1.8,
            'tp_multiplier_low': 2.2,
        }
    
    # 创建回测引擎
    engine = BacktestEngine(
        initial_balance=config['initial_balance'],
        leverage=config.get('leverage', 6),
        fee_rate=config.get('fee_rate', 0.001),
        slippage=config.get('slippage', 0.0001),
        dynamic_leverage=config.get('dynamic_leverage', False),
        funding_rate=config.get('funding_rate', 0.0001)  # 资金费率
    )

    # 统一使用生产士兵逻辑：预计算指标 + 指挥官指导
    df_with_indicators = calculate_technical_indicators(df.copy())
    guidance_path = config.get('guidance_path', 'data/guidance.json')
    guidance_state = load_guidance(Path(guidance_path))
    guidance_override = config.get('guidance_override')
    if guidance_override:
        guidance_state.update(guidance_override)

    strategy_func = create_soldier_strategy(df_with_indicators, guidance_state, config=config)

    # 运行回测
    results = engine.run(df, strategy_func, verbose=True)
    # 追加信号日志，便于后续分析
    results['signal_log'] = getattr(strategy_func, 'signal_log', [])
    
    return results


def run_ai_feedback(report_text: str, results: Dict, config: Dict, report_file: str, config_name: str) -> Tuple[str, Optional[Dict], List[Dict], Optional[str]]:
    """Send backtest summary to DeepSeek, enforce JSON schema, apply suggestions, and persist new config."""

    if not deepseek_client.api_key:
        return "⚠️ DeepSeek API key not configured; skipped AI反馈", None, [], None

    trades = results.get('trades', [])
    total_trades = len(trades)
    max_drawdown = results.get('max_drawdown', 0)
    total_return = results.get('total_return', 0)

    prompt = f"""
你是量化交易策略调参助手。读取回测摘要后，必须输出**严格的JSON**，不可包含任何额外文字或代码块标记。

【基础数据】
- 配置: {json.dumps(config, ensure_ascii=False)}
- 总收益率: {total_return:.4f}
- 最大回撤: {max_drawdown:.4f}
- 交易次数: {total_trades}

【回测报告】
{report_text}

按如下JSON schema输出（无多余说明）：
{{
  "summary": ["关键发现1", "关键发现2"],
  "adjustments": [
    {{"param": "leverage", "action": "set|increase|decrease", "target": 5, "bounds": [3,8], "reason": "简述原因"}},
    {{"param": "fee_rate", "action": "set", "target": 0.0006, "bounds": [0.0004, 0.001], "reason": ""}}
  ],
  "fallback_config": {{"leverage": 6, "fee_rate": 0.0008}},
  "validation_plan": ["如何验证1", "如何验证2"],
  "confidence": 0.0-1.0
}}
"adjustments" 中仅使用上述字段；数值用阿拉伯数字；确保是可被json.loads解析的合法JSON。
"""

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是严格的量化策略审阅者，只返回合法JSON，不要markdown或自然语言前后缀。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            stream=False,
        )
        content = response.choices[0].message.content.strip()
    except Exception as exc:
        content = f"⚠️ DeepSeek 调用失败: {exc}"
        return content, None, [], None

    parsed = extract_json_block(content)
    updated_config = None
    applied_changes: List[Dict] = []
    new_config_path = None

    if parsed:
        updated_config, applied_changes = apply_ai_adjustments(config, parsed)
        if applied_changes:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_config_name = f"{config_name}_ai_{timestamp}"
            new_config_path = os.path.join(CONFIGS_DIR, f"{new_config_name}.json")
            os.makedirs(CONFIGS_DIR, exist_ok=True)
            with open(new_config_path, 'w', encoding='utf-8') as f:
                json.dump(updated_config, f, indent=2, ensure_ascii=False)

    # Save raw feedback for audit
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    feedback_file = os.path.join(REPORTS_DIR, f"ai_feedback_{config_name}_{timestamp}.md")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(feedback_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return content, parsed, applied_changes, new_config_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='回测执行工具')
    parser.add_argument('--fetch-data', action='store_true', help='获取历史数据')
    parser.add_argument('--days', type=int, default=30, help='数据天数（默认30天）')
    parser.add_argument('--config', type=str, help='配置文件名（如baseline）')
    parser.add_argument('--data-file', type=str, help='指定数据文件路径')
    parser.add_argument('--ai-feedback', action='store_true', help='回测后调用DeepSeek生成调参建议')
    parser.add_argument('--guidance-file', type=str, help='指定指挥官指导文件（默认data/guidance.json）')
    
    args = parser.parse_args()
    
    # 数据文件路径
    data_file = args.data_file or f"{DATA_DIR}/historical_15m_{args.days}d.json"
    
    # 1. 获取或加载历史数据
    if args.fetch_data:
        df = fetch_historical_data(
            symbol='BTC/USDT:USDT',
            timeframe='15m',
            days=args.days,
            save_path=data_file
        )
    else:
        if not os.path.exists(data_file):
            print(f"❌ 数据文件不存在: {data_file}")
            print("💡 请先运行: python scripts/backtest_runner.py --fetch-data --days 30")
            return
        df = load_historical_data(data_file)
    
    # 2. 加载配置
    config = {
        'initial_balance': 100,
        'leverage': 6,
        'fee_rate': 0.001,
        'slippage': 0.0001,
        'funding_rate': 0.0001,
        'guidance_path': 'data/guidance.json',
        'atr_pct_min': 0.005,
        'atr_pct_max': 0.030,
        'funding_abs_max': 0.0003,
        'funding_long_min': -0.0001,
        'funding_long_max': 0.0002,
        'funding_short_min': -0.0002,
        'funding_short_max': 0.0001,
        'rsi_long_min': 45,
        'rsi_long_max': 75,
        'rsi_short_min': 25,
        'rsi_short_max': 55,
        'rsi_extreme_high': 75,
        'rsi_extreme_low': 25,
        'trend_score_entry': 65,
        'near_level_threshold': 0.002,
        'atr_high_threshold': 0.020,
        'atr_mid_threshold': 0.015,
        'sl_multiplier_high': 2.5,
        'tp_multiplier_high': 3.0,
        'sl_multiplier_mid': 2.0,
        'tp_multiplier_mid': 2.5,
        'sl_multiplier_low': 1.8,
        'tp_multiplier_low': 2.2,
    }
    
    if args.config:
        # Check if it's a direct path
        if args.config.endswith('.json') and os.path.exists(args.config):
             config_file = args.config
        else:
             config_file = f"{CONFIGS_DIR}/{args.config}.json"

        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                config.update(user_config)
            print(f"✅ 已加载配置: {config_file}")

    if args.guidance_file:
        config['guidance_path'] = args.guidance_file
    
    # 3. 运行回测
    results = run_backtest(df, config)
    
    # 4. 分析结果
    analyzer = BacktestAnalyzer(results)
    
    # 5. 生成报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Handle config name safely from path or name
    if args.config:
        config_name = os.path.basename(args.config)
        if config_name.endswith('.json'):
            config_name = config_name[:-5]
    else:
        config_name = 'default'

    report_file = f"{REPORTS_DIR}/backtest_report_{config_name}_{timestamp}.md"
    
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_text = analyzer.generate_report(filepath=report_file)
    
    # 打印报告
    print("\n" + report_text)
    
    # 保存结果数据
    results_file = f"{REPORTS_DIR}/backtest_results_{config_name}_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        # 转换datetime为字符串
        results_copy = results.copy()
        for trade in results_copy['trades']:
            if 'entry_time' in trade:
                trade['entry_time'] = str(trade['entry_time'])
            if 'exit_time' in trade:
                trade['exit_time'] = str(trade['exit_time'])
        for point in results_copy['equity_curve']:
            if 'timestamp' in point:
                point['timestamp'] = str(point['timestamp'])
        json.dump(results_copy, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    
    print(f"✅ 结果数据已保存至: {results_file}")
    
    # 创建最新报告的软链接
    latest_report = f"{REPORTS_DIR}/backtest_report_latest.md"
    if os.path.exists(latest_report):
        os.remove(latest_report)
    os.symlink(os.path.basename(report_file), latest_report)
    print(f"✅ 最新报告链接: {latest_report}")

    # 6. DeepSeek AI反馈
    if args.ai_feedback:
        feedback, parsed, applied_changes, new_config_path = run_ai_feedback(report_text, results, config, report_file, config_name)
        print("\n🤖 AI反馈:\n" + feedback)
        if parsed:
            print("\n🔧 解析后的JSON:")
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        if applied_changes:
            print("\n✅ 已应用的参数调整:")
            for change in applied_changes:
                print(f"- {change['param']} -> {change['target']} ({change.get('reason', '')})")
        if new_config_path:
            print(f"\n💾 新配置已保存: {new_config_path}")
        elif parsed and not applied_changes:
            print("\nℹ️ 未找到可用的参数调整，已保留原配置。")

if __name__ == '__main__':
    main()
