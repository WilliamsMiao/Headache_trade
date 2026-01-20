"""
Trade Executor Skill - 交易执行专家
负责智能订单路由、算法执行、滑点优化和执行质量监控
"""

import sys
import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_skills.base_skill import BaseSkill, SkillResult, SkillStatus
from ai_skills.config import AISkillsConfig
from trading_bots.config import exchange, TRADE_CONFIG
from trading_bots.execution import (
    set_tp_sl_orders,
    cancel_tp_sl_orders,
    get_current_position
)


class TradeExecutorSkill(BaseSkill):
    """交易执行专家技能"""
    
    def __init__(self):
        config = AISkillsConfig.get_skill_config('trade_executor')
        super().__init__(
            name='trade_executor',
            timeout=config['timeout'],
            enabled=config['enabled'],
            priority=config['priority']
        )
        self.execution_history = []  # 执行历史记录
        self.max_history = 100
    
    def get_required_inputs(self) -> List[str]:
        """获取所需的输入字段"""
        return ['risk_adjusted_signal']  # 需要风险调整后的信号
    
    def get_output_schema(self) -> Dict[str, Any]:
        """获取输出数据格式定义"""
        return {
            'execution_status': {
                'type': 'string',
                'values': ['success', 'partial', 'failed'],
                'description': '执行状态'
            },
            'filled_size': {
                'type': 'float',
                'description': '已成交数量'
            },
            'avg_price': {
                'type': 'float',
                'description': '平均成交价格'
            },
            'slippage': {
                'type': 'float',
                'description': '滑点（百分比）'
            },
            'execution_time': {
                'type': 'float',
                'description': '执行时间（秒）'
            },
            'order_ids': {
                'type': 'list',
                'description': '订单ID列表'
            }
        }
    
    def execute(
        self,
        context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> SkillResult:
        """执行交易"""
        try:
            signal = input_data.get('risk_adjusted_signal', {})
            action = signal.get('action', 'HOLD')
            
            # 如果是HOLD或CLOSE，特殊处理
            if action == 'HOLD':
                return SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.SUCCESS,
                    output={
                        'execution_status': 'success',
                        'filled_size': 0,
                        'avg_price': 0,
                        'slippage': 0,
                        'execution_time': 0,
                        'order_ids': [],
                        'message': 'HOLD信号，无需执行'
                    },
                    confidence=1.0
                )
            
            if action == 'CLOSE':
                return self._execute_close_position(signal)
            
            # 执行开仓或加仓
            if action in ['BUY', 'SELL']:
                return self._execute_trade(signal)
            
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"未知的交易动作: {action}"
            )
            
        except Exception as e:
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"交易执行失败: {str(e)}"
            )
    
    def _execute_trade(self, signal: Dict[str, Any]) -> SkillResult:
        """执行交易（开仓/加仓）"""
        start_time = time.time()
        order_ids = []
        
        try:
            action = signal.get('action')
            size = signal.get('size', 0)
            leverage = signal.get('leverage', TRADE_CONFIG.get('leverage', 6))
            stop_loss = signal.get('stop_loss', 0)
            take_profit = signal.get('take_profit', 0)
            
            if size <= 0:
                return SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.FAILED,
                    error="仓位大小为0，无法执行交易"
                )
            
            # 获取当前持仓
            current_position = get_current_position()
            
            # 检查是否需要平仓反向持仓
            if current_position:
                if (action == 'BUY' and current_position['side'] == 'short') or \
                   (action == 'SELL' and current_position['side'] == 'long'):
                    # 需要先平仓
                    close_result = self._close_position(current_position)
                    if not close_result['success']:
                        return SkillResult(
                            skill_name=self.name,
                            status=SkillStatus.FAILED,
                            error=f"平仓失败: {close_result.get('error')}"
                        )
                    time.sleep(1)  # 等待平仓完成
            
            # 设置杠杆（如果需要）
            if leverage != TRADE_CONFIG.get('leverage', 6):
                try:
                    exchange.set_leverage(leverage, TRADE_CONFIG['symbol'])
                except Exception as e:
                    print(f"⚠️ 设置杠杆失败: {e}")
            
            # 获取当前价格（用于滑点计算）
            ticker = exchange.fetch_ticker(TRADE_CONFIG['symbol'])
            expected_price = ticker['last']
            
            # 执行订单（使用算法执行优化滑点）
            execution_result = self._execute_with_slippage_optimization(
                action,
                size,
                expected_price
            )
            
            if not execution_result['success']:
                return SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.FAILED,
                    error=execution_result.get('error', '订单执行失败')
                )
            
            # 设置止盈止损订单
            tp_sl_order_ids = None
            if stop_loss > 0 or take_profit > 0:
                position_side = 'long' if action == 'BUY' else 'short'
                tp_sl_order_ids = set_tp_sl_orders(
                    TRADE_CONFIG['symbol'],
                    position_side,
                    execution_result['filled_size'],
                    stop_loss,
                    take_profit
                )
                if tp_sl_order_ids:
                    if tp_sl_order_ids.get('tp_order_id'):
                        order_ids.append(tp_sl_order_ids['tp_order_id'])
                    if tp_sl_order_ids.get('sl_order_id'):
                        order_ids.append(tp_sl_order_ids['sl_order_id'])
            
            execution_time = time.time() - start_time
            
            # 计算滑点
            actual_price = execution_result.get('avg_price', expected_price)
            slippage = abs(actual_price - expected_price) / expected_price if expected_price > 0 else 0
            
            # 记录执行历史
            self._record_execution({
                'action': action,
                'size': size,
                'filled_size': execution_result['filled_size'],
                'expected_price': expected_price,
                'actual_price': actual_price,
                'slippage': slippage,
                'execution_time': execution_time,
                'order_ids': order_ids
            })
            
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.SUCCESS,
                output={
                    'execution_status': 'success' if execution_result['filled_size'] >= size * 0.95 else 'partial',
                    'filled_size': execution_result['filled_size'],
                    'avg_price': actual_price,
                    'slippage': slippage,
                    'execution_time': execution_time,
                    'order_ids': order_ids
                },
                confidence=0.9 if execution_result['filled_size'] >= size * 0.95 else 0.7
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"交易执行异常: {str(e)}",
                execution_time=execution_time
            )
    
    def _execute_close_position(self, signal: Dict[str, Any]) -> SkillResult:
        """执行平仓"""
        start_time = time.time()
        
        try:
            current_position = get_current_position()
            if not current_position or current_position.get('size', 0) <= 0:
                return SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.SUCCESS,
                    output={
                        'execution_status': 'success',
                        'filled_size': 0,
                        'avg_price': 0,
                        'slippage': 0,
                        'execution_time': time.time() - start_time,
                        'order_ids': [],
                        'message': '无持仓，无需平仓'
                    },
                    confidence=1.0
                )
            
            close_result = self._close_position(current_position)
            execution_time = time.time() - start_time
            
            if close_result['success']:
                return SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.SUCCESS,
                    output={
                        'execution_status': 'success',
                        'filled_size': close_result.get('filled_size', current_position['size']),
                        'avg_price': close_result.get('avg_price', 0),
                        'slippage': close_result.get('slippage', 0),
                        'execution_time': execution_time,
                        'order_ids': close_result.get('order_ids', []),
                        'reason': signal.get('risk_adjustments', {}).get('reason', '风险管理平仓')
                    },
                    confidence=0.9
                )
            else:
                return SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.FAILED,
                    error=close_result.get('error', '平仓失败'),
                    execution_time=execution_time
                )
                
        except Exception as e:
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"平仓执行异常: {str(e)}"
            )
    
    def _close_position(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """平仓"""
        try:
            side = position['side']
            size = position['size']
            
            # 获取当前价格
            ticker = exchange.fetch_ticker(TRADE_CONFIG['symbol'])
            expected_price = ticker['last']
            
            # 执行平仓订单
            order_side = 'buy' if side == 'short' else 'sell'
            order = exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                order_side,
                size,
                params={'reduceOnly': True}
            )
            
            # 获取成交价格（简化处理，实际应该查询订单详情）
            actual_price = expected_price
            
            # 取消该持仓的止盈止损订单
            try:
                cancel_tp_sl_orders(TRADE_CONFIG['symbol'], None)
            except Exception as e:
                print(f"⚠️ 取消止盈止损订单失败: {e}")
            
            return {
                'success': True,
                'filled_size': size,
                'avg_price': actual_price,
                'slippage': 0,
                'order_ids': [order.get('id', '')] if order else []
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_with_slippage_optimization(
        self,
        action: str,
        size: float,
        expected_price: float
    ) -> Dict[str, Any]:
        """使用滑点优化执行订单"""
        try:
            # 根据订单大小决定执行策略
            # 小订单：直接市价单
            # 大订单：拆分执行（TWAP算法）
            
            if size <= 0.1:  # 小订单，直接执行
                return self._execute_market_order(action, size, expected_price)
            else:  # 大订单，使用TWAP算法
                return self._execute_twap(action, size, expected_price)
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_market_order(
        self,
        action: str,
        size: float,
        expected_price: float
    ) -> Dict[str, Any]:
        """执行市价单"""
        try:
            order_side = 'buy' if action == 'BUY' else 'sell'
            order = exchange.create_market_order(
                TRADE_CONFIG['symbol'],
                order_side,
                size
            )
            
            # 获取成交信息（简化处理）
            filled_size = size
            avg_price = expected_price
            
            return {
                'success': True,
                'filled_size': filled_size,
                'avg_price': avg_price
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _execute_twap(
        self,
        action: str,
        total_size: float,
        expected_price: float
    ) -> Dict[str, Any]:
        """
        执行TWAP（时间加权平均价格）算法
        将大订单拆分为多个小订单，在指定时间内均匀执行
        """
        try:
            # TWAP参数
            num_splits = min(5, max(2, int(total_size / 0.05)))  # 根据订单大小决定拆分数量
            split_size = total_size / num_splits
            interval = 2  # 每2秒执行一次
            
            filled_total = 0
            price_total = 0
            
            order_side = 'buy' if action == 'BUY' else 'sell'
            
            for i in range(num_splits):
                try:
                    order = exchange.create_market_order(
                        TRADE_CONFIG['symbol'],
                        order_side,
                        split_size
                    )
                    
                    filled_total += split_size
                    price_total += expected_price  # 简化处理，使用预期价格
                    
                    # 如果不是最后一次，等待间隔
                    if i < num_splits - 1:
                        time.sleep(interval)
                        
                except Exception as e:
                    print(f"⚠️ TWAP第{i+1}次执行失败: {e}")
                    # 继续执行剩余部分
                    continue
            
            avg_price = price_total / num_splits if num_splits > 0 else expected_price
            
            return {
                'success': filled_total > 0,
                'filled_size': filled_total,
                'avg_price': avg_price
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _record_execution(self, execution_data: Dict[str, Any]) -> None:
        """记录执行历史"""
        execution_data['timestamp'] = datetime.now().isoformat()
        self.execution_history.append(execution_data)
        
        # 限制历史记录数量
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        if not self.execution_history:
            return {
                'total_executions': 0,
                'avg_slippage': 0,
                'avg_execution_time': 0,
                'success_rate': 0
            }
        
        total = len(self.execution_history)
        slippages = [e.get('slippage', 0) for e in self.execution_history]
        execution_times = [e.get('execution_time', 0) for e in self.execution_history]
        
        return {
            'total_executions': total,
            'avg_slippage': sum(slippages) / len(slippages) if slippages else 0,
            'avg_execution_time': sum(execution_times) / len(execution_times) if execution_times else 0,
            'success_rate': 1.0  # 简化处理
        }
