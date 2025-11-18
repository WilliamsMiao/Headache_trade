"""
AI策略顾问
结合DeepSeek AI和技术分析，提供策略建议
"""

import json
import re
from typing import Dict, Optional, List
from datetime import datetime
from openai import OpenAI
import pandas as pd

from market_analyzer import MarketState, MarketRegime


class AIStrategyAdvisor:
    """AI策略顾问 - 结合AI思考和技术分析"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = "deepseek-chat"
        
        # AI建议历史
        self.advice_history = []
        
        # 可用策略
        self.available_strategies = {
            'grid': '网格交易',
            'trend': '趋势跟随',
            'mean_reversion': '均值回归',
            'breakout': '突破策略',
            'momentum': '动量策略'
        }
    
    def get_strategy_advice(self, 
                           market_state: MarketState,
                           price_data: pd.DataFrame,
                           current_strategy: Optional[str] = None,
                           strategy_performance: Optional[Dict] = None) -> Dict:
        """
        获取AI策略建议
        
        Args:
            market_state: 市场状态分析
            price_data: 价格数据
            current_strategy: 当前使用的策略
            strategy_performance: 策略历史表现
        
        Returns:
            dict: AI建议
                - recommended_strategy: 推荐策略
                - confidence: 置信度 0-100
                - reasoning: 推理过程
                - alternative_strategies: 备选策略列表
                - risk_warning: 风险提示
                - should_switch: 是否应该切换策略
        """
        try:
            prompt = self._build_strategy_prompt(
                market_state, 
                price_data, 
                current_strategy,
                strategy_performance
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,  # 较低温度保持一致性
                max_tokens=1500,
            )
            
            result_text = response.choices[0].message.content
            result = self._parse_strategy_response(result_text)
            
            # 记录建议历史
            self._record_advice(result, market_state)
            
            return result
            
        except Exception as e:
            print(f"❌ AI策略顾问失败: {e}")
            # 返回保守建议
            return self._get_fallback_advice(market_state, current_strategy)
    
    def get_signal_confirmation(self,
                               signal_type: str,
                               signal_data: Dict,
                               market_context: Dict) -> Dict:
        """
        AI确认交易信号
        
        Args:
            signal_type: 信号类型 (LONG/SHORT/HOLD)
            signal_data: 信号数据（入场价、止损、止盈等）
            market_context: 市场背景信息
        
        Returns:
            dict: 确认结果
                - confirmed: 是否确认信号
                - confidence_adjustment: 置信度调整 -20 to +20
                - reasoning: 理由
                - suggestions: 优化建议（止损/止盈调整等）
        """
        try:
            prompt = self._build_signal_prompt(signal_type, signal_data, market_context)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的交易信号验证专家，帮助确认交易信号的有效性。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=800,
            )
            
            result_text = response.choices[0].message.content
            return self._parse_signal_response(result_text)
            
        except Exception as e:
            print(f"❌ AI信号确认失败: {e}")
            # 返回中性确认
            return {
                'confirmed': True,
                'confidence_adjustment': 0,
                'reasoning': 'AI不可用，使用技术信号',
                'suggestions': {}
            }
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个经验丰富的量化交易策略专家，专注于加密货币市场。

你的职责：
1. 分析市场环境，识别市场状态（趋势、震荡、突破等）
2. 评估不同交易策略在当前市场的适用性
3. 提供策略选择建议，包含详细推理过程
4. 评估策略切换的必要性和时机
5. 识别潜在风险并给出预警

可用策略：
- grid（网格交易）：适合震荡市场，低买高卖
- trend（趋势跟随）：适合单边行情，趋势明确
- mean_reversion（均值回归）：适合超买超卖，价格回归
- breakout（突破策略）：适合盘整后突破，捕捉大行情
- momentum（动量策略）：适合强势加速，快进快出

分析原则：
- 结合技术指标和市场结构
- 考虑策略历史表现
- 评估风险收益比
- 保持理性，避免过度交易
- 策略切换需要充分理由

请以JSON格式返回结果。"""
    
    def _build_strategy_prompt(self, 
                              market_state: MarketState,
                              price_data: pd.DataFrame,
                              current_strategy: Optional[str],
                              strategy_performance: Optional[Dict]) -> str:
        """构建策略建议提示词"""
        
        # 价格数据摘要
        current_price = price_data['close'].iloc[-1]
        price_change_1h = (price_data['close'].iloc[-1] / price_data['close'].iloc[-2] - 1) * 100
        price_change_24h = (price_data['close'].iloc[-1] / price_data['close'].iloc[-24] - 1) * 100 if len(price_data) >= 24 else 0
        
        # 市场状态描述
        market_desc = f"""
市场状态：
- 当前状态: {market_state.regime.value}
- 趋势强度: {market_state.trend_strength:.1f}
- ADX: {market_state.adx:.1f}
- 波动率: {market_state.volatility:.2f}%
- 置信度: {market_state.confidence:.1f}%
- 技术建议: {market_state.recommendation}

价格信息：
- 当前价格: ${current_price:.2f}
- 1小时涨跌: {price_change_1h:+.2f}%
- 24小时涨跌: {price_change_24h:+.2f}%
"""
        
        # 当前策略信息
        if current_strategy:
            strategy_name = self.available_strategies.get(current_strategy, current_strategy)
            current_desc = f"""
当前策略：
- 策略: {strategy_name} ({current_strategy})
"""
            if strategy_performance:
                perf = strategy_performance.get(current_strategy, {})
                current_desc += f"""- 总交易: {perf.get('total_trades', 0)}
- 胜率: {perf.get('win_rate', 0):.1f}%
- 总盈亏: {perf.get('total_pnl', 0):.2f} USDT
- 最大回撤: {perf.get('max_drawdown', 0):.2f}%
"""
        else:
            current_desc = "当前策略：无（首次运行或暂停中）"
        
        # 所有策略表现
        perf_desc = "\n所有策略历史表现：\n"
        if strategy_performance:
            for strategy, perf in strategy_performance.items():
                strategy_name = self.available_strategies.get(strategy, strategy)
                perf_desc += f"""- {strategy_name}: 交易{perf.get('total_trades', 0)}次, 胜率{perf.get('win_rate', 0):.1f}%, 盈亏{perf.get('total_pnl', 0):+.2f} USDT
"""
        else:
            perf_desc += "- 暂无历史数据\n"
        
        prompt = f"""请分析当前市场并给出策略建议：

{market_desc}

{current_desc}

{perf_desc}

请回答以下问题并以JSON格式返回：

{{
    "recommended_strategy": "推荐的策略名称（grid/trend/mean_reversion/breakout/momentum）",
    "confidence": 置信度0-100,
    "reasoning": "详细推理过程，说明为什么选择这个策略",
    "alternative_strategies": ["备选策略1", "备选策略2"],
    "risk_warning": "当前市场的主要风险提示",
    "should_switch": true/false（是否建议切换策略）,
    "market_outlook": "short_term_trend/medium_term_trend的预测"
}}

注意：
1. 如果当前策略表现良好且市场环境未明显变化，建议保持
2. 只在有充分理由时才建议切换策略
3. 考虑策略切换的成本（平仓、等待、开新仓）
4. 置信度要反映市场的明确程度
"""
        
        return prompt
    
    def _build_signal_prompt(self,
                            signal_type: str,
                            signal_data: Dict,
                            market_context: Dict) -> str:
        """构建信号确认提示词"""
        
        prompt = f"""请验证以下交易信号：

信号类型: {signal_type}
入场价: ${signal_data.get('entry_price', 0):.2f}
止损价: ${signal_data.get('stop_loss', 0):.2f}
止盈价: ${signal_data.get('take_profit', 0):.2f}
技术置信度: {signal_data.get('confidence', 0):.1f}%

市场背景:
- 市场状态: {market_context.get('regime', 'UNKNOWN')}
- ADX: {market_context.get('adx', 0):.1f}
- RSI: {market_context.get('rsi', 50):.1f}
- 波动率: {market_context.get('volatility', 0):.2f}%

请以JSON格式返回：
{{
    "confirmed": true/false（是否确认信号），
    "confidence_adjustment": -20到+20（置信度调整，负数降低，正数提高），
    "reasoning": "确认或拒绝的理由",
    "suggestions": {{
        "stop_loss_adjustment": 建议的止损调整（可选），
        "take_profit_adjustment": 建议的止盈调整（可选），
        "position_size_adjustment": 建议的仓位调整（可选）
    }}
}}

评估要点：
1. 信号与市场环境是否匹配
2. 止损止盈设置是否合理
3. 风险收益比是否值得
4. 是否有明显的反向信号
"""
        
        return prompt
    
    def _parse_strategy_response(self, text: str) -> Dict:
        """解析策略建议响应"""
        try:
            # 提取JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 验证必需字段
                required_fields = ['recommended_strategy', 'confidence', 'reasoning']
                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"缺少必需字段: {field}")
                
                # 设置默认值
                result.setdefault('alternative_strategies', [])
                result.setdefault('risk_warning', '请注意市场风险')
                result.setdefault('should_switch', False)
                result.setdefault('market_outlook', 'uncertain')
                
                return result
            else:
                raise ValueError("未找到JSON格式")
                
        except Exception as e:
            print(f"⚠️ 解析AI响应失败: {e}")
            print(f"原始响应: {text[:200]}...")
            return self._get_default_advice()
    
    def _parse_signal_response(self, text: str) -> Dict:
        """解析信号确认响应"""
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                result.setdefault('confirmed', True)
                result.setdefault('confidence_adjustment', 0)
                result.setdefault('reasoning', 'AI确认通过')
                result.setdefault('suggestions', {})
                
                return result
            else:
                raise ValueError("未找到JSON格式")
                
        except Exception as e:
            print(f"⚠️ 解析信号响应失败: {e}")
            return {
                'confirmed': True,
                'confidence_adjustment': 0,
                'reasoning': '解析失败，默认确认',
                'suggestions': {}
            }
    
    def _get_fallback_advice(self, 
                            market_state: MarketState,
                            current_strategy: Optional[str]) -> Dict:
        """获取备用建议（AI不可用时）"""
        # 基于技术分析的简单映射
        strategy_map = {
            MarketRegime.STRONG_TREND: 'trend',
            MarketRegime.WEAK_TREND: 'trend',
            MarketRegime.RANGE_BOUND: 'grid',
            MarketRegime.HIGH_VOLATILITY: 'grid',
            MarketRegime.BREAKOUT_PENDING: 'breakout',
            MarketRegime.UNKNOWN: current_strategy or 'grid'
        }
        
        recommended = strategy_map.get(market_state.regime, 'grid')
        
        return {
            'recommended_strategy': recommended,
            'confidence': market_state.confidence * 0.8,  # 降低置信度
            'reasoning': f'AI不可用，基于技术分析建议使用{recommended}策略',
            'alternative_strategies': [],
            'risk_warning': 'AI分析服务暂时不可用，仅依赖技术指标',
            'should_switch': False if current_strategy == recommended else True,
            'market_outlook': 'uncertain'
        }
    
    def _get_default_advice(self) -> Dict:
        """获取默认建议"""
        return {
            'recommended_strategy': 'grid',
            'confidence': 50.0,
            'reasoning': '使用保守策略',
            'alternative_strategies': ['trend'],
            'risk_warning': '市场不明确，建议谨慎',
            'should_switch': False,
            'market_outlook': 'uncertain'
        }
    
    def _record_advice(self, advice: Dict, market_state: MarketState):
        """记录AI建议历史"""
        record = {
            'timestamp': datetime.now(),
            'strategy': advice['recommended_strategy'],
            'confidence': advice['confidence'],
            'market_regime': market_state.regime.value,
            'reasoning': advice['reasoning'][:100]  # 只保留前100字符
        }
        
        self.advice_history.append(record)
        
        # 只保留最近50条
        if len(self.advice_history) > 50:
            self.advice_history = self.advice_history[-50:]
    
    def get_advice_history(self, limit: int = 10) -> List[Dict]:
        """获取AI建议历史"""
        return self.advice_history[-limit:]
    
    def get_strategy_consistency(self, window: int = 5) -> Dict:
        """
        检查AI建议的一致性
        
        Args:
            window: 检查最近N条建议
        
        Returns:
            dict: 一致性分析
        """
        if len(self.advice_history) < window:
            return {
                'consistent': True,
                'dominant_strategy': None,
                'confidence_trend': 'stable'
            }
        
        recent = self.advice_history[-window:]
        strategies = [a['strategy'] for a in recent]
        confidences = [a['confidence'] for a in recent]
        
        # 统计最常见策略
        from collections import Counter
        strategy_counts = Counter(strategies)
        dominant_strategy = strategy_counts.most_common(1)[0][0]
        consistency_ratio = strategy_counts[dominant_strategy] / len(strategies)
        
        # 置信度趋势
        if confidences[-1] > confidences[0] + 10:
            confidence_trend = 'rising'
        elif confidences[-1] < confidences[0] - 10:
            confidence_trend = 'falling'
        else:
            confidence_trend = 'stable'
        
        return {
            'consistent': consistency_ratio >= 0.6,
            'dominant_strategy': dominant_strategy,
            'consistency_ratio': consistency_ratio,
            'confidence_trend': confidence_trend,
            'avg_confidence': sum(confidences) / len(confidences)
        }


def create_ai_advisor(api_key: str) -> AIStrategyAdvisor:
    """创建AI策略顾问"""
    return AIStrategyAdvisor(api_key)
