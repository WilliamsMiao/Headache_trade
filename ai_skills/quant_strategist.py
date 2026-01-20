"""
Quant Strategist Skill - 量化策略专家
负责动态策略选择、参数优化、多策略组合和信号生成
"""

import sys
import os
from typing import Dict, Any, List, Optional
import pandas as pd

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_skills.base_skill import BaseSkill, SkillResult, SkillStatus
from ai_skills.config import AISkillsConfig
from strategies.strategy_registry import StrategyRegistry
from strategies.optimizer import StrategyOptimizer
from trading_bots.config import deepseek_client, TRADE_CONFIG
from trading_bots.execution import get_current_position


class QuantStrategistSkill(BaseSkill):
    """量化策略专家技能"""
    
    def __init__(self):
        config = AISkillsConfig.get_skill_config('quant_strategist')
        super().__init__(
            name='quant_strategist',
            timeout=config['timeout'],
            enabled=config['enabled'],
            priority=config['priority']
        )
        self.optimizer = StrategyOptimizer(ai_client=deepseek_client)
        self.available_strategies = StrategyRegistry.list_strategies()
        self.strategy_weights = {}  # 策略权重缓存
    
    def get_required_inputs(self) -> List[str]:
        """获取所需的输入字段"""
        return ['market_analysis']  # 需要市场分析结果
    
    def get_output_schema(self) -> Dict[str, Any]:
        """获取输出数据格式定义"""
        return {
            'action': {
                'type': 'string',
                'values': ['BUY', 'SELL', 'HOLD'],
                'description': '交易动作'
            },
            'size': {
                'type': 'float',
                'description': '仓位大小'
            },
            'entry_conditions': {
                'type': 'dict',
                'description': '入场条件'
            },
            'exit_conditions': {
                'type': 'dict',
                'description': '出场条件'
            },
            'confidence': {
                'type': 'float',
                'range': [0, 1],
                'description': '信号置信度'
            },
            'strategy_name': {
                'type': 'string',
                'description': '使用的策略名称'
            },
            'reasoning': {
                'type': 'string',
                'description': '决策理由'
            }
        }
    
    def execute(
        self,
        context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> SkillResult:
        """执行策略生成"""
        try:
            market_analysis = input_data.get('market_analysis', {})
            
            # 1. 根据市场状态选择策略
            selected_strategy = self._select_strategy(market_analysis)
            
            # 2. 获取当前持仓状态
            position_info = self._get_position_info()
            
            # 3. 如果有持仓，检查是否需要平仓
            if position_info and position_info.get('size', 0) > 0:
                exit_signal = self._check_exit_conditions(
                    market_analysis,
                    position_info,
                    selected_strategy
                )
                if exit_signal:
                    return SkillResult(
                        skill_name=self.name,
                        status=SkillStatus.SUCCESS,
                        output=exit_signal,
                        confidence=exit_signal.get('confidence', 0.7)
                    )
            
            # 4. 生成交易信号
            signal = self._generate_signal(
                market_analysis,
                selected_strategy,
                position_info
            )
            
            if not signal:
                # 没有信号，返回HOLD
                return SkillResult(
                    skill_name=self.name,
                    status=SkillStatus.SUCCESS,
                    output={
                        'action': 'HOLD',
                        'size': 0,
                        'confidence': 0.5,
                        'strategy_name': selected_strategy,
                        'reasoning': '市场条件不满足交易要求'
                    },
                    confidence=0.5
                )
            
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.SUCCESS,
                output=signal,
                confidence=signal.get('confidence', 0.7)
            )
            
        except Exception as e:
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"策略生成失败: {str(e)}"
            )
    
    def _select_strategy(self, market_analysis: Dict[str, Any]) -> str:
        """根据市场状态选择策略"""
        market_regime = market_analysis.get('market_regime', 'ranging')
        trend_strength = market_analysis.get('trend_strength', 5.0)
        volatility = market_analysis.get('volatility', 0.01)
        
        # 策略选择逻辑
        if market_regime == 'trending' and trend_strength > 7:
            # 强趋势市场，使用趋势策略
            if 'trend' in self.available_strategies:
                return 'trend'
            elif 'signal' in self.available_strategies:
                return 'signal'
        
        elif market_regime == 'ranging':
            # 震荡市场，使用网格策略
            if 'grid' in self.available_strategies:
                return 'grid'
            elif 'signal' in self.available_strategies:
                return 'signal'
        
        elif market_regime == 'volatile' and volatility > 0.02:
            # 高波动市场，使用保守策略
            if 'signal' in self.available_strategies:
                return 'signal'
        
        # 默认使用signal策略
        if 'signal' in self.available_strategies:
            return 'signal'
        
        # 如果signal不可用，使用第一个可用策略
        return self.available_strategies[0] if self.available_strategies else 'signal'
    
    def _generate_signal(
        self,
        market_analysis: Dict[str, Any],
        strategy_name: str,
        position_info: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """生成交易信号"""
        try:
            # 获取策略实例
            strategy = StrategyRegistry.get_strategy(strategy_name)
            
            # 根据市场状态优化参数
            optimized_params = self._optimize_parameters(
                strategy,
                market_analysis
            )
            
            if optimized_params:
                strategy = StrategyRegistry.get_strategy(
                    strategy_name,
                    params=optimized_params
                )
            
            # 构建策略输入数据
            # 注意：这里需要将market_analysis转换为策略需要的格式
            # 由于策略接口需要DataFrame，我们需要从context获取或重新获取数据
            # 这里简化处理，使用市场分析的关键指标
            
            # 计算信号置信度
            confidence = self._calculate_signal_confidence(
                market_analysis,
                strategy_name
            )
            
            # 如果置信度太低，不生成信号
            if confidence < 0.5:
                return None
            
            # 根据市场分析生成基础信号
            trend_strength = market_analysis.get('trend_strength', 5.0)
            trend_direction = market_analysis.get('primary_analysis', {}).get('trend_direction', '震荡整理')
            market_regime = market_analysis.get('market_regime', 'ranging')
            
            # 决定交易方向
            action = 'HOLD'
            if trend_strength > 6:
                if '上涨' in trend_direction or '强势上涨' in trend_direction:
                    action = 'BUY'
                elif '下跌' in trend_direction or '强势下跌' in trend_direction:
                    action = 'SELL'
            
            # 如果市场状态不适合交易，保持HOLD
            if market_regime == 'volatile' and market_analysis.get('anomaly_flags'):
                action = 'HOLD'
            
            if action == 'HOLD':
                return None
            
            # 计算仓位大小（基础计算，实际由Risk Manager调整）
            base_size = self._calculate_base_size(market_analysis, confidence)
            
            # 构建信号
            signal = {
                'action': action,
                'size': base_size,
                'entry_conditions': {
                    'price': market_analysis.get('primary_analysis', {}).get('current_price'),
                    'rsi': market_analysis.get('primary_analysis', {}).get('rsi', 50),
                    'trend_strength': trend_strength
                },
                'exit_conditions': {
                    'stop_loss_pct': 0.02,  # 默认2%止损
                    'take_profit_pct': 0.04,  # 默认4%止盈
                    'trailing_stop': True
                },
                'confidence': confidence,
                'strategy_name': strategy_name,
                'reasoning': self._generate_reasoning(market_analysis, action, strategy_name)
            }
            
            return signal
            
        except Exception as e:
            print(f"⚠️ 信号生成失败: {e}")
            return None
    
    def _optimize_parameters(
        self,
        strategy_class,
        market_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """根据市场状态优化策略参数"""
        try:
            # 获取策略默认参数
            default_strategy = strategy_class()
            current_params = default_strategy.get_parameters()
            
            # 根据市场状态调整参数
            optimized_params = current_params.copy()
            
            market_regime = market_analysis.get('market_regime', 'ranging')
            volatility = market_analysis.get('volatility', 0.01)
            trend_strength = market_analysis.get('trend_strength', 5.0)
            
            # 根据市场状态调整参数
            if market_regime == 'volatile':
                # 高波动市场，收紧止损
                if 'stop_loss_pct' in optimized_params:
                    optimized_params['stop_loss_pct'] = optimized_params.get('stop_loss_pct', 0.02) * 0.8
                if 'risk_per_trade' in optimized_params:
                    optimized_params['risk_per_trade'] = optimized_params.get('risk_per_trade', 0.02) * 0.7
            
            elif market_regime == 'trending' and trend_strength > 7:
                # 强趋势市场，可以放宽止损，增加止盈
                if 'stop_loss_pct' in optimized_params:
                    optimized_params['stop_loss_pct'] = optimized_params.get('stop_loss_pct', 0.02) * 1.2
                if 'take_profit_pct' in optimized_params:
                    optimized_params['take_profit_pct'] = optimized_params.get('take_profit_pct', 0.04) * 1.5
            
            elif market_regime == 'ranging':
                # 震荡市场，使用更小的仓位
                if 'risk_per_trade' in optimized_params:
                    optimized_params['risk_per_trade'] = optimized_params.get('risk_per_trade', 0.02) * 0.8
            
            return optimized_params
            
        except Exception as e:
            print(f"⚠️ 参数优化失败: {e}")
            return None
    
    def _calculate_signal_confidence(
        self,
        market_analysis: Dict[str, Any],
        strategy_name: str
    ) -> float:
        """计算信号置信度"""
        confidence = 0.5  # 基础置信度
        
        # 趋势强度越高，置信度越高
        trend_strength = market_analysis.get('trend_strength', 5.0)
        if trend_strength > 8:
            confidence += 0.2
        elif trend_strength > 6:
            confidence += 0.1
        
        # 市场分析置信度
        analysis_confidence = market_analysis.get('confidence', 0.7)
        confidence = (confidence + analysis_confidence) / 2
        
        # 异常标志降低置信度
        anomaly_flags = market_analysis.get('anomaly_flags', [])
        if anomaly_flags:
            confidence -= len(anomaly_flags) * 0.1
        
        # 市场状态匹配度
        market_regime = market_analysis.get('market_regime', 'ranging')
        if (market_regime == 'trending' and strategy_name == 'trend') or \
           (market_regime == 'ranging' and strategy_name == 'grid'):
            confidence += 0.1
        
        return max(0.0, min(1.0, confidence))
    
    def _calculate_base_size(
        self,
        market_analysis: Dict[str, Any],
        confidence: float
    ) -> float:
        """计算基础仓位大小"""
        # 基础仓位（合约张数）
        base_size = TRADE_CONFIG.get('contract_size', 0.01)
        
        # 根据置信度调整
        size_multiplier = confidence
        
        # 根据市场状态调整
        market_regime = market_analysis.get('market_regime', 'ranging')
        if market_regime == 'volatile':
            size_multiplier *= 0.7
        elif market_regime == 'trending':
            size_multiplier *= 1.2
        
        return base_size * size_multiplier
    
    def _get_position_info(self) -> Optional[Dict[str, Any]]:
        """获取当前持仓信息"""
        try:
            position = get_current_position()
            if position and position.get('size', 0) > 0:
                return position
            return None
        except Exception as e:
            print(f"⚠️ 获取持仓信息失败: {e}")
            return None
    
    def _check_exit_conditions(
        self,
        market_analysis: Dict[str, Any],
        position_info: Dict[str, Any],
        strategy_name: str
    ) -> Optional[Dict[str, Any]]:
        """检查是否需要平仓"""
        # 简化的平仓逻辑
        # 实际应该根据策略和持仓情况判断
        
        # 如果市场状态发生重大变化，考虑平仓
        market_regime = market_analysis.get('market_regime', 'ranging')
        anomaly_flags = market_analysis.get('anomaly_flags', [])
        
        # 如果有严重异常，建议平仓
        if len(anomaly_flags) >= 3:
            return {
                'action': 'CLOSE',
                'size': position_info.get('size', 0),
                'confidence': 0.8,
                'strategy_name': strategy_name,
                'reasoning': f'检测到{len(anomaly_flags)}个异常标志，建议平仓'
            }
        
        return None
    
    def _generate_reasoning(
        self,
        market_analysis: Dict[str, Any],
        action: str,
        strategy_name: str
    ) -> str:
        """生成决策理由"""
        trend_strength = market_analysis.get('trend_strength', 5.0)
        market_regime = market_analysis.get('market_regime', 'ranging')
        trend_direction = market_analysis.get('primary_analysis', {}).get('trend_direction', '震荡整理')
        
        reasoning = f"基于{strategy_name}策略，"
        
        if action == 'BUY':
            reasoning += f"检测到{trend_direction}趋势（强度{trend_strength:.1f}/10），市场状态{market_regime}，建议做多"
        elif action == 'SELL':
            reasoning += f"检测到{trend_direction}趋势（强度{trend_strength:.1f}/10），市场状态{market_regime}，建议做空"
        else:
            reasoning += f"市场状态{market_regime}，趋势强度{trend_strength:.1f}/10，暂不交易"
        
        return reasoning
