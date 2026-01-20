"""
Risk Manager Skill - 风险管理专家
负责动态仓位sizing、最大回撤控制、流动性风险评估、黑天鹅事件检测
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_skills.base_skill import BaseSkill, SkillResult, SkillStatus
from ai_skills.config import AISkillsConfig
from trading_bots.risk import (
    ProtectionOrbit,
    DynamicTakeProfit,
    ProgressiveProtection,
    RiskRewardOptimizer
)
from trading_bots.config import TRADE_CONFIG, exchange, performance_tracker
from trading_bots.execution import get_current_position
from trading_bots.main_bot import _fetch_account_balance_usdt


class RiskManagerSkill(BaseSkill):
    """风险管理专家技能"""
    
    def __init__(self):
        config = AISkillsConfig.get_skill_config('risk_manager')
        super().__init__(
            name='risk_manager',
            timeout=config['timeout'],
            enabled=config['enabled'],
            priority=config['priority']
        )
        self.risk_reward_optimizer = RiskRewardOptimizer()
        self.max_drawdown_tracker = {}  # 跟踪最大回撤
        self.black_swan_threshold = 0.10  # 10%价格变化视为黑天鹅
    
    def get_required_inputs(self) -> List[str]:
        """获取所需的输入字段"""
        return ['strategy_signal', 'market_analysis']  # 需要策略信号和市场分析
    
    def get_output_schema(self) -> Dict[str, Any]:
        """获取输出数据格式定义"""
        return {
            'action': {
                'type': 'string',
                'values': ['BUY', 'SELL', 'HOLD', 'CLOSE'],
                'description': '风险调整后的交易动作'
            },
            'size': {
                'type': 'float',
                'description': '风险调整后的仓位大小'
            },
            'stop_loss': {
                'type': 'float',
                'description': '止损价格'
            },
            'take_profit': {
                'type': 'float',
                'description': '止盈价格'
            },
            'leverage': {
                'type': 'int',
                'description': '杠杆倍数'
            },
            'risk_score': {
                'type': 'float',
                'range': [0, 1],
                'description': '风险评分（0-1，越高风险越大）'
            },
            'risk_adjustments': {
                'type': 'dict',
                'description': '风险调整详情'
            }
        }
    
    def execute(
        self,
        context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> SkillResult:
        """执行风险管理"""
        try:
            strategy_signal = input_data.get('strategy_signal', {})
            market_analysis = input_data.get('market_analysis', {})
            
            # 1. 黑天鹅事件检测
            black_swan_detected = self._detect_black_swan(market_analysis)
            if black_swan_detected:
                # 如果检测到黑天鹅，建议平仓或拒绝交易
                position_info = get_current_position()
                if position_info and position_info.get('size', 0) > 0:
                    return SkillResult(
                        skill_name=self.name,
                        status=SkillStatus.SUCCESS,
                        output={
                            'action': 'CLOSE',
                            'size': position_info.get('size', 0),
                            'stop_loss': 0,
                            'take_profit': 0,
                            'leverage': 1,
                            'risk_score': 1.0,
                            'risk_adjustments': {
                                'reason': '黑天鹅事件检测',
                                'black_swan_flags': black_swan_detected
                            }
                        },
                        confidence=0.9
                    )
                else:
                    # 没有持仓，拒绝新交易
                    return SkillResult(
                        skill_name=self.name,
                        status=SkillStatus.SUCCESS,
                        output={
                            'action': 'HOLD',
                            'size': 0,
                            'stop_loss': 0,
                            'take_profit': 0,
                            'leverage': 1,
                            'risk_score': 1.0,
                            'risk_adjustments': {
                                'reason': '黑天鹅事件检测，拒绝交易',
                                'black_swan_flags': black_swan_detected
                            }
                        },
                        confidence=0.9
                    )
            
            # 2. 流动性风险评估
            liquidity_risk = self._assess_liquidity_risk(market_analysis)
            
            # 3. 最大回撤检查
            drawdown_check = self._check_max_drawdown(context)
            if not drawdown_check['allowed']:
                # 回撤超限，拒绝交易或建议减仓
                if strategy_signal.get('action') in ['BUY', 'SELL']:
                    return SkillResult(
                        skill_name=self.name,
                        status=SkillStatus.SUCCESS,
                        output={
                            'action': 'HOLD',
                            'size': 0,
                            'stop_loss': 0,
                            'take_profit': 0,
                            'leverage': 1,
                            'risk_score': 0.8,
                            'risk_adjustments': {
                                'reason': drawdown_check['reason']
                            }
                        },
                        confidence=0.8
                    )
            
            # 4. 动态仓位sizing
            adjusted_size = self._calculate_position_size(
                strategy_signal,
                market_analysis,
                liquidity_risk
            )
            
            # 5. 计算止损止盈
            stop_loss, take_profit = self._calculate_stop_loss_take_profit(
                strategy_signal,
                market_analysis
            )
            
            # 6. 计算杠杆
            leverage = self._calculate_leverage(
                market_analysis,
                liquidity_risk
            )
            
            # 7. 计算风险评分
            risk_score = self._calculate_risk_score(
                market_analysis,
                liquidity_risk,
                adjusted_size,
                stop_loss,
                take_profit
            )
            
            # 8. 如果风险过高，拒绝或调整交易
            if risk_score > 0.8:
                if strategy_signal.get('action') in ['BUY', 'SELL']:
                    return SkillResult(
                        skill_name=self.name,
                        status=SkillStatus.SUCCESS,
                        output={
                            'action': 'HOLD',
                            'size': 0,
                            'stop_loss': 0,
                            'take_profit': 0,
                            'leverage': 1,
                            'risk_score': risk_score,
                            'risk_adjustments': {
                                'reason': '风险评分过高，拒绝交易',
                                'original_signal': strategy_signal
                            }
                        },
                        confidence=0.8
                    )
            
            # 9. 构建风险调整后的信号
            adjusted_signal = {
                'action': strategy_signal.get('action', 'HOLD'),
                'size': adjusted_size,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'leverage': leverage,
                'risk_score': risk_score,
                'risk_adjustments': {
                    'size_adjustment': adjusted_size / max(strategy_signal.get('size', 0.01), 0.01),
                    'liquidity_risk': liquidity_risk,
                    'drawdown_status': drawdown_check,
                    'original_size': strategy_signal.get('size', 0)
                }
            }
            
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.SUCCESS,
                output=adjusted_signal,
                confidence=1.0 - risk_score  # 风险越低，置信度越高
            )
            
        except Exception as e:
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"风险管理失败: {str(e)}"
            )
    
    def _detect_black_swan(self, market_analysis: Dict[str, Any]) -> List[str]:
        """检测黑天鹅事件"""
        flags = []
        
        try:
            # 1. 价格突变检测
            primary_analysis = market_analysis.get('primary_analysis', {})
            if 'price_change' in primary_analysis:
                price_change = abs(primary_analysis['price_change'])
                if price_change > self.black_swan_threshold * 100:  # 转换为百分比
                    flags.append(f'极端价格变化: {price_change:.2f}%')
            
            # 2. 异常标志检测
            anomaly_flags = market_analysis.get('anomaly_flags', [])
            if len(anomaly_flags) >= 3:
                flags.append(f'多重异常: {len(anomaly_flags)}个异常标志')
            
            # 3. 波动率极端值
            volatility = market_analysis.get('volatility', 0.0)
            if volatility > 0.05:  # 5%以上波动率
                flags.append(f'极端波动率: {volatility:.2%}')
            
            # 4. 成交量异常
            volume_profile = primary_analysis.get('volume_profile', 'normal')
            if volume_profile == 'low' and volatility > 0.03:
                flags.append('低成交量高波动 - 疑似流动性危机')
        
        except Exception as e:
            print(f"⚠️ 黑天鹅检测失败: {e}")
        
        return flags
    
    def _assess_liquidity_risk(self, market_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """评估流动性风险"""
        risk_level = 'low'
        risk_score = 0.0
        
        try:
            primary_analysis = market_analysis.get('primary_analysis', {})
            volume_profile = primary_analysis.get('volume_profile', 'normal')
            volatility = market_analysis.get('volatility', 0.0)
            
            # 低成交量 + 高波动 = 高流动性风险
            if volume_profile == 'low' and volatility > 0.02:
                risk_level = 'high'
                risk_score = 0.8
            elif volume_profile == 'low' or volatility > 0.03:
                risk_level = 'medium'
                risk_score = 0.5
            else:
                risk_level = 'low'
                risk_score = 0.2
            
            # 检查异常标志
            anomaly_flags = market_analysis.get('anomaly_flags', [])
            if any('流动性' in flag for flag in anomaly_flags):
                risk_level = 'high'
                risk_score = 0.9
        
        except Exception as e:
            print(f"⚠️ 流动性风险评估失败: {e}")
        
        return {
            'level': risk_level,
            'score': risk_score,
            'factors': {
                'volume_profile': primary_analysis.get('volume_profile', 'normal'),
                'volatility': market_analysis.get('volatility', 0.0)
            }
        }
    
    def _check_max_drawdown(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """检查最大回撤"""
        try:
            # 从context获取性能指标
            performance_metrics = context.get('performance_metrics', {})
            max_drawdown = performance_metrics.get('max_drawdown', 0.0)
            max_drawdown_limit = TRADE_CONFIG.get('risk_management', {}).get('max_position_drawdown', 0.03)
            
            if max_drawdown > max_drawdown_limit:
                return {
                    'allowed': False,
                    'reason': f'最大回撤{max_drawdown:.2%}超过限制{max_drawdown_limit:.2%}',
                    'current_drawdown': max_drawdown,
                    'limit': max_drawdown_limit
                }
            
            # 检查每日PnL
            daily_pnl = performance_tracker.get('daily_pnl', 0.0)
            daily_threshold = TRADE_CONFIG.get('performance_tracking', {}).get('daily_pnl_threshold', -0.05)
            
            if daily_pnl < daily_threshold:
                return {
                    'allowed': False,
                    'reason': f'今日亏损{daily_pnl:.2%}超过阈值{daily_threshold:.2%}',
                    'daily_pnl': daily_pnl,
                    'threshold': daily_threshold
                }
            
            return {
                'allowed': True,
                'current_drawdown': max_drawdown,
                'limit': max_drawdown_limit
            }
            
        except Exception as e:
            print(f"⚠️ 回撤检查失败: {e}")
            return {'allowed': True, 'error': str(e)}
    
    def _calculate_position_size(
        self,
        strategy_signal: Dict[str, Any],
        market_analysis: Dict[str, Any],
        liquidity_risk: Dict[str, Any]
    ) -> float:
        """计算动态仓位大小"""
        try:
            # 基础仓位
            base_size = strategy_signal.get('size', TRADE_CONFIG.get('contract_size', 0.01))
            
            # 获取账户余额
            free_balance, total_balance = _fetch_account_balance_usdt()
            current_price = market_analysis.get('primary_analysis', {}).get('current_price', 50000)
            
            # 风险配置
            risk_config = TRADE_CONFIG.get('risk_management', {})
            base_risk_per_trade = risk_config.get('base_risk_per_trade', 0.02)
            
            # 根据胜率调整风险
            win_rate = performance_tracker.get('win_rate', 0.5)
            adaptive_risk = self._get_adaptive_risk(win_rate, risk_config)
            
            # 计算基于风险的仓位
            # 风险金额 = 账户余额 * 风险比例
            risk_amount = total_balance * adaptive_risk
            
            # 止损距离（从信号中获取或使用默认值）
            entry_price = current_price
            stop_loss_pct = strategy_signal.get('entry_conditions', {}).get('stop_loss_pct', 0.02)
            stop_loss_price = entry_price * (1 - stop_loss_pct) if strategy_signal.get('action') == 'BUY' else entry_price * (1 + stop_loss_pct)
            
            # 每张合约的风险 = |entry_price - stop_loss_price|
            risk_per_contract = abs(entry_price - stop_loss_price)
            
            if risk_per_contract > 0:
                # 基于风险的仓位 = 风险金额 / 每张合约风险
                risk_based_size = risk_amount / risk_per_contract
            else:
                risk_based_size = base_size
            
            # 流动性风险调整
            liquidity_score = liquidity_risk.get('score', 0.2)
            if liquidity_score > 0.7:
                risk_based_size *= 0.5  # 高流动性风险，减半仓位
            elif liquidity_score > 0.5:
                risk_based_size *= 0.7  # 中等流动性风险，减少30%
            
            # 波动率调整
            volatility = market_analysis.get('volatility', 0.01)
            if volatility > 0.03:
                risk_based_size *= 0.7
            elif volatility > 0.02:
                risk_based_size *= 0.85
            
            # 取较小值（保守策略）
            final_size = min(base_size, risk_based_size)
            
            # 确保不超过最小/最大限制
            min_size = TRADE_CONFIG.get('min_amount', 0.01)
            max_size = total_balance / current_price * 0.1  # 最多使用10%账户价值
            
            final_size = max(min_size, min(final_size, max_size))
            
            return round(final_size, 4)
            
        except Exception as e:
            print(f"⚠️ 仓位计算失败: {e}")
            return strategy_signal.get('size', TRADE_CONFIG.get('contract_size', 0.01))
    
    def _get_adaptive_risk(self, win_rate: float, risk_config: Dict[str, Any]) -> float:
        """根据胜率获取自适应风险比例"""
        if not risk_config.get('adaptive_risk_enabled', True):
            return risk_config.get('base_risk_per_trade', 0.02)
        
        risk_levels = risk_config.get('risk_levels', {})
        high_cfg = risk_levels.get('high_win_rate', {'threshold': 0.6, 'min_risk': 0.05, 'max_risk': 0.10})
        med_cfg = risk_levels.get('medium_win_rate', {'threshold': 0.4, 'min_risk': 0.03, 'max_risk': 0.05})
        low_cfg = risk_levels.get('low_win_rate', {'threshold': 0.0, 'min_risk': 0.01, 'max_risk': 0.02})
        
        if win_rate >= high_cfg.get('threshold', 0.6):
            return high_cfg.get('min_risk', 0.05)
        elif win_rate >= med_cfg.get('threshold', 0.4):
            return med_cfg.get('min_risk', 0.03)
        else:
            return low_cfg.get('min_risk', 0.01)
    
    def _calculate_stop_loss_take_profit(
        self,
        strategy_signal: Dict[str, Any],
        market_analysis: Dict[str, Any]
    ) -> tuple[float, float]:
        """计算止损止盈价格"""
        try:
            current_price = market_analysis.get('primary_analysis', {}).get('current_price', 50000)
            atr = market_analysis.get('primary_analysis', {}).get('technical_data', {}).get('atr', current_price * 0.01)
            action = strategy_signal.get('action', 'HOLD')
            
            # 从信号中获取条件
            exit_conditions = strategy_signal.get('exit_conditions', {})
            stop_loss_pct = exit_conditions.get('stop_loss_pct', 0.02)
            take_profit_pct = exit_conditions.get('take_profit_pct', 0.04)
            
            # 使用动态止盈计算
            dynamic_tp = DynamicTakeProfit()
            market_regime = market_analysis.get('market_regime', 'normal')
            
            if action == 'BUY':
                stop_loss = current_price * (1 - stop_loss_pct)
                take_profit = dynamic_tp.calculate_take_profit(
                    current_price, current_price, atr, market_regime, 0
                )
            elif action == 'SELL':
                stop_loss = current_price * (1 + stop_loss_pct)
                take_profit = dynamic_tp.calculate_take_profit(
                    current_price, current_price, atr, market_regime, 0
                )
            else:
                stop_loss = 0
                take_profit = 0
            
            return stop_loss, take_profit
            
        except Exception as e:
            print(f"⚠️ 止损止盈计算失败: {e}")
            return 0.0, 0.0
    
    def _calculate_leverage(
        self,
        market_analysis: Dict[str, Any],
        liquidity_risk: Dict[str, Any]
    ) -> int:
        """计算杠杆倍数"""
        try:
            risk_config = TRADE_CONFIG.get('risk_management', {})
            base_leverage = TRADE_CONFIG.get('leverage', 6)
            min_leverage = risk_config.get('min_leverage', 1)
            max_leverage = risk_config.get('max_leverage', 10)
            
            # 根据波动率调整
            volatility = market_analysis.get('volatility', 0.01)
            if volatility > 0.03:
                leverage = max(min_leverage, base_leverage - 2)
            elif volatility > 0.02:
                leverage = max(min_leverage, base_leverage - 1)
            else:
                leverage = base_leverage
            
            # 根据流动性风险调整
            liquidity_score = liquidity_risk.get('score', 0.2)
            if liquidity_score > 0.7:
                leverage = max(min_leverage, leverage - 2)
            elif liquidity_score > 0.5:
                leverage = max(min_leverage, leverage - 1)
            
            return max(min_leverage, min(leverage, max_leverage))
            
        except Exception as e:
            print(f"⚠️ 杠杆计算失败: {e}")
            return TRADE_CONFIG.get('leverage', 6)
    
    def _calculate_risk_score(
        self,
        market_analysis: Dict[str, Any],
        liquidity_risk: Dict[str, Any],
        position_size: float,
        stop_loss: float,
        take_profit: float
    ) -> float:
        """计算综合风险评分（0-1，越高风险越大）"""
        risk_score = 0.0
        
        # 波动率风险（0-0.3）
        volatility = market_analysis.get('volatility', 0.01)
        if volatility > 0.03:
            risk_score += 0.3
        elif volatility > 0.02:
            risk_score += 0.2
        else:
            risk_score += 0.1
        
        # 流动性风险（0-0.3）
        liquidity_score = liquidity_risk.get('score', 0.2)
        risk_score += liquidity_score * 0.3
        
        # 异常标志风险（0-0.2）
        anomaly_flags = market_analysis.get('anomaly_flags', [])
        risk_score += min(len(anomaly_flags) * 0.05, 0.2)
        
        # 仓位大小风险（0-0.1）
        # 仓位越大，风险越高（简化处理）
        if position_size > 0.1:
            risk_score += 0.1
        elif position_size > 0.05:
            risk_score += 0.05
        
        # 止损距离风险（0-0.1）
        if stop_loss > 0:
            current_price = market_analysis.get('primary_analysis', {}).get('current_price', 50000)
            stop_loss_pct = abs(stop_loss - current_price) / current_price
            if stop_loss_pct < 0.01:  # 止损太近
                risk_score += 0.1
            elif stop_loss_pct > 0.05:  # 止损太远
                risk_score += 0.05
        
        return min(1.0, risk_score)
