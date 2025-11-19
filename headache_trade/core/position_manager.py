"""
仓位管理模块
包含开仓、平仓、仓位计算等逻辑
"""

import ccxt
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime


class PositionManager:
    """仓位管理器"""
    
    def __init__(self, exchange: ccxt.Exchange, symbol: str = 'BTC/USDT:USDT'):
        self.exchange = exchange
        self.symbol = symbol
        self.current_position = None
        
    def get_current_position(self) -> Dict:
        """
        获取当前持仓信息
        
        Returns:
            dict: 持仓信息
        """
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            
            for pos in positions:
                if pos['symbol'] == self.symbol and float(pos['contracts']) != 0:
                    return {
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': abs(float(pos['contracts'])),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unrealizedPnl']),
                        'leverage': float(pos['leverage']),
                        'notional': float(pos['notional']),
                    }
            
            return None
        
        except Exception as e:
            print(f"❌ 获取持仓失败: {e}")
            return None
    
    def calculate_position_size(self, balance: float, risk_pct: float, 
                               entry_price: float, stop_loss_price: float,
                               leverage: int = 1) -> float:
        """
        计算仓位大小（基于风险百分比）
        
        Args:
            balance: 账户余额
            risk_pct: 风险百分比（如0.01表示1%）
            entry_price: 入场价格
            stop_loss_price: 止损价格
            leverage: 杠杆倍数
        
        Returns:
            float: 仓位大小（合约数量）
        """
        # 风险金额
        risk_amount = balance * risk_pct
        
        # 每张合约的风险
        price_diff = abs(entry_price - stop_loss_price)
        risk_per_contract = price_diff
        
        # 计算合约数量
        position_size = (risk_amount / risk_per_contract) * leverage
        
        # 确保至少0.001 BTC
        position_size = max(position_size, 0.001)
        
        # 四舍五入到3位小数
        position_size = round(position_size, 3)
        
        return position_size
    
    def execute_market_order(self, side: str, amount: float, 
                            reduce_only: bool = False) -> Optional[Dict]:
        """
        执行市价单
        
        Args:
            side: 'buy' or 'sell'
            amount: 数量
            reduce_only: 是否仅平仓
        
        Returns:
            dict: 订单信息
        """
        try:
            params = {
                'tdMode': 'cross',
            }
            
            if reduce_only:
                params['reduceOnly'] = True
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='market',
                side=side,
                amount=amount,
                params=params
            )
            
            print(f"✅ 市价单已执行: {side} {amount} {self.symbol}")
            return order
        
        except Exception as e:
            print(f"❌ 市价单执行失败: {e}")
            return None
    
    def execute_limit_order(self, side: str, amount: float, price: float,
                           reduce_only: bool = False) -> Optional[Dict]:
        """
        执行限价单
        
        Args:
            side: 'buy' or 'sell'
            amount: 数量
            price: 价格
            reduce_only: 是否仅平仓
        
        Returns:
            dict: 订单信息
        """
        try:
            params = {
                'tdMode': 'cross',
            }
            
            if reduce_only:
                params['reduceOnly'] = True
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='limit',
                side=side,
                amount=amount,
                price=price,
                params=params
            )
            
            print(f"✅ 限价单已提交: {side} {amount} @ {price}")
            return order
        
        except Exception as e:
            print(f"❌ 限价单执行失败: {e}")
            return None
    
    def close_position(self, reason: str = "manual") -> bool:
        """
        平仓当前持仓
        
        Args:
            reason: 平仓原因
        
        Returns:
            bool: 是否成功
        """
        position = self.get_current_position()
        
        if not position:
            print("⚠️ 无持仓需要平仓")
            return False
        
        side = position['side']
        size = position['size']
        
        # 反向平仓
        close_side = 'sell' if side == 'long' else 'buy'
        
        print(f"📤 准备平仓: {side} {size} BTC (原因: {reason})")
        
        order = self.execute_market_order(close_side, size, reduce_only=True)
        
        if order:
            print(f"✅ 平仓成功: PnL = {position['unrealized_pnl']:.2f} USDT")
            return True
        else:
            print("❌ 平仓失败")
            return False
    
    def set_leverage(self, leverage: int) -> bool:
        """
        设置杠杆倍数
        
        Args:
            leverage: 杠杆倍数
        
        Returns:
            bool: 是否成功
        """
        try:
            self.exchange.set_leverage(leverage, self.symbol)
            print(f"✅ 杠杆已设置为 {leverage}x")
            return True
        
        except Exception as e:
            print(f"❌ 设置杠杆失败: {e}")
            return False


