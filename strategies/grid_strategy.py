"""
区间网格策略
在价格区间内设置多个买卖网格，价格下跌时买入，上涨时卖出
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
from .base_strategy import BaseStrategy
from .market_analyzer import MarketAnalyzer


class GridStrategy(BaseStrategy):
    """区间网格策略"""
    
    PARAMETERS = {
        'price_range_lower': {
            'type': float,
            'default': -0.05,  # -5%
            'min': -0.20,
            'max': 0.0,
            'description': '价格区间下限（相对当前价格百分比）',
            'optimizable': True
        },
        'price_range_upper': {
            'type': float,
            'default': 0.05,  # +5%
            'min': 0.0,
            'max': 0.20,
            'description': '价格区间上限（相对当前价格百分比）',
            'optimizable': True
        },
        'grid_count': {
            'type': int,
            'default': 20,
            'min': 5,
            'max': 50,
            'description': '网格数量',
            'optimizable': True
        },
        'grid_mode': {
            'type': str,
            'default': 'ratio',
            'description': '网格模式: equal(等差) / ratio(等比)',
            'optimizable': False
        },
        'initial_position_ratio': {
            'type': float,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'description': '初始仓位比例（0-1）',
            'optimizable': True
        },
        'position_size_per_grid': {
            'type': float,
            'default': 0.01,
            'min': 0.001,
            'max': 0.1,
            'description': '每格仓位大小（合约张数）',
            'optimizable': True
        },
        'profit_per_grid_pct': {
            'type': float,
            'default': 0.003,  # 0.3%
            'min': 0.001,
            'max': 0.01,
            'description': '每格目标利润率（扣除手续费后）',
            'optimizable': True
        },
        'max_position_ratio': {
            'type': float,
            'default': 0.8,
            'min': 0.1,
            'max': 1.0,
            'description': '最大总仓位比例',
            'optimizable': True
        },
        'breakout_stop_loss_pct': {
            'type': float,
            'default': 0.02,  # 2%
            'min': 0.01,
            'max': 0.10,
            'description': '突破区间止损百分比',
            'optimizable': True
        },
        'total_profit_target_pct': {
            'type': float,
            'default': 0.05,  # 5%
            'min': 0.01,
            'max': 0.20,
            'description': '总收益目标（达到后全部平仓）',
            'optimizable': True
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
        # 网格状态
        if 'grids' not in self.state:
            self.state['grids'] = {}  # {grid_level: {'side': 'long'/'short', 'price': float, 'filled': bool}}
        if 'initial_price' not in self.state:
            self.state['initial_price'] = None
        if 'total_profit' not in self.state:
            self.state['total_profit'] = 0.0
        if 'total_invested' not in self.state:
            self.state['total_invested'] = 0.0
        
        # 市场分析器（用于自适应参数）
        self.market_analyzer = MarketAnalyzer()
    
    def reset_state(self):
        """重置策略状态"""
        super().reset_state()
        self.state['grids'] = {}
        self.state['initial_price'] = None
        self.state['total_profit'] = 0.0
        self.state['total_invested'] = 0.0
    
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
        volume = market_analysis.get('volume_profile', 'normal')
        
        # 基础参数
        base_grid_count = self.get_parameter('grid_count')
        base_range_lower = self.get_parameter('price_range_lower')
        base_range_upper = self.get_parameter('price_range_upper')
        base_profit_pct = self.get_parameter('profit_per_grid_pct')
        base_position_size = self.get_parameter('position_size_per_grid')
        base_max_position_ratio = self.get_parameter('max_position_ratio')
        base_stop_loss_pct = self.get_parameter('breakout_stop_loss_pct')
        
        # 根据波动率调整
        if volatility == 'high':
            # 高波动：减少网格数量，扩大区间，提高利润率
            adapted_params['grid_count'] = max(5, int(base_grid_count * 0.7))
            adapted_params['price_range_lower'] = base_range_lower * 1.5
            adapted_params['price_range_upper'] = base_range_upper * 1.5
            adapted_params['profit_per_grid_pct'] = min(base_profit_pct * 1.5, 0.01)
        elif volatility == 'low':
            # 低波动：增加网格数量，缩小区间
            adapted_params['grid_count'] = min(50, int(base_grid_count * 1.3))
            adapted_params['price_range_lower'] = base_range_lower * 0.7
            adapted_params['price_range_upper'] = base_range_upper * 0.7
        
        # 根据震荡强度调整
        if oscillation > 0.7:
            # 强震荡：增加网格数量，适当增加每格仓位
            current_grid_count = adapted_params.get('grid_count', base_grid_count)
            adapted_params['grid_count'] = min(50, int(current_grid_count * 1.2))
            adapted_params['position_size_per_grid'] = base_position_size * 1.1
        elif oscillation < 0.3:
            # 弱震荡：减少网格数量
            current_grid_count = adapted_params.get('grid_count', base_grid_count)
            adapted_params['grid_count'] = max(5, int(current_grid_count * 0.9))
        
        # 根据趋势强度调整
        if trend > 0.6:
            # 强趋势：扩大区间，放宽止损
            current_range_lower = adapted_params.get('price_range_lower', base_range_lower)
            current_range_upper = adapted_params.get('price_range_upper', base_range_upper)
            adapted_params['price_range_lower'] = current_range_lower * 1.3
            adapted_params['price_range_upper'] = current_range_upper * 1.3
            adapted_params['breakout_stop_loss_pct'] = min(base_stop_loss_pct * 1.5, 0.10)
        elif trend < 0.3:
            # 弱趋势/震荡：适合网格，可以稍微缩小区间
            current_range_lower = adapted_params.get('price_range_lower', base_range_lower)
            current_range_upper = adapted_params.get('price_range_upper', base_range_upper)
            adapted_params['price_range_lower'] = current_range_lower * 0.9
            adapted_params['price_range_upper'] = current_range_upper * 0.9
        
        # 根据成交量调整
        if volume == 'high':
            # 高成交量：增加仓位，允许更大总仓位
            current_position_size = adapted_params.get('position_size_per_grid', base_position_size)
            adapted_params['position_size_per_grid'] = min(current_position_size * 1.2, 0.1)
            adapted_params['max_position_ratio'] = min(base_max_position_ratio * 1.1, 1.0)
        elif volume == 'low':
            # 低成交量：减少仓位
            current_position_size = adapted_params.get('position_size_per_grid', base_position_size)
            adapted_params['position_size_per_grid'] = max(current_position_size * 0.8, 0.001)
        
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
    
    def _initialize_grids(self, current_price: float, effective_params: Dict = None):
        """初始化网格"""
        if self.state['initial_price'] is not None:
            return  # 已经初始化
        
        if effective_params is None:
            effective_params = self.get_parameters()
        
        self.state['initial_price'] = current_price
        
        # 计算价格区间（使用有效参数）
        lower_price = current_price * (1 + effective_params.get('price_range_lower', self.get_parameter('price_range_lower')))
        upper_price = current_price * (1 + effective_params.get('price_range_upper', self.get_parameter('price_range_upper')))
        
        grid_count = effective_params.get('grid_count', self.get_parameter('grid_count'))
        grid_mode = self.get_parameter('grid_mode')
        
        # 生成网格价格点
        if grid_mode == 'equal':
            # 等差网格
            price_step = (upper_price - lower_price) / grid_count
            grid_prices = [lower_price + i * price_step for i in range(grid_count + 1)]
        else:
            # 等比网格
            ratio = (upper_price / lower_price) ** (1.0 / grid_count)
            grid_prices = [lower_price * (ratio ** i) for i in range(grid_count + 1)]
        
        # 初始化网格状态
        for i, grid_price in enumerate(grid_prices):
            self.state['grids'][i] = {
                'price': grid_price,
                'side': None,  # 'long' 或 'short'
                'filled': False,
                'entry_price': None,
                'size': 0.0
            }
        
        # 初始建仓（在中间位置）
        initial_ratio = effective_params.get('initial_position_ratio', self.get_parameter('initial_position_ratio'))
        position_size_per_grid = effective_params.get('position_size_per_grid', self.get_parameter('position_size_per_grid'))
        if initial_ratio > 0:
            middle_grid = grid_count // 2
            if middle_grid in self.state['grids']:
                grid = self.state['grids'][middle_grid]
                grid['side'] = 'long'
                grid['filled'] = True
                grid['entry_price'] = grid['price']
                grid['size'] = position_size_per_grid * initial_ratio
                self.state['total_invested'] += grid['size'] * grid['price'] * 0.01
    
    def _check_grid_triggers(self, current_price: float, effective_params: Dict = None) -> List[Dict]:
        """检查网格触发，返回需要执行的交易列表"""
        signals = []
        
        if 'grids' not in self.state or not self.state['grids']:
            return signals
        
        if effective_params is None:
            effective_params = self.get_parameters()
        
        grid_count = len(self.state['grids']) - 1  # 网格数量
        position_size = effective_params.get('position_size_per_grid', self.get_parameter('position_size_per_grid'))
        profit_pct = effective_params.get('profit_per_grid_pct', self.get_parameter('profit_per_grid_pct'))
        max_position_ratio = effective_params.get('max_position_ratio', self.get_parameter('max_position_ratio'))
        
        # 检查每个网格
        for i in range(grid_count + 1):
            if i not in self.state['grids']:
                continue
            
            grid = self.state['grids'][i]
            grid_price = grid['price']
            
            # 检查买入网格（价格下跌到网格下方）
            if not grid['filled'] and grid['side'] is None:
                # 价格下跌到网格价格附近（允许0.1%误差）
                if current_price <= grid_price * 1.001:
                    # 检查是否超过最大仓位
                    total_position = sum(
                        g['size'] for g in self.state['grids'].values() if g['filled'] and g['side'] == 'long'
                    )
                    max_position = max_position_ratio * 10  # 假设最大10张
                    
                    if total_position + position_size <= max_position:
                        grid['side'] = 'long'
                        grid['filled'] = True
                        grid['entry_price'] = current_price
                        grid['size'] = position_size
                        self.state['total_invested'] += position_size * current_price * 0.01
                        
                        signals.append({
                            'action': 'BUY',
                            'size': position_size,
                            'price': current_price,
                            'grid_level': i,
                            'reason': f'网格买入: 网格{i}, 价格={grid_price:.2f}'
                        })
            
            # 检查卖出网格（价格上涨到网格上方，且有持仓）
            elif grid['filled'] and grid['side'] == 'long':
                # 计算目标卖出价格（网格价格 + 利润）
                target_sell_price = grid['entry_price'] * (1 + profit_pct)
                
                if current_price >= target_sell_price:
                    # 卖出
                    profit = (current_price - grid['entry_price']) / grid['entry_price'] * grid['size']
                    self.state['total_profit'] += profit
                    
                    signals.append({
                        'action': 'SELL',  # 平多仓
                        'size': grid['size'],
                        'price': current_price,
                        'grid_level': i,
                        'reason': f'网格卖出: 网格{i}, 盈利={profit*100:.2f}%'
                    })
                    
                    # 重置网格（可以再次买入）
                    grid['filled'] = False
                    grid['side'] = None
                    grid['entry_price'] = None
                    grid['size'] = 0.0
        
        return signals
    
    def _check_breakout(self, current_price: float, effective_params: Dict = None) -> Optional[Dict]:
        """检查价格突破区间"""
        if self.state['initial_price'] is None:
            return None
        
        if effective_params is None:
            effective_params = self.get_parameters()
        
        initial_price = self.state['initial_price']
        lower_bound = initial_price * (1 + effective_params.get('price_range_lower', self.get_parameter('price_range_lower')))
        upper_bound = initial_price * (1 + effective_params.get('price_range_upper', self.get_parameter('price_range_upper')))
        stop_loss_pct = effective_params.get('breakout_stop_loss_pct', self.get_parameter('breakout_stop_loss_pct'))
        
        # 检查是否突破区间
        if current_price < lower_bound or current_price > upper_bound:
            # 计算总亏损
            total_loss = 0.0
            total_size = 0.0
            
            for grid in self.state['grids'].values():
                if grid['filled'] and grid['side'] == 'long':
                    loss = (current_price - grid['entry_price']) / grid['entry_price'] * grid['size']
                    total_loss += loss
                    total_size += grid['size']
            
            # 如果亏损超过止损阈值，全部平仓
            if total_size > 0:
                loss_pct = abs(total_loss / total_size) if total_size > 0 else 0
                if loss_pct >= stop_loss_pct:
                    return {
                        'action': 'CLOSE_ALL',
                        'reason': f'突破区间止损: 亏损={loss_pct*100:.2f}%',
                        'total_size': total_size
                    }
        
        return None
    
    def _check_profit_target(self) -> Optional[Dict]:
        """检查是否达到总收益目标"""
        total_profit_pct = self.get_parameter('total_profit_target_pct')
        
        if self.state['total_invested'] > 0:
            profit_ratio = self.state['total_profit'] / self.state['total_invested']
            if profit_ratio >= total_profit_pct:
                # 计算需要平仓的总量
                total_size = sum(
                    grid['size'] for grid in self.state['grids'].values()
                    if grid['filled'] and grid['side'] == 'long'
                )
                
                if total_size > 0:
                    return {
                        'action': 'CLOSE_ALL',
                        'reason': f'达到总收益目标: {profit_ratio*100:.2f}%',
                        'total_size': total_size
                    }
        
        return None
    
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
        
        # 初始化网格（第一次调用时）
        self._initialize_grids(current_price, effective_params)
        
        # 检查是否达到总收益目标
        profit_signal = self._check_profit_target()
        if profit_signal:
            # 需要全部平仓
            if position is not None:
                return {
                    'action': 'CLOSE',
                    'size': position.size,
                    'stop_loss': None,
                    'take_profit': None,
                    'leverage': self.get_parameter('default_leverage'),
                    'reason': profit_signal['reason'],
                    'metadata': {'total_profit': self.state['total_profit']}
                }
        
        # 检查突破止损
        breakout_signal = self._check_breakout(current_price, effective_params)
        if breakout_signal:
            if position is not None:
                return {
                    'action': 'CLOSE',
                    'size': position.size,
                    'stop_loss': None,
                    'take_profit': None,
                    'leverage': self.get_parameter('default_leverage'),
                    'reason': breakout_signal['reason'],
                    'metadata': {}
                }
        
        # 检查网格触发
        grid_signals = self._check_grid_triggers(current_price, effective_params)
        
        if grid_signals:
            # 返回第一个信号（实际应用中可能需要合并多个信号）
            signal = grid_signals[0]
            
            # 如果是买入信号且当前无持仓，开仓
            if signal['action'] == 'BUY' and position is None:
                # 计算止损止盈（基于网格区间）
                initial_price = self.state['initial_price']
                lower_bound = initial_price * (1 + effective_params.get('price_range_lower', self.get_parameter('price_range_lower')))
                upper_bound = initial_price * (1 + effective_params.get('price_range_upper', self.get_parameter('price_range_upper')))
                profit_pct = effective_params.get('profit_per_grid_pct', self.get_parameter('profit_per_grid_pct'))
                
                return {
                    'action': 'BUY',
                    'size': signal['size'],
                    'stop_loss': lower_bound * 0.99,  # 略低于区间下限
                    'take_profit': signal['price'] * (1 + profit_pct),
                    'leverage': self.get_parameter('default_leverage'),
                    'reason': signal['reason'] + (f" [市场: {market_analysis.get('market_regime', 'N/A')}]" if market_analysis else ""),
                    'metadata': {
                        'grid_level': signal['grid_level'],
                        'grid_price': self.state['grids'][signal['grid_level']]['price'],
                        'market_analysis': market_analysis
                    }
                }
            
            # 如果是卖出信号且当前有持仓，平仓
            elif signal['action'] == 'SELL' and position is not None:
                return {
                    'action': 'CLOSE',
                    'size': min(signal['size'], position.size),  # 平仓数量不超过持仓
                    'stop_loss': None,
                    'take_profit': None,
                    'leverage': self.get_parameter('default_leverage'),
                    'reason': signal['reason'],
                    'metadata': {
                        'grid_level': signal['grid_level'],
                        'total_profit': self.state['total_profit']
                    }
                }
        
        return None
    
    def get_description(self) -> str:
        """获取策略描述"""
        return "区间网格策略 - 在价格区间内设置买卖网格，低买高卖赚取差价"
