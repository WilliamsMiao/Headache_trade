import os
import sys
import time
import schedule
from openai import OpenAI
import ccxt
import pandas as pd
import numpy as np
import re
from dotenv import load_dotenv
import json
import requests
from datetime import datetime, timedelta
import fcntl
import traceback
import threading

load_dotenv()

# 初始化DeepSeek客户端
deepseek_client = OpenAI(
    api_key=os.getenv('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)

# 初始化OKX交易所
exchange = ccxt.okx({
    'options': {
        'defaultType': 'swap',
    },
    'apiKey': os.getenv('OKX_API_KEY'),
    'secret': os.getenv('OKX_SECRET'),
    'password': os.getenv('OKX_PASSWORD'),
})

# OKX手续费率配置（合约交易）
# Maker: 0.02% (0.0002), Taker: 0.05% (0.0005)
# 开仓+平仓总成本：0.1% (0.001) - 假设都是Taker订单
TRADING_FEE_RATE = 0.001  # 0.1% 总手续费率（开仓+平仓）

# 锁定止损机制配置
LOCK_STOP_LOSS_PROFIT_THRESHOLD = 0.8  # 🔧 优化v2：从1.5%降至0.8%，更早激活盈利保护
LOCK_STOP_LOSS_BUFFER = 0.1  # 盈亏平衡点缓冲（%）
LOCK_STOP_LOSS_RATIO = 0.3  # 基础锁定比例（已废弃，使用下面的分段配置）

# 🔧 优化v2：分段锁定比例配置
LOCK_STOP_LOSS_RATIOS = {
    'low': {'min_profit': 0.008, 'max_profit': 0.015, 'ratio': 0.4},    # 0.8%-1.5%盈利：锁定40%
    'medium': {'min_profit': 0.015, 'max_profit': 0.025, 'ratio': 0.5},  # 1.5%-2.5%盈利：锁定50%
    'high': {'min_profit': 0.025, 'max_profit': float('inf'), 'ratio': 0.6}  # >2.5%盈利：锁定60%
}

# =============================================================================
# 智能移动止盈止损系统配置
# =============================================================================

# 三阶段保护级别配置
PROTECTION_LEVELS = {
    'defensive': {    # 防守阶段：开仓初期
        'stop_loss_multiplier': 2.0,    # 🔧 优化v2：从1.5提高到2.0，给予更大呼吸空间
        'take_profit_multiplier': 2.5,  # 🔧 优化v2：从2.0提高到2.5，扩大止盈目标
        'activation_time': 30,           # 30秒后进入平衡阶段
        'min_profit_required': 0.0      # 无盈利要求
    },
    'balanced': {     # 平衡阶段：有盈利后
        'stop_loss_multiplier': 1.5,    # 保持1.5，与defensive一致
        'take_profit_multiplier': 2.5,  # 🔧 关键修复：从1.0提高到2.5，扩大止盈目标（约1.5%）
        'activation_time': 0,            # 立即激活（基于盈利条件）
        'min_profit_required': 0.2      # 🔧 关键修复：从0.5%降低到0.2%，更容易进入balanced阶段
    },
    'aggressive': {   # 进攻阶段：大幅盈利后
        'stop_loss_multiplier': 0.8,    # 宽松止损，让利润奔跑
        'take_profit_multiplier': 1.5,  # 保持1.5，让利润继续奔跑
        'activation_time': 0,            # 立即激活（基于盈利条件）
        'min_profit_required': 0.5      # 🔧 关键修复：从1.0%降低到0.5%，更容易进入aggressive阶段
    }
}

# 轨道更新间隔（秒）
ORBIT_UPDATE_INTERVAL = 120  # 🔧 优化v2：从60秒提高到120秒，进一步减少订单操作
ORBIT_INITIAL_PROTECTION_TIME = 300  # 🔧 新增：开仓后前5分钟（300秒）不更新轨道
ORBIT_MIN_TRIGGER_TIME = 180  # 🔧 新增：开仓后前3分钟（180秒）禁止保护轨道触发平仓

# 🔧 优化v2：订单更新阈值配置
ORDER_UPDATE_THRESHOLD = 0.005  # 止盈止损价格变化超过0.5%才更新订单
ORDER_UPDATE_MIN_CHANGE = 0.002  # 最小价格变化0.2%，避免频繁微调

# 持仓验证保护期配置
POSITION_VERIFY_PROTECTION_SECONDS = 60  # 开仓后60秒内跳过持仓验证，避免数据同步延迟误判
POSITION_VERIFY_FAIL_THRESHOLD = 3  # 连续验证失败3次才清空持仓信息

# 优化的交易参数配置 - 基于"趋势为王，结构修边"理念
TRADE_CONFIG = {
    'symbol': 'BTC/USDT:USDT',
    'leverage': 6,  # 默认杠杆6x，平衡风险与收益（趋势为王策略，可动态调整至1-10x）
    'timeframe': '15m',
    'test_mode': False,
    'data_points': 96,
    'analysis_periods': {
        'short_term': 20,
        'medium_term': 50,
        'long_term': 96
    },
    # 基于趋势强度的风险管理 - 趋势为王理念
    'risk_management': {
        'max_daily_drawdown': 0.05,  # 单日最大回撤5%
        'max_position_drawdown': 0.03,  # 单笔最大亏损3%（实际使用的风险控制参数）
        'base_risk_per_trade': 0.02,  # [已废弃，保留用于向后兼容] 单笔基础风险2%，旧逻辑使用，新逻辑已改用 max_position_drawdown (3%)
        # 资金利用率配置（积极利用模式）
        'max_capital_utilization': 0.60,  # 最大60%资金利用率
        'min_capital_utilization': 0.30,  # 最小30%资金利用率（确保有缓冲）
        'target_capital_utilization': 0.50,  # 目标资金利用率50%，用于优化
        'min_leverage': 1,  # 最小杠杆
        'max_leverage': 10,  # 最大杠杆，根据风险动态调整
        # 动态风险调整配置（基于策略胜率）
        'adaptive_risk_enabled': True,  # 启用动态风险调整
        'risk_levels': {
            'high_win_rate': {'threshold': 0.60, 'min_risk': 0.05, 'max_risk': 0.10},  # 胜率>60%：5-10%
            'medium_win_rate': {'threshold': 0.40, 'min_risk': 0.03, 'max_risk': 0.05},  # 胜率40-60%：3-5%
            'low_win_rate': {'min_risk': 0.01, 'max_risk': 0.02}  # 胜率<40%：1-2%
        },
        'min_trades_for_adaptive': 10,  # 至少需要10笔交易才启用动态调整
        # 趋势强度仓位乘数 (趋势为王理念)
        'trend_strength_multipliers': {
            'strong_trend': 1.5,    # 趋势强度8-10分
            'medium_trend': 1.2,    # 趋势强度6-7分  
            'normal_trend': 1.0,    # 趋势强度4-5分
            'weak_trend': 0.5       # 趋势强度0-3分
        },
        # 结构优化仓位乘数 (结构修边理念)
        'structure_optimized_multiplier': 1.2,
        # 信心程度仓位乘数（保留原有逻辑）
        'confidence_multipliers': {
            'HIGH': 1.0,
            'MEDIUM': 0.7, 
            'LOW': 0.3
        },
        # 保留原有乘数（向后兼容）
        'high_confidence_multiplier': 1.2,
        'medium_confidence_multiplier': 0.8,
        'low_confidence_multiplier': 0.3,
        'trend_strength_multiplier': 1.1,
        'volatility_multiplier': 0.9  # 高波动性时降低仓位
    },
    'performance_tracking': {
        'daily_pnl_threshold': -0.03,  # 日亏损3%暂停交易
        'weekly_pnl_threshold': -0.08   # 周亏损8%全面检查
    }
}

# 全局性能跟踪
performance_tracker = {
    'daily_pnl': 0,
    'weekly_pnl': 0,
    'trade_count': 0,
    'last_trade_time': None,  # 🔧 新增：记录上次交易时间
    'daily_trade_count': 0,  # 🔧 新增：每日交易次数
    'last_trade_date': None,  # 🔧 新增：上次交易日期
    'win_count': 0,  # 盈利交易数量
    'loss_count': 0,  # 亏损交易数量
    'win_rate': 0,
    'trade_results': [],  # 最近交易结果记录 [{'result': 'win'/'loss', 'pnl': float, 'timestamp': str}]
    'last_reset': datetime.now(),
    'is_trading_paused': False
}

# 全局信号历史记录
signal_history = []

# 全局交易操作记录（用于Dashboard显示AI决策的加减仓操作）
trade_operations = []

# 市场情绪API监控状态
sentiment_api_monitor = {
    'last_check': None,
    'last_success': None,
    'consecutive_failures': 0,
    'is_available': True,
    'failure_count_today': 0,
    'last_error': None,
    'total_requests': 0,
    'successful_requests': 0,
    'last_reset_date': datetime.now().date()
}

# Dashboard数据文件路径
DASHBOARD_DATA_FILE = '/root/crypto_deepseek/data/dashboard_data.json'
# 初始资金配置文件
INITIAL_BALANCE_FILE = '/root/crypto_deepseek/data/initial_balance.json'

# 全局价格监控实例
price_monitor = None

# =============================================================================
# 智能移动止盈止损系统核心类
# =============================================================================

class ProtectionOrbit:
    """
    保护轨道系统 - 管理双轨道（止盈轨道 + 止损轨道）
    根据盈利水平和持仓时间自动切换保护级别
    """
    
    def __init__(self, entry_price, atr, position_side):
        """
        初始化保护轨道
        
        Args:
            entry_price: 入场价格
            atr: 平均真实波幅
            position_side: 持仓方向 'long' 或 'short'
        """
        self.entry_price = entry_price
        self.atr = atr
        self.position_side = position_side
        self.current_level = 'defensive'  # 初始为防守阶段
        self.entry_time = datetime.now()
        
        # 初始化轨道
        self.upper_orbit = self.calculate_upper_orbit()
        self.lower_orbit = self.calculate_lower_orbit()
        
        print(f"🛡️ 保护轨道初始化: 入场价={entry_price:.2f}, ATR={atr:.2f}, 级别={self.current_level}")
        print(f"   - 止盈轨道: {self.upper_orbit:.2f}")
        print(f"   - 止损轨道: {self.lower_orbit:.2f}")
    
    def update_orbits(self, current_price, time_elapsed, profit_pct, volatility=0.5, trend_strength=0.5):
        """
        更新双轨道
        
        Args:
            current_price: 当前价格
            time_elapsed: 持仓时间（秒）
            profit_pct: 当前盈亏百分比
            volatility: 市场波动性（0-1，可选）
            trend_strength: 趋势强度（0-1，可选）
        """
        # 根据盈利水平和持仓时间确定保护级别
        new_level = self._determine_protection_level(time_elapsed, profit_pct)
        
        # 如果级别改变，记录日志
        if new_level != self.current_level:
            print(f"🔄 保护级别切换: {self.current_level} → {new_level} (盈利: {profit_pct:.2f}%, 持仓时间: {time_elapsed:.0f}秒)")
            self.current_level = new_level
        
        # 重新计算轨道
        old_upper = self.upper_orbit
        old_lower = self.lower_orbit
        
        self.upper_orbit = self.calculate_upper_orbit()
        self.lower_orbit = self.calculate_lower_orbit()
        
        # 记录轨道变化（如果变化明显）
        if abs(self.upper_orbit - old_upper) > self.atr * 0.1 or abs(self.lower_orbit - old_lower) > self.atr * 0.1:
            print(f"📊 轨道更新: 止盈 {old_upper:.2f} → {self.upper_orbit:.2f}, 止损 {old_lower:.2f} → {self.lower_orbit:.2f}")
    
    def _determine_protection_level(self, time_elapsed, profit_pct):
        """
        根据持仓时间和盈利水平确定保护级别
        🔧 优化：降低切换门槛，更容易进入balanced和aggressive阶段
        
        Returns:
            str: 'defensive', 'balanced', 或 'aggressive'
        """
        # 防守阶段：开仓初期（30秒内）或亏损
        if time_elapsed < PROTECTION_LEVELS['defensive']['activation_time'] or profit_pct < 0:
            return 'defensive'
        
        # 进攻阶段：大幅盈利（0.5%以上，从1.0%降低）
        if profit_pct >= PROTECTION_LEVELS['aggressive']['min_profit_required']:
            return 'aggressive'
        
        # 🔧 优化：平衡阶段门槛从0.5%降低到0.2%，更容易进入
        # 平衡阶段：有盈利但未达到进攻阶段（0.2%-0.5%）
        if profit_pct >= PROTECTION_LEVELS['balanced']['min_profit_required']:
            return 'balanced'
        
        # 默认返回防守阶段
        return 'defensive'
    
    def calculate_upper_orbit(self):
        """
        计算止盈轨道 - 基于当前保护级别
        
        Returns:
            float: 止盈价格
        """
        config = PROTECTION_LEVELS[self.current_level]
        multiplier = config['take_profit_multiplier']
        
        if self.position_side == 'long':
            # 多头：止盈价 = 入场价 + ATR * 倍数
            upper_orbit = self.entry_price + (self.atr * multiplier)
        else:
            # 空头：止盈价 = 入场价 - ATR * 倍数
            upper_orbit = self.entry_price - (self.atr * multiplier)
        
        return upper_orbit
    
    def calculate_lower_orbit(self):
        """
        计算止损轨道 - 基于当前保护级别
        
        Returns:
            float: 止损价格
        """
        config = PROTECTION_LEVELS[self.current_level]
        multiplier = config['stop_loss_multiplier']
        
        if self.position_side == 'long':
            # 多头：止损价 = 入场价 - ATR * 倍数
            lower_orbit = self.entry_price - (self.atr * multiplier)
        else:
            # 空头：止损价 = 入场价 + ATR * 倍数
            lower_orbit = self.entry_price + (self.atr * multiplier)
        
        return lower_orbit
    
    def get_current_level(self):
        """获取当前保护级别"""
        return self.current_level
    
    def get_orbits(self):
        """获取当前双轨道"""
        return {
            'upper_orbit': self.upper_orbit,
            'lower_orbit': self.lower_orbit,
            'level': self.current_level
        }

class DynamicTakeProfit:
    """
    动态止盈计算 - 基于盈利水平、ATR、市场条件计算动态止盈价
    """
    
    def calculate_take_profit(self, entry_price, current_price, atr, market_condition='normal', profit_pct=0):
        """
        基于多种因素计算动态止盈价位
        
        Args:
            entry_price: 入场价格
            current_price: 当前价格
            atr: 平均真实波幅
            market_condition: 市场条件 'normal', 'volatile', 'stable'
            profit_pct: 当前盈亏百分比
        
        Returns:
            float: 动态止盈价格
        """
        # 计算基础盈利
        if entry_price > 0:
            base_profit = abs((current_price - entry_price) / entry_price)
        else:
            base_profit = 0
        
        # 🔧 优化：根据盈利阶段调整止盈策略，确保止盈目标覆盖手续费+利润
        if base_profit < 0.001:  # 微利阶段（<0.1%）
            # 🔧 优化：从0.5倍ATR提高到1.0倍ATR，确保覆盖手续费
            if current_price > entry_price:  # 多头
                take_profit = entry_price + (atr * 1.0)
            else:  # 空头
                take_profit = entry_price - (atr * 1.0)
        elif base_profit < 0.005:  # 中等盈利（0.1%-0.5%）
            # 🔧 关键修复：从0.8倍ATR提高到1.5倍ATR，确保止盈目标足够大
            if current_price > entry_price:  # 多头
                take_profit = current_price + (atr * 1.5)
            else:  # 空头
                take_profit = current_price - (atr * 1.5)
        else:  # 高盈利阶段（>0.5%）
            # 🔧 优化：从1.2倍ATR提高到1.8倍ATR，让利润继续奔跑
            if current_price > entry_price:  # 多头
                take_profit = current_price + (atr * 1.8)
            else:  # 空头
                take_profit = current_price - (atr * 1.8)
        
        # 根据市场条件调整
        if market_condition == 'volatile':
            # 波动市场：扩大止盈目标
            if current_price > entry_price:  # 多头
                take_profit = take_profit + (atr * 0.2)
            else:  # 空头
                take_profit = take_profit - (atr * 0.2)
        elif market_condition == 'stable':
            # 稳定市场：缩小止盈目标
            if current_price > entry_price:  # 多头
                take_profit = take_profit - (atr * 0.1)
            else:  # 空头
                take_profit = take_profit + (atr * 0.1)
        
        return take_profit

class ProgressiveProtection:
    """
    渐进式保护 - 基于多因素（盈利、波动性、趋势强度）计算动态保护级别
    """
    
    def calculate_dynamic_levels(self, current_profit, volatility, trend_strength):
        """
        基于多因素计算动态保护级别
        
        Args:
            current_profit: 当前盈利百分比（0-1，如0.01表示1%）
            volatility: 市场波动性指数（0-1）
            trend_strength: 趋势强度（0-1）
        
        Returns:
            tuple: (stop_multiplier, take_profit_multiplier)
        """
        # 盈利越高，保护越宽松（让利润奔跑）
        if current_profit > 0.01:  # 1%以上盈利
            stop_multiplier = 0.6 + (0.4 * trend_strength)  # 趋势强则更宽松
            take_profit_multiplier = 1.2 + (0.8 * trend_strength)
        else:
            # 盈利较低时，根据波动性调整
            stop_multiplier = 1.5 - (0.5 * volatility)  # 波动高则收紧止损
            take_profit_multiplier = 0.8 + (0.4 * trend_strength)
        
        # 确保倍数在合理范围内
        stop_multiplier = max(0.5, min(2.0, stop_multiplier))
        take_profit_multiplier = max(0.5, min(2.5, take_profit_multiplier))
        
        return stop_multiplier, take_profit_multiplier

class RiskRewardOptimizer:
    """
    风险收益优化器 - 优化风险收益比，保持在1:2到1:3之间
    """
    
    def calculate_risk_reward_ratio(self, position_data):
        """
        计算当前风险收益比
        
        Args:
            position_data: 持仓数据字典，包含 entry_price, stop_loss, take_profit
        
        Returns:
            float: 风险收益比
        """
        entry_price = position_data.get('entry_price', 0)
        stop_loss = position_data.get('stop_loss', 0)
        take_profit = position_data.get('take_profit', 0)
        position_side = position_data.get('position_side', 'long')
        
        if entry_price == 0:
            return 0
        
        if position_side == 'long':
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
        else:  # short
            risk = abs(stop_loss - entry_price)
            reward = abs(entry_price - take_profit)
        
        if risk == 0:
            return 0
        
        return reward / risk
    
    def optimize_protection_levels(self, position_data, market_conditions):
        """
        基于风险收益比动态优化保护级别
        
        Args:
            position_data: 持仓数据
            market_conditions: 市场条件
        
        Returns:
            dict: 优化后的保护级别配置
        """
        current_rr_ratio = self.calculate_risk_reward_ratio(position_data)
        
        if current_rr_ratio < 1.5:  # 风险收益比过低
            return self._adjust_for_better_rr(position_data, 'aggressive')
        elif current_rr_ratio > 3:  # 风险收益比过高
            return self._adjust_for_better_rr(position_data, 'conservative')
        else:
            return self._maintain_current_levels(position_data)
    
    def _adjust_for_better_rr(self, position_data, strategy):
        """调整保护级别以改善风险收益比"""
        entry_price = position_data.get('entry_price', 0)
        atr = position_data.get('atr', entry_price * 0.01)
        position_side = position_data.get('position_side', 'long')
        
        if strategy == 'aggressive':
            # 扩大止盈，收紧止损
            if position_side == 'long':
                stop_loss = entry_price - (atr * 1.0)
                take_profit = entry_price + (atr * 2.5)
            else:
                stop_loss = entry_price + (atr * 1.0)
                take_profit = entry_price - (atr * 2.5)
        else:  # conservative
            # 缩小止盈，放宽止损
            if position_side == 'long':
                stop_loss = entry_price - (atr * 1.8)
                take_profit = entry_price + (atr * 2.0)
            else:
                stop_loss = entry_price + (atr * 1.8)
                take_profit = entry_price - (atr * 2.0)
        
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'strategy': strategy
        }
    
    def _maintain_current_levels(self, position_data):
        """维持当前保护级别"""
        return {
            'stop_loss': position_data.get('stop_loss', 0),
            'take_profit': position_data.get('take_profit', 0),
            'strategy': 'maintain'
        }

class RealTimePriceMonitor:
    """实时价格监控和动态止盈止损管理"""
    
    def __init__(self, exchange, trade_config):
        self.exchange = exchange
        self.trade_config = trade_config
        self.monitor_interval = 10  # 10秒检查一次（从30秒优化到10秒，提高响应速度）
        self.is_monitoring = False
        self.monitor_thread = None
        self.last_order_update_time = None  # 记录上次订单更新时间，用于频率控制
        self.min_update_interval = ORBIT_UPDATE_INTERVAL  # 使用配置的轨道更新间隔（60秒）
        self.last_orbit_update_time = None  # 记录上次轨道更新时间
        
        # 智能移动止盈止损系统组件
        self.protection_orbit = None  # ProtectionOrbit实例
        self.dynamic_take_profit = DynamicTakeProfit()  # DynamicTakeProfit实例
        self.progressive_protection = ProgressiveProtection()  # ProgressiveProtection实例
        self.risk_optimizer = RiskRewardOptimizer()  # RiskRewardOptimizer实例
        
        # 持仓相关时间记录
        self.position_open_time = None  # 持仓开始时间
        self.atr_value = 0  # 当前ATR值
        self.position_verify_fail_count = 0  # 持仓验证失败计数器
        
        # 当前持仓的风控参数
        self.current_position_info = {
            'entry_price': 0,
            'stop_loss': 0,
            'take_profit': 0,
            'position_side': None,  # 'long' or 'short'
            'position_size': 0,
            'leverage': 1,  # 杠杆倍数
            'trailing_stop_activated': False,
            'highest_profit': 0,  # 用于移动止盈
            'lowest_profit': 0,    # 用于移动止损
            'tp_sl_order_ids': None  # 止盈止损订单ID {'tp_order_id': 'xxx', 'sl_order_id': 'xxx'}
        }
        
        # 锁定止损配置 - 可根据市场状况调整
        self.lock_stop_loss_config = {
            'profit_threshold': LOCK_STOP_LOSS_PROFIT_THRESHOLD / 100,  # 激活锁定止损的盈利阈值 0.5%
            'buffer_ratio': LOCK_STOP_LOSS_BUFFER / 100,  # 盈亏平衡点缓冲 0.1%
            'lock_ratio': LOCK_STOP_LOSS_RATIO,  # 锁定比例 30%
            'min_lock_distance': 0.002,  # 最小锁定距离 0.2%
            'activated': False,
            'locked_stop_price': 0,
            'breakeven_price': 0,
            'peak_profit_price': 0,  # 🔧 新增：记录历史最高盈利点价格
            'high_volatility_multiplier': 1.2,  # 高波动性时提高阈值
            'low_volatility_multiplier': 0.8,   # 低波动性时降低阈值
        }
        
        # 盈利分批平仓配置
        self.profit_taking_config = {
            'partial_close_threshold_1': 0.02,  # 盈利2%平仓一半
            'partial_close_threshold_2': 0.04,  # 盈利4%平仓全部
            'partial_close_ratio_1': 0.5,       # 第一次平仓比例50%
            'min_partial_close_size': 0.01,     # 最小平仓数量
            'partial_close_1_executed': False,  # 第一次平仓是否已执行
            'partial_close_2_executed': False,  # 第二次平仓是否已执行
            'last_partial_close_time': None,    # 上次平仓时间
            'min_close_interval': 10,           # 最小平仓间隔(秒)
        }
    
    def start_monitoring(self):
        """启动价格监控"""
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("🎯 实时价格监控已启动")
    
    def stop_monitoring(self):
        """停止价格监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("⏹️ 实时价格监控已停止")
    
    def update_position_info(self, signal_data, price_data, position_size):
        """更新持仓信息（开仓时调用）"""
        current_price = price_data['price']
        position_side = 'long' if signal_data['signal'] == 'BUY' else 'short'
        
        # 🔧 获取ATR值用于保护轨道系统
        atr = price_data.get('technical_data', {}).get('atr', current_price * 0.01)
        self.atr_value = atr
        
        # 🔧 初始化保护轨道系统
        try:
            self.protection_orbit = ProtectionOrbit(
                entry_price=current_price,
                atr=atr,
                position_side=position_side
            )
            print(f"✅ 保护轨道系统已初始化")
        except Exception as e:
            print(f"⚠️ 初始化保护轨道系统失败: {e}")
            self.protection_orbit = None
        
        # 🔧 记录持仓开始时间
        self.position_open_time = datetime.now()
        self.last_orbit_update_time = None  # 重置轨道更新时间
        self.position_verify_fail_count = 0  # 🔧 重置持仓验证失败计数（开仓时重置）
        
        # 关键修复：先取消该交易对的所有策略订单（不依赖订单ID）
        # 这样可以确保清除所有旧订单，避免订单累积
        try:
            print("🔄 取消该交易对的所有旧止盈止损订单...")
            cancel_tp_sl_orders(self.trade_config['symbol'], None)  # None表示取消所有
            time.sleep(0.5)  # 等待取消完成
        except Exception as e:
            print(f"⚠️ 取消旧订单时出错（继续执行）: {e}")
        
        # 设置新的止盈止损订单
        order_ids = None
        try:
            order_ids = set_tp_sl_orders(
                self.trade_config['symbol'],
                position_side,
                position_size,
                signal_data['stop_loss'],
                signal_data['take_profit'],
                current_price
            )
        except Exception as e:
            print(f"⚠️ 设置止盈止损订单时出错: {e}")
            print(f"⚠️ 将使用代码监控作为备用机制")
        
        # 获取当前杠杆
        try:
            actual_position = get_current_position()
            current_leverage = actual_position.get('leverage', self.trade_config.get('leverage', 1)) if actual_position else self.trade_config.get('leverage', 1)
        except:
            current_leverage = self.trade_config.get('leverage', 1)
        
        self.current_position_info = {
            'entry_price': current_price,
            'stop_loss': signal_data['stop_loss'],
            'take_profit': signal_data['take_profit'],
            'position_side': position_side,
            'position_size': position_size,
            'leverage': current_leverage,  # 存储杠杆信息
            'trailing_stop_activated': False,
            'highest_profit': current_price if signal_data['signal'] == 'BUY' else 0,
            'lowest_profit': current_price if signal_data['signal'] == 'SELL' else float('inf'),
            'update_time': datetime.now(),
            'tp_sl_order_ids': order_ids,
            'atr': atr,  # 存储ATR值
            'trend_score': signal_data.get('trend_score', 0)  # 🔧 优化：保存趋势强度用于分批止盈
        }
        
        # 初始化锁定止损配置
        if position_side == 'long':
            self.lock_stop_loss_config['breakeven_price'] = current_price * (1 + TRADING_FEE_RATE)
        else:  # short
            self.lock_stop_loss_config['breakeven_price'] = current_price * (1 - TRADING_FEE_RATE)
        self.lock_stop_loss_config['activated'] = False
        self.lock_stop_loss_config['locked_stop_price'] = 0
        self.lock_stop_loss_config['peak_profit_price'] = 0  # 🔧 重置历史最高盈利点
        
        # 🔧 重置盈利平仓状态
        self.profit_taking_config.update({
            'partial_close_1_executed': False,
            'partial_close_2_executed': False,
            'last_partial_close_time': None
        })
        print("🔄 盈利分批平仓状态已重置")
        
        print(f"📝 更新持仓监控:")
        print(f"   - 方向: {self.current_position_info['position_side']}")
        print(f"   - 入场价: {current_price:.2f}")
        print(f"   - 止损: {signal_data['stop_loss']:.2f}")
        print(f"   - 止盈: {signal_data['take_profit']:.2f}")
        print(f"   - ATR: {atr:.2f}")
        if order_ids:
            print(f"   - 止盈止损订单: 已设置 (TP: {order_ids.get('tp_order_id', 'N/A')}, SL: {order_ids.get('sl_order_id', 'N/A')})")
        else:
            print(f"   - 止盈止损订单: 使用代码监控")
    
    def clear_position_info(self):
        """清空持仓信息（平仓时调用）"""
        # 🔧 新增：检查是否在开仓保护期内，保护期内不执行清仓（避免误判）
        if self.position_open_time:
            time_elapsed = (datetime.now() - self.position_open_time).total_seconds()
            if time_elapsed < POSITION_VERIFY_PROTECTION_SECONDS:
                print(f"⚠️ 保护期内（开仓后{time_elapsed:.1f}秒）检测到清仓请求，可能是数据同步延迟导致的误判，跳过清仓操作")
                return
        
        # 🔧 修复：强制取消所有策略订单，无论是否有订单ID（避免订单残留）
        try:
            print("🔄 平仓时强制取消该交易对的所有止盈止损订单...")
            cancel_tp_sl_orders(self.trade_config['symbol'], None)  # None表示取消所有
            time.sleep(0.5)  # 等待取消完成
        except Exception as e:
            print(f"⚠️ 取消所有订单时出错（继续执行）: {e}")
        
        # 如果还有已知的订单ID，也尝试取消（双重保险）
        order_ids = self.current_position_info.get('tp_sl_order_ids')
        if order_ids:
            try:
                cancel_tp_sl_orders(self.trade_config['symbol'], order_ids)
            except Exception as e:
                print(f"⚠️ 取消已知订单ID时出错: {e}")
        
        # 🔧 清空保护轨道系统
        self.protection_orbit = None
        self.position_open_time = None
        self.atr_value = 0
        self.last_orbit_update_time = None
        
        self.current_position_info = {
            'entry_price': 0,
            'stop_loss': 0,
            'take_profit': 0,
            'position_side': None,
            'position_size': 0,
            'leverage': 1,
            'trailing_stop_activated': False,
            'highest_profit': 0,
            'lowest_profit': 0,
            'tp_sl_order_ids': None
        }
        
        # 重置锁定止损配置
        self.lock_stop_loss_config['activated'] = False
        self.lock_stop_loss_config['locked_stop_price'] = 0
        self.lock_stop_loss_config['breakeven_price'] = 0
        self.lock_stop_loss_config['peak_profit_price'] = 0  # 🔧 重置历史最高盈利点
        
        # 🔧 重置盈利平仓状态
        self.profit_taking_config.update({
            'partial_close_1_executed': False,
            'partial_close_2_executed': False,
            'last_partial_close_time': None
        })
        
        # 🔧 重置持仓验证失败计数
        self.position_verify_fail_count = 0
    
    def initialize_existing_position(self, current_position, price_data):
        """初始化现有持仓的监控信息（启动时调用）
        
        Args:
            current_position: 当前持仓信息字典
            price_data: 价格数据字典
            
        Returns:
            bool: 是否成功初始化
        """
        try:
            if not current_position or current_position['size'] == 0:
                # 无持仓，无需初始化
                return False
            
            if not price_data:
                print("⚠️ 无法获取价格数据，跳过初始化")
                return False
            
            print(f"📋 检测到现有持仓，初始化监控信息...")
            print(f"   - 方向: {current_position['side']}仓")
            print(f"   - 数量: {current_position['size']} 张")
            print(f"   - 入场价: {current_position['entry_price']:.2f}")
            
            current_price = price_data['price']
            
            # 根据持仓方向创建临时signal_data
            signal = 'BUY' if current_position['side'] == 'long' else 'SELL'
            temp_signal_data = {
                'signal': signal,
                'confidence': 'MEDIUM',  # 默认中等信心
                'reason': '现有持仓初始化监控'
            }
            
            # 计算动态止损止盈（需要导入函数）
            import sys
            current_module = sys.modules[__name__]
            calculate_dynamic_stop_loss = getattr(current_module, 'calculate_dynamic_stop_loss', None)
            
            if not calculate_dynamic_stop_loss:
                print("⚠️ 无法访问calculate_dynamic_stop_loss函数，使用默认止损止盈")
                # 使用默认止损止盈（2%止损，3%止盈）
                if current_position['side'] == 'long':
                    stop_loss = current_position['entry_price'] * 0.98
                    take_profit = current_position['entry_price'] * 1.03
                else:  # short
                    stop_loss = current_position['entry_price'] * 1.02
                    take_profit = current_position['entry_price'] * 0.97
            else:
                stop_loss, take_profit = calculate_dynamic_stop_loss(temp_signal_data, price_data)
            
            # 先取消该交易对的所有旧策略订单（避免累积）
            try:
                print("🔄 初始化时取消该交易对的所有旧止盈止损订单...")
                cancel_tp_sl_orders(self.trade_config['symbol'], None)  # None表示取消所有
                time.sleep(0.5)  # 等待取消完成
            except Exception as e:
                print(f"⚠️ 取消旧订单时出错（继续执行）: {e}")
            
            # 设置止盈止损订单
            order_ids = None
            try:
                order_ids = set_tp_sl_orders(
                    self.trade_config['symbol'],
                    current_position['side'],
                    current_position['size'],
                    stop_loss,
                    take_profit,
                    current_position['entry_price']
                )
            except Exception as e:
                print(f"⚠️ 设置止盈止损订单时出错: {e}")
                print(f"⚠️ 将使用代码监控作为备用机制")
            
            # 🔧 修复：初始化保护轨道系统（现有持仓也需要）
            atr = price_data.get('technical_data', {}).get('atr', current_price * 0.01)
            self.atr_value = atr
            try:
                self.protection_orbit = ProtectionOrbit(
                    entry_price=current_position['entry_price'],  # 使用实际入场价
                    atr=atr,
                    position_side=current_position['side']
                )
                print(f"✅ 保护轨道系统已初始化（现有持仓）")
            except Exception as e:
                print(f"⚠️ 初始化保护轨道系统失败: {e}")
                self.protection_orbit = None
            
            # 初始化监控信息
            leverage = current_position.get('leverage', self.trade_config.get('leverage', 1))
            self.current_position_info = {
                'entry_price': current_position['entry_price'],  # 使用实际入场价
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_side': current_position['side'],
                'position_size': current_position['size'],
                'leverage': leverage,  # 存储杠杆信息
                'trailing_stop_activated': False,
                'highest_profit': current_price if current_position['side'] == 'long' else 0,
                'lowest_profit': current_price if current_position['side'] == 'short' else float('inf'),
                'update_time': datetime.now(),
                'peak_profit': 0,
                'tp_sl_order_ids': order_ids
            }
            
            # 🔧 修复：记录持仓开始时间（用于保护轨道系统）
            self.position_open_time = datetime.now()
            self.last_orbit_update_time = None  # 重置轨道更新时间
            
            # 计算当前盈亏，判断是否激活移动止盈
            # 获取杠杆信息
            leverage = current_position.get('leverage', self.trade_config.get('leverage', 1))
            
            if current_position['side'] == 'long':
                price_change_pct = (current_price - current_position['entry_price']) / current_position['entry_price'] * 100
                # 盈亏百分比 = 价格变化百分比 * 杠杆倍数
                profit_pct = price_change_pct * leverage
                if current_price > self.current_position_info['highest_profit']:
                    self.current_position_info['highest_profit'] = current_price
            else:  # short
                price_change_pct = (current_position['entry_price'] - current_price) / current_position['entry_price'] * 100
                # 盈亏百分比 = 价格变化百分比 * 杠杆倍数
                profit_pct = price_change_pct * leverage
                if current_price < self.current_position_info['lowest_profit']:
                    self.current_position_info['lowest_profit'] = current_price
            
            # 🔧 优化：根据趋势强度动态调整移动止盈激活条件
            trend_score = self.current_position_info.get('trend_score', 0)
            if trend_score >= 8:  # 极强趋势：0.5%就激活
                trailing_activation = 0.5
            elif trend_score >= 6:  # 强趋势：0.8%激活
                trailing_activation = 0.8
            else:  # 中等趋势：1%激活
                trailing_activation = 1.0
            
            if profit_pct > trailing_activation:
                if not self.current_position_info.get('trailing_stop_activated', False):
                    self.current_position_info['trailing_stop_activated'] = True
                    trend_desc = "极强趋势" if trend_score >= 8 else "强趋势" if trend_score >= 6 else "中等趋势"
                    print(f"🎯 移动止盈已激活（盈利{profit_pct:.2f}% > {trailing_activation:.1f}%，{trend_desc}）")
                self.current_position_info['peak_profit'] = profit_pct
            
            print(f"✅ 现有持仓监控已初始化:")
            print(f"   - 入场价: {current_position['entry_price']:.2f}")
            print(f"   - 当前价: {current_price:.2f}")
            print(f"   - 当前盈亏: {profit_pct:+.2f}%")
            print(f"   - 止损: {stop_loss:.2f}")
            print(f"   - 止盈: {take_profit:.2f}")
            print(f"   - 移动止盈: {'已激活' if self.current_position_info['trailing_stop_activated'] else '未激活'}")
            if order_ids:
                print(f"   - 止盈止损订单: 已设置 (TP: {order_ids.get('tp_order_id', 'N/A')}, SL: {order_ids.get('sl_order_id', 'N/A')})")
            else:
                print(f"   - 止盈止损订单: 使用代码监控")
            
            return True
            
        except Exception as e:
            print(f"❌ 初始化现有持仓监控失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _update_protection_orbits(self, current_price, profit_pct):
        """
        更新保护轨道（动态间隔调用）
        
        Args:
            current_price: 当前价格
            profit_pct: 当前盈亏百分比
        """
        if not self.protection_orbit:
            return
        
        try:
            # 计算持仓时间
            if self.position_open_time:
                time_elapsed = (datetime.now() - self.position_open_time).total_seconds()
            else:
                time_elapsed = 0
            
            # 🔧 优化v2：开仓后前5分钟（300秒）不更新轨道
            if time_elapsed < ORBIT_INITIAL_PROTECTION_TIME:
                return
            
            # 获取市场波动性和趋势强度（简化版本，可以从price_data获取）
            volatility = 0.5  # 默认值，可以从技术指标获取
            trend_strength = 0.5  # 默认值，可以从趋势分析获取
            
            # 更新轨道
            self.protection_orbit.update_orbits(
                current_price=current_price,
                time_elapsed=time_elapsed,
                profit_pct=profit_pct,
                volatility=volatility,
                trend_strength=trend_strength
            )
            
            # 更新内存中的止损和止盈
            orbits = self.protection_orbit.get_orbits()
            self.current_position_info['stop_loss'] = orbits['lower_orbit']
            self.current_position_info['take_profit'] = orbits['upper_orbit']
            
            self.last_orbit_update_time = datetime.now()
            
        except Exception as e:
            print(f"⚠️ 更新保护轨道失败: {e}")
    
    def _check_orbit_triggers(self, current_price, profit_pct):
        """
        检查轨道触发条件
        
        Args:
            current_price: 当前价格
            profit_pct: 当前盈亏百分比
        
        Returns:
            bool: 是否应该平仓
        """
        if not self.protection_orbit:
            return False
        
        try:
            # 🔧 优化v2：开仓后前3分钟（180秒）禁止保护轨道触发平仓
            if self.position_open_time:
                time_elapsed = (datetime.now() - self.position_open_time).total_seconds()
                if time_elapsed < ORBIT_MIN_TRIGGER_TIME:
                    return False
            
            orbits = self.protection_orbit.get_orbits()
            upper_orbit = orbits['upper_orbit']
            lower_orbit = orbits['lower_orbit']
            position_side = self.current_position_info['position_side']
            
            if position_side == 'long':
                # 多头：检查止盈和止损
                if current_price >= upper_orbit:
                    # 🔧 修复：检查扣除手续费后的实际盈亏
                    actual_profit_pct = self._calculate_actual_profit_with_fees(current_price, profit_pct)
                    if actual_profit_pct > 0:
                        print(f"🎯 止盈轨道触发: {current_price:.2f} >= {upper_orbit:.2f}, 实际盈亏={actual_profit_pct:.2f}% (扣除手续费后)")
                        return True
                    else:
                        print(f"⚠️ 止盈轨道已触发但扣除手续费后亏损: 浮盈={profit_pct:.2f}%, 实际={actual_profit_pct:.2f}%, 继续持仓")
                if current_price <= lower_orbit:
                    print(f"🚨 止损轨道触发: {current_price:.2f} <= {lower_orbit:.2f}")
                    return True
            else:  # short
                # 空头：检查止盈和止损
                if current_price <= upper_orbit:
                    # 🔧 修复：检查扣除手续费后的实际盈亏
                    actual_profit_pct = self._calculate_actual_profit_with_fees(current_price, profit_pct)
                    if actual_profit_pct > 0:
                        print(f"🎯 止盈轨道触发: {current_price:.2f} <= {upper_orbit:.2f}, 实际盈亏={actual_profit_pct:.2f}% (扣除手续费后)")
                        return True
                    else:
                        print(f"⚠️ 止盈轨道已触发但扣除手续费后亏损: 浮盈={profit_pct:.2f}%, 实际={actual_profit_pct:.2f}%, 继续持仓")
                if current_price >= lower_orbit:
                    print(f"🚨 止损轨道触发: {current_price:.2f} >= {lower_orbit:.2f}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ 检查轨道触发条件失败: {e}")
            return False
    
    def _sync_orbits_to_exchange(self):
        """
        同步轨道到OKX交易所
        
        每60秒更新一次保护轨道订单
        """
        if not self.protection_orbit:
            return
        
        # 检查更新频率
        now = datetime.now()
        if self.last_order_update_time:
            time_since_last_update = (now - self.last_order_update_time).total_seconds()
            if time_since_last_update < self.min_update_interval:
                return  # 距离上次更新不足60秒，跳过
        
        try:
            orbits = self.protection_orbit.get_orbits()
            upper_orbit = orbits['upper_orbit']
            lower_orbit = orbits['lower_orbit']
            
            # 更新OKX订单
            new_order_ids = update_tp_sl_orders(
                self.trade_config['symbol'],
                self.current_position_info['position_side'],
                self.current_position_info['position_size'],
                lower_orbit,  # 止损轨道
                upper_orbit,  # 止盈轨道
                self.current_position_info['tp_sl_order_ids']  # 旧订单ID
            )
            
            if new_order_ids:
                # 只有当订单真正成功时才更新
                if new_order_ids.get('sl_order_id') and new_order_ids.get('tp_order_id'):
                    self.current_position_info['tp_sl_order_ids'] = new_order_ids
                    self.last_order_update_time = now
                    print(f"✅ 保护轨道已同步到交易所: 止盈={upper_orbit:.2f}, 止损={lower_orbit:.2f}")
                else:
                    print(f"⚠️ 部分订单更新失败，保持原订单")
            else:
                print(f"⚠️ 订单更新失败，继续使用代码监控")
                
        except Exception as e:
            print(f"⚠️ 同步轨道到交易所失败: {e}")
    
    def _monitor_loop(self):
        """监控主循环"""
        while self.is_monitoring:
            try:
                # 🔧 修复：验证实际持仓状态，如果实际无持仓但内存中有信息，则清空内存信息，防止残留订单
                # 🔧 新增：添加开仓保护期和重试机制，避免数据同步延迟误判
                try:
                    # 检查是否在开仓保护期内
                    is_in_protection_period = False
                    if self.position_open_time:
                        time_elapsed = (datetime.now() - self.position_open_time).total_seconds()
                        if time_elapsed < POSITION_VERIFY_PROTECTION_SECONDS:
                            is_in_protection_period = True
                    
                    actual_position = get_current_position()
                    if not actual_position or actual_position['size'] <= 0:
                        # 实际无持仓，但内存中可能有残留信息
                        if self.current_position_info['position_side'] or self.current_position_info['position_size'] > 0:
                            if is_in_protection_period:
                                # 保护期内：只记录警告，不执行清仓，重置失败计数
                                time_elapsed = (datetime.now() - self.position_open_time).total_seconds()
                                print(f"⚠️ 保护期内检测到实际无持仓但内存中有持仓信息（开仓后{time_elapsed:.1f}秒），可能是数据同步延迟，跳过验证")
                                self.position_verify_fail_count = 0  # 重置失败计数
                            else:
                                # 保护期外：增加失败计数，连续失败3次才清仓
                                self.position_verify_fail_count += 1
                                print(f"⚠️ 检测到实际无持仓但内存中有持仓信息（失败次数: {self.position_verify_fail_count}/{POSITION_VERIFY_FAIL_THRESHOLD}）")
                                
                                if self.position_verify_fail_count >= POSITION_VERIFY_FAIL_THRESHOLD:
                                    print(f"⚠️ 连续{self.position_verify_fail_count}次验证失败，清空内存信息，避免残留订单")
                                    self.clear_position_info()
                                    self.position_verify_fail_count = 0  # 重置计数
                        else:
                            # 内存中也没有持仓信息，重置失败计数
                            self.position_verify_fail_count = 0
                        time.sleep(self.monitor_interval)
                        continue
                    else:
                        # 验证成功，重置失败计数
                        if self.position_verify_fail_count > 0:
                            print(f"✅ 持仓验证成功，重置失败计数（之前失败{self.position_verify_fail_count}次）")
                        self.position_verify_fail_count = 0
                    
                    # 验证持仓方向是否匹配（保护期外才执行严格验证）
                    if not is_in_protection_period and self.current_position_info['position_side']:
                        if actual_position['side'] != self.current_position_info['position_side']:
                            print(f"⚠️ 检测到持仓方向不匹配（实际: {actual_position['side']}, 内存: {self.current_position_info['position_side']}），清空内存信息")
                            self.clear_position_info()
                            self.position_verify_fail_count = 0  # 重置计数
                            time.sleep(self.monitor_interval)
                            continue
                except Exception as e:
                    print(f"⚠️ 验证实际持仓时出错: {e}")
                    # 验证失败时继续执行，但记录错误
                    # 不在保护期内时才增加失败计数
                    if self.position_open_time:
                        time_elapsed = (datetime.now() - self.position_open_time).total_seconds()
                        if time_elapsed >= POSITION_VERIFY_PROTECTION_SECONDS:
                            self.position_verify_fail_count += 1
                
                # 只有有持仓时才监控
                if self.current_position_info['position_side'] and self.current_position_info['position_size'] > 0:
                    # 检查价格条件（包含轨道触发检查）
                    self._check_price_conditions()
                    
                    # 每60秒更新一次保护轨道
                    now = datetime.now()
                    if not self.last_orbit_update_time or (now - self.last_orbit_update_time).total_seconds() >= ORBIT_UPDATE_INTERVAL:
                        # 获取当前价格和盈亏用于更新轨道
                        try:
                            ticker = self.exchange.fetch_ticker(self.trade_config['symbol'])
                            current_price = ticker['last']
                            
                            # 计算当前盈亏
                            position = self.current_position_info
                            leverage = position.get('leverage', 1)
                            if position['position_side'] == 'long':
                                price_change_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
                            else:
                                price_change_pct = (position['entry_price'] - current_price) / position['entry_price'] * 100
                            profit_pct = price_change_pct * leverage
                            
                            # 更新保护轨道
                            self._update_protection_orbits(current_price, profit_pct)
                            
                            # 同步到交易所
                            self._sync_orbits_to_exchange()
                            
                        except Exception as e:
                            print(f"⚠️ 更新保护轨道时出错: {e}")
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                print(f"❌ 价格监控异常: {e}")
                time.sleep(self.monitor_interval)
    
    def _check_price_conditions(self):
        """检查价格条件"""
        try:
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(self.trade_config['symbol'])
            current_price = ticker['last']
            
            position = self.current_position_info
            if not position['position_side']:
                return
            
            # 计算当前盈亏
            # 优先使用position中存储的杠杆（最可靠）
            leverage = position.get('leverage', 1)
            
            # 尝试获取实际持仓信息以获取实际盈亏
            try:
                actual_position = get_current_position()
                if actual_position:
                    # 使用实际的未实现盈亏
                    unrealized_pnl = actual_position.get('unrealized_pnl', 0)
                    # 如果实际持仓有杠杆信息，使用实际杠杆（更准确）
                    if actual_position.get('leverage'):
                        leverage = actual_position.get('leverage')
                else:
                    unrealized_pnl = 0
            except Exception as e:
                unrealized_pnl = 0
            
            # 计算价格变化百分比
            if position['position_side'] == 'long':
                price_change_pct = (current_price - position['entry_price']) / position['entry_price'] * 100
            else:  # short
                price_change_pct = (position['entry_price'] - current_price) / position['entry_price'] * 100
            
            # 盈亏百分比 = 价格变化百分比 * 杠杆倍数（考虑杠杆后的实际盈亏）
            profit_pct = price_change_pct * leverage
            
            # 如果无法获取实际盈亏，使用计算值
            if unrealized_pnl == 0:
                if position['position_side'] == 'long':
                    unrealized_pnl = (current_price - position['entry_price']) * position['position_size'] * self.trade_config.get('contract_size', 0.01)
                else:  # short
                    unrealized_pnl = (position['entry_price'] - current_price) * position['position_size'] * self.trade_config.get('contract_size', 0.01)
            
            # 计算实际盈利（扣除手续费）
            actual_profit_pct = self._calculate_actual_profit_with_fees(current_price, profit_pct)
            
            # 详细的监控日志输出（包含杠杆信息用于调试）
            print(f"🔍 价格监控: {current_price:.2f} | 盈亏: {profit_pct:+.2f}% (实际: {actual_profit_pct:+.2f}%) | 浮动: {unrealized_pnl:+.2f} USDT")
            print(f"   📌 入场价: {position['entry_price']:.2f}")
            print(f"   🛑 止损价: {position['stop_loss']:.2f} | 距离: {abs(current_price - position['stop_loss']):.2f}")
            print(f"   🎯 止盈价: {position['take_profit']:.2f} | 距离: {abs(current_price - position['take_profit']):.2f}")
            
            # 锁定止损详细信息
            if self.lock_stop_loss_config['activated']:
                lock_status = "🔒 已激活"
                if self.lock_stop_loss_config['locked_stop_price'] > 0:
                    lock_status += f" | 锁定价: {self.lock_stop_loss_config['locked_stop_price']:.2f}"
            else:
                threshold = self.lock_stop_loss_config['profit_threshold'] * 100
                lock_status = f"⏸️ 未激活 (需盈利≥{threshold:.1f}%，当前: {actual_profit_pct:.2f}%)"
            
            print(f"   {lock_status}")
            if self.lock_stop_loss_config['breakeven_price'] > 0:
                print(f"   💰 盈亏平衡: {self.lock_stop_loss_config['breakeven_price']:.2f}")
            if self.lock_stop_loss_config['peak_profit_price'] > 0:
                peak_label = "历史最高价" if position['position_side'] == 'long' else "历史最低价"
                print(f"   📊 {peak_label}: {self.lock_stop_loss_config['peak_profit_price']:.2f}")
            
            # 盈利平仓状态
            profit_config = self.profit_taking_config
            if profit_config['partial_close_2_executed']:
                profit_status = "✅ 已全部平仓(4%)"
            elif profit_config['partial_close_1_executed']:
                profit_status = f"🟡 已平仓一半(2%) | 等待4% ({actual_profit_pct:.2f}%)"
            else:
                threshold_1 = profit_config['partial_close_threshold_1'] * 100
                threshold_2 = profit_config['partial_close_threshold_2'] * 100
                profit_status = f"⏳ 等待盈利: {threshold_1:.0f}%/{threshold_2:.0f}% (当前: {actual_profit_pct:.2f}%)"
            
            print(f"   💰 盈利平仓: {profit_status}")
            
            # 🔧 优化：移动止盈信息（根据趋势强度显示动态回撤窗口）
            if position['trailing_stop_activated']:
                trailing_window = position.get('trailing_window', 0.005)  # 默认0.5%
                if position['position_side'] == 'long':
                    trailing_stop = position['highest_profit'] * (1 - trailing_window)
                    print(f"   📈 移动止盈: 最高价 {position['highest_profit']:.2f} | 触发价 {trailing_stop:.2f} | 回撤窗口: {trailing_window*100:.1f}%")
                else:  # short
                    trailing_stop = position['lowest_profit'] * (1 + trailing_window)
                    print(f"   📉 移动止盈: 最低价 {position['lowest_profit']:.2f} | 触发价 {trailing_stop:.2f} | 回撤窗口: {trailing_window*100:.1f}%")
            else:
                trend_score = position.get('trend_score', 0)
                if trend_score >= 8:
                    activation_threshold = 0.5
                elif trend_score >= 6:
                    activation_threshold = 0.8
                else:
                    activation_threshold = 1.0
                print(f"   ⏸️  移动止盈: 未激活 (需盈利>{activation_threshold:.1f}%，当前: {profit_pct:.2f}%)")
            
            # 峰值盈利信息
            if position.get('peak_profit', 0) > 0:
                print(f"   📊 峰值盈利: {position['peak_profit']:.2f}%")
            
            # 检查止损止盈条件
            if self._should_close_position(current_price, profit_pct):
                self._execute_emergency_close(current_price, profit_pct)
                # 🔧 修复：平仓后立即返回，避免继续执行订单更新逻辑，防止创建残留订单
                return
            
            # 检查盈利平仓条件（在止损检查之后，止盈检查之前）
            self._check_profit_taking_conditions(current_price, actual_profit_pct, position)
            
            # 更新移动止盈止损
            self._update_trailing_stops(current_price, profit_pct)
            
            # 🔧 新增：实时更新滑动止损到交易所（窄窗口+频繁滑动策略）
            self._update_sliding_stop_loss_to_exchange(current_price, profit_pct)
            
            # 🔧 新增：将移动止盈止损位同步到交易所
            self._update_trailing_stop_to_exchange(current_price, profit_pct)
            
        except Exception as e:
            print(f"❌ 价格检查失败: {e}")
    
    def _calculate_actual_profit_with_fees(self, current_price, profit_pct):
        """
        计算扣除手续费后的实际盈亏百分比
        
        Args:
            current_price: 当前价格
            profit_pct: 未实现盈亏百分比（已考虑杠杆）
        
        Returns:
            float: 扣除手续费后的实际盈亏百分比
        """
        position = self.current_position_info
        entry_price = position.get('entry_price', 0)
        position_size = position.get('position_size', 0)
        contract_size = self.trade_config.get('contract_size', 0.01)
        
        if entry_price <= 0 or position_size <= 0:
            # 如果无法获取有效数据，使用简化的手续费估算
            return profit_pct - (TRADING_FEE_RATE * 100)
        
        # 计算开仓名义价值
        entry_notional = position_size * contract_size * entry_price
        
        # 计算平仓名义价值
        exit_notional = position_size * contract_size * current_price
        
        # 计算手续费（都是Taker订单，费率0.05%）
        TAKER_FEE_RATE = 0.0005  # 0.05%
        entry_fee = entry_notional * TAKER_FEE_RATE
        exit_fee = exit_notional * TAKER_FEE_RATE
        total_fee = entry_fee + exit_fee
        
        # 计算手续费百分比（相对于开仓名义价值）
        fee_pct = (total_fee / entry_notional) * 100 if entry_notional > 0 else 0
        
        # 计算实际盈亏百分比
        actual_profit_pct = profit_pct - fee_pct
        
        return actual_profit_pct
    
    def _validate_stop_loss_price(self, stop_loss_price, current_price, position_side):
        """
        验证止损价合理性
        
        Args:
            stop_loss_price: 止损价格
            current_price: 当前价格
            position_side: 持仓方向 'long' or 'short'
        
        Returns:
            bool: 是否有效
        """
        if stop_loss_price <= 0:
            return False
        
        if position_side == 'long':
            # 🔧 修复：多头止损价验证，从99.5%放宽到98.5%，允许更大的止损距离
            if stop_loss_price >= current_price * 0.985:
                return False
        else:  # short
            # 🔧 修复：空头止损价验证，从100.5%放宽到101.5%，允许更大的止损距离
            if stop_loss_price <= current_price * 1.015:
                return False
        
        return True
    
    def _is_stop_loss_improvement(self, new_stop_loss, current_stop_loss, position_side):
        """
        检查新止损价是否是对当前止损价的改善
        
        多头：新止损价 > 当前止损价（上移）
        空头：新止损价 < 当前止损价（下移）
        
        Args:
            new_stop_loss: 新止损价
            current_stop_loss: 当前止损价
            position_side: 持仓方向
        
        Returns:
            bool: 是否改善
        """
        if position_side == 'long':
            improvement = new_stop_loss > current_stop_loss * 1.001  # 至少提高0.1%
            direction = "上移" if improvement else "未上移"
        else:  # short
            improvement = new_stop_loss < current_stop_loss * 0.999  # 至少降低0.1%
            direction = "下移" if improvement else "未下移"
        
        print(f"   🔄 止损改善检查: {current_stop_loss:.2f} → {new_stop_loss:.2f} [{direction}]")
        return improvement
    
    def _get_dynamic_lock_ratio(self, actual_profit_pct):
        """
        🔧 优化v2：根据盈利百分比获取动态锁定比例
        
        Args:
            actual_profit_pct: 实际盈利百分比（扣除手续费后）
        
        Returns:
            float: 锁定比例（0-1之间）
        """
        profit_decimal = actual_profit_pct / 100
        
        for level_name, level_config in LOCK_STOP_LOSS_RATIOS.items():
            if level_config['min_profit'] <= profit_decimal < level_config['max_profit']:
                return level_config['ratio']
        
        # 默认返回最高比例
        return LOCK_STOP_LOSS_RATIOS['high']['ratio']
    
    def _calculate_locked_stop_loss(self, current_price, actual_profit_pct):
        """
        计算锁定止损价格 - 🔧 修复：基于历史最高盈利点计算，确保不回退
        🔧 优化v2：使用分段锁定比例（盈利越高，锁定比例越大）
        
        Args:
            current_price: 当前价格
            actual_profit_pct: 实际盈利百分比（扣除手续费后）
        
        Returns:
            float or None: 锁定止损价，如果无效则返回None
        """
        position = self.current_position_info
        config = self.lock_stop_loss_config
        breakeven_price = config['breakeven_price']
        
        if breakeven_price <= 0:
            print(f"   ⚠️ 盈亏平衡价无效: {breakeven_price:.2f}")
            return None
        
        # 🔧 优化v2：获取动态锁定比例
        dynamic_lock_ratio = self._get_dynamic_lock_ratio(actual_profit_pct)
        if dynamic_lock_ratio != config['lock_ratio']:
            print(f"   🎯 使用动态锁定比例: {dynamic_lock_ratio*100:.0f}% (盈利: {actual_profit_pct:.2f}%)")
        
        # 🔧 关键修复：更新历史最高盈利点价格
        if position['position_side'] == 'long':
            # 多头：记录历史最高价格
            if config['peak_profit_price'] == 0 or current_price > config['peak_profit_price']:
                old_peak = config['peak_profit_price']
                config['peak_profit_price'] = current_price
                if old_peak > 0:
                    print(f"   📈 更新历史最高价: {old_peak:.2f} → {current_price:.2f}")
                else:
                    print(f"   📈 记录历史最高价: {current_price:.2f}")
        else:  # short
            # 空头：记录历史最低价格（对空头来说是最有利的）
            if config['peak_profit_price'] == 0 or current_price < config['peak_profit_price']:
                old_peak = config['peak_profit_price']
                config['peak_profit_price'] = current_price
                if old_peak > 0:
                    print(f"   📉 更新历史最低价: {old_peak:.2f} → {current_price:.2f}")
                else:
                    print(f"   📉 记录历史最低价: {current_price:.2f}")
        
        # 🔧 关键修复：使用历史最高盈利点价格计算，而不是当前价格
        peak_price = config['peak_profit_price']
        if peak_price == 0:
            peak_price = current_price  # 如果没有记录，使用当前价格
        
        print(f"🔧 锁定止损计算:")
        print(f"   - 持仓方向: {position['position_side']}")
        print(f"   - 入场价: {position['entry_price']:.2f}")
        print(f"   - 盈亏平衡价: {breakeven_price:.2f}")
        print(f"   - 当前价格: {current_price:.2f}")
        print(f"   - 历史最高盈利点: {peak_price:.2f}")
        print(f"   - 实际盈利: {actual_profit_pct:.2f}%")
        
        if position['position_side'] == 'long':
            # 多头锁定止损计算 - 基于历史最高价格
            if config['locked_stop_price'] == 0:
                # 首次计算：使用盈亏平衡点 + 缓冲
                locked_stop = breakeven_price * (1 + config['buffer_ratio'])
                print(f"   - 首次锁定: 盈亏平衡{breakeven_price:.2f} + 缓冲{config['buffer_ratio']*100:.1f}% = {locked_stop:.2f}")
            else:
                # 后续计算：使用历史最高价格和动态锁定比例
                price_range = peak_price - breakeven_price
                locked_stop = breakeven_price + (price_range * dynamic_lock_ratio)
                print(f"   - 比例锁定: {breakeven_price:.2f} + ({peak_price:.2f}-{breakeven_price:.2f})×{dynamic_lock_ratio*100:.0f}% = {locked_stop:.2f}")
            
            # 确保最小锁定距离
            min_lock_price = breakeven_price * (1 + config['min_lock_distance'])
            if locked_stop < min_lock_price:
                print(f"   - 应用最小锁定距离: {locked_stop:.2f} → {min_lock_price:.2f}")
                locked_stop = min_lock_price
            
            # 🔧 关键修复：确保不低于当前止损价（只能上移，不能回退）
            # 如果计算出的止损价低于当前止损价，使用当前止损价（保持不回退）
            if locked_stop < position['stop_loss']:
                print(f"   - 价格回撤，保持止损价不变: {locked_stop:.2f} < 当前止损 {position['stop_loss']:.2f}")
                locked_stop = position['stop_loss']  # 保持当前止损价，不回退
            
            # 确保不超过当前价格的安全范围
            max_allowed_stop = current_price * 0.995  # 当前价格的99.5%
            if locked_stop >= max_allowed_stop:
                print(f"   - OKX限制: 不能高于当前价格{current_price:.2f}的99.5% ({max_allowed_stop:.2f})")
                locked_stop = max_allowed_stop
                # 如果被限制后的止损价低于当前止损价，保持当前止损价
                if locked_stop < position['stop_loss']:
                    print(f"   - 限制后止损价低于当前止损，保持当前止损价: {position['stop_loss']:.2f}")
                    locked_stop = position['stop_loss']
                
        else:  # short - 修复空头逻辑
            if config['locked_stop_price'] == 0:
                # 首次计算：使用盈亏平衡点 - 缓冲
                locked_stop = breakeven_price * (1 - config['buffer_ratio'])
                print(f"   - 首次锁定: 盈亏平衡{breakeven_price:.2f} - 缓冲{config['buffer_ratio']*100:.1f}% = {locked_stop:.2f}")
            else:
                # 后续计算：使用历史最低价格（对空头最有利）和动态锁定比例
                price_range = breakeven_price - peak_price
                locked_stop = breakeven_price - (price_range * dynamic_lock_ratio)
                print(f"   - 比例锁定: {breakeven_price:.2f} - ({breakeven_price:.2f}-{peak_price:.2f})×{dynamic_lock_ratio*100:.0f}% = {locked_stop:.2f}")
            
            # 确保最小锁定距离
            min_lock_price = breakeven_price * (1 - config['min_lock_distance'])
            if locked_stop > min_lock_price:
                print(f"   - 应用最小锁定距离: {locked_stop:.2f} → {min_lock_price:.2f}")
                locked_stop = min_lock_price
            
            # 🔧 修复空头OKX限制：止损价不能低于当前价格的100.5%
            min_allowed_stop = current_price * 1.005  # 当前价格的100.5%
            if locked_stop < min_allowed_stop:
                print(f"   - OKX限制: 不能低于当前价格{current_price:.2f}的100.5% ({min_allowed_stop:.2f})")
                locked_stop = min_allowed_stop
            
            # 🔧 关键修复：确保不超过当前止损价（空头只能下移，即数值变小）
            # 如果计算出的止损价高于当前止损价，使用当前止损价（保持不回退）
            if locked_stop > position['stop_loss']:
                print(f"   - 价格回撤，保持止损价不变: {locked_stop:.2f} > 当前止损 {position['stop_loss']:.2f}")
                locked_stop = position['stop_loss']  # 保持当前止损价，不回退
        
        print(f"   ✅ 最终锁定止损价: {locked_stop:.2f}")
        return locked_stop
    
    def _calculate_sliding_stop_loss(self, current_price, profit_pct, position):
        """
        计算滑动止损价格（原有逻辑）
        
        Args:
            current_price: 当前价格
            profit_pct: 盈亏百分比
            position: 持仓信息
        
        Returns:
            tuple: (new_stop_loss, should_update, stop_reason)
        """
        new_stop_loss = None
        should_update = False
        stop_reason = "滑动止损"
        
        if position['position_side'] == 'long':
            # 多头：价格有利时，止损位上移
            if profit_pct > 0.3:  # 盈利超过0.3%时开始滑动
                # 新的止损位：至少保护0.2%利润，或使用入场价+0.2%
                new_stop_loss = max(
                    position['entry_price'] * 1.002,  # 至少保护0.2%利润
                    position['stop_loss']  # 不能低于当前止损
                )
                
                # 🔧 修复：新止损不能高于当前价格（标记价格），否则OKX会拒绝
                max_allowed_stop = current_price * 0.995  # 当前价格的99.5%
                if new_stop_loss >= max_allowed_stop:
                    new_stop_loss = max_allowed_stop
                    print(f"⚠️ 滑动止损被限制：不能高于当前价格，使用 {new_stop_loss:.2f} (当前价: {current_price:.2f})")
                    if new_stop_loss <= position['stop_loss'] * 1.001:
                        should_update = False
                        print(f"⚠️ 限制后的止损价不高于当前止损，跳过更新")
                
                # 只有当新止损位明显高于当前止损时才更新（至少提高0.1%）
                if new_stop_loss > position['stop_loss'] * 1.001:
                    should_update = True
                    print(f"📈 滑动止损：当前止损 {position['stop_loss']:.2f} → 新止损 {new_stop_loss:.2f} (保护利润: {profit_pct:.2f}%)")
        
        else:  # short
            # 空头：价格有利时，止损位下移
            if profit_pct > 0.3:  # 盈利超过0.3%时开始滑动
                # 新的止损位：至少保护0.2%利润，或使用入场价-0.2%
                new_stop_loss = min(
                    position['entry_price'] * 0.998,  # 至少保护0.2%利润
                    position['stop_loss']  # 不能高于当前止损
                )
                
                # 🔧 修复：新止损不能低于当前价格（标记价格），否则OKX会拒绝
                min_allowed_stop = current_price * 1.005  # 当前价格的100.5%
                if new_stop_loss <= min_allowed_stop:
                    new_stop_loss = min_allowed_stop
                    print(f"⚠️ 滑动止损被限制：不能低于当前价格，使用 {new_stop_loss:.2f} (当前价: {current_price:.2f})")
                    if new_stop_loss >= position['stop_loss'] * 0.999:
                        should_update = False
                        print(f"⚠️ 限制后的止损价不低于当前止损，跳过更新")
                
                # 只有当新止损位明显低于当前止损时才更新（至少降低0.1%）
                if new_stop_loss < position['stop_loss'] * 0.999:
                    should_update = True
                    print(f"📉 滑动止损：当前止损 {position['stop_loss']:.2f} → 新止损 {new_stop_loss:.2f} (保护利润: {profit_pct:.2f}%)")
        
        return new_stop_loss, should_update, stop_reason
    
    def _should_close_position(self, current_price, profit_pct):
        """判断是否应该平仓"""
        position = self.current_position_info
        
        # 🔧 优先检查轨道触发条件（智能移动止盈止损系统）
        if self.protection_orbit:
            if self._check_orbit_triggers(current_price, profit_pct):
                return True
        
        # 🔧 安全检查：验证止损价的合理性，防止因内存中的错误止损价导致误触发
        if position['position_side'] == 'long':
            # 多头：止损价应该低于当前价格
            if position['stop_loss'] > current_price:
                print(f"⚠️ 警告：内存中的止损价 {position['stop_loss']:.2f} 高于当前价格 {current_price:.2f}，忽略该止损价（可能是滑动止损更新失败导致）")
                # 不触发止损，继续监控
            else:
                # 多头止损
                if current_price <= position['stop_loss']:
                    print(f"🚨 多头止损触发: {current_price:.2f} <= {position['stop_loss']:.2f}")
                    return True
        else:  # short
            # 空头：止损价应该高于当前价格
            if position['stop_loss'] < current_price:
                print(f"⚠️ 警告：内存中的止损价 {position['stop_loss']:.2f} 低于当前价格 {current_price:.2f}，忽略该止损价（可能是滑动止损更新失败导致）")
                # 不触发止损，继续监控
            else:
                # 空头止损
                if current_price >= position['stop_loss']:
                    print(f"🚨 空头止损触发: {current_price:.2f} >= {position['stop_loss']:.2f}")
                    return True
        
        # 止盈检查（不受安全检查影响）- 🔧 修复：考虑手续费
        if position['position_side'] == 'long':
            # 多头止盈：检查价格是否达到止盈价，且扣除手续费后仍盈利
            if current_price >= position['take_profit']:
                # 计算扣除手续费后的实际盈亏百分比
                actual_profit_pct = self._calculate_actual_profit_with_fees(current_price, profit_pct)
                if actual_profit_pct > 0:
                    print(f"🎯 多头止盈触发: {current_price:.2f} >= {position['take_profit']:.2f}, 实际盈亏={actual_profit_pct:.2f}% (扣除手续费后)")
                    return True
                else:
                    print(f"⚠️ 止盈价已触发但扣除手续费后亏损: 浮盈={profit_pct:.2f}%, 实际={actual_profit_pct:.2f}%, 继续持仓")
        else:  # short
            # 空头止盈：检查价格是否达到止盈价，且扣除手续费后仍盈利
            if current_price <= position['take_profit']:
                # 计算扣除手续费后的实际盈亏百分比
                actual_profit_pct = self._calculate_actual_profit_with_fees(current_price, profit_pct)
                if actual_profit_pct > 0:
                    print(f"🎯 空头止盈触发: {current_price:.2f} <= {position['take_profit']:.2f}, 实际盈亏={actual_profit_pct:.2f}% (扣除手续费后)")
                    return True
                else:
                    print(f"⚠️ 止盈价已触发但扣除手续费后亏损: 浮盈={profit_pct:.2f}%, 实际={actual_profit_pct:.2f}%, 继续持仓")
        
        # 移动止盈检查
        if position['trailing_stop_activated']:
            if position['position_side'] == 'long':
                trailing_stop = position['highest_profit'] * 0.995  # 回撤0.5%平仓
                if current_price <= trailing_stop:
                    print(f"📉 多头移动止盈触发: {current_price:.2f} <= {trailing_stop:.2f}")
                    return True
            else:
                trailing_stop = position['lowest_profit'] * 1.005  # 回撤0.5%平仓
                if current_price >= trailing_stop:
                    print(f"📉 空头移动止盈触发: {current_price:.2f} >= {trailing_stop:.2f}")
                    return True
        
        # 紧急风控：单笔亏损超过5%
        if profit_pct < -5:
            print(f"🚨 紧急风控: 亏损超过5% ({profit_pct:.2f}%)")
            return True
            
        # 紧急风控：盈利回撤超过50%
        if profit_pct > 2 and profit_pct < position.get('peak_profit', 0) * 0.5:
            print(f"📉 盈利回撤过大: 当前{profit_pct:.2f}%, 峰值{position.get('peak_profit', 0):.2f}%")
            return True
            
        return False
    
    def _check_profit_taking_conditions(self, current_price, actual_profit_pct, position):
        """
        检查盈利平仓条件
        🔧 优化：根据趋势强度动态调整分批止盈阈值
        
        Args:
            current_price: 当前价格
            actual_profit_pct: 实际盈利百分比（扣除手续费后）
            position: 持仓信息
        """
        config = self.profit_taking_config
        
        # 🔧 优化：根据趋势强度动态调整分批止盈阈值
        trend_score = position.get('trend_score', 0)  # 从持仓信息中获取趋势强度
        
        if trend_score >= 8:  # 极强趋势：让利润奔跑更多
            threshold_1 = 0.03  # 3%平仓一半
            threshold_2 = 0.06  # 6%平仓全部
            trend_desc = "极强趋势"
        elif trend_score >= 6:  # 强趋势
            threshold_1 = 0.025  # 2.5%平仓一半
            threshold_2 = 0.05   # 5%平仓全部
            trend_desc = "强趋势"
        else:  # 中等趋势：使用默认值
            threshold_1 = config['partial_close_threshold_1']  # 2%平仓一半
            threshold_2 = config['partial_close_threshold_2']  # 4%平仓全部
            trend_desc = "中等趋势"
        
        # 检查平仓间隔
        now = datetime.now()
        if config['last_partial_close_time']:
            time_since_last_close = (now - config['last_partial_close_time']).total_seconds()
            if time_since_last_close < config['min_close_interval']:
                return
        
        # 检查第二次平仓条件
        if (not config['partial_close_2_executed'] and 
            actual_profit_pct >= threshold_2 * 100):
            
            print(f"🎯 触发盈利平仓条件2({trend_desc}): 盈利{actual_profit_pct:.2f}% ≥ {threshold_2*100:.1f}%")
            self._execute_profit_taking(current_price, 1.0, f"盈利{threshold_2*100:.1f}%平仓全部({trend_desc})")
            config['partial_close_2_executed'] = True
            config['last_partial_close_time'] = now
            return
        
        # 检查第一次平仓条件
        if (not config['partial_close_1_executed'] and 
            actual_profit_pct >= threshold_1 * 100):
            
            print(f"🎯 触发盈利平仓条件1({trend_desc}): 盈利{actual_profit_pct:.2f}% ≥ {threshold_1*100:.1f}%")
            self._execute_profit_taking(current_price, config['partial_close_ratio_1'], f"盈利{threshold_1*100:.1f}%平仓一半({trend_desc})")
            config['partial_close_1_executed'] = True
            config['last_partial_close_time'] = now
    
    def _execute_profit_taking(self, current_price, close_ratio, reason):
        """
        执行盈利平仓
        
        Args:
            current_price: 当前价格
            close_ratio: 平仓比例 (0.0-1.0)
            reason: 平仓原因
        """
        position = self.current_position_info
        config = self.profit_taking_config
        
        if not position['position_side'] or position['position_size'] <= 0:
            print("⚠️ 无持仓，跳过盈利平仓")
            return
        
        try:
            # 计算平仓数量
            close_size = position['position_size'] * close_ratio
            close_size = round(close_size, 2)  # 保留2位小数
            
            # 确保不低于最小平仓数量
            if close_size < config['min_partial_close_size']:
                close_size = config['min_partial_close_size']
                print(f"⚠️ 平仓数量调整到最小值: {close_size}")
            
            # 确保不超过当前持仓
            if close_size > position['position_size']:
                close_size = position['position_size']
                print(f"⚠️ 平仓数量调整到持仓总量: {close_size}")
            
            print(f"💰 执行盈利平仓: {close_size:.2f}张 ({close_ratio*100:.0f}%) - {reason}")
            
            # 执行平仓
            if position['position_side'] == 'long':
                self.exchange.create_market_order(
                    self.trade_config['symbol'],
                    'sell',
                    close_size,
                    params={'reduceOnly': True}
                )
            else:  # short
                self.exchange.create_market_order(
                    self.trade_config['symbol'],
                    'buy',
                    close_size,
                    params={'reduceOnly': True}
                )
            
            print(f"✅ 盈利平仓成功: {close_size:.2f}张 @ {current_price:.2f}")
            
            # 更新持仓信息
            remaining_size = position['position_size'] - close_size
            
            if remaining_size <= 0.001:  # 接近0，视为全部平仓
                print("🎯 持仓已全部平仓")
                self.clear_position_info()
            else:
                # 更新持仓数量
                position['position_size'] = remaining_size
                print(f"📊 剩余持仓: {remaining_size:.2f}张")
                
                # 更新止盈止损订单（因为持仓数量变化）
                self._update_tp_sl_for_partial_close(remaining_size)
                
        except Exception as e:
            print(f"❌ 盈利平仓失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_tp_sl_for_partial_close(self, new_position_size):
        """
        部分平仓后更新止盈止损订单
        
        Args:
            new_position_size: 新的持仓数量
        """
        position = self.current_position_info
        
        try:
            # 取消旧订单
            if position['tp_sl_order_ids']:
                cancel_tp_sl_orders(self.trade_config['symbol'], position['tp_sl_order_ids'])
                time.sleep(0.3)
            
            # 设置新订单（使用新的持仓数量）
            new_order_ids = set_tp_sl_orders(
                self.trade_config['symbol'],
                position['position_side'],
                new_position_size,
                position['stop_loss'],
                position['take_profit'],
                position['entry_price']
            )
            
            if new_order_ids:
                position['tp_sl_order_ids'] = new_order_ids
                print(f"✅ 止盈止损订单已更新: 新仓位 {new_position_size:.2f}张")
            else:
                print("⚠️ 止盈止损订单更新失败，继续使用代码监控")
                
        except Exception as e:
            print(f"⚠️ 更新止盈止损订单时出错: {e}")
    
    def _update_trailing_stops(self, current_price, profit_pct):
        """更新移动止盈止损
        🔧 优化：根据趋势强度动态调整移动止盈激活条件和回撤窗口
        """
        position = self.current_position_info
        
        # 🔧 优化：根据趋势强度动态调整移动止盈参数
        trend_score = position.get('trend_score', 0)
        if trend_score >= 8:  # 极强趋势
            trailing_activation = 0.5  # 0.5%就激活
            trailing_window = 0.01  # 1%回撤窗口（更宽松）
        elif trend_score >= 6:  # 强趋势
            trailing_activation = 0.8  # 0.8%激活
            trailing_window = 0.007  # 0.7%回撤窗口
        else:  # 中等趋势
            trailing_activation = 1.0  # 1%激活
            trailing_window = 0.005  # 0.5%回撤窗口
        
        # 更新峰值盈亏
        if position['position_side'] == 'long':
            if current_price > position['highest_profit']:
                position['highest_profit'] = current_price
                # 🔧 优化：根据趋势强度动态激活移动止盈
                if profit_pct > trailing_activation and not position['trailing_stop_activated']:
                    position['trailing_stop_activated'] = True
                    trend_desc = "极强趋势" if trend_score >= 8 else "强趋势" if trend_score >= 6 else "中等趋势"
                    print(f"🎯 移动止盈已激活（盈利{profit_pct:.2f}% > {trailing_activation:.1f}%，{trend_desc}）")
        else:  # short
            if current_price < position['lowest_profit']:
                position['lowest_profit'] = current_price
                # 🔧 优化：根据趋势强度动态激活移动止盈
                if profit_pct > trailing_activation and not position['trailing_stop_activated']:
                    position['trailing_stop_activated'] = True
                    trend_desc = "极强趋势" if trend_score >= 8 else "强趋势" if trend_score >= 6 else "中等趋势"
                    print(f"🎯 移动止盈已激活（盈利{profit_pct:.2f}% > {trailing_activation:.1f}%，{trend_desc}）")
        
        # 更新峰值盈利记录
        if profit_pct > position.get('peak_profit', 0):
            position['peak_profit'] = profit_pct
        
        # 🔧 优化：保存回撤窗口到持仓信息（用于后续计算）
        position['trailing_window'] = trailing_window
    
    def _update_sliding_stop_loss_to_exchange(self, current_price, profit_pct):
        """
        当价格有利时，实时更新止损位到交易所（滑动止损 + 锁定止损）
        实现真正的"窄窗口+频繁滑动"策略，并在盈利达到阈值时锁定利润
        
        Args:
            current_price: 当前价格
            profit_pct: 当前盈亏百分比（未扣除手续费）
        """
        position = self.current_position_info
        
        # 🔧 修复：检查是否有持仓和订单，增加 position_size 检查，防止平仓后仍尝试更新订单
        if not position['position_side'] or not position['tp_sl_order_ids'] or position['position_size'] <= 0:
            return
        
        # 计算实际盈利（扣除手续费后的净盈利）
        try:
            actual_profit_pct = self._calculate_actual_profit_with_fees(current_price, profit_pct)
        except:
            actual_profit_pct = profit_pct - (TRADING_FEE_RATE * 100)
        
        # 🔧 优化：当接近或达到锁定止损阈值时，提高更新频率
        current_interval = self.min_update_interval
        threshold_pct = self.lock_stop_loss_config['profit_threshold'] * 100
        if actual_profit_pct >= (threshold_pct * 0.8):  # 达到阈值的80%
            self.min_update_interval = 10  # 缩短到10秒
            if current_interval != 10:
                print(f"🚀 提高更新频率: 30秒 → 10秒 (接近锁定止损阈值)")
        else:
            self.min_update_interval = ORBIT_UPDATE_INTERVAL  # 恢复60秒
        
        # 检查更新频率
        now = datetime.now()
        if self.last_order_update_time:
            time_since_last_update = (now - self.last_order_update_time).total_seconds()
            if time_since_last_update < self.min_update_interval:
                return
        
        # 🔧 详细调试日志
        print(f"🔍 止损更新检查:")
        print(f"   - 浮盈: {profit_pct:.2f}%, 实际盈利: {actual_profit_pct:.2f}% (扣除手续费)")
        print(f"   - 锁定止损阈值: {threshold_pct:.1f}%")
        print(f"   - 锁定状态: {'已激活' if self.lock_stop_loss_config['activated'] else '未激活'}")
        
        try:
            # 计算盈亏平衡点（考虑手续费）
            entry_price = position['entry_price']
            if position['position_side'] == 'long':
                # 多头：盈亏平衡价 = 入场价 × (1 + 手续费率)
                break_even_price = entry_price * (1 + TRADING_FEE_RATE)
            else:  # short
                # 空头：盈亏平衡价 = 入场价 × (1 - 手续费率)
                break_even_price = entry_price * (1 - TRADING_FEE_RATE)
            
            # 更新配置中的盈亏平衡价
            self.lock_stop_loss_config['breakeven_price'] = break_even_price
            
            # 检查是否应该激活锁定止损
            should_activate_lock = (actual_profit_pct >= threshold_pct)
            
            new_stop_loss = None
            should_update = False
            stop_reason = ""
            
            # 🔒 锁定止损逻辑（盈利达到阈值时优先使用）
            if should_activate_lock and not self.lock_stop_loss_config['activated']:
                # 首次激活锁定止损
                self.lock_stop_loss_config['activated'] = True
                print(f"🎯 锁定止损已激活！实际盈利: {actual_profit_pct:.2f}% ≥ {threshold_pct:.1f}%")
            
            if self.lock_stop_loss_config['activated']:
                # 使用锁定止损逻辑
                new_stop_loss = self._calculate_locked_stop_loss(current_price, actual_profit_pct)
                stop_reason = "锁定止损"
                
                if new_stop_loss:
                    # 🔧 关键修复：如果锁定止损已激活，即使计算出的止损价等于当前止损价，也应该保持
                    # 确保止损价不会回退（只能向更优方向移动或保持不变）
                    if position['position_side'] == 'long':
                        is_valid = new_stop_loss >= position['stop_loss']
                    else:  # short
                        is_valid = new_stop_loss <= position['stop_loss']
                    
                    if is_valid:
                        # 验证止损价合理性
                        if self._validate_stop_loss_price(new_stop_loss, current_price, position['position_side']):
                            # 检查止损价是否改善或保持不变
                            if self._is_stop_loss_improvement(new_stop_loss, position['stop_loss'], position['position_side']) or new_stop_loss == position['stop_loss']:
                                # 如果止损价改善，才更新；如果相等，说明价格回撤但保持止损价不变，不需要更新订单
                                if new_stop_loss != position['stop_loss']:
                                    should_update = True
                                    print(f"✅ 锁定止损计算: {position['stop_loss']:.2f} → {new_stop_loss:.2f}")
                                else:
                                    print(f"✅ 锁定止损保持: {new_stop_loss:.2f} (价格回撤，止损价不变)")
                            else:
                                print(f"⚠️ 锁定止损价未改善: {new_stop_loss:.2f} vs 当前 {position['stop_loss']:.2f}")
                        else:
                            print(f"⚠️ 锁定止损价验证失败: {new_stop_loss:.2f}")
                    else:
                        # 这种情况不应该发生，因为_calculate_locked_stop_loss已经处理了
                        print(f"⚠️ 锁定止损价异常: {new_stop_loss:.2f} vs 当前 {position['stop_loss']:.2f}，保持当前止损价")
                else:
                    # 🔧 关键修复：如果锁定止损已激活但计算返回None，保持当前止损价不变
                    print(f"⚠️ 锁定止损计算返回None，保持当前止损价不变: {position['stop_loss']:.2f}")
            else:
                # 使用原有的滑动止损逻辑
                new_stop_loss, should_update, stop_reason = self._calculate_sliding_stop_loss(
                    current_price, profit_pct, position
                )
            
            # 执行更新
            if should_update and new_stop_loss:
                new_order_ids = update_tp_sl_orders(
                    self.trade_config['symbol'],
                    position['position_side'],
                    position['position_size'],
                    new_stop_loss,
                    position['take_profit'],
                    position['tp_sl_order_ids']
                )
                
                if new_order_ids and new_order_ids.get('sl_order_id'):
                    old_stop_loss = position['stop_loss']
                    position['stop_loss'] = new_stop_loss
                    position['tp_sl_order_ids'] = new_order_ids
                    self.last_order_update_time = now
                    
                    # 如果是锁定止损，更新锁定价格
                    if self.lock_stop_loss_config['activated']:
                        self.lock_stop_loss_config['locked_stop_price'] = new_stop_loss
                    
                    print(f"🎯 {stop_reason}更新成功: {old_stop_loss:.2f} → {new_stop_loss:.2f}")
                    print(f"   📊 订单ID: {new_order_ids['sl_order_id']}")
                else:
                    print(f"⚠️ {stop_reason}订单设置失败，保持原止损价 {position['stop_loss']:.2f}")
                    if new_order_ids and new_order_ids.get('tp_order_id'):
                        print(f"   ℹ️ 止盈订单已更新，但止损订单失败，继续使用代码监控原止损价")
        
        except Exception as e:
            print(f"❌ 止损更新异常: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_trailing_stop_to_exchange(self, current_price, profit_pct):
        """
        将移动止盈的止损位同步到交易所
        确保交易所订单反映最新的移动止盈状态
        
        Args:
            current_price: 当前价格
            profit_pct: 当前盈亏百分比
        """
        position = self.current_position_info
        
        # 🔧 修复：检查移动止盈是否激活，增加 position_side 和 position_size 检查，防止平仓后仍尝试更新订单
        if not position['position_side'] or position['position_size'] <= 0 or not position['trailing_stop_activated'] or not position['tp_sl_order_ids']:
            return
        
        # 检查更新频率
        now = datetime.now()
        if self.last_order_update_time:
            time_since_last_update = (now - self.last_order_update_time).total_seconds()
            if time_since_last_update < self.min_update_interval:
                return
        
        try:
            # 使用全局的update_tp_sl_orders函数（已在文件顶部定义）
            # 计算新的移动止损位
            if position['position_side'] == 'long':
                trailing_stop = position['highest_profit'] * 0.995  # 回撤0.5%平仓
                # 只有当新止损位明显高于当前止损时才更新（至少提高0.1%）
                if trailing_stop > position['stop_loss'] * 1.001:
                    new_order_ids = update_tp_sl_orders(
                        self.trade_config['symbol'],
                        position['position_side'],
                        position['position_size'],
                        trailing_stop,  # 新的移动止损
                        position['take_profit'],  # 止盈不变
                        position['tp_sl_order_ids']  # 旧订单ID
                    )
                    
                    if new_order_ids:
                        position['stop_loss'] = trailing_stop
                        position['tp_sl_order_ids'] = new_order_ids
                        self.last_order_update_time = now
                        print(f"✅ 移动止盈止损已同步到交易所: {trailing_stop:.2f} (最高价: {position['highest_profit']:.2f})")
            
            else:  # short
                trailing_stop = position['lowest_profit'] * 1.005  # 回撤0.5%平仓
                # 只有当新止损位明显低于当前止损时才更新（至少降低0.1%）
                if trailing_stop < position['stop_loss'] * 0.999:
                    new_order_ids = update_tp_sl_orders(
                        self.trade_config['symbol'],
                        position['position_side'],
                        position['position_size'],
                        trailing_stop,  # 新的移动止损
                        position['take_profit'],  # 止盈不变
                        position['tp_sl_order_ids']  # 旧订单ID
                    )
                    
                    if new_order_ids:
                        position['stop_loss'] = trailing_stop
                        position['tp_sl_order_ids'] = new_order_ids
                        self.last_order_update_time = now
                        print(f"✅ 移动止盈止损已同步到交易所: {trailing_stop:.2f} (最低价: {position['lowest_profit']:.2f})")
        
        except Exception as e:
            print(f"⚠️ 更新移动止盈止损到交易所时出错: {e}")
            # 不影响主流程，继续使用代码监控
    
    def _execute_emergency_close(self, current_price, profit_pct):
        """执行紧急平仓"""
        try:
            position = self.current_position_info
            print(f"🚨 执行紧急平仓 | 价格: {current_price:.2f} | 盈亏: {profit_pct:+.2f}%")
            
            # 🔧 修复：先强制取消所有策略订单，避免订单残留
            try:
                print("🔄 紧急平仓前，先取消所有止盈止损订单...")
                cancel_tp_sl_orders(self.trade_config['symbol'], None)  # None表示取消所有
                time.sleep(0.3)  # 短暂等待
            except Exception as e:
                print(f"⚠️ 取消订单时出错（继续平仓）: {e}")
            
            if position['position_side'] == 'long':
                # 平多仓
                self.exchange.create_market_order(
                    self.trade_config['symbol'],
                    'sell',
                    position['position_size'],
                    params={'reduceOnly': True}
                )
            else:  # short
                # 平空仓
                self.exchange.create_market_order(
                    self.trade_config['symbol'],
                    'buy',
                    position['position_size'],
                    params={'reduceOnly': True}
                )
            
            print("✅ 紧急平仓执行成功")
            # 🔧 修复：计算实际盈亏时考虑手续费
            # profit_pct是未实现盈亏百分比，需要扣除手续费（0.1%）
            actual_profit_pct = profit_pct - (TRADING_FEE_RATE * 100)  # 扣除手续费百分比
            is_win = actual_profit_pct > 0
            
            # 计算实际盈亏金额（估算）
            position_size = position.get('position_size', 0)
            entry_price = position.get('entry_price', 0)
            contract_size = self.trade_config.get('contract_size', 0.01)
            position_notional = position_size * contract_size * current_price
            actual_pnl = position_notional * (actual_profit_pct / 100)
            
            print(f"💰 紧急平仓实际盈亏: 未实现={profit_pct:.2f}%, 手续费={TRADING_FEE_RATE*100:.2f}%, 实际={actual_profit_pct:.2f}% ({actual_pnl:.4f} USDT)")
            update_trade_result(is_win, actual_pnl)
            self.clear_position_info()  # 这会再次清理订单（双重保险）
            
        except Exception as e:
            print(f"❌ 紧急平仓失败: {e}")
            # 即使平仓失败，也尝试清理订单
            try:
                cancel_tp_sl_orders(self.trade_config['symbol'], None)
            except:
                pass

# =============================================================================
# OKX止盈止损订单管理函数
# =============================================================================

def set_tp_sl_orders(symbol, position_side, position_size, stop_loss_price, take_profit_price, entry_price=None):
    """
    在OKX交易所设置止盈止损订单
    
    Args:
        symbol: 交易对，如 'BTC/USDT:USDT'
        position_side: 持仓方向 'long' 或 'short'
        position_size: 持仓数量（张数）
        stop_loss_price: 止损价格
        take_profit_price: 止盈价格
        entry_price: 入场价格（可选，用于验证）
    
    Returns:
        dict: 包含订单ID的字典，格式为 {'tp_order_id': 'xxx', 'sl_order_id': 'xxx'} 或 None
    """
    try:
        # 🔧 改进：先取消该交易对的所有旧策略订单，避免重复下单
        try:
            print("🔄 设置新订单前，先取消该交易对的所有旧止盈止损订单...")
            cancel_tp_sl_orders(symbol, None)  # None表示取消所有
            time.sleep(0.5)  # 等待取消完成
        except Exception as e:
            print(f"⚠️ 取消旧订单时出错（继续执行）: {e}")
        
        # 获取市场信息
        markets = exchange.load_markets()
        market = markets[symbol]
        inst_id = market['id']  # OKX使用instId格式，如 'BTC-USDT-SWAP'
        
        # 转换交易方向（平仓方向）
        if position_side == 'long':
            # 平多仓，使用sell
            trade_side = 'sell'
        else:
            # 平空仓，使用buy
            trade_side = 'buy'
        
        order_ids = {'tp_order_id': None, 'sl_order_id': None}
        
        # 设置止损订单（Stop Loss）
        if stop_loss_price > 0:
            try:
                # 在单向持仓模式下，OKX不需要posSide参数，或使用'net'
                # 调用OKX API设置止损订单
                try:
                    # OKX的止盈止损订单API - 单向持仓模式不需要posSide
                    params = {
                        'instId': inst_id,
                        'tdMode': 'cross',
                        'side': trade_side,
                        # 单向持仓模式下不传posSide参数
                        'ordType': 'conditional',
                        'sz': str(position_size),
                        'slTriggerPx': str(stop_loss_price),
                        'slOrdPx': '-1',  # 使用市价单
                        'slTriggerPxType': 'mark',  # 使用标记价格触发
                    }
                    
                    # 使用ccxt的request方法（ccxt会自动添加/api/v5前缀）
                    response = exchange.request('trade/order-algo', 'private', 'POST', params)
                    
                    if response and response.get('code') == '0':
                        order_ids['sl_order_id'] = response.get('data', [{}])[0].get('algoId')
                        print(f"✅ 止损订单设置成功: {stop_loss_price:.2f} (订单ID: {order_ids['sl_order_id']})")
                    else:
                        print(f"⚠️ 止损订单设置失败: {response.get('msg', '未知错误')}")
                except AttributeError:
                    # 如果ccxt不支持request方法，尝试使用私有方法
                    try:
                        response = exchange.private_post_trade_order_algo(params)
                        if response and response.get('code') == '0':
                            order_ids['sl_order_id'] = response.get('data', [{}])[0].get('algoId')
                            print(f"✅ 止损订单设置成功: {stop_loss_price:.2f} (订单ID: {order_ids['sl_order_id']})")
                        else:
                            print(f"⚠️ 止损订单设置失败: {response.get('msg', '未知错误')}")
                    except:
                        raise
                    
            except Exception as e:
                print(f"⚠️ 设置止损订单时出错: {e}")
                # 尝试使用备用方法：通过普通条件订单
                try:
                    # 使用ccxt的create_order方法，但OKX可能不支持直接设置止损
                    # 这里记录错误，但不阻止程序继续运行
                    print(f"⚠️ 止损订单设置失败，将使用代码监控作为备用")
                except:
                    pass
        
        # 设置止盈订单（Take Profit）
        if take_profit_price > 0:
            try:
                # 调用OKX API设置止盈订单
                try:
                    # OKX的止盈止损订单API - 单向持仓模式不需要posSide
                    params = {
                        'instId': inst_id,
                        'tdMode': 'cross',
                        'side': trade_side,
                        # 单向持仓模式下不传posSide参数
                        'ordType': 'conditional',
                        'sz': str(position_size),
                        'tpTriggerPx': str(take_profit_price),
                        'tpOrdPx': '-1',  # 使用市价单
                        'tpTriggerPxType': 'mark',  # 使用标记价格触发
                    }
                    
                    # 使用ccxt的request方法（ccxt会自动添加/api/v5前缀）
                    response = exchange.request('trade/order-algo', 'private', 'POST', params)
                    
                    if response and response.get('code') == '0':
                        order_ids['tp_order_id'] = response.get('data', [{}])[0].get('algoId')
                        print(f"✅ 止盈订单设置成功: {take_profit_price:.2f} (订单ID: {order_ids['tp_order_id']})")
                    else:
                        print(f"⚠️ 止盈订单设置失败: {response.get('msg', '未知错误')}")
                except AttributeError:
                    # 如果ccxt不支持request方法，尝试使用私有方法
                    try:
                        response = exchange.private_post_trade_order_algo(params)
                        if response and response.get('code') == '0':
                            order_ids['tp_order_id'] = response.get('data', [{}])[0].get('algoId')
                            print(f"✅ 止盈订单设置成功: {take_profit_price:.2f} (订单ID: {order_ids['tp_order_id']})")
                        else:
                            print(f"⚠️ 止盈订单设置失败: {response.get('msg', '未知错误')}")
                    except:
                        raise
                    
            except Exception as e:
                print(f"⚠️ 设置止盈订单时出错: {e}")
                print(f"⚠️ 止盈订单设置失败，将使用代码监控作为备用")
        
        # 🔧 修复：如果止损订单失败，但这是滑动止损更新，应该返回None或只包含成功订单的字典
        # 当前逻辑：只要有任一订单成功就返回字典（包含None值）
        # 这样调用者可以通过检查sl_order_id来判断止损订单是否成功
        if order_ids['tp_order_id'] or order_ids['sl_order_id']:
            return order_ids
        else:
            return None
        
    except Exception as e:
        print(f"❌ 设置止盈止损订单失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def cancel_tp_sl_orders(symbol, order_ids=None):
    """
    取消OKX交易所的止盈止损订单
    
    Args:
        symbol: 交易对
        order_ids: 订单ID字典，格式为 {'tp_order_id': 'xxx', 'sl_order_id': 'xxx'}
                  如果为None，则取消该交易对的所有策略订单
    
    Returns:
        bool: 是否成功取消
    """
    try:
        markets = exchange.load_markets()
        market = markets[symbol]
        inst_id = market['id']
        
        if order_ids:
            # 取消指定的订单
            cancelled = False
            if order_ids.get('tp_order_id'):
                try:
                    # 使用批量取消方法（正确的方法）
                    cancel_params = [{'algoId': order_ids['tp_order_id'], 'instId': inst_id}]
                    response = None
                    try:
                        # 方法1：使用ccxt的批量取消方法（正确的方法）
                        if hasattr(exchange, 'private_post_trade_cancel_algos'):
                            response = exchange.private_post_trade_cancel_algos(cancel_params)
                        # 方法2：使用request方法
                        elif hasattr(exchange, 'request'):
                            response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                        else:
                            response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                    except AttributeError:
                        # 备用方法
                        response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                    
                    if response:
                        if response.get('code') == '0':
                            # 检查返回数据中的sCode
                            data = response.get('data', [])
                            if data and len(data) > 0:
                                s_code = data[0].get('sCode', '0')
                                if s_code == '0':
                                    print(f"✅ 止盈订单已取消: {order_ids['tp_order_id']}")
                                    cancelled = True
                                else:
                                    print(f"❌ 取消止盈订单失败: {data[0].get('sMsg', '未知错误')} (sCode: {s_code})")
                            else:
                                print(f"✅ 止盈订单已取消: {order_ids['tp_order_id']}")
                                cancelled = True
                        elif response.get('code') == '404':
                            # 404表示订单不存在，记录警告但不视为成功
                            print(f"⚠️ 止盈订单不存在（订单ID可能错误或已触发）: {order_ids['tp_order_id']}")
                        else:
                            print(f"❌ 取消止盈订单失败: {response.get('msg', '未知错误')} (code: {response.get('code')})")
                except Exception as e:
                    # 记录错误，不视为成功
                    error_str = str(e)
                    if '404' in error_str or 'Not Found' in error_str:
                        print(f"⚠️ 取消止盈订单时出错（订单可能不存在）: {order_ids['tp_order_id']} - {e}")
                    else:
                        print(f"❌ 取消止盈订单失败: {e}")
            
            if order_ids.get('sl_order_id'):
                try:
                    # 使用批量取消方法（正确的方法）
                    cancel_params = [{'algoId': order_ids['sl_order_id'], 'instId': inst_id}]
                    response = None
                    try:
                        # 方法1：使用ccxt的批量取消方法（正确的方法）
                        if hasattr(exchange, 'private_post_trade_cancel_algos'):
                            response = exchange.private_post_trade_cancel_algos(cancel_params)
                        # 方法2：使用request方法
                        elif hasattr(exchange, 'request'):
                            response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                        else:
                            response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                    except AttributeError:
                        response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                    
                    if response:
                        if response.get('code') == '0':
                            # 检查返回数据中的sCode
                            data = response.get('data', [])
                            if data and len(data) > 0:
                                s_code = data[0].get('sCode', '0')
                                if s_code == '0':
                                    print(f"✅ 止损订单已取消: {order_ids['sl_order_id']}")
                                    cancelled = True
                                else:
                                    print(f"❌ 取消止损订单失败: {data[0].get('sMsg', '未知错误')} (sCode: {s_code})")
                            else:
                                print(f"✅ 止损订单已取消: {order_ids['sl_order_id']}")
                                cancelled = True
                        elif response.get('code') == '404':
                            # 404表示订单不存在，记录警告但不视为成功
                            print(f"⚠️ 止损订单不存在（订单ID可能错误或已触发）: {order_ids['sl_order_id']}")
                        else:
                            print(f"❌ 取消止损订单失败: {response.get('msg', '未知错误')} (code: {response.get('code')})")
                except Exception as e:
                    # 记录错误，不视为成功
                    error_str = str(e)
                    if '404' in error_str or 'Not Found' in error_str:
                        print(f"⚠️ 取消止损订单时出错（订单可能不存在）: {order_ids['sl_order_id']} - {e}")
                    else:
                        print(f"❌ 取消止损订单失败: {e}")
            
            return cancelled
        else:
            # 取消该交易对的所有策略订单
            # 方法：先查询所有待处理算法订单，然后批量取消
            try:
                cancelled_count = 0
                failed_count = 0
                
                # 尝试查询待处理算法订单（使用不同的参数组合）
                orders = []
                # 方法1：指定instType、instId和ordType
                params1 = {
                    'instType': 'SWAP',
                    'instId': inst_id,
                    'ordType': 'conditional',  # 条件订单类型
                }
                try:
                    if hasattr(exchange, 'private_get_trade_orders_algo_pending'):
                        response = exchange.private_get_trade_orders_algo_pending(params1)
                    elif hasattr(exchange, 'request'):
                        response = exchange.request('trade/orders-algo-pending', 'private', 'GET', params1)
                    else:
                        response = exchange.request('trade/orders-algo-pending', 'private', 'GET', params1)
                    
                    if response and response.get('code') == '0':
                        orders = response.get('data', [])
                except Exception as e1:
                    # 如果方法1失败，尝试方法2：只指定instType
                    try:
                        params2 = {'instType': 'SWAP'}
                        if hasattr(exchange, 'private_get_trade_orders_algo_pending'):
                            response = exchange.private_get_trade_orders_algo_pending(params2)
                        elif hasattr(exchange, 'request'):
                            response = exchange.request('trade/orders-algo-pending', 'private', 'GET', params2)
                        else:
                            response = exchange.request('trade/orders-algo-pending', 'private', 'GET', params2)
                        
                        if response and response.get('code') == '0':
                            # 过滤出该交易对的订单
                            all_orders = response.get('data', [])
                            orders = [o for o in all_orders if o.get('instId') == inst_id]
                    except Exception as e2:
                        print(f"⚠️ 查询策略订单失败: {e1}, {e2}")
                        # 如果查询失败，返回True（不阻止后续操作）
                        return True
                
                # 批量取消订单
                for order in orders:
                    algo_id = order.get('algoId')
                    if algo_id:
                        try:
                            # 使用批量取消方法（正确的方法）
                            cancel_params = [{'algoId': algo_id, 'instId': inst_id}]
                            cancel_response = None
                            try:
                                if hasattr(exchange, 'private_post_trade_cancel_algos'):
                                    cancel_response = exchange.private_post_trade_cancel_algos(cancel_params)
                                elif hasattr(exchange, 'request'):
                                    cancel_response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                                else:
                                    cancel_response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                            except AttributeError:
                                cancel_response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                            
                            if cancel_response:
                                if cancel_response.get('code') == '0':
                                    # 检查返回数据中的sCode
                                    data = cancel_response.get('data', [])
                                    if data and len(data) > 0:
                                        s_code = data[0].get('sCode', '0')
                                        if s_code == '0':
                                            cancelled_count += 1
                                        else:
                                            failed_count += 1
                                    else:
                                        cancelled_count += 1
                                elif cancel_response.get('code') == '404':
                                    # 404表示订单不存在，计入失败（订单ID可能错误）
                                    failed_count += 1
                                else:
                                    failed_count += 1
                        except Exception as e:
                            # 记录单个订单取消失败
                            error_str = str(e)
                            if '404' in error_str or 'Not Found' in error_str:
                                failed_count += 1  # 404也计入失败
                            else:
                                failed_count += 1
                
                if cancelled_count > 0:
                    print(f"✅ 已取消 {cancelled_count} 个策略订单")
                    if failed_count > 0:
                        print(f"⚠️ {failed_count} 个订单取消失败（可能已不存在）")
                    return True
                else:
                    if failed_count > 0:
                        print(f"ℹ️ 尝试取消 {failed_count} 个订单，但都失败（可能已不存在）")
                    else:
                        print("ℹ️ 没有找到需要取消的策略订单")
                    return True
                        
            except Exception as e:
                print(f"⚠️ 取消策略订单时出错: {e}")
                # 即使出错也返回True，不阻止后续操作
                return True
        
    except Exception as e:
        print(f"❌ 取消止盈止损订单失败: {e}")
        return False

def update_tp_sl_orders(symbol, position_side, position_size, stop_loss_price, take_profit_price, old_order_ids=None):
    """
    更新止盈止损订单（先取消旧订单，再设置新订单）
    
    Args:
        symbol: 交易对
        position_side: 持仓方向
        position_size: 持仓数量
        stop_loss_price: 新的止损价格
        take_profit_price: 新的止盈价格
        old_order_ids: 旧的订单ID字典
    
    Returns:
        dict: 新的订单ID字典
    """
    try:
        # 🔧 修复：在设置新订单前，先验证实际持仓状态，防止无持仓时创建残留订单
        try:
            actual_position = get_current_position()
            if not actual_position or actual_position['size'] <= 0:
                print(f"⚠️ 更新止盈止损订单时检测到实际无持仓，取消操作，避免创建残留订单")
                # 仍然尝试取消旧订单，但不创建新订单
                if old_order_ids:
                    cancel_tp_sl_orders(symbol, old_order_ids)
                return None
            
            # 验证持仓方向是否匹配
            if actual_position['side'] != position_side:
                print(f"⚠️ 更新止盈止损订单时检测到持仓方向不匹配（实际: {actual_position['side']}, 预期: {position_side}），取消操作")
                if old_order_ids:
                    cancel_tp_sl_orders(symbol, old_order_ids)
                return None
        except Exception as e:
            print(f"⚠️ 验证实际持仓时出错，继续执行订单更新: {e}")
        
        # 先取消旧订单
        if old_order_ids:
            cancel_tp_sl_orders(symbol, old_order_ids)
            time.sleep(0.5)  # 等待订单取消完成
        
        # 设置新订单
        new_order_ids = set_tp_sl_orders(
            symbol, position_side, position_size, 
            stop_loss_price, take_profit_price
        )
        
        return new_order_ids
        
    except Exception as e:
        print(f"❌ 更新止盈止损订单失败: {e}")
        return None

def initialize_price_monitor():
    """初始化价格监控"""
    global price_monitor
    price_monitor = RealTimePriceMonitor(exchange, TRADE_CONFIG)
    price_monitor.start_monitoring()
    return price_monitor

def setup_exchange():
    """设置交易所参数"""
    try:
        print("🔍 获取BTC合约规格...")
        markets = exchange.load_markets()
        btc_market = markets[TRADE_CONFIG['symbol']]

        contract_size = float(btc_market['contractSize'])
        TRADE_CONFIG['contract_size'] = contract_size
        TRADE_CONFIG['min_amount'] = btc_market['limits']['amount']['min']

        print(f"✅ 合约规格: 1张 = {contract_size} BTC")
        print(f"📏 最小交易量: {TRADE_CONFIG['min_amount']} 张")

        # 检查现有持仓
        print("🔍 检查现有持仓模式...")
        positions = exchange.fetch_positions([TRADE_CONFIG['symbol']])

        has_isolated_position = False
        for pos in positions:
            if pos['symbol'] == TRADE_CONFIG['symbol']:
                contracts = float(pos.get('contracts', 0))
                mode = pos.get('mgnMode')
                if contracts > 0 and mode == 'isolated':
                    has_isolated_position = True
                    print("❌ 检测到逐仓持仓，请手动处理")
                    return False

        # 设置交易模式
        print("🔄 设置单向持仓模式...")
        try:
            exchange.set_position_mode(False, TRADE_CONFIG['symbol'])
            print("✅ 已设置单向持仓模式")
        except Exception as e:
            print(f"⚠️ 设置单向持仓模式失败（可能已有持仓或订单）: {e}")
            print("ℹ️ 继续运行，将使用当前持仓模式")

        # 设置全仓模式和杠杆
        print("⚙️ 设置全仓模式和杠杆...")
        try:
            exchange.set_leverage(
                TRADE_CONFIG['leverage'],
                TRADE_CONFIG['symbol'],
                {'mgnMode': 'cross'}
            )
            print(f"✅ 已设置全仓模式，杠杆倍数: {TRADE_CONFIG['leverage']}x")
        except Exception as e:
            print(f"⚠️ 设置杠杆失败: {e}")
            print(f"ℹ️ 尝试使用更低杠杆...")
            # 尝试1倍杠杆
            try:
                exchange.set_leverage(1, TRADE_CONFIG['symbol'], {'mgnMode': 'cross'})
                TRADE_CONFIG['leverage'] = 1
                print(f"✅ 已设置杠杆倍数为1x（保守模式）")
            except Exception as e2:
                print(f"❌ 设置杠杆失败: {e2}")
                raise e2

        # 验证设置
        balance = exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        print(f"💰 当前USDT余额: {usdt_balance:.2f}")
        
        if usdt_balance == 0:
            print("⚠️ 账户余额为0，将运行演示模式")
            TRADE_CONFIG['test_mode'] = True

        current_pos = get_current_position()
        if current_pos:
            print(f"📦 当前持仓: {current_pos['side']}仓 {current_pos['size']}张")
        else:
            print("📦 当前无持仓")

        print("🎯 程序配置完成")
        return True

    except Exception as e:
        print(f"❌ 交易所设置失败: {e}")
        traceback.print_exc()
        return False

def calculate_atr(df, period=14):
    """计算平均真实波幅(ATR) - 返回整个Series用于DataFrame赋值"""
    try:
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = np.maximum(np.maximum(high_low, high_close), low_close)
        atr = true_range.rolling(period).mean()
        return atr
    except Exception as e:
        print(f"ATR计算失败: {e}")
        return pd.Series([0] * len(df), index=df.index)

def calculate_volatility(df, period=20):
    """计算价格波动率"""
    try:
        returns = df['close'].pct_change()
        volatility = returns.rolling(period).std() * np.sqrt(365 * 24 * 4)  # 年化波动率
        return volatility.iloc[-1]
    except Exception as e:
        print(f"波动率计算失败: {e}")
        return 0

def check_trading_conditions():
    """检查交易条件"""
    global performance_tracker
    
    # 检查是否暂停交易
    if performance_tracker['is_trading_paused']:
        print("🚫 交易已暂停，等待人工干预")
        return False
    
    # 检查日亏损
    if performance_tracker['daily_pnl'] < TRADE_CONFIG['performance_tracking']['daily_pnl_threshold']:
        print(f"🚫 日亏损达到{performance_tracker['daily_pnl']:.2%}，暂停交易")
        performance_tracker['is_trading_paused'] = True
        return False
    
    return True

def calculate_win_rate(recent_trades_count=20):
    """
    计算策略胜率（基于最近的交易记录）
    
    Args:
        recent_trades_count: 考虑最近多少笔交易，默认20笔
        
    Returns:
        float: 胜率（0.0-1.0），如果交易记录不足返回None
    """
    global performance_tracker
    
    # 从交易所获取最近的交易记录
    try:
        trades = exchange.fetch_my_trades(TRADE_CONFIG['symbol'], limit=recent_trades_count * 2)
        
        if not trades or len(trades) < 10:  # 至少需要10笔交易
            return None
        
        # 按时间排序
        trades = sorted(trades, key=lambda x: x['timestamp'], reverse=True)
        trades = trades[:recent_trades_count]  # 取最近N笔
        
        # 计算盈亏：需要配对开仓和平仓
        # 简化版本：基于持仓变化和价格变化估算
        # 或者使用performance_tracker中的记录
        
        # 如果performance_tracker中有胜率记录，优先使用
        if performance_tracker.get('win_rate', 0) > 0 and performance_tracker.get('trade_count', 0) >= 10:
            return performance_tracker['win_rate']
        
        # 否则返回None，使用默认基础风险
        return None
        
    except Exception as e:
        print(f"⚠️ 计算胜率失败: {e}")
        return None

def update_trade_result(is_win, pnl=0):
    """
    更新交易结果到performance_tracker
    
    Args:
        is_win: 是否盈利（True/False）
        pnl: 盈亏金额（可选，用于记录）
    """
    global performance_tracker
    
    performance_tracker['trade_count'] += 1
    
    if is_win:
        performance_tracker['win_count'] += 1
        result = 'win'
    else:
        performance_tracker['loss_count'] += 1
        result = 'loss'
    
    # 记录交易结果（保留最近50笔）
    performance_tracker['trade_results'].append({
        'result': result,
        'pnl': pnl,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # 限制记录数量
    if len(performance_tracker['trade_results']) > 50:
        performance_tracker['trade_results'] = performance_tracker['trade_results'][-50:]
    
    # 计算胜率
    if performance_tracker['trade_count'] > 0:
        performance_tracker['win_rate'] = performance_tracker['win_count'] / performance_tracker['trade_count']
    
    print(f"📊 交易结果更新: {'盈利' if is_win else '亏损'}, 总交易: {performance_tracker['trade_count']}, 胜率: {performance_tracker['win_rate']:.1%}")

def get_dynamic_base_risk(win_rate=None):
    """
    根据策略胜率动态调整基础风险
    
    Args:
        win_rate: 策略胜率（0.0-1.0），如果为None则计算
        
    Returns:
        float: 动态基础风险（0.01-0.10）
    """
    risk_config = TRADE_CONFIG['risk_management']
    
    # 如果未启用动态调整，返回默认值
    if not risk_config.get('adaptive_risk_enabled', False):
        return risk_config['base_risk_per_trade']
    
    # 如果胜率为None，尝试计算
    if win_rate is None:
        win_rate_value = calculate_win_rate()
        if win_rate_value is None:
            # 交易记录不足，使用默认值
            return risk_config['base_risk_per_trade']
        win_rate = win_rate_value
    
    # 检查交易数量是否足够
    min_trades = risk_config.get('min_trades_for_adaptive', 10)
    if performance_tracker.get('trade_count', 0) < min_trades:
        return risk_config['base_risk_per_trade']
    
    risk_levels = risk_config['risk_levels']
    
    # 根据胜率返回对应的基础风险
    if win_rate > risk_levels['high_win_rate']['threshold']:
        # 高胜率（>60%）：5-10%，根据胜率线性调整
        min_risk = risk_levels['high_win_rate']['min_risk']
        max_risk = risk_levels['high_win_rate']['max_risk']
        # 胜率在60%-100%之间线性映射到5%-10%
        threshold = risk_levels['high_win_rate']['threshold']
        risk_range = max_risk - min_risk
        win_rate_range = 1.0 - threshold
        if win_rate_range > 0:
            risk = min_risk + (win_rate - threshold) / win_rate_range * risk_range
        else:
            risk = max_risk
        return min(max(risk, min_risk), max_risk)  # 确保在范围内
    elif win_rate >= risk_levels['medium_win_rate']['threshold']:
        # 中等胜率（40-60%）：3-5%，根据胜率线性调整
        min_risk = risk_levels['medium_win_rate']['min_risk']
        max_risk = risk_levels['medium_win_rate']['max_risk']
        # 胜率在40%-60%之间线性映射到3%-5%
        threshold = risk_levels['medium_win_rate']['threshold']
        risk_range = max_risk - min_risk
        win_rate_range = 0.60 - threshold  # 40%-60%的范围
        if win_rate_range > 0:
            risk = min_risk + (win_rate - threshold) / win_rate_range * risk_range
        else:
            risk = max_risk
        return min(max(risk, min_risk), max_risk)  # 确保在范围内
    else:
        # 低胜率（<40%）：1-2%，根据胜率线性调整
        min_risk = risk_levels['low_win_rate']['min_risk']
        max_risk = risk_levels['low_win_rate']['max_risk']
        # 胜率在0%-40%之间线性映射到1%-2%
        risk_range = max_risk - min_risk
        win_rate_range = 0.40  # 0%-40%的范围
        if win_rate_range > 0:
            risk = min_risk + win_rate / win_rate_range * risk_range
        else:
            risk = max_risk
        return min(max(risk, min_risk), max_risk)  # 确保在范围内

def get_dynamic_leverage(win_rate=None):
    """
    根据策略胜率动态调整杠杆倍数
    
    Args:
        win_rate: 策略胜率（0.0-1.0），如果为None则计算
        
    Returns:
        int: 动态杠杆倍数（1-10）
    """
    # 如果未启用动态调整，返回默认值
    default_leverage = TRADE_CONFIG.get('leverage', 6)
    
    # 如果胜率为None，尝试计算
    if win_rate is None:
        win_rate_value = calculate_win_rate()
        if win_rate_value is None:
            # 交易记录不足，使用默认值
            return default_leverage
        win_rate = win_rate_value
    
    # 检查交易数量是否足够
    min_trades = TRADE_CONFIG['risk_management'].get('min_trades_for_adaptive', 10)
    if performance_tracker.get('trade_count', 0) < min_trades:
        return default_leverage
    
    # 根据胜率返回对应的杠杆倍数
    if win_rate > 0.60:
        # 高胜率（>60%）：6-10x，根据胜率线性调整
        min_leverage = 6
        max_leverage = 10
        # 胜率在60%-100%之间线性映射到6-10x
        threshold = 0.60
        leverage_range = max_leverage - min_leverage
        win_rate_range = 1.0 - threshold
        if win_rate_range > 0:
            leverage = min_leverage + (win_rate - threshold) / win_rate_range * leverage_range
        else:
            leverage = max_leverage
        return int(min(max(leverage, min_leverage), max_leverage))  # 确保在范围内
    elif win_rate >= 0.40:
        # 中等胜率（40-60%）：3-5x，根据胜率线性调整
        min_leverage = 3
        max_leverage = 5
        # 胜率在40%-60%之间线性映射到3-5x
        threshold = 0.40
        leverage_range = max_leverage - min_leverage
        win_rate_range = 0.60 - threshold
        if win_rate_range > 0:
            leverage = min_leverage + (win_rate - threshold) / win_rate_range * leverage_range
        else:
            leverage = max_leverage
        return int(min(max(leverage, min_leverage), max_leverage))  # 确保在范围内
    else:
        # 低胜率（<40%）：1-2x，根据胜率线性调整
        min_leverage = 1
        max_leverage = 2
        # 胜率在0%-40%之间线性映射到1-2x
        leverage_range = max_leverage - min_leverage
        win_rate_range = 0.40
        if win_rate_range > 0:
            leverage = min_leverage + win_rate / win_rate_range * leverage_range
        else:
            leverage = max_leverage
        return int(min(max(leverage, min_leverage), max_leverage))  # 确保在范围内

def calculate_intelligent_position(signal_data, price_data, current_position):
    """
    基于风险反推的智能仓位计算
    根据止损距离和最大可承受亏损（3%）反推最大安全交易金额，然后优化杠杆和资金利用率
    """
    risk_config = TRADE_CONFIG['risk_management']
    
    try:
        # 1. 先读取账户价值（总资产）
        balance = exchange.fetch_balance()
        total_balance = balance.get('USDT', {}).get('total', 0)  # 总资产（包括已占用的保证金）
        free_balance = balance.get('USDT', {}).get('free', 0)  # 可用余额
        
        if TRADE_CONFIG.get('test_mode', False):
            total_balance = 10000  # 测试模式
            free_balance = 10000
        
        # 检查当前持仓占用的保证金
        current_margin_used = 0
        if current_position and current_position.get('size', 0) > 0:
            current_position_size = current_position['size']
            current_leverage = current_position.get('leverage', TRADE_CONFIG.get('leverage', 6))
            current_margin_used = (current_position_size * price_data['price'] * TRADE_CONFIG['contract_size']) / current_leverage
        
        print(f"💰 账户信息:")
        print(f"   - 总资产: {total_balance:.2f} USDT")
        print(f"   - 可用余额: {free_balance:.2f} USDT")
        if current_margin_used > 0:
            print(f"   - 当前持仓占用保证金: {current_margin_used:.2f} USDT")
        
        # 使用总资产进行后续计算（确保基于完整账户价值计算资金利用率）
        
        # 1. 获取止损距离
        stop_loss = signal_data.get('stop_loss', 0)
        current_price = price_data['price']
        if stop_loss > 0:
            stop_loss_distance = abs(stop_loss - current_price)
            stop_loss_distance_pct = stop_loss_distance / current_price
        else:
            # 如果没有止损，使用默认1%
            stop_loss_distance_pct = 0.01
            print(f"⚠️ 未找到止损价，使用默认止损距离1%")
        
        print(f"📊 止损分析: 当前价={current_price:.2f}, 止损价={stop_loss:.2f}, 止损距离={stop_loss_distance_pct:.2%}")
        
        # 2. 计算最大可承受亏损和最大安全交易金额
        max_acceptable_loss = total_balance * risk_config['max_position_drawdown']  # 3%
        max_safe_trade_amount = max_acceptable_loss / stop_loss_distance_pct
        
        print(f"📊 风险控制:")
        print(f"   - 最大可承受亏损: {max_acceptable_loss:.2f} USDT ({risk_config['max_position_drawdown']:.1%})")
        print(f"   - 最大安全交易金额: {max_safe_trade_amount:.2f} USDT")
        
        # 3. 根据最大安全交易金额计算合约张数
        contract_value_per_unit = price_data['price'] * TRADE_CONFIG['contract_size']
        max_safe_contract_size = max_safe_trade_amount / contract_value_per_unit
        
        # 4. 根据目标资金利用率优化杠杆和仓位
        target_utilization = risk_config.get('target_capital_utilization', 0.50)
        max_utilization = risk_config.get('max_capital_utilization', 0.60)
        min_leverage = risk_config.get('min_leverage', 1)
        max_leverage = risk_config.get('max_leverage', 10)
        target_margin = total_balance * target_utilization
        
        # 5. 计算最优杠杆和仓位
        win_rate = performance_tracker.get('win_rate', 0)
        dynamic_leverage = get_dynamic_leverage(win_rate)
        print(f"📊 动态杠杆调整: 胜率={win_rate:.1%}, 初始杠杆={dynamic_leverage}x")
        
        optimal_leverage = dynamic_leverage
        optimal_contract_size = max_safe_contract_size
        
        # 计算当前保证金和资金利用率
        current_margin = (optimal_contract_size * contract_value_per_unit) / optimal_leverage
        current_utilization = current_margin / total_balance if total_balance > 0 else 0
        
        # 如果资金利用率低于目标，尝试优化杠杆
        if current_utilization < target_utilization and current_utilization < max_utilization:
            # 尝试提高杠杆（在安全范围内）
            for test_leverage in range(int(optimal_leverage), min(max_leverage + 1, 11)):
                test_margin = (optimal_contract_size * contract_value_per_unit) / test_leverage
                test_utilization = test_margin / total_balance if total_balance > 0 else 0
                if test_utilization <= max_utilization:
                    optimal_leverage = test_leverage
                    current_margin = test_margin
                    current_utilization = test_utilization
                else:
                    break
            if optimal_leverage > dynamic_leverage:
                print(f"📈 优化杠杆: {dynamic_leverage}x → {optimal_leverage}x (资金利用率: {current_utilization:.1%})")
        
        # 6. 最终验证和调整
        if current_utilization > max_utilization:
            # 按最大资金利用率调整
            max_margin = total_balance * max_utilization
            optimal_contract_size = (max_margin * optimal_leverage) / contract_value_per_unit
            optimal_contract_size = round(optimal_contract_size, 2)
            current_margin = (optimal_contract_size * contract_value_per_unit) / optimal_leverage
            current_utilization = current_margin / total_balance if total_balance > 0 else 0
            print(f"⚠️ 资金利用率超过上限，已调整仓位以符合最大利用率限制")
        
        # 7. 确保不低于最小交易量
        min_contracts = TRADE_CONFIG.get('min_amount', 0.01)
        
        # 🧪 测试模式：如果启用测试模式，强制使用最小仓位
        if TRADE_CONFIG.get('test_mode', False) and TRADE_CONFIG.get('force_min_position', False):
            optimal_contract_size = min_contracts
            print(f"🧪 测试模式：强制使用最小仓位 {min_contracts} 张")
        else:
            optimal_contract_size = max(optimal_contract_size, min_contracts)
        
        optimal_contract_size = round(optimal_contract_size, 2)
        
        # 重新计算最终保证金和资金利用率
        final_margin = (optimal_contract_size * contract_value_per_unit) / optimal_leverage
        final_utilization = final_margin / total_balance if total_balance > 0 else 0
        final_trade_amount = optimal_contract_size * contract_value_per_unit
        
        print(f"📊 智能仓位计算（基于风险反推）:")
        print(f"   - 止损距离: {stop_loss_distance_pct:.2%}")
        print(f"   - 最大可承受亏损: {max_acceptable_loss:.2f} USDT (3%)")
        print(f"   - 最大安全交易金额: {max_safe_trade_amount:.2f} USDT")
        print(f"   - 最优杠杆: {optimal_leverage}x")
        print(f"   - 最终仓位: {optimal_contract_size:.2f} 张")
        print(f"   - 实际交易金额: {final_trade_amount:.2f} USDT")
        print(f"   - 实际保证金: {final_margin:.2f} USDT")
        print(f"   - 资金利用率: {final_utilization:.1%} (目标: {target_utilization:.0%}, 上限: {max_utilization:.0%})")
        
        return {
            'contract_size': optimal_contract_size,
            'optimal_leverage': optimal_leverage
        }
        
    except Exception as e:
        print(f"❌ 仓位计算失败: {e}")
        traceback.print_exc()
        # 紧急备用
        base_amount = 100  # 基础100USDT
        default_leverage = TRADE_CONFIG.get('leverage', 6)
        contract_size = (base_amount * default_leverage) / (price_data['price'] * TRADE_CONFIG.get('contract_size', 0.01))
        contract_size = round(max(contract_size, TRADE_CONFIG.get('min_amount', 0.01)), 2)
        return {
            'contract_size': contract_size,
            'optimal_leverage': default_leverage
        }

def calculate_trend_based_position(signal_data, price_data, current_position):
    """
    基于风险反推的智能仓位计算 - 趋势为王理念
    根据止损距离和最大可承受亏损（3%）反推最大安全交易金额，然后优化杠杆和资金利用率
    
    Args:
        signal_data: 信号数据
        price_data: 价格数据
        current_position: 当前持仓
        
    Returns:
        dict: {'contract_size': float, 'optimal_leverage': int} 合约张数和最优杠杆
    """
    risk_config = TRADE_CONFIG['risk_management']
    
    # 1. 先读取账户价值（总资产）
    balance = exchange.fetch_balance()
    total_balance = balance.get('USDT', {}).get('total', 0)  # 总资产（包括已占用的保证金）
    free_balance = balance.get('USDT', {}).get('free', 0)  # 可用余额
    
    if TRADE_CONFIG.get('test_mode', False):
        total_balance = 10000
        free_balance = 10000
    
    # 检查当前持仓占用的保证金
    current_margin_used = 0
    if current_position and current_position.get('size', 0) > 0:
        current_position_size = current_position['size']
        current_leverage = current_position.get('leverage', TRADE_CONFIG.get('leverage', 6))
        current_margin_used = (current_position_size * price_data['price'] * TRADE_CONFIG['contract_size']) / current_leverage
    
    print(f"💰 账户信息:")
    print(f"   - 总资产: {total_balance:.2f} USDT")
    print(f"   - 可用余额: {free_balance:.2f} USDT")
    if current_margin_used > 0:
        print(f"   - 当前持仓占用保证金: {current_margin_used:.2f} USDT")
    
    # 使用总资产进行后续计算（确保基于完整账户价值计算资金利用率）
    
    # 1. 获取止损距离
    stop_loss = signal_data.get('stop_loss', 0)
    current_price = price_data['price']
    if stop_loss > 0:
        stop_loss_distance = abs(stop_loss - current_price)
        stop_loss_distance_pct = stop_loss_distance / current_price
    else:
        # 如果没有止损，使用默认1%
        stop_loss_distance_pct = 0.01
        print(f"⚠️ 未找到止损价，使用默认止损距离1%")
    
    print(f"📊 止损分析: 当前价={current_price:.2f}, 止损价={stop_loss:.2f}, 止损距离={stop_loss_distance_pct:.2%}")
    
    # 2. 计算最大可承受亏损和最大安全交易金额
    max_acceptable_loss = total_balance * risk_config['max_position_drawdown']  # 3%
    max_safe_trade_amount = max_acceptable_loss / stop_loss_distance_pct
    
    print(f"📊 风险控制:")
    print(f"   - 最大可承受亏损: {max_acceptable_loss:.2f} USDT ({risk_config['max_position_drawdown']:.1%})")
    print(f"   - 最大安全交易金额: {max_safe_trade_amount:.2f} USDT")
    
    # 3. 根据最大安全交易金额计算合约张数
    contract_value_per_unit = price_data['price'] * TRADE_CONFIG['contract_size']
    max_safe_contract_size = max_safe_trade_amount / contract_value_per_unit
    
    # 4. 根据目标资金利用率优化杠杆和仓位
    target_utilization = risk_config.get('target_capital_utilization', 0.50)
    max_utilization = risk_config.get('max_capital_utilization', 0.60)
    min_leverage = risk_config.get('min_leverage', 1)
    max_leverage = risk_config.get('max_leverage', 10)
    target_margin = total_balance * target_utilization
    
    # 5. 计算最优杠杆和仓位
    win_rate = performance_tracker.get('win_rate', 0)
    dynamic_leverage = get_dynamic_leverage(win_rate)
    print(f"📊 动态杠杆调整: 胜率={win_rate:.1%}, 初始杠杆={dynamic_leverage}x")
    
    optimal_leverage = dynamic_leverage
    optimal_contract_size = max_safe_contract_size
    
    # 计算当前保证金和资金利用率
    current_margin = (optimal_contract_size * contract_value_per_unit) / optimal_leverage
    current_utilization = current_margin / total_balance if total_balance > 0 else 0
    
    # 如果资金利用率低于目标，尝试优化杠杆
    if current_utilization < target_utilization and current_utilization < max_utilization:
        # 尝试提高杠杆（在安全范围内）
        for test_leverage in range(int(optimal_leverage), min(max_leverage + 1, 11)):
            test_margin = (optimal_contract_size * contract_value_per_unit) / test_leverage
            test_utilization = test_margin / total_balance if total_balance > 0 else 0
            if test_utilization <= max_utilization:
                optimal_leverage = test_leverage
                current_margin = test_margin
                current_utilization = test_utilization
            else:
                break
        if optimal_leverage > dynamic_leverage:
            print(f"📈 优化杠杆: {dynamic_leverage}x → {optimal_leverage}x (资金利用率: {current_utilization:.1%})")
    
    # 6. 最终验证和调整
    if current_utilization > max_utilization:
        # 按最大资金利用率调整
        max_margin = total_balance * max_utilization
        optimal_contract_size = (max_margin * optimal_leverage) / contract_value_per_unit
        optimal_contract_size = round(optimal_contract_size, 2)
        current_margin = (optimal_contract_size * contract_value_per_unit) / optimal_leverage
        current_utilization = current_margin / total_balance if total_balance > 0 else 0
        print(f"⚠️ 资金利用率超过上限，已调整仓位以符合最大利用率限制")
    
    # 7. 确保不低于最小交易量
    min_contracts = TRADE_CONFIG.get('min_amount', 0.01)
    optimal_contract_size = max(optimal_contract_size, min_contracts)
    optimal_contract_size = round(optimal_contract_size, 2)
    
    # 重新计算最终保证金和资金利用率
    final_margin = (optimal_contract_size * contract_value_per_unit) / optimal_leverage
    final_utilization = final_margin / total_balance if total_balance > 0 else 0
    final_trade_amount = optimal_contract_size * contract_value_per_unit
    
    # 趋势强度信息（用于日志显示和仓位调整）
    trend_score = signal_data.get('trend_score', 0)
    if trend_score >= 8:
        trend_desc = "极强趋势"
    elif trend_score >= 7:
        trend_desc = "强趋势"
    elif trend_score >= 5:
        trend_desc = "中等趋势"
    elif trend_score >= 4:
        trend_desc = "正常趋势"
    else:
        trend_desc = "弱趋势"
    
    # 🔧 优化：根据趋势强度过滤，中等趋势降低仓位50%
    trend_strength_multiplier = 1.0
    if trend_score >= 7:
        # 强趋势：正常仓位
        trend_strength_multiplier = 1.0
        print(f"✅ 强趋势({trend_score}/10)：正常仓位")
    elif trend_score >= 5:
        # 中等趋势：降低仓位50%
        trend_strength_multiplier = 0.5
        print(f"⚠️ 中等趋势({trend_score}/10)：降低仓位50%")
    else:
        # 弱趋势：不应该交易（已在信号生成时过滤），但这里作为保护
        trend_strength_multiplier = 0.3
        print(f"❌ 弱趋势({trend_score}/10)：极低仓位（建议观望）")
    
    # 应用趋势强度过滤乘数
    optimal_contract_size = optimal_contract_size * trend_strength_multiplier
    
    # 🎯 布林带位置作为结构优化乘数
    bb_position = price_data['technical_data'].get('bb_position', 0.5)
    structure_multiplier = 1.0
    
    if bb_position < 0.1 or bb_position > 0.9:
        # 布林带极端位置：如果是顺势，可能是趋势加速；如果是逆势，需要谨慎
        if (signal_data['signal'] == 'BUY' and bb_position < 0.1) or (signal_data['signal'] == 'SELL' and bb_position > 0.9):
            # 顺势的布林带极端位置：趋势加速信号，可以适当增加仓位
            structure_multiplier = 1.2
            print(f"🚀 布林带极端位置顺势：趋势加速信号，仓位乘数 ×{structure_multiplier}")
        else:
            # 逆势的布林带极端位置：需要谨慎，降低仓位
            structure_multiplier = 0.7
            print(f"⚠️ 布林带极端位置逆势：谨慎交易，仓位乘数 ×{structure_multiplier}")
    elif bb_position < 0.2 or bb_position > 0.8:
        # 布林带边缘位置：正常结构信号
        structure_multiplier = 1.0
    else:
        # 布林带中部：无特殊结构信号
        structure_multiplier = 0.9
        print(f"📊 布林带中部：无明确结构信号，仓位乘数 ×{structure_multiplier}")
    
    # 应用结构优化乘数
    optimal_contract_size = optimal_contract_size * structure_multiplier
    optimal_contract_size = round(optimal_contract_size, 2)
    
    # 重新计算最终保证金和资金利用率
    final_margin = (optimal_contract_size * contract_value_per_unit) / optimal_leverage
    final_utilization = final_margin / total_balance if total_balance > 0 else 0
    final_trade_amount = optimal_contract_size * contract_value_per_unit
    
    print(f"📊 趋势为王仓位管理（结构优化）:")
    print(f"   - 止损距离: {stop_loss_distance_pct:.2%}")
    print(f"   - 趋势强度: {trend_score}/10 ({trend_desc}) → 趋势过滤乘数 ×{trend_strength_multiplier}")
    print(f"   - 布林带位置: {bb_position:.3f} → 结构乘数 ×{structure_multiplier}")
    print(f"   - 最优杠杆: {optimal_leverage}x")
    print(f"   - 最终仓位: {optimal_contract_size:.2f} 张")
    print(f"   - 实际交易金额: {final_trade_amount:.2f} USDT")
    print(f"   - 资金利用率: {final_utilization:.1%}")
    
    return {
        'contract_size': optimal_contract_size,
        'optimal_leverage': optimal_leverage
    }

def calculate_technical_indicators(df):
    """增强技术指标计算"""
    try:
        # 移动平均线
        df['sma_5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['sma_20'] = df['close'].rolling(window=20, min_periods=1).mean()
        df['sma_50'] = df['close'].rolling(window=50, min_periods=1).mean()
        
        # EMA
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 布林带
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 成交量
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # ATR
        df['atr'] = calculate_atr(df)
        
        # 填充NaN
        df = df.bfill().ffill()
        
        return df
    except Exception as e:
        print(f"技术指标计算失败: {e}")
        return df

def get_market_trend(df):
    """增强趋势分析"""
    try:
        current_price = df['close'].iloc[-1]
        
        # 多时间框架趋势
        trend_short = "上涨" if current_price > df['sma_20'].iloc[-1] else "下跌"
        trend_medium = "上涨" if current_price > df['sma_50'].iloc[-1] else "下跌"
        
        # MACD趋势
        macd_trend = "bullish" if df['macd'].iloc[-1] > df['macd_signal'].iloc[-1] else "bearish"
        
        # 价格位置分析
        bb_position = df['bb_position'].iloc[-1]
        if bb_position > 0.7:
            price_level = "高位"
        elif bb_position < 0.3:
            price_level = "低位"
        else:
            price_level = "中位"
            
        # 综合趋势判断
        if trend_short == "上涨" and trend_medium == "上涨":
            overall_trend = "强势上涨"
            trend_strength = "强"
        elif trend_short == "下跌" and trend_medium == "下跌":
            overall_trend = "强势下跌" 
            trend_strength = "强"
        else:
            overall_trend = "震荡整理"
            trend_strength = "弱"
            
        return {
            'short_term': trend_short,
            'medium_term': trend_medium,
            'macd': macd_trend,
            'overall': overall_trend,
            'trend_strength': trend_strength,
            'price_level': price_level,
            'rsi_level': df['rsi'].iloc[-1],
            'bb_position': bb_position
        }
    except Exception as e:
        print(f"趋势分析失败: {e}")
        return {}

def detect_market_regime(df):
    """
    识别市场环境：趋势市场 vs 震荡市场
    🔧 优化：用于减少在震荡市场的无效交易
    
    Args:
        df: 包含技术指标的DataFrame
        
    Returns:
        str: 'trending' (趋势市场) 或 'ranging' (震荡市场)
    """
    try:
        current_price = df['close'].iloc[-1]
        sma_20 = df['sma_20'].iloc[-1]
        sma_50 = df['sma_50'].iloc[-1]
        
        # 计算价格相对均线的偏离度
        price_vs_sma20 = abs((current_price - sma_20) / sma_20) if sma_20 > 0 else 0
        price_vs_sma50 = abs((current_price - sma_50) / sma_50) if sma_50 > 0 else 0
        
        # 计算最近20根K线的价格波动范围
        recent_high = df['high'].tail(20).max()
        recent_low = df['low'].tail(20).min()
        price_range_pct = (recent_high - recent_low) / recent_low if recent_low > 0 else 0
        
        # 判断标准：
        # 1. 价格在均线附近窄幅波动（<0.5%和<1%）
        # 2. 最近20根K线波动范围较小（<2%）
        # 3. 均线接近（20日均线和50日均线差距<1%）
        sma_gap = abs((sma_20 - sma_50) / sma_50) if sma_50 > 0 else 0
        
        if (price_vs_sma20 < 0.005 and price_vs_sma50 < 0.01 and 
            price_range_pct < 0.02 and sma_gap < 0.01):
            return 'ranging'  # 震荡市场
        else:
            return 'trending'  # 趋势市场
    except Exception as e:
        print(f"⚠️ 市场环境识别失败: {e}")
        return 'trending'  # 默认返回趋势市场

def get_support_resistance_levels(df, lookback=20):
    """计算支撑阻力位"""
    try:
        recent_high = df['high'].tail(lookback).max()
        recent_low = df['low'].tail(lookback).min()
        current_price = df['close'].iloc[-1]

        resistance_level = recent_high
        support_level = recent_low

        # 动态支撑阻力（基于布林带）
        bb_upper = df['bb_upper'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]

        return {
            'static_resistance': resistance_level,
            'static_support': support_level,
            'dynamic_resistance': bb_upper,
            'dynamic_support': bb_lower,
            'price_vs_resistance': ((resistance_level - current_price) / current_price) * 100,
            'price_vs_support': ((current_price - support_level) / support_level) * 100
        }
    except Exception as e:
        print(f"支撑阻力计算失败: {e}")
        return {}

# =============================================================================
# 趋势为王，结构修边 - 核心功能模块
# =============================================================================

def enhanced_trend_analysis(df):
    """
    增强趋势分析 - 实现"趋势为王"理念
    通过多维度指标量化趋势强度，为交易决策提供核心依据
    
    Args:
        df: 包含技术指标的DataFrame
        
    Returns:
        dict: 包含趋势类型、强度评分、置信度等信息的字典
    """
    # 1. 均线系统趋势判断（核心趋势）
    ma_trend = "震荡"
    if df['sma_5'].iloc[-1] > df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1]:
        ma_trend = "强势上涨"
    elif df['sma_5'].iloc[-1] < df['sma_20'].iloc[-1] < df['sma_50'].iloc[-1]:
        ma_trend = "强势下跌"
    
    # 2. 趋势强度评分系统（0-10分）
    trend_score = 0
    
    # 均线排列得分（核心权重）
    if ma_trend == "强势上涨":
        trend_score += 3
    elif ma_trend == "强势下跌":
        trend_score += 3
    
    # 价格位置得分 - 修复：考虑下跌情况
    current_price = df['close'].iloc[-1]
    if ma_trend == "强势上涨":
        # 上涨趋势：价格高于均线得分
        if current_price > df['sma_20'].iloc[-1]:
            trend_score += 2
        if current_price > df['sma_50'].iloc[-1]:
            trend_score += 1
    elif ma_trend == "强势下跌":
        # 下跌趋势：价格低于均线得分
        if current_price < df['sma_20'].iloc[-1]:
            trend_score += 2
        if current_price < df['sma_50'].iloc[-1]:
            trend_score += 1
    else:
        # 震荡趋势：价格相对位置得分
        if current_price > df['sma_20'].iloc[-1]:
            trend_score += 1
    
    # MACD趋势得分 - 修复：考虑下跌情况
    macd_value = df['macd'].iloc[-1]
    macd_signal = df['macd_signal'].iloc[-1]
    macd_histogram = df['macd_histogram'].iloc[-1]
    
    if ma_trend == "强势上涨":
        # 上涨趋势：MACD金叉和正柱状图得分
        if macd_value > macd_signal:
            trend_score += 2
        if macd_histogram > 0:
            trend_score += 1
    elif ma_trend == "强势下跌":
        # 下跌趋势：MACD死叉和负柱状图得分
        if macd_value < macd_signal:
            trend_score += 2
        if macd_histogram < 0:
            trend_score += 1
    else:
        # 震荡趋势：MACD方向得分
        if macd_value > macd_signal:
            trend_score += 1
    
    # 成交量确认得分
    if df['volume_ratio'].iloc[-1] > 1.2:
        trend_score += 1
    
    # 3. 趋势等级和置信度判断
    if trend_score >= 7:
        trend_level = "强趋势"
        confidence = "高"
    elif trend_score >= 4:
        trend_level = "中等趋势" 
        confidence = "中"
    else:
        trend_level = "弱趋势"
        confidence = "低"
    
    return {
        'primary_trend': ma_trend,      # 主要趋势方向
        'trend_score': trend_score,     # 趋势强度评分(0-10)
        'trend_level': trend_level,     # 趋势等级描述
        'confidence': confidence,       # 趋势置信度
        'current_price': current_price  # 当前价格
    }

def structure_timing_signals(df, primary_trend):
    """
    结构修边 - 寻找优化入场时机
    在主要趋势确定的基础上，寻找技术结构提供的入场时机
    
    Args:
        df: 包含技术指标的DataFrame
        primary_trend: 主要趋势方向
        
    Returns:
        list: 结构信号列表
    """
    current_price = df['close'].iloc[-1]
    signals = []
    
    if primary_trend == "强势上涨":
        # 上涨趋势中的结构买入机会
        if current_price < df['sma_5'].iloc[-1] and df['rsi'].iloc[-1] < 60:
            signals.append("回踩5日线买入机会")
        if current_price < df['bb_middle'].iloc[-1] and df['bb_position'].iloc[-1] < 0.4:
            signals.append("回踩布林中轨买入机会")
        if df['macd_histogram'].iloc[-1] > df['macd_histogram'].iloc[-2] and df['macd_histogram'].iloc[-2] < 0:
            signals.append("MACD绿柱放大买入机会")
        if df['rsi'].iloc[-1] < 45 and df['rsi'].iloc[-1] > df['rsi'].iloc[-2]:
            signals.append("RSI超卖反弹买入机会")
    
    elif primary_trend == "强势下跌":
        # 下跌趋势中的结构做空机会 - 修复：添加更多做空信号
        if current_price > df['sma_5'].iloc[-1] and df['rsi'].iloc[-1] > 40:
            signals.append("反弹5日线做空机会")
        if current_price > df['bb_middle'].iloc[-1] and df['bb_position'].iloc[-1] > 0.6:
            signals.append("反弹布林中轨做空机会")
        if df['macd_histogram'].iloc[-1] < df['macd_histogram'].iloc[-2] and df['macd_histogram'].iloc[-2] > 0:
            signals.append("MACD红柱放大做空机会")
        if df['rsi'].iloc[-1] > 55 and df['rsi'].iloc[-1] < df['rsi'].iloc[-2]:
            signals.append("RSI超买回落做空机会")
        # 新增下跌趋势信号
        if current_price > df['sma_20'].iloc[-1] and df['rsi'].iloc[-1] > 50:
            signals.append("反弹20日线做空机会")
        if df['bb_position'].iloc[-1] > 0.8:  # 接近布林带上轨
            signals.append("布林带上轨阻力做空机会")
    
    return signals

def generate_trend_king_signal(price_data):
    """
    基于"趋势为王，结构修边"理念生成交易信号
    核心逻辑：趋势决定方向，结构优化时机
    
    Args:
        price_data: 价格数据字典
        
    Returns:
        dict: 交易信号字典
    """
    df = price_data['full_data']
    
    # 1. 趋势分析 - 趋势为王
    trend_analysis = enhanced_trend_analysis(df)
    primary_trend = trend_analysis['primary_trend']
    trend_score = trend_analysis['trend_score']
    
    # 🔧 优化：市场环境识别
    market_regime = detect_market_regime(df)
    
    # 2. 结构分析 - 结构修边
    structure_signals = structure_timing_signals(df, primary_trend)
    
    # 3. 信号生成逻辑 - 🔧 优化：趋势强度过滤 + 市场环境识别，提高胜率
    # 震荡市场且趋势不强时，建议观望
    if market_regime == 'ranging' and trend_score < 6:
        # 震荡市场且趋势不强：建议观望
        return {
            "signal": "HOLD",
            "reason": f"震荡市场且趋势不强(强度{trend_score}/10)，建议观望",
            "confidence": "LOW",
            "trend_score": trend_score,
            "primary_trend": primary_trend,
            "structure_signals": structure_signals,
            "structure_optimized": False,
            "risk_assessment": "高风险",
            "market_regime": market_regime
        }
    
    # 🔧 修复：严格执行趋势强度过滤，只在极强趋势中交易，减少频繁开仓平仓
    # 提高门槛：从≥7提高到≥8，完全禁止<8的交易
    if trend_score >= 8:  # 极强趋势：正常交易
        if primary_trend == "强势上涨":
            base_signal = "BUY"
            base_confidence = "HIGH"
        elif primary_trend == "强势下跌":
            base_signal = "SELL"
            base_confidence = "HIGH"
        else:
            base_signal = "HOLD"
            base_confidence = "LOW"
    else:  # 趋势强度<8：坚决观望，禁止交易
        base_signal = "HOLD"
        base_confidence = "LOW"
    
    # 4. 🔧 优化：结构信号优化入场时机
    final_signal = base_signal
    final_confidence = base_confidence
    
    if base_signal != "HOLD" and structure_signals:
        # 有趋势且有结构信号支持 - 最佳情况
        if base_confidence == "MEDIUM":
            final_confidence = "HIGH"  # 结构信号提升信心
        reason = f"趋势确认({primary_trend}, 强度{trend_score}/10)，结构信号:{', '.join(structure_signals)}"
        structure_optimized = True
    elif base_signal != "HOLD":
        # 🔧 优化：极强趋势但无结构信号时，等待更好时机
        # 注意：base_signal != "HOLD"意味着trend_score >= 8（因为门槛已提高到≥8）
        if trend_score >= 8:
            # 极强趋势但无结构信号：建议等待，不立即入场
            final_signal = "HOLD"
            final_confidence = "LOW"
            reason = f"极强趋势({primary_trend}, 强度{trend_score}/10)但无结构信号，等待更好入场时机"
            structure_optimized = False
        else:
            # 这种情况理论上不应该发生（因为门槛已提高到≥8），但保留作为保护
            reason = f"趋势确认({primary_trend}, 强度{trend_score}/10)，等待更好结构时机"
            structure_optimized = False
    else:
        # 无明确趋势 - 建议观望
        reason = f"趋势不明确(强度{trend_score}/10)，建议观望"
        structure_optimized = False
    
    return {
        "signal": final_signal,
        "reason": reason,
        "confidence": final_confidence,
        "trend_score": trend_score,
        "primary_trend": primary_trend,
        "structure_signals": structure_signals,
        "structure_optimized": structure_optimized,
        "risk_assessment": "低风险" if final_confidence == "HIGH" else "中风险" if final_confidence == "MEDIUM" else "高风险",
        "market_regime": market_regime  # 🔧 优化：添加市场环境信息
    }

def get_btc_ohlcv_enhanced():
    """增强版：获取BTC K线数据并计算技术指标"""
    try:
        # 获取K线数据
        ohlcv = exchange.fetch_ohlcv(TRADE_CONFIG['symbol'], TRADE_CONFIG['timeframe'],
                                     limit=TRADE_CONFIG['data_points'])

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # 计算技术指标
        df = calculate_technical_indicators(df)

        current_data = df.iloc[-1]
        previous_data = df.iloc[-2]

        # 获取技术分析数据
        trend_analysis = get_market_trend(df)
        levels_analysis = get_support_resistance_levels(df)

        return {
            'price': current_data['close'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'high': current_data['high'],
            'low': current_data['low'],
            'volume': current_data['volume'],
            'timeframe': TRADE_CONFIG['timeframe'],
            'price_change': ((current_data['close'] - previous_data['close']) / previous_data['close']) * 100,
            'kline_data': df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(10).to_dict('records'),
            'technical_data': {
                'sma_5': current_data.get('sma_5', 0),
                'sma_20': current_data.get('sma_20', 0),
                'sma_50': current_data.get('sma_50', 0),
                'rsi': current_data.get('rsi', 0),
                'macd': current_data.get('macd', 0),
                'macd_signal': current_data.get('macd_signal', 0),
                'macd_histogram': current_data.get('macd_histogram', 0),
                'bb_upper': current_data.get('bb_upper', 0),
                'bb_lower': current_data.get('bb_lower', 0),
                'bb_position': current_data.get('bb_position', 0),
                'volume_ratio': current_data.get('volume_ratio', 0),
                'atr': current_data.get('atr', 0)
            },
            'trend_analysis': trend_analysis,
            'levels_analysis': levels_analysis,
            'full_data': df
        }
    except Exception as e:
        print(f"获取增强K线数据失败: {e}")
        traceback.print_exc()
        return None

def generate_technical_analysis_text(price_data):
    """生成技术分析文本"""
    if 'technical_data' not in price_data:
        return "技术指标数据不可用"

    tech = price_data['technical_data']
    trend = price_data.get('trend_analysis', {})
    levels = price_data.get('levels_analysis', {})

    # 检查数据有效性
    def safe_float(value, default=0):
        return float(value) if value and pd.notna(value) else default

    analysis_text = f"""
    【技术指标分析】
    📈 移动平均线:
    - 5周期: {safe_float(tech['sma_5']):.2f} | 价格相对: {(price_data['price'] - safe_float(tech['sma_5'])) / safe_float(tech['sma_5']) * 100:+.2f}%
    - 20周期: {safe_float(tech['sma_20']):.2f} | 价格相对: {(price_data['price'] - safe_float(tech['sma_20'])) / safe_float(tech['sma_20']) * 100:+.2f}%
    - 50周期: {safe_float(tech['sma_50']):.2f} | 价格相对: {(price_data['price'] - safe_float(tech['sma_50'])) / safe_float(tech['sma_50']) * 100:+.2f}%

    🎯 趋势分析:
    - 短期趋势: {trend.get('short_term', 'N/A')}
    - 中期趋势: {trend.get('medium_term', 'N/A')}
    - 整体趋势: {trend.get('overall', 'N/A')}
    - MACD方向: {trend.get('macd', 'N/A')}

    📊 动量指标:
    - RSI: {safe_float(tech['rsi']):.2f} ({'超买' if safe_float(tech['rsi']) > 70 else '超卖' if safe_float(tech['rsi']) < 30 else '中性'})
    - MACD: {safe_float(tech['macd']):.4f}
    - 信号线: {safe_float(tech['macd_signal']):.4f}

    🎚️ 布林带位置: {safe_float(tech['bb_position']):.2%} ({'上部' if safe_float(tech['bb_position']) > 0.7 else '下部' if safe_float(tech['bb_position']) < 0.3 else '中部'})

    💰 关键水平:
    - 静态阻力: {safe_float(levels.get('static_resistance', 0)):.2f}
    - 静态支撑: {safe_float(levels.get('static_support', 0)):.2f}
    """
    return analysis_text

def get_sentiment_indicators():
    """获取市场情绪指标 - 带监控和降级处理"""
    global sentiment_api_monitor
    
    # 每日重置失败计数
    current_date = datetime.now().date()
    if sentiment_api_monitor['last_reset_date'] != current_date:
        sentiment_api_monitor['failure_count_today'] = 0
        sentiment_api_monitor['last_reset_date'] = current_date
        print("🔄 市场情绪API监控：每日计数器已重置")
    
    API_URL = "https://service.cryptoracle.network/openapi/v2/endpoint"
    API_KEY = os.getenv('CRYPTORACLE_API_KEY', '')
    
    # 更新监控状态
    sentiment_api_monitor['last_check'] = datetime.now()
    sentiment_api_monitor['total_requests'] += 1
    
    # 如果API密钥未配置，直接返回None
    if not API_KEY:
        print("⚠️ 市场情绪API密钥未配置，跳过情绪分析")
        sentiment_api_monitor['is_available'] = False
        return None
    
    # 如果连续失败超过5次，暂停使用API（避免频繁请求失败的服务）
    if sentiment_api_monitor['consecutive_failures'] >= 5:
        print(f"⚠️ 市场情绪API连续失败{sentiment_api_monitor['consecutive_failures']}次，暂停使用")
        sentiment_api_monitor['is_available'] = False
        return None
    
    try:
        # 设置超时时间（避免长时间等待）
        timeout = 10  # 10秒超时
        
        # 获取最近4小时数据
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=4)

        request_body = {
            "apiKey": API_KEY,
            "endpoints": ["CO-A-02-01", "CO-A-02-02"],
            "startTime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "timeType": "15m",
            "token": ["BTC"]
        }

        headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}
        
        # 发送请求（带超时控制）
        response = requests.post(API_URL, json=request_body, headers=headers, timeout=timeout)

        # 检查HTTP状态码
        if response.status_code == 200:
            data = response.json()
            
            # 检查API返回的业务状态码
            if data.get("code") == 200 and data.get("data"):
                time_periods = data["data"][0]["timePeriods"]

                # 查找第一个有有效数据的时间段
                for period in time_periods:
                    period_data = period.get("data", [])

                    sentiment = {}
                    valid_data_found = False

                    for item in period_data:
                        endpoint = item.get("endpoint")
                        value = item.get("value", "").strip()

                        if value:
                            try:
                                if endpoint in ["CO-A-02-01", "CO-A-02-02"]:
                                    sentiment[endpoint] = float(value)
                                    valid_data_found = True
                            except (ValueError, TypeError):
                                continue

                    # 如果找到有效数据
                    if valid_data_found and "CO-A-02-01" in sentiment and "CO-A-02-02" in sentiment:
                        positive = sentiment['CO-A-02-01']
                        negative = sentiment['CO-A-02-02']
                        net_sentiment = positive - negative

                        # 计算数据延迟
                        data_delay = int((datetime.now() - datetime.strptime(
                            period['startTime'], '%Y-%m-%d %H:%M:%S')).total_seconds() // 60)

                        # 更新监控状态 - 成功
                        sentiment_api_monitor['consecutive_failures'] = 0
                        sentiment_api_monitor['is_available'] = True
                        sentiment_api_monitor['last_success'] = datetime.now()
                        sentiment_api_monitor['successful_requests'] += 1
                        sentiment_api_monitor['last_error'] = None

                        print(f"✅ 市场情绪API正常: 乐观{positive:.1%} 悲观{negative:.1%} 净值{net_sentiment:+.3f} (延迟:{data_delay}分钟)")

                        return {
                            'positive_ratio': positive,
                            'negative_ratio': negative,
                            'net_sentiment': net_sentiment,
                            'data_time': period['startTime'],
                            'data_delay_minutes': data_delay
                        }

                # 数据为空但HTTP请求成功
                error_msg = "API返回数据为空"
                sentiment_api_monitor['consecutive_failures'] += 1
                sentiment_api_monitor['failure_count_today'] += 1
                sentiment_api_monitor['last_error'] = error_msg
                print(f"⚠️ 市场情绪API: {error_msg}")
                return None
            else:
                # API返回错误码
                error_msg = f"API返回错误码: {data.get('code', 'unknown')}, 消息: {data.get('msg', 'unknown')}"
                sentiment_api_monitor['consecutive_failures'] += 1
                sentiment_api_monitor['failure_count_today'] += 1
                sentiment_api_monitor['last_error'] = error_msg
                print(f"⚠️ 市场情绪API: {error_msg}")
                return None
        else:
            # HTTP错误
            error_msg = f"HTTP错误: {response.status_code}"
            sentiment_api_monitor['consecutive_failures'] += 1
            sentiment_api_monitor['failure_count_today'] += 1
            sentiment_api_monitor['last_error'] = error_msg
            print(f"⚠️ 市场情绪API: {error_msg}")
            return None

    except requests.exceptions.Timeout:
        error_msg = "请求超时（超过10秒）"
        sentiment_api_monitor['consecutive_failures'] += 1
        sentiment_api_monitor['failure_count_today'] += 1
        sentiment_api_monitor['last_error'] = error_msg
        print(f"⚠️ 市场情绪API: {error_msg}")
        return None
        
    except requests.exceptions.ConnectionError:
        error_msg = "连接错误（无法连接到服务器）"
        sentiment_api_monitor['consecutive_failures'] += 1
        sentiment_api_monitor['failure_count_today'] += 1
        sentiment_api_monitor['last_error'] = error_msg
        print(f"⚠️ 市场情绪API: {error_msg}")
        return None
        
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        sentiment_api_monitor['consecutive_failures'] += 1
        sentiment_api_monitor['failure_count_today'] += 1
        sentiment_api_monitor['last_error'] = error_msg
        print(f"⚠️ 市场情绪API获取失败: {e}")
        traceback.print_exc()
        return None

def check_sentiment_api_health():
    """检查市场情绪API健康状态"""
    global sentiment_api_monitor
    
    if sentiment_api_monitor['last_check'] is None:
        return "未检查"
    
    if not sentiment_api_monitor['is_available']:
        return f"不可用 (连续失败{sentiment_api_monitor['consecutive_failures']}次)"
    
    if sentiment_api_monitor['last_success']:
        time_since_success = (datetime.now() - sentiment_api_monitor['last_success']).total_seconds() / 60
        if time_since_success > 30:  # 超过30分钟没有成功
            return f"警告 (上次成功: {time_since_success:.1f}分钟前)"
    
    success_rate = 0
    if sentiment_api_monitor['total_requests'] > 0:
        success_rate = (sentiment_api_monitor['successful_requests'] / sentiment_api_monitor['total_requests']) * 100
    
    return f"正常 (成功率: {success_rate:.1f}%, 今日失败: {sentiment_api_monitor['failure_count_today']}次)"

def should_execute_trade(signal_data, price_data, current_position):
    """交易执行条件检查 - 重新设计：布林带极端位置是结构优化机会"""
    tech = price_data['technical_data']
    trend = price_data['trend_analysis']
    
    # 1. RSI极端值过滤（保持原有逻辑）
    rsi = tech.get('rsi', 50)
    if rsi > 80 or rsi < 20:
        print(f"⚠️ RSI极端值({rsi:.1f})，暂停交易")
        return False
        
    # 2. 🎯 重新设计布林带位置逻辑 - 作为结构优化信号
    bb_position = tech.get('bb_position', 0.5)
    trend_score = signal_data.get('trend_score', 0)
    primary_trend = signal_data.get('primary_trend', '')
    
    # 布林带位置解读
    if bb_position < 0.1:
        bb_signal = "触及布林带下轨 - 超卖反弹机会" if primary_trend == "强势上涨" else "突破布林带下轨 - 趋势加速"
    elif bb_position > 0.9:
        bb_signal = "触及布林带上轨 - 超买回落机会" if primary_trend == "强势下跌" else "突破布林带上轨 - 趋势加速"
    elif bb_position < 0.2:
        bb_signal = "接近布林带下轨 - 潜在支撑"
    elif bb_position > 0.8:
        bb_signal = "接近布林带上轨 - 潜在阻力"
    else:
        bb_signal = "布林带中部 - 正常波动"
    
    print(f"📊 布林带结构信号: 位置{bb_position:.3f} → {bb_signal}")
    
    # 🎯 核心逻辑：布林带极端位置是结构优化机会，不是限制条件
    # 只有在趋势与布林带信号严重冲突时才暂停交易
    should_pause = False
    pause_reason = ""
    
    if trend_score >= 7:  # 强趋势
        # 强趋势中，布林带极端位置是趋势加速的信号
        if (primary_trend == "强势上涨" and bb_position < 0.1) or (primary_trend == "强势下跌" and bb_position > 0.9):
            # 趋势方向与布林带位置严重冲突：上涨趋势中触及下轨或下跌趋势中触及上轨
            should_pause = True
            pause_reason = f"强趋势{primary_trend}与布林带位置{bb_position:.3f}严重冲突"
        else:
            # 其他情况都是正常的结构信号
            print(f"🎯 强趋势下的布林带结构信号: {bb_signal}")
    
    elif trend_score >= 4:  # 中等趋势
        # 中等趋势中，只过滤最冲突的情况
        if (primary_trend == "强势上涨" and bb_position < 0.05) or (primary_trend == "强势下跌" and bb_position > 0.95):
            should_pause = True
            pause_reason = f"中等趋势{primary_trend}与布林带极度位置{bb_position:.3f}冲突"
    
    else:  # 弱趋势
        # 弱趋势中，布林带极端位置可能是重要反转信号
        if bb_position < 0.1 or bb_position > 0.9:
            print(f"⚠️ 弱趋势+布林带极端位置{bb_position:.3f}，可能反转，谨慎交易")
            # 不暂停，但会在仓位计算中降低仓位
    
    if should_pause:
        print(f"⏸️ {pause_reason}，暂停交易")
        return False
        
    # 3. 信号连续性检查
    if len(signal_history) >= 2:
        last_signals = [s['signal'] for s in signal_history[-2:]]
        if signal_data['signal'] in last_signals and signal_data['confidence'] == 'LOW':
            print("⚠️ 连续低信心相同信号，暂停执行")
            return False
            
    # 4. 持仓优化检查
    if current_position:
        current_side = current_position['side']
        signal_side = 'long' if signal_data['signal'] == 'BUY' else 'short' if signal_data['signal'] == 'SELL' else None
        
        # 同方向信号检查
        if signal_side == current_side and signal_data['confidence'] == 'LOW':
            print("⚠️ 同方向低信心信号，不调整仓位")
            return False
    
    # 5. 🔧 新增：交易频率限制，减少频繁开仓平仓
    if signal_data['signal'] != 'HOLD':
        now = datetime.now()
        current_date = now.date()
        
        # 检查是否是新的一天，重置每日交易计数
        if performance_tracker.get('last_trade_date') != current_date:
            performance_tracker['daily_trade_count'] = 0
            performance_tracker['last_trade_date'] = current_date
            print(f"📅 新的一天，重置每日交易计数")
        
        # 检查最小交易间隔（2小时）
        last_trade_time = performance_tracker.get('last_trade_time')
        if last_trade_time:
            time_since_last_trade = (now - last_trade_time).total_seconds() / 3600  # 转换为小时
            if time_since_last_trade < 2.0:
                print(f"⏸️ 交易频率限制：距离上次交易仅{time_since_last_trade:.1f}小时，需等待至少2小时")
                return False
        else:
            time_since_last_trade = 999  # 如果没有上次交易记录，允许交易
        
        # 检查每日最大交易次数（10笔/天）
        daily_trade_count = performance_tracker.get('daily_trade_count', 0)
        if daily_trade_count >= 10:
            print(f"⏸️ 交易频率限制：今日已交易{daily_trade_count}笔，达到每日上限10笔")
            return False
        
        print(f"✅ 交易频率检查通过：距离上次交易{time_since_last_trade:.1f}小时，今日已交易{daily_trade_count}笔")
            
    return True

def calculate_dynamic_stop_loss(signal_data, price_data):
    """动态止损止盈计算 - 集成智能移动止盈止损系统
    🔧 优化：根据趋势强度动态调整盈亏比，强趋势中让利润奔跑更多
    """
    current_price = price_data['price']
    atr = price_data['technical_data'].get('atr', current_price * 0.01)
    volatility = calculate_volatility(price_data['full_data'])
    
    # 🔧 获取趋势强度，用于动态调整盈亏比
    trend_score = signal_data.get('trend_score', 0)
    
    # 🔧 根据趋势强度动态调整止损止盈倍数（核心优化）
    if trend_score >= 8:  # 极强趋势
        stop_loss_multiplier = 1.2  # 更紧的止损
        take_profit_multiplier = 3.0  # 更大的止盈（风险收益比1:2.5）
        print(f"📊 极强趋势({trend_score}/10)：止损1.2xATR，止盈3.0xATR（风险收益比1:2.5）")
    elif trend_score >= 6:  # 强趋势
        stop_loss_multiplier = 1.5  # 标准止损
        take_profit_multiplier = 2.5  # 较大止盈（风险收益比1:1.67）
        print(f"📊 强趋势({trend_score}/10)：止损1.5xATR，止盈2.5xATR（风险收益比1:1.67）")
    else:  # 中等或弱趋势
        stop_loss_multiplier = 1.5  # 标准止损
        take_profit_multiplier = 2.0  # 标准止盈（风险收益比1:1.33）
        print(f"📊 中等趋势({trend_score}/10)：止损1.5xATR，止盈2.0xATR（风险收益比1:1.33）")
    
    # 波动性调整（在趋势强度基础上微调）
    if volatility > 1.0:  # 高波动性
        stop_loss_multiplier = min(stop_loss_multiplier + 0.3, 2.0)  # 高波动时稍微放宽止损
    elif volatility < 0.3:  # 低波动性
        stop_loss_multiplier = max(stop_loss_multiplier - 0.2, 1.0)  # 低波动时稍微收紧止损
    
    atr_multiplier = stop_loss_multiplier
        
    if signal_data['signal'] == 'BUY':
        stop_loss = current_price - atr * atr_multiplier
        # 🔧 优化：根据趋势强度使用动态止盈倍数
        take_profit = current_price + atr * take_profit_multiplier
    else:  # SELL
        stop_loss = current_price + atr * atr_multiplier
        # 🔧 优化：根据趋势强度使用动态止盈倍数
        take_profit = current_price - atr * take_profit_multiplier
        
    # 🔧 修复：提高最小止损距离，避免止损过紧被正常波动触发
    min_stop_distance = current_price * 0.015  # 最小1.5%（从0.8%提高到1.5%，减少频繁触发）
    if abs(stop_loss - current_price) < min_stop_distance:
        if signal_data['signal'] == 'BUY':
            stop_loss = current_price * 0.985  # 至少1.5%止损距离（从0.992改为0.985）
        else:
            stop_loss = current_price * 1.015  # 至少1.5%止损距离（从1.008改为1.015）
    
    # 🔧 修复：确保止盈价至少覆盖手续费成本（至少0.1%）
    min_profit_distance = current_price * (TRADING_FEE_RATE + 0.0005)  # 手续费0.1% + 额外0.05%缓冲
    if signal_data['signal'] == 'BUY':
        # 多头：止盈价必须至少高于当前价格的0.15%
        min_take_profit = current_price * 1.0015
        if take_profit < min_take_profit:
            take_profit = min_take_profit
            print(f"⚠️ 止盈价已调整：确保覆盖手续费成本，新止盈价={take_profit:.2f}")
    else:  # SELL
        # 空头：止盈价必须至少低于当前价格的0.15%
        min_take_profit = current_price * 0.9985
        if take_profit > min_take_profit:
            take_profit = min_take_profit
            print(f"⚠️ 止盈价已调整：确保覆盖手续费成本，新止盈价={take_profit:.2f}")
            
    print(f"🎯 动态风控: 止损={stop_loss:.2f}, 止盈={take_profit:.2f}, ATR={atr:.2f} (已考虑手续费成本，使用智能止盈系统)")
    return stop_loss, take_profit

def analyze_with_deepseek(price_data):
    """增强版DeepSeek分析"""
    
    # 生成技术分析文本
    technical_analysis = generate_technical_analysis_text(price_data)
    
    # 尝试获取市场情绪数据（带监控）
    sentiment_data = get_sentiment_indicators()
    sentiment_text = ""
    if sentiment_data:
        sign = '+' if sentiment_data['net_sentiment'] >= 0 else ''
        sentiment_text = f"""
    【市场情绪】
    - 乐观比例: {sentiment_data['positive_ratio']:.1%}
    - 悲观比例: {sentiment_data['negative_ratio']:.1%}
    - 情绪净值: {sign}{sentiment_data['net_sentiment']:.3f}
    - 数据时间: {sentiment_data['data_time']} (延迟: {sentiment_data['data_delay_minutes']}分钟)
    """
    else:
        sentiment_text = """
    【市场情绪】
    - 数据暂不可用（API中断或配置问题，已自动降级为纯技术分析模式）
    """
    
    # 构建提示词
    prompt = f"""
    你是一个专业的加密货币交易分析师。请基于以下BTC/USDT {TRADE_CONFIG['timeframe']}周期数据进行分析：

    {technical_analysis}

    【当前行情】
    - 当前价格: ${price_data['price']:,.2f}
    - 时间: {price_data['timestamp']}
    - 价格变化: {price_data['price_change']:+.2f}%
    - 波动率: {calculate_volatility(price_data['full_data']):.2%}
    {sentiment_text}

    【交易指导原则 - 必须遵守】
    1. **趋势优先**: 只在明确趋势中交易，避免震荡市频繁操作
    2. **风险控制**: 每笔交易风险控制在1-2%，使用ATR动态止损
    3. **信号确认**: 需要至少2个技术指标确认才发出交易信号
    4. **耐心等待**: 宁可错过不要做错，只在高质量机会出手

    【当前技术状况】
    - 整体趋势: {price_data['trend_analysis'].get('overall', 'N/A')}
    - 趋势强度: {price_data['trend_analysis'].get('trend_strength', 'N/A')}
    - 价格位置: {price_data['trend_analysis'].get('price_level', 'N/A')}
    - RSI: {price_data['technical_data'].get('rsi', 0):.1f}
    - 布林带位置: {price_data['technical_data'].get('bb_position', 0):.2%}

    【信号生成规则】
    - 强势上涨趋势 + RSI<70 → 高信心BUY
    - 强势下跌趋势 + RSI>30 → 高信心SELL  
    - 震荡整理 + 无明确方向 → HOLD
    - 任何极端指标(RSI>80/<20, 布林带极端) → HOLD

    请用以下JSON格式回复：
    {{
        "signal": "BUY|SELL|HOLD",
        "reason": "简要分析理由",
        "confidence": "HIGH|MEDIUM|LOW",
        "risk_assessment": "低风险|中风险|高风险"
    }}
    """

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "您是一位严格遵循风险管理的专业交易员。"},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            temperature=0.1
        )

        result = response.choices[0].message.content
        print(f"DeepSeek原始回复: {result}")

        # 提取JSON
        start_idx = result.find('{')
        end_idx = result.rfind('}') + 1

        if start_idx != -1 and end_idx != 0:
            json_str = result[start_idx:end_idx]
            signal_data = safe_json_parse(json_str)
        else:
            signal_data = create_fallback_signal(price_data)

        # 验证字段
        if not all(field in signal_data for field in ['signal', 'reason', 'confidence', 'risk_assessment']):
            signal_data = create_fallback_signal(price_data)

        # 计算动态止损止盈
        stop_loss, take_profit = calculate_dynamic_stop_loss(signal_data, price_data)
        signal_data['stop_loss'] = stop_loss
        signal_data['take_profit'] = take_profit

        # 保存信号
        signal_data['timestamp'] = price_data['timestamp']
        signal_history.append(signal_data)
        if len(signal_history) > 30:
            signal_history.pop(0)

        return signal_data

    except Exception as e:
        print(f"DeepSeek分析失败: {e}")
        return create_fallback_signal(price_data)

def analyze_with_deepseek_trend_king(price_data):
    """
    基于趋势为王理念的DeepSeek分析
    将技术信号与AI分析结合，确保符合趋势跟踪理念
    
    Args:
        price_data: 价格数据
        
    Returns:
        dict: 交易信号
    """
    # 先生成技术分析信号
    technical_signal = generate_trend_king_signal(price_data)
    
    # 尝试获取市场情绪数据（带监控）
    sentiment_data = get_sentiment_indicators()
    sentiment_text = ""
    if sentiment_data:
        sign = '+' if sentiment_data['net_sentiment'] >= 0 else ''
        sentiment_text = f"""
    【市场情绪】
    - 乐观比例: {sentiment_data['positive_ratio']:.1%}
    - 悲观比例: {sentiment_data['negative_ratio']:.1%}
    - 情绪净值: {sign}{sentiment_data['net_sentiment']:.3f}
    - 数据时间: {sentiment_data['data_time']} (延迟: {sentiment_data['data_delay_minutes']}分钟)
    """
    else:
        sentiment_text = """
    【市场情绪】
    - 数据暂不可用（API中断或配置问题，已自动降级为纯技术分析模式）
    """
    
    # 构建强调趋势为王理念的提示词
    bb_position = price_data['technical_data'].get('bb_position', 0)
    
    # 生成布林带位置的结构意义描述
    bb_interpretation = ""
    if bb_position < 0.1:
        bb_interpretation = "价格触及布林带下轨，可能是超卖反弹机会"
    elif bb_position > 0.9:
        bb_interpretation = "价格触及布林带上轨，可能是超买回落机会"
    elif bb_position < 0.2:
        bb_interpretation = "价格接近布林带下轨，显示弱势"
    elif bb_position > 0.8:
        bb_interpretation = "价格接近布林带上轨，显示强势"
    else:
        bb_interpretation = "价格在布林带中部，正常波动"
    
    # 判断趋势与布林带结构的关系
    structure_relation = ""
    if technical_signal['trend_score'] >= 8:  # 🔧 更新：与新的趋势强度门槛一致
        if (technical_signal['primary_trend'] == '强势上涨' and bb_position < 0.1) or (technical_signal['primary_trend'] == '强势下跌' and bb_position > 0.9):
            structure_relation = "趋势加速"
        else:
            structure_relation = "结构确认"
    else:
        structure_relation = "结构确认"
    
    prompt = f"""
    【核心理念更新：布林带位置是结构优化信号】
    
    你是一个严格遵循"趋势为王，结构修边"理念的专业加密货币交易员。
    在"趋势为王，结构修边"理念中，布林带极端位置不是限制条件，而是重要的结构优化信号。
    
    【核心交易理念】
    1. 趋势为王：主要趋势决定交易方向，不要因小级别的波动或次要阻力改变大方向判断
    2. 结构修边：用结构信号优化入场时机和仓位管理，但不是否定趋势
    
    【当前技术状况分析】
    - 主要趋势: {technical_signal['primary_trend']}
    - 趋势强度: {technical_signal['trend_score']}/10 ({technical_signal['confidence']}信心)
    - 结构信号: {', '.join(technical_signal['structure_signals']) if technical_signal['structure_signals'] else '无'}
    - 当前价格: ${price_data['price']:,.2f}
    - 价格变化: {price_data['price_change']:+.2f}%
    - RSI: {price_data['technical_data'].get('rsi', 0):.1f}
    - 布林带位置: {bb_position:.3f}
    - MACD方向: {price_data['trend_analysis'].get('macd', 'N/A')}
    - 波动率: {calculate_volatility(price_data['full_data']):.2%}
    {sentiment_text}
    
    【布林带位置的结构意义】
    布林带位置{bb_position:.3f}表示：{bb_interpretation}
    
    【结构修边决策规则】
    1. 顺势的布林带极端位置：趋势加速信号，应该积极跟进
    2. 逆势的布林带极端位置：潜在反转信号，需要谨慎验证
    3. 布林带边缘位置：正常的结构信号，按趋势方向交易
    4. 布林带中部：无明确结构信号，主要依赖趋势判断
    
    【当前情况评估】
    趋势强度: {technical_signal['trend_score']}/10 - {technical_signal['primary_trend']}
    布林带位置: {bb_position:.3f} - 这为{technical_signal['primary_trend']}提供了{structure_relation}信号
    
    【趋势为王决策指导原则】
    - 极强趋势(强度≥8): 坚决做多/做空，回调是买入/做空机会，不要因接近阻力位而过度保守
    - 强趋势(强度7): 可以交易，但需等待结构信号优化
    - 中等趋势(强度5-6): 不建议交易，等待更强趋势
    - 弱趋势(强度<5): 坚决观望，禁止交易
    
    【结构修边时机把握原则】  
    - 有趋势 + 有结构信号 = 高信心交易，适当增加仓位
    - 有趋势 + 无结构信号 = 中等信心交易，正常仓位（趋势为王）
    - 无趋势 + 有结构信号 = 低信心轻仓尝试或观望
    - 无趋势 + 无结构信号 = 坚决观望
    
    【重要】请基于"趋势为王，结构修边"理念，将布林带位置作为结构优化信号而非限制条件：
    - 当趋势明确时，次要的阻力/支撑不应成为主要HOLD理由
    - 趋势的持续性比完美的入场时机更重要
    - 宁可顺着趋势方向中等信心入场，也不要因追求完美时机而错过趋势
    - 布林带极端位置是优化交易时机的工具，不是阻止交易的障碍
    
    你是一个专业的，富有经验的合约交易员，请仔细思考，独立判断上述数据的分析，并给出最终交易决策：
    {{
        "signal": "BUY|SELL|HOLD",
        "reason": "详细分析理由",
        "confidence": "HIGH|MEDIUM|LOW",
        "risk_assessment": "低风险|中风险|高风险"
    }}
    """
    
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "您是一位严格遵循'趋势为王，结构修边'理念的专业交易员。趋势判断优先，结构信号辅助优化。"},
                {"role": "user", "content": prompt}
            ],
            stream=False,
            temperature=0.1
        )
        
        result = response.choices[0].message.content
        print(f"🎯 DeepSeek趋势为王分析回复: {result}")
        
        # 解析JSON响应
        start_idx = result.find('{')
        end_idx = result.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = result[start_idx:end_idx]
            signal_data = safe_json_parse(json_str)
        else:
            signal_data = technical_signal
        
        # 确保必要字段存在
        if not all(field in signal_data for field in ['signal', 'reason', 'confidence']):
            signal_data = technical_signal
        
        # 添加趋势分析数据
        signal_data['trend_score'] = technical_signal['trend_score']
        signal_data['primary_trend'] = technical_signal['primary_trend']
        signal_data['structure_signals'] = technical_signal['structure_signals']
        signal_data['structure_optimized'] = technical_signal['structure_optimized']
        
        # 🔧 关键修复：严格执行趋势强度过滤，禁止AI覆盖技术信号的严格过滤
        # 如果技术信号是HOLD（因为趋势强度<8），强制保持HOLD，无论AI分析如何
        trend_score = technical_signal.get('trend_score', 0)
        technical_signal_type = technical_signal.get('signal', 'HOLD')
        
        if trend_score < 8:
            # 趋势强度<8：强制HOLD，禁止AI覆盖
            if signal_data.get('signal') != 'HOLD':
                print(f"🛑 强制HOLD：趋势强度{trend_score}/10 < 8，禁止AI覆盖技术信号")
                signal_data['signal'] = 'HOLD'
                signal_data['confidence'] = 'LOW'
                signal_data['reason'] = f"趋势强度{trend_score}/10 < 8，严格执行趋势强度过滤（技术信号：{technical_signal_type}，AI建议被拒绝）"
        elif technical_signal_type == 'HOLD' and trend_score >= 8:
            # 如果技术信号是HOLD但趋势强度≥8，允许AI分析覆盖（可能是其他原因导致的HOLD）
            print(f"✅ 趋势强度{trend_score}/10 ≥ 8，允许AI分析覆盖技术信号HOLD")
        
        # 确保有risk_assessment字段
        if 'risk_assessment' not in signal_data:
            signal_data['risk_assessment'] = technical_signal['risk_assessment']
        
        # 计算动态止损止盈
        stop_loss, take_profit = calculate_dynamic_stop_loss(signal_data, price_data)
        signal_data['stop_loss'] = stop_loss
        signal_data['take_profit'] = take_profit
        
        # 保存到信号历史
        signal_data['timestamp'] = price_data['timestamp']
        signal_history.append(signal_data)
        if len(signal_history) > 30:
            signal_history.pop(0)
            
        return signal_data
        
    except Exception as e:
        print(f"❌ DeepSeek趋势为王分析失败: {e}")
        traceback.print_exc()
        # 使用纯技术信号作为备用，确保系统稳定运行
        stop_loss, take_profit = calculate_dynamic_stop_loss(technical_signal, price_data)
        technical_signal['stop_loss'] = stop_loss
        technical_signal['take_profit'] = take_profit
        technical_signal['is_fallback'] = True
        return technical_signal

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

def get_current_position():
    """获取当前持仓情况 - OKX版本"""
    try:
        positions = exchange.fetch_positions([TRADE_CONFIG['symbol']])

        for pos in positions:
            if pos['symbol'] == TRADE_CONFIG['symbol']:
                contracts = float(pos['contracts']) if pos['contracts'] else 0

                if contracts > 0:
                    return {
                        'side': pos['side'],  # 'long' or 'short'
                        'size': contracts,
                        'entry_price': float(pos['entryPrice']) if pos['entryPrice'] else 0,
                        'unrealized_pnl': float(pos['unrealizedPnl']) if pos['unrealizedPnl'] else 0,
                        'leverage': float(pos['leverage']) if pos['leverage'] else TRADE_CONFIG['leverage'],
                        'symbol': pos['symbol']
                    }

        return None

    except Exception as e:
        print(f"获取持仓失败: {e}")
        traceback.print_exc()
        return None

def safe_json_parse(json_str):
    """安全解析JSON，处理格式不规范的情况"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            # 修复常见的JSON格式问题
            json_str = json_str.replace("'", '"')
            json_str = re.sub(r'(\w+):', r'"\1":', json_str)
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败，原始内容: {json_str}")
            print(f"错误详情: {e}")
            return None

def create_fallback_signal(price_data):
    """创建备用交易信号"""
    return {
        "signal": "HOLD",
        "reason": "因技术分析暂时不可用，采取保守策略",
        "stop_loss": price_data['price'] * 0.98,  # -2%
        "take_profit": price_data['price'] * 1.02,  # +2%
        "confidence": "LOW",
        "risk_assessment": "高风险",
        "is_fallback": True
    }

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

def analyze_with_deepseek_with_retry(price_data, max_retries=2):
    """带重试的DeepSeek分析（保留原有函数用于向后兼容）"""
    for attempt in range(max_retries):
        try:
            signal_data = analyze_with_deepseek(price_data)
            if signal_data and not signal_data.get('is_fallback', False):
                return signal_data

            print(f"第{attempt + 1}次尝试失败，进行重试...")
            time.sleep(1)

        except Exception as e:
            print(f"第{attempt + 1}次尝试异常: {e}")
            if attempt == max_retries - 1:
                return create_fallback_signal(price_data)
            time.sleep(1)

    return create_fallback_signal(price_data)

def analyze_with_deepseek_trend_king_with_retry(price_data, max_retries=2):
    """带重试的趋势为王DeepSeek分析"""
    for attempt in range(max_retries):
        try:
            signal_data = analyze_with_deepseek_trend_king(price_data)
            if signal_data and not signal_data.get('is_fallback', False):
                return signal_data

            print(f"第{attempt + 1}次尝试失败，进行重试...")
            time.sleep(1)

        except Exception as e:
            print(f"第{attempt + 1}次尝试异常: {e}")
            if attempt == max_retries - 1:
                # 使用纯技术信号作为备用
                technical_signal = generate_trend_king_signal(price_data)
                stop_loss, take_profit = calculate_dynamic_stop_loss(technical_signal, price_data)
                technical_signal['stop_loss'] = stop_loss
                technical_signal['take_profit'] = take_profit
                technical_signal['is_fallback'] = True
                return technical_signal
            time.sleep(1)

    # 最终备用
    technical_signal = generate_trend_king_signal(price_data)
    stop_loss, take_profit = calculate_dynamic_stop_loss(technical_signal, price_data)
    technical_signal['stop_loss'] = stop_loss
    technical_signal['take_profit'] = take_profit
    technical_signal['is_fallback'] = True
    return technical_signal

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

    print(f"BTC当前价格: ${price_data['price']:,.2f}")
    print(f"数据周期: {TRADE_CONFIG['timeframe']}")
    print(f"价格变化: {price_data['price_change']:+.2f}%")

    # 2. 使用趋势为王理念的DeepSeek分析（带重试）
    signal_data = analyze_with_deepseek_trend_king_with_retry(price_data)

    if signal_data.get('is_fallback', False):
        print("⚠️ 使用备用技术信号")

    # 3. 执行智能交易（已集成趋势为王策略）
    execute_intelligent_trade(signal_data, price_data)
    
    # 4. 导出数据到Dashboard
    export_dashboard_data(price_data, signal_data)
    
    # 5. 记录市场情绪API监控状态（每10次交易记录一次）
    if len(signal_history) % 10 == 0:
        sentiment_health = check_sentiment_api_health()
        print(f"📊 市场情绪API监控: {sentiment_health}")

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