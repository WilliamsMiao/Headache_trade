"""
风险管理模块
包含止损、止盈、仓位管理等风控逻辑
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta


# =============================================================================
# 智能移动止盈止损系统配置
# =============================================================================

# 基础止盈止损倍数（相对ATR）
BASE_STOP_LOSS_ATR_MULTIPLIER = 2.0  # 止损：2倍ATR
BASE_TAKE_PROFIT_ATR_MULTIPLIER = 4.0  # 止盈：4倍ATR（风险回报比1:2）

# 动态调整参数
DYNAMIC_TP_SL_CONFIG = {
    'min_sl_atr_multiplier': 1.5,
    'max_sl_atr_multiplier': 3.0,
    'min_tp_atr_multiplier': 3.0,
    'max_tp_atr_multiplier': 6.0,
    'volatility_threshold': 0.02,
}

# 移动止损配置
TRAILING_STOP_CONFIG = {
    'activation_profit_pct': 0.5,  # 盈利0.5%后激活移动止损
    'trailing_distance_pct': 0.3,  # 距离最高点0.3%触发止损
    'step_size_pct': 0.2,          # 每次上移0.2%
}

# 保护轨道配置
PROTECTION_ORBIT_CONFIG = {
    'check_interval': 60,          # 检查间隔（秒）
    'price_change_threshold': 0.001,  # 价格变化阈值
    'max_drawdown_from_peak': 0.005,  # 最大回撤（从峰值）
}


class ProtectionOrbit:
    """
    保护轨道系统
    实时监控持仓，动态调整止盈止损
    """
    
    def __init__(self, entry_price, position_side, stop_loss_price, take_profit_price):
        self.entry_price = entry_price
        self.position_side = position_side  # 'long' or 'short'
        self.initial_stop_loss = stop_loss_price
        self.initial_take_profit = take_profit_price
        
        self.current_stop_loss = stop_loss_price
        self.current_take_profit = take_profit_price
        
        self.highest_price = entry_price if position_side == 'long' else None
        self.lowest_price = entry_price if position_side == 'short' else None
        
        self.max_profit_pct = 0
        self.is_trailing_active = False
        
        self.last_update_time = datetime.now()
        
    def update(self, current_price, atr=None):
        """
        更新保护轨道
        
        Args:
            current_price: 当前价格
            atr: 当前ATR（可选）
        
        Returns:
            dict: 更新结果
        """
        result = {
            'stop_loss_updated': False,
            'take_profit_updated': False,
            'should_close': False,
            'reason': None
        }
        
        # 计算当前盈亏百分比
        if self.position_side == 'long':
            profit_pct = (current_price - self.entry_price) / self.entry_price
            
            # 更新最高价
            if self.highest_price is None or current_price > self.highest_price:
                self.highest_price = current_price
                self.max_profit_pct = max(self.max_profit_pct, profit_pct)
            
            # 检查是否激活移动止损
            if not self.is_trailing_active and profit_pct >= TRAILING_STOP_CONFIG['activation_profit_pct'] / 100:
                self.is_trailing_active = True
                print(f"✅ 移动止损已激活（盈利 {profit_pct*100:.2f}%）")
            
            # 移动止损逻辑
            if self.is_trailing_active:
                new_stop_loss = self.highest_price * (1 - TRAILING_STOP_CONFIG['trailing_distance_pct'] / 100)
                if new_stop_loss > self.current_stop_loss:
                    old_sl = self.current_stop_loss
                    self.current_stop_loss = new_stop_loss
                    result['stop_loss_updated'] = True
                    print(f"📈 止损上移: {old_sl:.2f} → {new_stop_loss:.2f}")
            
            # 检查是否触发止损
            if current_price <= self.current_stop_loss:
                result['should_close'] = True
                result['reason'] = 'stop_loss'
            
            # 检查是否触发止盈
            if current_price >= self.current_take_profit:
                result['should_close'] = True
                result['reason'] = 'take_profit'
        
        else:  # short position
            profit_pct = (self.entry_price - current_price) / self.entry_price
            
            # 更新最低价
            if self.lowest_price is None or current_price < self.lowest_price:
                self.lowest_price = current_price
                self.max_profit_pct = max(self.max_profit_pct, profit_pct)
            
            # 检查是否激活移动止损
            if not self.is_trailing_active and profit_pct >= TRAILING_STOP_CONFIG['activation_profit_pct'] / 100:
                self.is_trailing_active = True
                print(f"✅ 移动止损已激活（盈利 {profit_pct*100:.2f}%）")
            
            # 移动止损逻辑
            if self.is_trailing_active:
                new_stop_loss = self.lowest_price * (1 + TRAILING_STOP_CONFIG['trailing_distance_pct'] / 100)
                if new_stop_loss < self.current_stop_loss:
                    old_sl = self.current_stop_loss
                    self.current_stop_loss = new_stop_loss
                    result['stop_loss_updated'] = True
                    print(f"📉 止损下移: {old_sl:.2f} → {new_stop_loss:.2f}")
            
            # 检查是否触发止损
            if current_price >= self.current_stop_loss:
                result['should_close'] = True
                result['reason'] = 'stop_loss'
            
            # 检查是否触发止盈
            if current_price <= self.current_take_profit:
                result['should_close'] = True
                result['reason'] = 'take_profit'
        
        self.last_update_time = datetime.now()
        return result
    
    def get_current_prices(self):
        """获取当前止盈止损价格"""
        return {
            'stop_loss': self.current_stop_loss,
            'take_profit': self.current_take_profit,
            'entry_price': self.entry_price,
            'max_profit_pct': self.max_profit_pct,
            'is_trailing_active': self.is_trailing_active,
        }


class DynamicTakeProfit:
    """
    动态止盈系统
    根据市场波动性和趋势强度调整止盈目标
    """
    
    @staticmethod
    def calculate(entry_price, position_side, atr, volatility, trend_strength):
        """
        计算动态止盈价格
        
        Args:
            entry_price: 入场价格
            position_side: 'long' or 'short'
            atr: 平均真实波动范围
            volatility: 波动率
            trend_strength: 趋势强度 (0-1)
        
        Returns:
            float: 止盈价格
        """
        # 基础倍数
        base_multiplier = BASE_TAKE_PROFIT_ATR_MULTIPLIER
        
        # 根据趋势强度调整
        trend_adjustment = 1 + (trend_strength * 0.5)  # 最多增加50%
        
        # 根据波动率调整
        if volatility > DYNAMIC_TP_SL_CONFIG['volatility_threshold']:
            volatility_adjustment = 1.2  # 高波动，扩大止盈
        else:
            volatility_adjustment = 0.9  # 低波动，收紧止盈
        
        final_multiplier = base_multiplier * trend_adjustment * volatility_adjustment
        final_multiplier = np.clip(
            final_multiplier,
            DYNAMIC_TP_SL_CONFIG['min_tp_atr_multiplier'],
            DYNAMIC_TP_SL_CONFIG['max_tp_atr_multiplier']
        )
        
        if position_side == 'long':
            take_profit_price = entry_price + (atr * final_multiplier)
        else:
            take_profit_price = entry_price - (atr * final_multiplier)
        
        return take_profit_price


class ProgressiveProtection:
    """
    渐进式保护系统
    根据盈利进度逐步收紧止损
    """
    
    @staticmethod
    def adjust_stop_loss(entry_price, current_price, initial_stop_loss, position_side):
        """
        根据当前盈利调整止损
        
        Returns:
            float: 新的止损价格
        """
        if position_side == 'long':
            profit_pct = (current_price - entry_price) / entry_price
            
            if profit_pct >= 0.03:  # 盈利3%以上
                # 止损移至入场价上方0.5%
                new_stop_loss = entry_price * 1.005
            elif profit_pct >= 0.02:  # 盈利2-3%
                # 止损移至入场价
                new_stop_loss = entry_price
            elif profit_pct >= 0.01:  # 盈利1-2%
                # 止损收紧至50%
                new_stop_loss = entry_price - (entry_price - initial_stop_loss) * 0.5
            else:
                new_stop_loss = initial_stop_loss
            
            return max(new_stop_loss, initial_stop_loss)
        
        else:  # short
            profit_pct = (entry_price - current_price) / entry_price
            
            if profit_pct >= 0.03:
                new_stop_loss = entry_price * 0.995
            elif profit_pct >= 0.02:
                new_stop_loss = entry_price
            elif profit_pct >= 0.01:
                new_stop_loss = entry_price + (initial_stop_loss - entry_price) * 0.5
            else:
                new_stop_loss = initial_stop_loss
            
            return min(new_stop_loss, initial_stop_loss)


class RiskRewardOptimizer:
    """
    风险回报比优化器
    确保每笔交易满足最小风险回报比要求
    """
    
    MIN_RISK_REWARD_RATIO = 1.5  # 最小风险回报比1:1.5
    
    @staticmethod
    def validate_trade(entry_price, stop_loss, take_profit, position_side):
        """
        验证交易是否满足风险回报比要求
        
        Returns:
            tuple: (is_valid, risk_reward_ratio, adjusted_take_profit)
        """
        if position_side == 'long':
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
        
        if risk <= 0:
            return False, 0, take_profit
        
        rr_ratio = reward / risk
        
        if rr_ratio < RiskRewardOptimizer.MIN_RISK_REWARD_RATIO:
            # 调整止盈以满足最小风险回报比
            if position_side == 'long':
                adjusted_tp = entry_price + (risk * RiskRewardOptimizer.MIN_RISK_REWARD_RATIO)
            else:
                adjusted_tp = entry_price - (risk * RiskRewardOptimizer.MIN_RISK_REWARD_RATIO)
            
            return True, RiskRewardOptimizer.MIN_RISK_REWARD_RATIO, adjusted_tp
        
        return True, rr_ratio, take_profit
    
    @staticmethod
    def optimize(entry_price, stop_loss, take_profit, position_side):
        """
        优化止盈止损设置
        
        Returns:
            dict: 优化后的止盈止损价格
        """
        is_valid, rr_ratio, adjusted_tp = RiskRewardOptimizer.validate_trade(
            entry_price, stop_loss, take_profit, position_side
        )
        
        return {
            'is_valid': is_valid,
            'risk_reward_ratio': rr_ratio,
            'stop_loss': stop_loss,
            'take_profit': adjusted_tp,
            'adjusted': adjusted_tp != take_profit,
        }


def calculate_dynamic_stop_loss(signal_data, price_data):
    """
    计算动态止损价格
    
    Args:
        signal_data: AI信号数据
        price_data: 价格数据
    
    Returns:
        float: 止损价格
    """
    current_price = price_data['close'].iloc[-1]
    
    # 计算ATR
    from indicators import calculate_atr
    atr = calculate_atr(price_data)
    
    # 基础止损倍数
    base_multiplier = BASE_STOP_LOSS_ATR_MULTIPLIER
    
    # 根据信号置信度调整
    confidence = signal_data.get('confidence', 50)
    if confidence >= 80:
        confidence_adjustment = 0.9  # 高置信度，收紧止损
    elif confidence <= 40:
        confidence_adjustment = 1.2  # 低置信度，放宽止损
    else:
        confidence_adjustment = 1.0
    
    final_multiplier = base_multiplier * confidence_adjustment
    final_multiplier = np.clip(
        final_multiplier,
        DYNAMIC_TP_SL_CONFIG['min_sl_atr_multiplier'],
        DYNAMIC_TP_SL_CONFIG['max_sl_atr_multiplier']
    )
    
    signal = signal_data.get('signal', 'hold')
    if signal == 'buy':
        stop_loss_price = current_price - (atr * final_multiplier)
    elif signal == 'sell':
        stop_loss_price = current_price + (atr * final_multiplier)
    else:
        stop_loss_price = None
    
    return stop_loss_price


def check_trading_conditions() -> Dict[str, bool]:
    """
    检查交易条件
    
    Returns:
        dict: 交易条件检查结果
    """
    # 检查市场开放时间
    current_hour = datetime.now().hour
    is_market_hours = True  # 加密货币24小时交易
    
    # 检查波动率
    # （需要实际实现）
    volatility_ok = True
    
    # 检查API健康状态
    api_healthy = True
    
    return {
        'is_market_hours': is_market_hours,
        'volatility_ok': volatility_ok,
        'api_healthy': api_healthy,
        'can_trade': is_market_hours and volatility_ok and api_healthy,
    }


# =============================================================================
# 仓位管理
# =============================================================================

def calculate_win_rate(recent_trades_count=20):
    """
    计算最近交易的胜率
    
    Args:
        recent_trades_count: 统计的交易数量
    
    Returns:
        float: 胜率百分比
    """
    # 从文件读取交易历史
    try:
        from utils import safe_read_json
        trade_history = safe_read_json('data/trade_history.json', default={'trades': []})
        
        recent_trades = trade_history.get('trades', [])[-recent_trades_count:]
        
        if len(recent_trades) == 0:
            return 50.0  # 默认胜率50%
        
        wins = sum(1 for trade in recent_trades if trade.get('pnl', 0) > 0)
        win_rate = (wins / len(recent_trades)) * 100
        
        return win_rate
    
    except Exception as e:
        print(f"⚠️ 计算胜率失败: {e}")
        return 50.0


def get_dynamic_base_risk(win_rate=None):
    """
    根据胜率动态调整基础风险比例
    
    Args:
        win_rate: 胜率百分比（可选）
    
    Returns:
        float: 基础风险比例
    """
    if win_rate is None:
        win_rate = calculate_win_rate()
    
    # 基础风险
    base_risk = 0.01  # 1%
    
    # 根据胜率调整
    if win_rate >= 60:
        risk_multiplier = 1.5  # 增加50%
    elif win_rate >= 50:
        risk_multiplier = 1.0  # 保持不变
    elif win_rate >= 40:
        risk_multiplier = 0.7  # 减少30%
    else:
        risk_multiplier = 0.5  # 减少50%
    
    dynamic_risk = base_risk * risk_multiplier
    
    return min(dynamic_risk, 0.02)  # 最大2%


def get_dynamic_leverage(win_rate=None):
    """
    根据胜率动态调整杠杆倍数
    
    Args:
        win_rate: 胜率百分比（可选）
    
    Returns:
        int: 杠杆倍数
    """
    if win_rate is None:
        win_rate = calculate_win_rate()
    
    if win_rate >= 60:
        leverage = 3
    elif win_rate >= 50:
        leverage = 2
    elif win_rate >= 40:
        leverage = 1
    else:
        leverage = 1
    
    return leverage
