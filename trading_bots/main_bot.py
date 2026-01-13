"""DeepSeek trend-following trading bot entrypoint.

This file previously had duplicated/corrupted DeepSeek helpers at the top. The
header is rebuilt to rely on the shared signals module and centralized config.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional
import fcntl
import pandas as pd

from trading_bots.config import (
    TRADE_CONFIG,
    TRADING_FEE_RATE,
    deepseek_client,
    exchange,
    performance_tracker,
    signal_history,
)
from trading_bots.execution import (
    cancel_tp_sl_orders,
    get_current_position,
    set_tp_sl_orders,
    update_tp_sl_orders,
)
from trading_bots.indicators import (
    calculate_technical_indicators,
    calculate_volatility,
    get_market_trend,
    get_support_resistance_levels,
)
from trading_bots.signals import (
    calculate_dynamic_stop_loss,
    check_sentiment_api_health,
    generate_signal_with_guidance,
    generate_trend_king_signal,
    get_sentiment_indicators,
    should_execute_trade,
)

# Constants for file paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DATA_FILE = os.path.join(PROJECT_ROOT, 'data/dashboard_data.json')


class PriceMonitor:
    """Price monitor tracking trailing stops and position metadata."""

    def __init__(self):
        self.current_position_info = None

    def update_position_info(self, signal_data, price_data, position_size):
        entry_price = price_data.get("price")
        position_side = signal_data.get("signal", "HOLD").lower()
        self.current_position_info = {
            "position_side": position_side,
            "position_size": position_size,
            "entry_price": entry_price,
            "stop_loss": signal_data.get("stop_loss"),
            "take_profit": signal_data.get("take_profit"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trailing_stop_activated": False,
            "highest_profit": entry_price if position_side == "long" else 0,
            "lowest_profit": entry_price if position_side == "short" else 0,
            "peak_profit": 0,
            "trailing_stop_price": None,
        }

    def clear_position_info(self):
        self.current_position_info = None

    def initialize_existing_position(self, current_position, price_data):
        entry_price = current_position.get("entry_price", price_data.get("price"))
        side = current_position.get("side")
        self.current_position_info = {
            "position_side": side,
            "position_size": current_position.get("size", 0),
            "entry_price": entry_price,
            "stop_loss": current_position.get("stop_loss", None),
            "take_profit": current_position.get("take_profit", None),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trailing_stop_activated": False,
            "highest_profit": entry_price if side == "long" else 0,
            "lowest_profit": entry_price if side == "short" else 0,
            "peak_profit": 0,
            "trailing_stop_price": None,
        }

    def update_with_price(self, current_price: float, trailing_window: float = 0.005):
        """Evolve trailing-stop stats using the latest trade price.

        trailing_window is a percentage as a decimal (0.005 = 0.5%).
        """

        if not self.current_position_info:
            return

        info = self.current_position_info
        entry = info.get("entry_price") or current_price
        side = info.get("position_side")

        if side == "long":
            info["highest_profit"] = max(info.get("highest_profit", entry), current_price)
            profit_pct = (current_price - entry) / entry * 100 if entry else 0
            if profit_pct > info.get("peak_profit", 0):
                info["peak_profit"] = profit_pct
            if profit_pct >= trailing_window * 100:
                info["trailing_stop_activated"] = True
                info["trailing_stop_price"] = info["highest_profit"] * (1 - trailing_window)
        elif side == "short":
            info["lowest_profit"] = min(info.get("lowest_profit", entry), current_price)
            profit_pct = (entry - current_price) / entry * 100 if entry else 0
            if profit_pct > info.get("peak_profit", 0):
                info["peak_profit"] = profit_pct
            if profit_pct >= trailing_window * 100:
                info["trailing_stop_activated"] = True
                info["trailing_stop_price"] = info["lowest_profit"] * (1 + trailing_window)

    def stop_monitoring(self):
        self.clear_position_info()


def initialize_price_monitor() -> PriceMonitor:
    return PriceMonitor()


def update_trade_result(is_win: bool, pnl: float = 0) -> None:
    """Update performance tracker with a new trade result."""

    performance_tracker["trade_count"] += 1
    performance_tracker["win_count"] += 1 if is_win else 0
    performance_tracker["loss_count"] += 0 if is_win else 1
    performance_tracker["daily_pnl"] = performance_tracker.get("daily_pnl", 0) + pnl

    # Keep a short trade history for dashboard use
    performance_tracker.setdefault("trade_results", []).append(
        {
            "result": "win" if is_win else "loss",
            "pnl": pnl,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    performance_tracker["trade_results"] = performance_tracker["trade_results"][-50:]

    win_rate = performance_tracker["win_count"] / performance_tracker["trade_count"]
    performance_tracker["win_rate"] = round(win_rate, 4)


def check_trading_conditions() -> bool:
    """Block trading if daily limits or pause flags are hit."""

    today = datetime.now().date()
    last_date = performance_tracker.get("last_trade_date")
    if last_date and last_date != today:
        performance_tracker["daily_pnl"] = 0
        performance_tracker["daily_trade_count"] = 0
        performance_tracker["is_trading_paused"] = False
        performance_tracker["last_trade_date"] = today

    if performance_tracker.get("is_trading_paused"):
        print("⏸️ 交易已暂停，等待手动恢复")
        return False

    daily_threshold = TRADE_CONFIG.get("performance_tracking", {}).get("daily_pnl_threshold", -0.05)
    if performance_tracker.get("daily_pnl", 0) <= daily_threshold:
        performance_tracker["is_trading_paused"] = True
        print(f"🛑 达到当日最大回撤限制({daily_threshold:.2%})，暂停交易")
        return False

    return True


def get_dynamic_leverage(win_rate: Optional[float]) -> int:
    risk_cfg = TRADE_CONFIG.get("risk_management", {})
    min_leverage = risk_cfg.get("min_leverage", 1)
    max_leverage = risk_cfg.get("max_leverage", TRADE_CONFIG.get("leverage", 6))
    base_leverage = TRADE_CONFIG.get("leverage", 6)

    if win_rate is None:
        return base_leverage

    if win_rate >= 0.60:
        return min(max_leverage, max(base_leverage + 2, min_leverage))
    if win_rate >= 0.40:
        return min(max_leverage, max(base_leverage, min_leverage))
    return max(min_leverage, base_leverage - 2)


def get_dynamic_base_risk(win_rate: Optional[float]) -> float:
    risk_cfg = TRADE_CONFIG.get("risk_management", {})
    levels = risk_cfg.get("risk_levels", {})

    high_cfg = levels.get("high_win_rate", {"threshold": 0.6, "min_risk": 0.05, "max_risk": 0.10})
    med_cfg = levels.get("medium_win_rate", {"threshold": 0.4, "min_risk": 0.03, "max_risk": 0.05})
    low_cfg = levels.get("low_win_rate", {"threshold": 0.0, "min_risk": 0.01, "max_risk": 0.02})

    if win_rate is None:
        return risk_cfg.get("base_risk_per_trade", 0.02)

    if win_rate >= high_cfg.get("threshold", 0.6):
        return high_cfg.get("min_risk", 0.05)
    if win_rate >= med_cfg.get("threshold", 0.4):
        return med_cfg.get("min_risk", 0.03)
    return low_cfg.get("min_risk", 0.01)


def get_btc_ohlcv_enhanced():
    """Fetch OHLCV data and enrich with indicators and trend context."""

    try:
        ohlcv = exchange.fetch_ohlcv(
            TRADE_CONFIG["symbol"], TRADE_CONFIG["timeframe"], limit=TRADE_CONFIG["data_points"]
        )
        if not ohlcv:
            print("⚠️ 未获取到有效K线数据")
            return None

        funding_rate = 0
        try:
            funding_info = exchange.fetch_funding_rate(TRADE_CONFIG["symbol"])
            funding_rate = funding_info.get("fundingRate", 0)
        except Exception as fetch_err:
            print(f"⚠️ 获取资金费率失败，使用0作为默认值: {fetch_err}")

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        df = calculate_technical_indicators(df)
        current_data = df.iloc[-1]
        previous_data = df.iloc[-2]

        trend_analysis = get_market_trend(df)
        levels_analysis = get_support_resistance_levels(df)

        return {
            "price": current_data["close"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "high": current_data["high"],
            "low": current_data["low"],
            "volume": current_data["volume"],
            "timeframe": TRADE_CONFIG["timeframe"],
            "price_change": ((current_data["close"] - previous_data["close"]) / previous_data["close"]) * 100,
            "kline_data": df[["timestamp", "open", "high", "low", "close", "volume"]].tail(10).to_dict(
                "records"
            ),
            "technical_data": {
                "sma_5": current_data.get("sma_5", 0),
                "sma_20": current_data.get("sma_20", 0),
                "sma_50": current_data.get("sma_50", 0),
                "rsi": current_data.get("rsi", 0),
                "macd": current_data.get("macd", 0),
                "macd_signal": current_data.get("macd_signal", 0),
                "macd_histogram": current_data.get("macd_histogram", 0),
                "bb_upper": current_data.get("bb_upper", 0),
                "bb_lower": current_data.get("bb_lower", 0),
                "bb_position": current_data.get("bb_position", 0),
                "volume_ratio": current_data.get("volume_ratio", 0),
                "atr": current_data.get("atr", 0),
            },
            "trend_analysis": trend_analysis,
            "levels_analysis": levels_analysis,
            "funding_rate": funding_rate,
            "full_data": df,
        }
    except Exception as e:
        print(f"获取增强K线数据失败: {e}")
        traceback.print_exc()
        return None


# ----------------------
# Position sizing helpers
# ----------------------

def _fetch_account_balance_usdt() -> tuple[float, float]:
    """Fetch available/total USDT balances with safe fallbacks."""

    try:
        balance = exchange.fetch_balance()
        usdt = balance.get("USDT", {})
        total = float(usdt.get("total", 0) or 0)
        free = float(usdt.get("free", 0) or 0)
        if total == 0 and free == 0:
            # Some exchanges nest under 'info'
            total = float(balance.get("total", {}).get("USDT", 0) or 0)
            free = float(balance.get("free", {}).get("USDT", 0) or 0)
        if total == 0:
            total = free
        if free == 0:
            free = total
        return free, total
    except Exception as exc:
        print(f"⚠️ 获取账户余额失败，使用1000 USDT默认值: {exc}")
        return 1000.0, 1000.0


def _compute_contracts(price: float, stop_loss_price: float, risk_pct: float) -> tuple[float, float]:
    """Compute contract size and notional from price/stop distance and risk fraction."""

    price = max(price, 1e-6)
    stop_loss_pct = abs(price - stop_loss_price) / price if stop_loss_price else 0.01
    stop_loss_pct = max(stop_loss_pct, 0.001)

    free_usdt, total_usdt = _fetch_account_balance_usdt()
    target_util = TRADE_CONFIG.get("risk_management", {}).get("target_capital_utilization", 0.5)
    max_util = TRADE_CONFIG.get("risk_management", {}).get("max_capital_utilization", 0.6)

    # Risk in dollars and cap by utilization
    risk_usdt = total_usdt * risk_pct
    max_notional = total_usdt * max_util * TRADE_CONFIG.get("leverage", 6)
    notional = risk_usdt / stop_loss_pct
    notional = max(0, min(notional, max_notional))

    contract_value = TRADE_CONFIG.get("contract_size", 0.01) * price
    contracts = notional / contract_value if contract_value else 0
    contracts = max(contracts, TRADE_CONFIG.get("min_amount", 0.01))

    # Soft-cap by target utilization if free balance is low
    current_util = (total_usdt - free_usdt) / total_usdt if total_usdt > 0 else 0
    if current_util > target_util:
        contracts *= 0.8

    return contracts, notional


def calculate_trend_based_position(signal_data, price_data, current_position=None):
    """Size position using trend score/confidence and dynamic risk/leverage."""

    price = price_data.get("price")
    stop_loss_price = signal_data.get("stop_loss") or price * 0.99

    win_rate = performance_tracker.get("win_rate", None)
    base_risk = get_dynamic_base_risk(win_rate)

    trend_score = signal_data.get("trend_score", 0)
    confidence = signal_data.get("confidence", "MEDIUM").upper()

    risk_multiplier = 1.0
    if trend_score >= 8:
        risk_multiplier += 0.2
    elif trend_score <= 5:
        risk_multiplier -= 0.2

    if confidence == "HIGH":
        risk_multiplier += 0.1
    elif confidence == "LOW":
        risk_multiplier -= 0.1

    risk_multiplier = max(0.5, min(1.5, risk_multiplier))
    risk_pct = max(0.001, base_risk * risk_multiplier)

    contracts, notional = _compute_contracts(price, stop_loss_price, risk_pct)
    optimal_leverage = get_dynamic_leverage(win_rate)

    return {
        "contract_size": contracts,
        "notional": notional,
        "optimal_leverage": optimal_leverage,
        "risk_pct": risk_pct,
    }


def calculate_intelligent_position(signal_data, price_data, current_position=None):
    """Backward-compatible position sizing without trend fields."""

    price = price_data.get("price")
    stop_loss_price = signal_data.get("stop_loss") or price * 0.99

    win_rate = performance_tracker.get("win_rate", None)
    risk_pct = get_dynamic_base_risk(win_rate)

    contracts, notional = _compute_contracts(price, stop_loss_price, risk_pct)
    optimal_leverage = get_dynamic_leverage(win_rate)

    return {
        "contract_size": contracts,
        "notional": notional,
        "optimal_leverage": optimal_leverage,
        "risk_pct": risk_pct,
    }


# Runtime state containers
price_monitor: Optional[PriceMonitor] = None
trade_history: list = []
trade_operations: list = []
def execute_intelligent_trade(signal_data, price_data):
    """修复版智能交易执行 - 集成价格监控和趋势为王策略"""
    global performance_tracker, price_monitor
    
    if not check_trading_conditions():
        return
        
    print("\n" + "="*60)
    print("🔥 开始执行交易流程...")
    print(f"📊 信号: {signal_data['signal']} | 信心: {signal_data['confidence']}")
    
    # 显示趋势强度与布林带结构关系
    trend_score = signal_data.get('trend_score', 0)
    bb_position = price_data['technical_data'].get('bb_position', 0.5)
    primary_trend = signal_data.get('primary_trend', '')
    
    # 🔧 修复：根据趋势强度显示准确的趋势描述，避免误导
    if trend_score >= 7:
        trend_desc = "强趋势"
    elif trend_score >= 4:
        trend_desc = "中等趋势"
    else:
        trend_desc = "弱趋势"
    
    # 显示趋势方向和强度
    trend_direction = primary_trend.replace("强势", "").replace("震荡", "震荡")  # 移除"强势"字样
    print(f"🎯 趋势: {trend_direction} ({trend_desc}, 强度: {trend_score}/10)")
    print(f"📊 布林带位置: {bb_position:.3f}")
    
    # 趋势与布林带结构关系评估
    if bb_position < 0.1:
        if primary_trend == "强势上涨":
            structure_relation = "🚀 上涨趋势+布林带下轨 → 超卖反弹机会"
        elif primary_trend == "强势下跌":
            structure_relation = "📉 下跌趋势+布林带下轨 → 趋势加速确认"
        else:
            structure_relation = "⚠️ 震荡趋势+布林带下轨 → 潜在反转信号"
    
    elif bb_position > 0.9:
        if primary_trend == "强势上涨":
            structure_relation = "📈 上涨趋势+布林带上轨 → 趋势加速确认"
        elif primary_trend == "强势下跌":
            structure_relation = "🚀 下跌趋势+布林带上轨 → 超买回落机会"
        else:
            structure_relation = "⚠️ 震荡趋势+布林带上轨 → 潜在反转信号"
    
    elif bb_position < 0.2:
        structure_relation = "📊 接近布林带下轨 → 弱势结构信号"
    elif bb_position > 0.8:
        structure_relation = "📊 接近布林带上轨 → 强势结构信号"
    else:
        structure_relation = "📈 布林带中部 → 正常结构条件"
    
    print(f"🔄 趋势-结构关系: {structure_relation}")
    print(f"💰 当前价格: ${price_data['price']:,.2f}")
    print("="*60)
    
    try:
        current_position = get_current_position()
        print(f"✅ 当前持仓: {current_position}")
        
        # 交易执行条件检查
        if not should_execute_trade(signal_data, price_data, current_position):
            print("⏸️ 交易条件不满足，跳过执行")
            return
        
        # 趋势强度提示
        trend_score = signal_data.get('trend_score', 0)
        if trend_score >= 7 and signal_data['signal'] != 'HOLD':
            print(f"🚀 强趋势确认({trend_score}/10)，积极执行{signal_data['signal']}信号")
        elif trend_score >= 5 and signal_data['signal'] != 'HOLD':
            print(f"📈 中等趋势({trend_score}/10)，正常执行{signal_data['signal']}信号")
        elif trend_score < 5 and signal_data['signal'] != 'HOLD':
            print(f"⚠️ 弱趋势({trend_score}/10)，谨慎执行{signal_data['signal']}信号")
            
        # 根据是否有趋势强度信息选择仓位计算函数
        if 'trend_score' in signal_data:
            # 使用趋势为王版本的仓位计算
            position_result = calculate_trend_based_position(signal_data, price_data, current_position)
        else:
            # 使用原有仓位计算（向后兼容）
            position_result = calculate_intelligent_position(signal_data, price_data, current_position)
        
        # 提取仓位和最优杠杆
        position_size = position_result['contract_size']
        optimal_leverage = position_result['optimal_leverage']
        
        # 获取当前杠杆设置
        current_leverage = TRADE_CONFIG.get('leverage', 6)
        if current_position and current_position.get('leverage'):
            current_leverage = current_position['leverage']
        
        # 如果最优杠杆与当前杠杆不一致，更新杠杆
        if optimal_leverage != current_leverage:
            try:
                exchange.set_leverage(optimal_leverage, TRADE_CONFIG['symbol'])
                TRADE_CONFIG['leverage'] = optimal_leverage
                print(f"🔧 更新杠杆: {current_leverage}x → {optimal_leverage}x")
            except Exception as e:
                print(f"⚠️ 更新杠杆失败: {e}，继续使用当前杠杆 {current_leverage}x")
                optimal_leverage = current_leverage
        
        print(f"\n📋 交易决策:")
        print(f"   信号: {signal_data['signal']}")
        if 'primary_trend' in signal_data:
            trend_score = signal_data.get('trend_score', 0)
            # 🔧 修复：根据趋势强度显示准确的趋势描述
            if trend_score >= 7:
                trend_desc = "强趋势"
            elif trend_score >= 4:
                trend_desc = "中等趋势"
            else:
                trend_desc = "弱趋势"
            trend_direction = signal_data['primary_trend'].replace("强势", "").replace("震荡", "震荡")
            print(f"   趋势: {trend_direction} ({trend_desc}, 强度{trend_score}/10)")
        print(f"   信心: {signal_data['confidence']}")
        print(f"   仓位: {position_size:.2f} 张")
        print(f"   杠杆: {optimal_leverage}x")
        print(f"   理由: {signal_data['reason']}")
        print(f"   止损: {signal_data['stop_loss']:.2f}")
        print(f"   止盈: {signal_data['take_profit']:.2f}")
        
        # 初始化价格监控（如果尚未初始化）
        if price_monitor is None:
            price_monitor = initialize_price_monitor()
        
        # 执行交易逻辑
        if signal_data['signal'] in ['BUY', 'SELL']:
            # 更新价格监控的持仓信息
            price_monitor.update_position_info(signal_data, price_data, position_size)
            
            if TRADE_CONFIG['test_mode']:
                print("🧪 测试模式 - 仅模拟交易")
            else:
                if signal_data['signal'] == 'BUY':
                    execute_buy_logic(current_position, position_size, signal_data, optimal_leverage)
                else:  # SELL
                    execute_sell_logic(current_position, position_size, signal_data, optimal_leverage)
                    
        elif signal_data['signal'] == 'HOLD':
            print("⏸️ 建议观望，不执行交易")
            # 如果是HOLD信号但需要平仓，检查价格监控
            if current_position and should_close_existing_position(signal_data, price_data, current_position):
                close_existing_position(current_position)
                price_monitor.clear_position_info()
            return
            
        print("✅ 交易执行完成")
        
        # 🔧 新增：更新交易时间和计数（交易频率限制）
        if signal_data['signal'] in ['BUY', 'SELL']:
            now = datetime.now()
            performance_tracker['last_trade_time'] = now
            performance_tracker['daily_trade_count'] = performance_tracker.get('daily_trade_count', 0) + 1
            print(f"📊 交易频率记录：今日已交易{performance_tracker['daily_trade_count']}笔")
        
        time.sleep(2)
        
        # 更新持仓信息
        updated_position = get_current_position()
        print(f"📊 更新后持仓: {updated_position}")
        
        # 如果没有持仓了，清空监控
        if not updated_position or updated_position['size'] == 0:
            price_monitor.clear_position_info()
        
    except Exception as e:
        print(f"❌ 交易执行失败: {e}")
        traceback.print_exc()

def execute_buy_logic(current_position, position_size, signal_data, leverage=None):
    """执行买入逻辑 - 修复版：智能加仓/减仓
    
    Args:
        current_position: 当前持仓
        position_size: 目标仓位大小
        signal_data: 信号数据
        leverage: 最优杠杆（已在之前设置，这里仅用于记录）
    """
    global trade_operations
    
    if current_position and current_position['side'] == 'short':
        # 平空开多
        if current_position['size'] > 0:
            print(f"🔄 平空仓 {current_position['size']:.2f} 张并开多仓 {position_size:.2f} 张...")
            exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                'buy',
                current_position['size'],
                params={'reduceOnly': True}
            )
            # 记录操作
            trade_operations.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'action': '平空开多',
                'side': 'buy',
                'amount': current_position['size'],
                'reason': f"信号反转：从空转多 | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {signal_data.get('trend_score', 0)}/10)",
                'confidence': signal_data.get('confidence', 'N/A'),
                'trend_score': signal_data.get('trend_score', 0)
            })
            time.sleep(1)
        exchange.create_market_order(
            TRADE_CONFIG['symbol'],
            'buy',
            position_size
        )
        # 记录开多操作
        trade_operations.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': '开多仓',
            'side': 'buy',
            'amount': position_size,
            'reason': signal_data.get('reason', 'BUY信号'),
            'confidence': signal_data.get('confidence', 'N/A'),
            'trend_score': signal_data.get('trend_score', 0)
        })
    elif current_position and current_position['side'] == 'long':
        # 同方向调整
        size_diff = position_size - current_position['size']
        trend_score = signal_data.get('trend_score', 0)
        confidence = signal_data.get('confidence', 'MEDIUM')
        
        # 智能加仓逻辑：即使仓位差异很小，如果趋势强度>=8且信心HIGH，允许最小单位加仓
        if abs(size_diff) < 0.01 and size_diff > 0 and trend_score >= 8 and confidence == 'HIGH':
            # 强趋势高信心，允许最小单位加仓（仅在应该加仓时执行）
            min_contract = TRADE_CONFIG.get('min_amount', 0.01)
            print(f"🔥 强趋势({trend_score}/10)高信心({confidence})，执行最小单位加仓 {min_contract:.2f} 张")
            exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                'buy',
                min_contract
            )
            # 记录操作
            trade_operations.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'action': '强趋势加仓',
                'side': 'buy',
                'amount': min_contract,
                'reason': f"强趋势({trend_score}/10)高信心({confidence})，执行最小单位加仓 | {signal_data.get('reason', '')[:100]}",
                'confidence': confidence,
                'trend_score': trend_score
            })
        elif abs(size_diff) >= 0.01:
            if size_diff > 0:
                print(f"📈 多仓加仓 {size_diff:.2f} 张")
                exchange.create_market_order(
                    TRADE_CONFIG['symbol'],
                    'buy',
                    size_diff
                )
                # 记录操作
                trade_operations.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'action': '多仓加仓',
                    'side': 'buy',
                    'amount': size_diff,
                    'reason': f"仓位调整：从{current_position['size']:.2f}增加到{position_size:.2f} | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {trend_score}/10)",
                    'confidence': confidence,
                    'trend_score': trend_score
                })
            else:
                print(f"📉 多仓减仓 {abs(size_diff):.2f} 张")
                exchange.create_market_order(
                    TRADE_CONFIG['symbol'],
                    'sell',
                    abs(size_diff),
                    params={'reduceOnly': True}
                )
                # 记录操作
                trade_operations.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'action': '多仓减仓',
                    'side': 'sell',
                    'amount': abs(size_diff),
                    'reason': f"仓位调整：从{current_position['size']:.2f}减少到{position_size:.2f} | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {trend_score}/10)",
                    'confidence': confidence,
                    'trend_score': trend_score
                })
        else:
            print("✅ 多仓仓位合适，保持现状（已更新止损止盈）")
            # 即使不调整仓位，也记录这个决策
            trade_operations.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'action': '保持仓位',
                'side': 'long',
                'amount': current_position['size'],
                'reason': f"仓位已合适({current_position['size']:.2f}张)，保持现状并更新止损止盈 | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {trend_score}/10)",
                'confidence': confidence,
                'trend_score': trend_score
            })
    else:
        # 开新多仓
        print(f"📈 开多仓 {position_size:.2f} 张...")
        exchange.create_market_order(
            TRADE_CONFIG['symbol'],
            'buy',
            position_size
        )
        # 记录操作
        trade_operations.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': '开多仓',
            'side': 'buy',
            'amount': position_size,
            'reason': signal_data.get('reason', 'BUY信号'),
            'confidence': signal_data.get('confidence', 'N/A'),
            'trend_score': signal_data.get('trend_score', 0)
        })
    
    # 限制操作记录数量
    if len(trade_operations) > 100:
        trade_operations = trade_operations[-100:]

def execute_sell_logic(current_position, position_size, signal_data, leverage=None):
    """执行卖出逻辑 - 修复版：智能加仓/减仓
    
    Args:
        current_position: 当前持仓
        position_size: 目标仓位大小
        signal_data: 信号数据
        leverage: 最优杠杆（已在之前设置，这里仅用于记录）
    """
    global trade_operations
    
    if current_position and current_position['side'] == 'long':
        # 平多开空
        if current_position['size'] > 0:
            print(f"🔄 平多仓 {current_position['size']:.2f} 张并开空仓 {position_size:.2f} 张...")
            exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                'sell',
                current_position['size'],
                params={'reduceOnly': True}
            )
            # 记录操作
            trade_operations.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'action': '平多开空',
                'side': 'sell',
                'amount': current_position['size'],
                'reason': f"信号反转：从多转空 | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {signal_data.get('trend_score', 0)}/10)",
                'confidence': signal_data.get('confidence', 'N/A'),
                'trend_score': signal_data.get('trend_score', 0)
            })
            time.sleep(1)
        exchange.create_market_order(
            TRADE_CONFIG['symbol'],
            'sell',
            position_size
        )
        # 记录开空操作
        trade_operations.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': '开空仓',
            'side': 'sell',
            'amount': position_size,
            'reason': signal_data.get('reason', 'SELL信号'),
            'confidence': signal_data.get('confidence', 'N/A'),
            'trend_score': signal_data.get('trend_score', 0)
        })
    elif current_position and current_position['side'] == 'short':
        # 同方向调整
        size_diff = position_size - current_position['size']
        trend_score = signal_data.get('trend_score', 0)
        confidence = signal_data.get('confidence', 'MEDIUM')
        
        # 智能加仓逻辑：即使仓位差异很小，如果趋势强度>=8且信心HIGH，允许最小单位加仓
        if abs(size_diff) < 0.01 and size_diff > 0 and trend_score >= 8 and confidence == 'HIGH':
            # 强趋势高信心，允许最小单位加仓（仅在应该加仓时执行）
            min_contract = TRADE_CONFIG.get('min_amount', 0.01)
            print(f"🔥 强趋势({trend_score}/10)高信心({confidence})，执行最小单位加仓 {min_contract:.2f} 张")
            exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                'sell',
                min_contract
            )
            # 记录操作
            trade_operations.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'action': '强趋势加仓',
                'side': 'sell',
                'amount': min_contract,
                'reason': f"强趋势({trend_score}/10)高信心({confidence})，执行最小单位加仓 | {signal_data.get('reason', '')[:100]}",
                'confidence': confidence,
                'trend_score': trend_score
            })
        elif abs(size_diff) >= 0.01:
            if size_diff > 0:
                print(f"📉 空仓加仓 {size_diff:.2f} 张")
                exchange.create_market_order(
                    TRADE_CONFIG['symbol'],
                    'sell',
                    size_diff
                )
                # 记录操作
                trade_operations.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'action': '空仓加仓',
                    'side': 'sell',
                    'amount': size_diff,
                    'reason': f"仓位调整：从{current_position['size']:.2f}增加到{position_size:.2f} | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {trend_score}/10)",
                    'confidence': confidence,
                    'trend_score': trend_score
                })
            else:
                print(f"📈 空仓减仓 {abs(size_diff):.2f} 张")
                exchange.create_market_order(
                    TRADE_CONFIG['symbol'],
                    'buy',
                    abs(size_diff),
                    params={'reduceOnly': True}
                )
                # 记录操作
                trade_operations.append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'action': '空仓减仓',
                    'side': 'buy',
                    'amount': abs(size_diff),
                    'reason': f"仓位调整：从{current_position['size']:.2f}减少到{position_size:.2f} | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {trend_score}/10)",
                    'confidence': confidence,
                    'trend_score': trend_score
                })
        else:
            print("✅ 空仓仓位合适，保持现状（已更新止损止盈）")
            # 即使不调整仓位，也记录这个决策
            trade_operations.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'action': '保持仓位',
                'side': 'short',
                'amount': current_position['size'],
                'reason': f"仓位已合适({current_position['size']:.2f}张)，保持现状并更新止损止盈 | 趋势: {signal_data.get('primary_trend', 'N/A')} (强度: {trend_score}/10)",
                'confidence': confidence,
                'trend_score': trend_score
            })
    else:
        # 开新空仓
        print(f"📉 开空仓 {position_size:.2f} 张...")
        exchange.create_market_order(
            TRADE_CONFIG['symbol'],
            'sell',
            position_size
        )
        # 记录操作
        trade_operations.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': '开空仓',
            'side': 'sell',
            'amount': position_size,
            'reason': signal_data.get('reason', 'SELL信号'),
            'confidence': signal_data.get('confidence', 'N/A'),
            'trend_score': signal_data.get('trend_score', 0)
        })
    
    # 限制操作记录数量
    if len(trade_operations) > 100:
        trade_operations = trade_operations[-100:]

def should_close_existing_position(signal_data, price_data, current_position):
    """检查是否应该平掉现有持仓"""
    # 基于新信号判断是否与现有持仓冲突
    if current_position['side'] == 'long' and signal_data.get('trend_bias') == 'bearish':
        return True
    elif current_position['side'] == 'short' and signal_data.get('trend_bias') == 'bullish':
        return True
        
    # 基于技术指标判断
    tech = price_data['technical_data']
    rsi = tech.get('rsi', 50)
    
    if current_position['side'] == 'long' and rsi > 80:
        return True
    elif current_position['side'] == 'short' and rsi < 20:
        return True
        
    return False

def close_existing_position(current_position):
    """平仓并记录交易结果"""
    try:
        # 🔧 修复：平仓前先清理所有策略订单，避免订单残留
        try:
            print("🔄 平仓前强制取消该交易对的所有止盈止损订单...")
            cancel_tp_sl_orders(TRADE_CONFIG['symbol'], None)  # None表示取消所有
            time.sleep(0.3)  # 短暂等待
        except Exception as e:
            print(f"⚠️ 取消订单时出错（继续平仓）: {e}")
        
        # 如果价格监控器存在，也调用清理函数（双重保险）
        global price_monitor
        if price_monitor:
            try:
                price_monitor.clear_position_info()
            except Exception as e:
                print(f"⚠️ 清理价格监控信息时出错: {e}")
        
        # 🔧 修复：计算实际盈亏时扣除手续费（开仓+平仓）
        # 获取持仓名义价值用于计算手续费
        position_size = current_position.get('size', 0)
        entry_price = current_position.get('entry_price', 0)
        current_price = 0
        
        # 获取当前价格
        try:
            ticker = exchange.fetch_ticker(TRADE_CONFIG['symbol'])
            current_price = ticker['last']
        except:
            # 如果获取失败，使用未实现盈亏估算
            unrealized_pnl = current_position.get('unrealized_pnl', 0)
            if current_position['side'] == 'long':
                current_price = entry_price * (1 + unrealized_pnl / 100)
            else:
                current_price = entry_price * (1 - unrealized_pnl / 100)
        
        # 计算持仓名义价值
        contract_size = TRADE_CONFIG.get('contract_size', 0.01)  # 默认0.01 BTC/张
        position_notional = position_size * contract_size * current_price  # 名义价值
        
        # 计算手续费（开仓+平仓）
        total_fee = position_notional * TRADING_FEE_RATE  # 0.1% 总手续费
        
        # 计算实际盈亏 = 未实现盈亏 - 手续费
        unrealized_pnl = current_position.get('unrealized_pnl', 0)
        # 将未实现盈亏百分比转换为金额
        if current_position['side'] == 'long':
            pnl_amount = position_notional * (unrealized_pnl / 100)
        else:
            pnl_amount = position_notional * (unrealized_pnl / 100)
        
        # 扣除手续费
        actual_pnl = pnl_amount - total_fee
        actual_pnl_pct = (actual_pnl / position_notional) * 100 if position_notional > 0 else 0
        
        is_win = actual_pnl > 0
        print(f"💰 实际盈亏计算: 未实现盈亏={unrealized_pnl:.2f}%, 手续费={total_fee:.4f} USDT ({TRADING_FEE_RATE*100:.2f}%), 实际盈亏={actual_pnl:.4f} USDT ({actual_pnl_pct:.2f}%)")
        
        if current_position['side'] == 'long':
            exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                'sell',
                current_position['size'],
                params={'reduceOnly': True}
            )
        else:  # short
            exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                'buy', 
                current_position['size'],
                params={'reduceOnly': True}
            )
        print(f"✅ 已平掉{current_position['side']}仓")
        
        # 记录交易结果（使用实际盈亏）
        update_trade_result(is_win, actual_pnl)
        
    except Exception as e:
        print(f"❌ 平仓失败: {e}")
        # 即使平仓失败，也尝试清理订单
        try:
            cancel_tp_sl_orders(TRADE_CONFIG['symbol'], None)
        except:
            pass

def get_or_set_initial_balance(current_balance):
    """获取或设置初始资金"""
    try:
        # 尝试读取初始资金配置
        if os.path.exists(INITIAL_BALANCE_FILE):
            with open(INITIAL_BALANCE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('initial_balance', current_balance)
        else:
            # 如果不存在，使用当前余额作为初始值并保存
            initial_data = {
                'initial_balance': current_balance,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            os.makedirs(os.path.dirname(INITIAL_BALANCE_FILE), exist_ok=True)
            with open(INITIAL_BALANCE_FILE, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
            print(f"📝 初始资金已设置: {current_balance:.2f} USDT")
            return current_balance
    except Exception as e:
        print(f"⚠️ 读取初始资金失败，使用当前余额: {e}")
        return current_balance

def get_recent_trades(limit=50):
    """获取最近的交易历史"""
    try:
        # 使用fetch_my_trades获取成交记录（OKX不支持fetch_orders）
        trades = exchange.fetch_my_trades(TRADE_CONFIG['symbol'], limit=limit)
        
        trade_history = []
        for trade in trades:
            trade_history.append({
                'trade_id': trade['id'],
                'order_id': trade.get('order', 'N/A'),
                'timestamp': datetime.fromtimestamp(trade['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S') if trade['timestamp'] else 'N/A',
                'side': trade['side'],  # 'buy' or 'sell'
                'type': trade.get('type', 'market'),
                'price': trade['price'],
                'amount': trade['amount'],
                'cost': trade['cost'],
                'fee': trade.get('fee', {}).get('cost', 0) if trade.get('fee') else 0,
                'fee_currency': trade.get('fee', {}).get('currency', 'USDT') if trade.get('fee') else 'USDT'
            })
        
        # 按时间倒序排列（最新的在前）
        trade_history.reverse()
        return trade_history
        
    except Exception as e:
        print(f"⚠️ 获取交易历史失败: {e}")
        traceback.print_exc()
        return []

def export_dashboard_data(price_data, signal_data=None):
    """导出数据到Dashboard JSON文件"""
    global price_monitor
    try:
        # 获取当前持仓
        current_position = get_current_position()
        
        # 获取账户余额 - 使用total获取真实总资产（包含可用+保证金+盈亏）
        balance = exchange.fetch_balance()
        usdt_free = balance.get('USDT', {}).get('free', 0)  # 可用余额
        usdt_used = balance.get('USDT', {}).get('used', 0)  # 占用保证金
        usdt_total = balance.get('USDT', {}).get('total', 0)  # 真实总资产
        
        # 如果是测试模式，使用模拟余额
        if TRADE_CONFIG.get('test_mode', False):
            usdt_total = 10000.0  # 测试模式使用10000 USDT
            usdt_free = 10000.0
        
        # 使用OKX返回的total作为真实总资产（已经包含盈亏）
        total_value = usdt_total
        
        # 计算持仓名义价值（仅用于展示）
        position_notional = 0
        if current_position:
            # 名义价值 = 合约数量 * 合约乘数 * 当前价格
            position_notional = current_position['size'] * TRADE_CONFIG.get('contract_size', 0.01) * price_data['price']
        
        # 获取或设置初始资金
        initial_value = get_or_set_initial_balance(total_value)
        
        # 计算收益率
        if initial_value > 0:
            change_percent = ((total_value - initial_value) / initial_value) * 100
        else:
            change_percent = 0
        
        # 获取加密货币价格
        crypto_prices = {}
        try:
            symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT', 'XRP/USDT']
            for symbol in symbols:
                ticker = exchange.fetch_ticker(symbol)
                base_symbol = symbol.split('/')[0]
                crypto_prices[base_symbol] = {
                    'price': ticker['last'],
                    'change': ticker['percentage']
                }
        except Exception as e:
            print(f"获取加密货币价格失败: {e}")
        
        # 获取交易历史
        trade_history = get_recent_trades(limit=50)
        
        # 获取AI交易操作记录（最近50条）
        global trade_operations
        recent_operations = trade_operations[-50:] if trade_operations else []
        
        # 获取价格监控信息（止盈止损监控）
        price_monitor_info = None
        if price_monitor and price_monitor.current_position_info.get('position_side'):
            position_info = price_monitor.current_position_info
            current_price = price_data['price']
            
            # 计算当前盈亏
            if position_info['position_side'] == 'long':
                profit_pct = (current_price - position_info['entry_price']) / position_info['entry_price'] * 100
            else:  # short
                profit_pct = (position_info['entry_price'] - current_price) / position_info['entry_price'] * 100
            
            # 计算移动止盈触发价
            trailing_stop_price = None
            if position_info['trailing_stop_activated']:
                if position_info['position_side'] == 'long':
                    trailing_stop_price = position_info['highest_profit'] * 0.995
                else:  # short
                    trailing_stop_price = position_info['lowest_profit'] * 1.005
            
            price_monitor_info = {
                "entry_price": position_info['entry_price'],
                "stop_loss": position_info['stop_loss'],
                "take_profit": position_info['take_profit'],
                "current_profit_pct": round(profit_pct, 2),
                "trailing_stop_activated": position_info['trailing_stop_activated'],
                "trailing_stop_price": round(trailing_stop_price, 2) if trailing_stop_price else None,
                "highest_profit": position_info.get('highest_profit', 0) if position_info['position_side'] == 'long' else None,
                "lowest_profit": position_info.get('lowest_profit', 0) if position_info['position_side'] == 'short' else None,
                "peak_profit": round(position_info.get('peak_profit', 0), 2),
                "trailing_window": 0.5  # 回撤窗口0.5%
            }
        
        # 计算资金利用率
        capital_utilization = (usdt_used / total_value * 100) if total_value > 0 else 0
        max_utilization = TRADE_CONFIG['risk_management'].get('max_capital_utilization', 0.60) * 100
        min_utilization = TRADE_CONFIG['risk_management'].get('min_capital_utilization', 0.30) * 100
        
        # 获取动态杠杆（基于当前胜率）
        win_rate = performance_tracker.get('win_rate', 0)
        dynamic_leverage = get_dynamic_leverage(win_rate)
        current_leverage = TRADE_CONFIG.get('leverage', 6)  # 当前设置的杠杆
        
        # 获取交易胜率统计
        trade_count = performance_tracker.get('trade_count', 0)
        win_count = performance_tracker.get('win_count', 0)
        loss_count = performance_tracker.get('loss_count', 0)
        win_rate_pct = win_rate * 100 if win_rate else 0
        
        # 获取动态基础风险
        dynamic_base_risk = get_dynamic_base_risk(win_rate)
        dynamic_base_risk_pct = dynamic_base_risk * 100
        
        # 构建数据
        dashboard_data = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "account": {
                "balance": usdt_free,  # 可用余额
                "total_value": total_value,  # 真实总资产
                "change_percent": change_percent,
                "initial_balance": initial_value,
                "margin_used": usdt_used,  # 占用保证金
                "position_notional": position_notional,  # 持仓名义价值（仅供参考）
                "capital_utilization": round(capital_utilization, 2),  # 资金利用率（%）
                "max_capital_utilization": round(max_utilization, 2),  # 最大资金利用率（%）
                "min_capital_utilization": round(min_utilization, 2)  # 最小资金利用率（%）
            },
            "risk_management": {
                "current_leverage": current_leverage,  # 当前设置的杠杆
                "dynamic_leverage": dynamic_leverage,  # 动态杠杆（基于胜率）
                "base_risk_per_trade": round(TRADE_CONFIG['risk_management']['base_risk_per_trade'] * 100, 2),  # 基础风险（%）
                "dynamic_base_risk": round(dynamic_base_risk_pct, 2),  # 动态基础风险（%）
                "adaptive_risk_enabled": TRADE_CONFIG['risk_management'].get('adaptive_risk_enabled', False)
            },
            "performance_stats": {
                "win_rate": round(win_rate_pct, 2),  # 胜率（%）
                "trade_count": trade_count,  # 总交易次数
                "win_count": win_count,  # 盈利次数
                "loss_count": loss_count,  # 亏损次数
                "min_trades_for_adaptive": TRADE_CONFIG['risk_management'].get('min_trades_for_adaptive', 10),
                "adaptive_active": trade_count >= TRADE_CONFIG['risk_management'].get('min_trades_for_adaptive', 10)  # 是否已启用动态调整
            },
            "position": current_position,
            "signals": signal_history[-20:] if signal_history else [],  # 最近20个信号
            "trades": trade_history,  # 交易所成交历史
            "trade_operations": recent_operations,  # AI决策的加减仓操作记录
            "price_data": {
                "price": price_data['price'],
                "timestamp": price_data['timestamp'],
                "high": price_data['high'],
                "low": price_data['low'],
                "volume": price_data['volume'],
                "price_change": price_data['price_change']
            },
            "technical_analysis": {
                "rsi": price_data['technical_data'].get('rsi', 50),
                "macd": price_data['technical_data'].get('macd', 0),
                "trend": price_data['trend_analysis'].get('overall', '震荡整理'),
                "trend_strength": price_data['trend_analysis'].get('trend_strength', 'N/A'),
                "price_level": price_data['trend_analysis'].get('price_level', 'N/A')
            },
            "crypto_prices": crypto_prices,
            "price_monitor": price_monitor_info,  # 价格监控和止盈止损信息
            "performance_history": []  # 这个由Dashboard维护
        }
        
        # 写入文件（使用文件锁）
        with open(DASHBOARD_DATA_FILE, 'w', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 排他锁
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
        
        print(f"✅ Dashboard数据已导出: {dashboard_data['timestamp']}")
        print(f"   - 总资产: {total_value:.2f} USDT")
        print(f"   - 收益率: {change_percent:+.2f}%")
        print(f"   - 资金利用率: {capital_utilization:.1f}% (目标: {min_utilization:.0f}%-{max_utilization:.0f}%)")
        print(f"   - 交易记录: {len(trade_history)} 条")
        print(f"   - 交易胜率: {win_rate_pct:.1f}% (总交易: {trade_count}, 盈利: {win_count}, 亏损: {loss_count})")
        print(f"   - 动态杠杆: {dynamic_leverage}x (当前设置: {current_leverage}x)")
        print(f"   - 动态基础风险: {dynamic_base_risk_pct:.1f}%")
        sys.stdout.flush()
        
    except Exception as e:
        print(f"❌ 导出Dashboard数据失败: {e}")
        traceback.print_exc()
        sys.stdout.flush()

def wait_for_next_period():
    """等待到下一个15分钟整点"""
    now = datetime.now()
    current_minute = now.minute
    current_second = now.second

    # 计算下一个整点时间（00, 15, 30, 45分钟）
    next_period_minute = ((current_minute // 15) + 1) * 15
    if next_period_minute == 60:
        next_period_minute = 0

    # 计算需要等待的总秒数
    if next_period_minute > current_minute:
        minutes_to_wait = next_period_minute - current_minute
    else:
        minutes_to_wait = 60 - current_minute + next_period_minute

    seconds_to_wait = minutes_to_wait * 60 - current_second

    # 显示友好的等待时间
    display_minutes = minutes_to_wait - 1 if current_second > 0 else minutes_to_wait
    display_seconds = 60 - current_second if current_second > 0 else 0

    if display_minutes > 0:
        print(f"🕒 等待 {display_minutes} 分 {display_seconds} 秒到整点...")
    else:
        print(f"🕒 等待 {display_seconds} 秒到整点...")

    return seconds_to_wait

def trading_bot(immediate=False):
    """主交易机器人函数 - 使用趋势为王策略"""
    # 等待到整点再执行（除非立即执行）
    if not immediate:
        wait_seconds = wait_for_next_period()
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    print("\n" + "=" * 60)
    print(f"🎯 趋势为王策略执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 0. 检查市场情绪API健康状态
    sentiment_health = check_sentiment_api_health()
    print(f"📊 市场情绪API状态: {sentiment_health}")
    if "不可用" in sentiment_health or "警告" in sentiment_health:
        print("⚠️ 市场情绪API异常，将仅基于技术分析进行交易决策")

    # 1. 获取增强版K线数据
    price_data = get_btc_ohlcv_enhanced()
    if not price_data:
        return

    # 更新价格监控的 trailing 数据
    if price_monitor and price_monitor.current_position_info:
        price_monitor.update_with_price(price_data['price'])

    print(f"BTC当前价格: ${price_data['price']:,.2f}")
    print(f"数据周期: {TRADE_CONFIG['timeframe']}")
    print(f"价格变化: {price_data['price_change']:+.2f}%")

    # 2. 使用指导缓存的趋势为王信号（非阻塞，指挥官异步更新 guidance）
    signal_data = generate_signal_with_guidance(price_data)

    # 3. 执行智能交易（已集成趋势为王策略）
    execute_intelligent_trade(signal_data, price_data)
    
    # 4. 导出数据到Dashboard
    export_dashboard_data(price_data, signal_data)
    
    # 5. 记录市场情绪API监控状态（每10次交易记录一次）
    if len(signal_history) % 10 == 0:
        sentiment_health = check_sentiment_api_health()
        print(f"📊 市场情绪API监控: {sentiment_health}")

def setup_exchange():
    """初始化并验证交易所连接"""
    try:
        print("🔌 正在连接交易所...")
        exchange.load_markets()
        print("✅ 交易所连接成功")
        return True
    except Exception as e:
        print(f"❌ 交易所连接失败: {str(e)}")
        # 即使连接失败（可能是网络问题），也返回True让程序继续运行，
        # 因为exchange对象已经存在，可能会在后续恢复
        return False

def main():
    """主函数 - 集成价格监控和趋势为王策略"""
    print("🚀 BTC/USDT 趋势为王交易机器人启动")
    print("✅ 基于'趋势为王，结构修边'理念优化")
    print("🎯 核心特性: 趋势强度量化 + 结构时机优化 + 智能仓位管理")
    print("✅ 实时价格监控 + 动态止盈止损")
    
    if not setup_exchange():
        print("❌ 交易所初始化失败")
        return
    
    # 🔧 修复：程序启动时强制清理所有残留的策略订单（避免订单残留）
    try:
        print("🔄 启动时清理所有残留的策略订单...")
        cancel_tp_sl_orders(TRADE_CONFIG['symbol'], None)  # None表示取消所有
        print("✅ 残留订单清理完成")
    except Exception as e:
        print(f"⚠️ 清理残留订单时出错（继续运行）: {e}")
    
    # 初始化价格监控
    global price_monitor
    price_monitor = initialize_price_monitor()
    
    # 初始化现有持仓的监控信息（如果存在）
    try:
        current_position = get_current_position()
        if current_position and current_position['size'] > 0:
            # 获取价格数据用于计算止损止盈
            price_data = get_btc_ohlcv_enhanced()
            if price_data:
                price_monitor.initialize_existing_position(current_position, price_data)
    except Exception as e:
        print(f"⚠️ 初始化现有持仓监控时出错: {e}")
        # 继续运行，不影响主流程
        
    print("🔄 开始主交易循环...")
    
    # 立即执行一次
    trading_bot(immediate=True)
    
    # 主循环
    try:
        while True:
            trading_bot()
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 程序被用户中断")
    finally:
        # 确保停止价格监控
        if price_monitor:
            price_monitor.stop_monitoring()

if __name__ == "__main__":
    main()