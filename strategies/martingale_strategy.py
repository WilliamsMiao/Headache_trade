"""
马丁格尔策略
亏损后加倍仓位，直到盈利后重置，适合震荡市场
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
from .base_strategy import BaseStrategy
from .market_analyzer import MarketAnalyzer


class MartingaleStrategy(BaseStrategy):
    """马丁格尔策略"""
    
    PARAMETERS = {
        'initial_size': {
            'type': float,
            'default': 0.01,
            'min': 0.001,
            'max': 0.1,
            'description': '初始仓位大小（合约张数）',
            'optimizable': True
        },
        'martingale_multiplier': {
            'type': float,
            'default': 2.0,
            'min': 1.5,
            'max': 5.0,
            'description': '加仓倍数',
            'optimizable': True
        },
        'max_iterations': {
            'type': int,
            'default': 5,
            'min': 2,
            'max': 10,
            'description': '最大加仓次数（防止资金耗尽）',
            'optimizable': True
        },
        'entry_interval_pct': {
            'type': float,
            'default': 0.01,  # 1%
            'min': 0.005,
            'max': 0.05,
            'description': '加仓触发间隔（价格变动百分比）',
            'optimizable': True
        },
        'take_profit_pct': {
            'type': float,
            'default': 0.015,  # 1.5%
            'min': 0.005,
            'max': 0.05,
            'description': '止盈目标（总仓位盈利百分比）',
            'optimizable': True
        },
        'stop_loss_pct': {
            'type': float,
            'default': 0.05,  # 5%
            'min': 0.01,
            'max': 0.20,
            'description': '总止损（所有仓位总亏损百分比）',
            'optimizable': True
        },
        'reset_after_profit': {
            'type': bool,
            'default': True,
            'description': '盈利后是否重置',
            'optimizable': False
        },
        'direction': {
            'type': str,
            'default': 'auto',
            'description': '初始方向: long/short/auto',
            'optimizable': False
        },
        'trend_filter_enabled': {
            'type': bool,
            'default': True,
            'description': '是否启用趋势过滤',
            'optimizable': False
        },
        'default_leverage': {
            'type': int,
            'default': 6,
            'min': 1,
            'max': 20,
            'description': '默认杠杆倍数',
            'optimizable': True
        }
    }
    
    def __init__(self, **kwargs):
        # adaptive_params_enabled不是策略参数，先提取
        self.adaptive_params_enabled = kwargs.pop('adaptive_params_enabled', True)
        
        super().__init__(**kwargs)
        # 加仓序列状态
        if 'entries' not in self.state:
            self.state['entries'] = []  # [{'price': float, 'size': float}]
        if 'total_size' not in self.state:
            self.state['total_size'] = 0.0
        if 'avg_price' not in self.state:
            self.state['avg_price'] = 0.0
        if 'iteration' not in self.state:
            self.state['iteration'] = 0
        if 'initial_direction' not in self.state:
            self.state['initial_direction'] = None
        if 'last_entry_price' not in self.state:
            self.state['last_entry_price'] = None
        
        # 市场分析器（用于自适应参数）
        self.market_analyzer = MarketAnalyzer()
    
    def reset_state(self):
        """重置策略状态"""
        super().reset_state()
        self.state['entries'] = []
        self.state['total_size'] = 0.0
        self.state['avg_price'] = 0.0
        self.state['iteration'] = 0
        self.state['initial_direction'] = None
        self.state['last_entry_price'] = None
    
    def _detect_trend_direction(self, df: pd.DataFrame, index: int) -> str:
        """检测趋势方向（用于auto模式）"""
        if index < 50:
            return 'long'  # 默认做多
        
        window_df = df.iloc[max(0, index-50):index+1]
        sma_20 = window_df['close'].rolling(20).mean().iloc[-1]
        current_price = window_df['close'].iloc[-1]
        
        if current_price > sma_20:
            return 'long'
        else:
            return 'short'
    
    def _calculate_avg_price(self) -> float:
        """计算平均入场价格"""
        if not self.state['entries']:
            return 0.0
        
        total_value = sum(entry['price'] * entry['size'] for entry in self.state['entries'])
        total_size = sum(entry['size'] for entry in self.state['entries'])
        
        if total_size > 0:
            return total_value / total_size
        return 0.0
    
    def _calculate_unrealized_pnl(self, current_price: float) -> float:
        """计算未实现盈亏百分比"""
        if not self.state['entries'] or self.state['total_size'] == 0:
            return 0.0
        
        avg_price = self.state['avg_price']
        if avg_price == 0:
            return 0.0
        
        direction = self.state['initial_direction']
        if direction == 'long':
            pnl_pct = (current_price - avg_price) / avg_price
        else:  # short
            pnl_pct = (avg_price - current_price) / avg_price
        
        return pnl_pct
    
    def _check_take_profit(self, current_price: float) -> bool:
        """检查是否达到止盈"""
        pnl_pct = self._calculate_unrealized_pnl(current_price)
        return pnl_pct >= self.get_parameter('take_profit_pct')
    
    def _check_stop_loss(self, current_price: float) -> bool:
        """检查是否触发止损"""
        pnl_pct = self._calculate_unrealized_pnl(current_price)
        direction = self.state['initial_direction']
        
        if direction == 'long':
            return pnl_pct <= -self.get_parameter('stop_loss_pct')
        else:  # short
            return pnl_pct <= -self.get_parameter('stop_loss_pct')
    
    def _check_add_position(self, current_price: float, effective_params: Dict = None) -> bool:
        """检查是否需要加仓"""
        if not self.state['entries']:
            return True  # 首次开仓
        
        if effective_params is None:
            effective_params = self.get_parameters()
        
        # 检查是否达到最大加仓次数
        max_iterations = effective_params.get('max_iterations', self.get_parameter('max_iterations'))
        if self.state['iteration'] >= max_iterations:
            return False
        
        # 检查价格变动是否达到加仓间隔
        if self.state['last_entry_price'] is None:
            return True
        
        direction = self.state['initial_direction']
        entry_interval = effective_params.get('entry_interval_pct', self.get_parameter('entry_interval_pct'))
        
        if direction == 'long':
            # 做多：价格下跌达到间隔时加仓
            price_change = (self.state['last_entry_price'] - current_price) / self.state['last_entry_price']
            return price_change >= entry_interval
        else:  # short
            # 做空：价格上涨达到间隔时加仓
            price_change = (current_price - self.state['last_entry_price']) / self.state['last_entry_price']
            return price_change >= entry_interval
    
    def _calculate_next_size(self, effective_params: Dict = None) -> float:
        """计算下一次加仓的仓位大小"""
        if effective_params is None:
            effective_params = self.get_parameters()
        
        if not self.state['entries']:
            return effective_params.get('initial_size', self.get_parameter('initial_size'))
        
        # 马丁格尔：上次仓位 * 倍数
        last_size = self.state['entries'][-1]['size']
        multiplier = effective_params.get('martingale_multiplier', self.get_parameter('martingale_multiplier'))
        return last_size * multiplier
    
    def generate_signal(
        self,
        index: int,
        df: pd.DataFrame,
        position: Optional[Any],
        current_balance: float,
        performance_stats: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """生成交易信号"""
        current_price = df['close'].iloc[index]
        
        # 市场分析（如果启用自适应参数）
        market_analysis = None
        if self.adaptive_params_enabled:
            try:
                market_analysis = self.market_analyzer.analyze_market(df, index)
            except Exception:
                # 如果分析失败，使用默认参数
                market_analysis = None
        
        # 获取有效参数（基础参数 + 自适应调整）
        effective_params = self._get_effective_parameters(market_analysis)
        
        # 如果当前有持仓，检查止盈止损
        if position is not None:
            # 更新平均价格
            self.state['avg_price'] = self._calculate_avg_price()
            
            # 检查止盈（使用有效参数）
            take_profit_pct = effective_params.get('take_profit_pct', self.get_parameter('take_profit_pct'))
            pnl_pct = self._calculate_unrealized_pnl(current_price)
            if pnl_pct >= take_profit_pct:
                # 全部平仓
                self._reset_after_profit()
                return {
                    'action': 'CLOSE',
                    'size': position.size,
                    'stop_loss': None,
                    'take_profit': None,
                    'leverage': self.get_parameter('default_leverage'),
                    'reason': f'马丁格尔止盈: 盈利达到目标 ({pnl_pct*100:.2f}%)',
                    'metadata': {
                        'iteration': self.state['iteration'],
                        'total_entries': len(self.state['entries']),
                        'market_analysis': market_analysis
                    }
                }
            
            # 检查止损（使用有效参数）
            stop_loss_pct = effective_params.get('stop_loss_pct', self.get_parameter('stop_loss_pct'))
            direction = self.state['initial_direction']
            if direction == 'long':
                should_stop = pnl_pct <= -stop_loss_pct
            else:  # short
                should_stop = pnl_pct <= -stop_loss_pct
            
            if should_stop:
                # 全部平仓
                self.reset_state()
                return {
                    'action': 'CLOSE',
                    'size': position.size,
                    'stop_loss': None,
                    'take_profit': None,
                    'leverage': self.get_parameter('default_leverage'),
                    'reason': f'马丁格尔止损: 亏损达到阈值 ({pnl_pct*100:.2f}%)',
                    'metadata': {
                        'iteration': self.state['iteration'],
                        'total_entries': len(self.state['entries']),
                        'market_analysis': market_analysis
                    }
                }
            
            # 检查是否需要加仓
            if self._check_add_position(current_price, effective_params):
                next_size = self._calculate_next_size(effective_params)
                direction = self.state['initial_direction']
                
                # 记录加仓
                self.state['entries'].append({
                    'price': current_price,
                    'size': next_size
                })
                self.state['total_size'] += next_size
                self.state['avg_price'] = self._calculate_avg_price()
                self.state['iteration'] += 1
                self.state['last_entry_price'] = current_price
                
                # 返回加仓信号
                action = 'BUY' if direction == 'long' else 'SELL'
                return {
                    'action': action,
                    'size': next_size,
                    'stop_loss': None,  # 止损由总止损控制
                    'take_profit': None,  # 止盈由总止盈控制
                    'leverage': self.get_parameter('default_leverage'),
                    'reason': f'马丁格尔加仓: 第{self.state["iteration"]}次, 价格={current_price:.2f}' + 
                             (f" [市场: {market_analysis.get('market_regime', 'N/A')}]" if market_analysis else ""),
                    'metadata': {
                        'iteration': self.state['iteration'],
                        'avg_price': self.state['avg_price'],
                        'total_size': self.state['total_size'],
                        'market_analysis': market_analysis
                    }
                }
            
            return None  # 持仓中，无需操作
        
        # 无持仓，检查是否需要开仓
        if not self.state['entries']:
            # 确定初始方向（考虑趋势过滤）
            direction_param = self.get_parameter('direction')
            trend_filter_enabled = effective_params.get('trend_filter_enabled', self.get_parameter('trend_filter_enabled'))
            
            if direction_param == 'auto':
                if trend_filter_enabled:
                    direction = self._detect_trend_direction(df, index)
                else:
                    direction = 'long'  # 默认做多
            else:
                direction = direction_param
            
            self.state['initial_direction'] = direction
            
            # 首次开仓（使用有效参数）
            initial_size = effective_params.get('initial_size', self.get_parameter('initial_size'))
            stop_loss_pct = effective_params.get('stop_loss_pct', self.get_parameter('stop_loss_pct'))
            take_profit_pct = effective_params.get('take_profit_pct', self.get_parameter('take_profit_pct'))
            
            self.state['entries'].append({
                'price': current_price,
                'size': initial_size
            })
            self.state['total_size'] = initial_size
            self.state['avg_price'] = current_price
            self.state['iteration'] = 1
            self.state['last_entry_price'] = current_price
            
            action = 'BUY' if direction == 'long' else 'SELL'
            
            # 计算止损止盈（基于总止损止盈）
            if direction == 'long':
                stop_loss = current_price * (1 - stop_loss_pct)
                take_profit = current_price * (1 + take_profit_pct)
            else:  # short
                stop_loss = current_price * (1 + stop_loss_pct)
                take_profit = current_price * (1 - take_profit_pct)
            
            return {
                'action': action,
                'size': initial_size,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': self.get_parameter('default_leverage'),
                'reason': f'马丁格尔首次开仓: {direction}, 价格={current_price:.2f}' +
                         (f" [市场: {market_analysis.get('market_regime', 'N/A')}]" if market_analysis else ""),
                'metadata': {
                    'iteration': 1,
                    'direction': direction,
                    'market_analysis': market_analysis
                }
            }
        
        # 有加仓序列但无持仓（可能被强制平仓），重置
        self.reset_state()
        return None
    
    def _reset_after_profit(self):
        """盈利后重置"""
        if self.get_parameter('reset_after_profit'):
            self.reset_state()
        else:
            # 不清空状态，继续使用
            self.state['last_entry_price'] = None
    
    def _adapt_parameters_to_market(self, market_analysis: Dict) -> Dict:
        """
        根据市场分析结果调整参数
        
        Args:
            market_analysis: 市场分析结果字典
            
        Returns:
            调整后的参数字典（只包含需要调整的参数）
        """
        if not self.adaptive_params_enabled:
            return {}
        
        adapted_params = {}
        
        volatility = market_analysis.get('volatility_level', 'medium')
        oscillation = market_analysis.get('oscillation_strength', 0.5)
        trend = market_analysis.get('trend_strength', 0.5)
        regime = market_analysis.get('market_regime', 'ranging')
        
        base_interval = self.get_parameter('entry_interval_pct')
        base_multiplier = self.get_parameter('martingale_multiplier')
        base_stop_loss = self.get_parameter('stop_loss_pct')
        base_take_profit = self.get_parameter('take_profit_pct')
        base_max_iterations = self.get_parameter('max_iterations')
        
        # 根据波动率调整
        if volatility == 'high':
            # 高波动：增大加仓间隔，放宽止损，提高止盈
            adapted_params['entry_interval_pct'] = min(base_interval * 1.5, 0.05)
            adapted_params['stop_loss_pct'] = min(base_stop_loss * 1.3, 0.20)
            adapted_params['take_profit_pct'] = min(base_take_profit * 1.5, 0.05)
        elif volatility == 'low':
            # 低波动：减小加仓间隔，收紧止损
            adapted_params['entry_interval_pct'] = max(base_interval * 0.7, 0.005)
            adapted_params['stop_loss_pct'] = max(base_stop_loss * 0.8, 0.01)
        
        # 根据震荡强度调整
        if oscillation > 0.7:
            # 强震荡：适合马丁格尔，可以更激进
            adapted_params['martingale_multiplier'] = min(base_multiplier * 1.2, 3.0)
            current_interval = adapted_params.get('entry_interval_pct', base_interval)
            adapted_params['entry_interval_pct'] = max(current_interval * 0.8, 0.005)
        elif oscillation < 0.3:
            # 弱震荡：不适合马丁格尔，保守策略
            adapted_params['martingale_multiplier'] = max(base_multiplier * 0.8, 1.5)
            adapted_params['max_iterations'] = max(base_max_iterations - 1, 2)
        
        # 根据趋势强度调整
        if trend > 0.6:
            # 强趋势：避免逆势加仓
            current_interval = adapted_params.get('entry_interval_pct', base_interval)
            adapted_params['entry_interval_pct'] = min(current_interval * 1.5, 0.05)
            current_max_iterations = adapted_params.get('max_iterations', base_max_iterations)
            adapted_params['max_iterations'] = max(current_max_iterations - 2, 2)
            current_stop_loss = adapted_params.get('stop_loss_pct', base_stop_loss)
            adapted_params['stop_loss_pct'] = max(current_stop_loss * 0.7, 0.01)
            adapted_params['trend_filter_enabled'] = True
        elif trend < 0.3:
            # 弱趋势/震荡：适合马丁格尔
            current_interval = adapted_params.get('entry_interval_pct', base_interval)
            adapted_params['entry_interval_pct'] = max(current_interval * 0.9, 0.005)
        
        # 根据市场状态调整
        if regime == 'trending':
            # 趋势市场：减少加仓次数，启用趋势过滤
            current_max_iterations = adapted_params.get('max_iterations', base_max_iterations)
            adapted_params['max_iterations'] = max(current_max_iterations - 1, 2)
            adapted_params['trend_filter_enabled'] = True
        elif regime == 'ranging':
            # 震荡市场：适合马丁格尔，保持或稍微增加倍数
            if 'martingale_multiplier' not in adapted_params:
                adapted_params['martingale_multiplier'] = base_multiplier
        elif regime == 'volatile':
            # 高波动市场：增大间隔，放宽止损
            current_interval = adapted_params.get('entry_interval_pct', base_interval)
            adapted_params['entry_interval_pct'] = min(current_interval * 1.3, 0.05)
            current_stop_loss = adapted_params.get('stop_loss_pct', base_stop_loss)
            adapted_params['stop_loss_pct'] = min(current_stop_loss * 1.2, 0.20)
        
        return adapted_params
    
    def _get_effective_parameters(self, market_analysis: Optional[Dict] = None) -> Dict:
        """
        获取有效参数（基础参数 + 自适应调整）
        
        Args:
            market_analysis: 市场分析结果，如果为None则不进行自适应调整
            
        Returns:
            有效参数字典
        """
        effective_params = self.get_parameters().copy()
        
        if market_analysis:
            adapted_params = self._adapt_parameters_to_market(market_analysis)
            effective_params.update(adapted_params)
        
        return effective_params
    
    def get_description(self) -> str:
        """获取策略描述"""
        return "马丁格尔策略 - 亏损后加倍仓位，直到盈利后重置"