def calculate_intelligent_position(signal_data: Dict, price_data, 
                                   current_position: Optional[Dict]) -> Dict:
    """
    智能仓位计算（基于趋势强度）
    
    Args:
        signal_data: AI信号数据
        price_data: 价格数据
        current_position: 当前持仓
    
    Returns:
        dict: 仓位计算结果
    """
    # 基础参数
    confidence = signal_data.get('confidence', 50)
    trend_score = signal_data.get('trend_score', 0)
    
    # 基础仓位比例
    base_position_pct = 0.3  # 30%
    
    # 根据置信度调整
    if confidence >= 80:
        confidence_multiplier = 1.5
    elif confidence >= 60:
        confidence_multiplier = 1.2
    elif confidence >= 40:
        confidence_multiplier = 1.0
    else:
        confidence_multiplier = 0.7
    
    # 根据趋势强度调整
    trend_multiplier = 1 + (abs(trend_score) / 10)
    
    # 最终仓位比例
    final_position_pct = base_position_pct * confidence_multiplier * trend_multiplier
    final_position_pct = min(final_position_pct, 0.8)  # 最大80%
    
    return {
        'position_pct': final_position_pct,
        'confidence_multiplier': confidence_multiplier,
        'trend_multiplier': trend_multiplier,
    }


def calculate_trend_based_position(signal_data: Dict, price_data,
                                   current_position: Optional[Dict]) -> Dict:
    """
    基于趋势的仓位计算（趋势之王策略）
    
    Args:
        signal_data: 信号数据
        price_data: 价格数据
        current_position: 当前持仓
    
    Returns:
        dict: 仓位计算结果
    """
    trend = signal_data.get('trend', 'neutral')
    confidence = signal_data.get('confidence', 50)
    
    # 趋势强度映射
    trend_strength_map = {
        'strong_bullish': 1.0,
        'bullish': 0.7,
        'neutral': 0.3,
        'bearish': 0.7,
        'strong_bearish': 1.0,
    }
    
    trend_strength = trend_strength_map.get(trend, 0.5)
    
    # 基础仓位
    base_size = 0.5  # 50%账户
    
    # 调整系数
    confidence_factor = confidence / 100
    final_factor = trend_strength * confidence_factor
    
    # 最终仓位比例
    position_pct = base_size * final_factor
    position_pct = max(0.1, min(0.9, position_pct))  # 限制在10%-90%
    
    return {
        'position_pct': position_pct,
        'trend_strength': trend_strength,
        'confidence_factor': confidence_factor,
        'final_factor': final_factor,
    }


def should_execute_trade(signal_data: Dict, price_data, 
                        current_position: Optional[Dict]) -> Tuple[bool, str]:
    """
    判断是否应该执行交易
    
    Args:
        signal_data: 信号数据
        price_data: 价格数据
        current_position: 当前持仓
    
    Returns:
        tuple: (should_execute, reason)
    """
    signal = signal_data.get('signal', 'hold')
    confidence = signal_data.get('confidence', 0)
    
    # 检查信号类型
    if signal == 'hold':
        return False, "信号为HOLD，不执行交易"
    
    # 检查置信度
    if confidence < 60:
        return False, f"置信度过低 ({confidence}%)"
    
    # 检查是否已有持仓
    if current_position:
        position_side = current_position['side']
        
        # 检查是否同向
        if (signal == 'buy' and position_side == 'long') or \
           (signal == 'sell' and position_side == 'short'):
            return False, "已有同向持仓"
        
        # 检查是否需要反向开仓（先平仓）
        if (signal == 'buy' and position_side == 'short') or \
           (signal == 'sell' and position_side == 'long'):
            return True, "反向信号，需要先平仓"
    
    # 检查风险控制
    from risk_management import check_trading_conditions
    conditions = check_trading_conditions()
    
    if not conditions['can_trade']:
        return False, "交易条件不满足"
    
    return True, "满足交易条件"


def should_close_existing_position(signal_data: Dict, price_data,
                                   current_position: Optional[Dict]) -> Tuple[bool, str]:
    """
    判断是否应该平仓
    
    Args:
        signal_data: 信号数据
        price_data: 价格数据
        current_position: 当前持仓
    
    Returns:
        tuple: (should_close, reason)
    """
    if not current_position:
        return False, "无持仓"
    
    signal = signal_data.get('signal', 'hold')
    position_side = current_position['side']
    
    # 反向信号
    if (signal == 'buy' and position_side == 'short') or \
       (signal == 'sell' and position_side == 'long'):
        return True, "反向信号"
    
    # 信号消失
    if signal == 'hold':
        # 检查是否盈利
        unrealized_pnl = current_position.get('unrealized_pnl', 0)
        if unrealized_pnl > 0:
            return True, "信号消失且有盈利，锁定利润"
    
    return False, "继续持有"
