"""
策略调度器
根据市场环境动态选择和切换策略
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

from market_analyzer import MarketAnalyzer, MarketRegime, MarketState
from strategies.base_strategy import BaseStrategy, TradingSignal, SignalType
from strategies.grid_strategy import GridTradingStrategy
from strategies.trend_following import TrendFollowingStrategy
from ai_strategy_advisor import AIStrategyAdvisor


class StrategyScheduler:
    """策略调度器 - 结合AI和技术分析"""
    
    def __init__(self, exchange, symbol: str = "BTC/USDT:USDT", 
                 ai_api_key: Optional[str] = None, use_ai: bool = True):
        self.exchange = exchange
        self.symbol = symbol
        
        # 市场分析器
        self.market_analyzer = MarketAnalyzer()
        
        # AI策略顾问
        self.use_ai = use_ai and ai_api_key is not None
        if self.use_ai:
            self.ai_advisor = AIStrategyAdvisor(ai_api_key)
            print("✅ AI策略顾问已启用")
        else:
            self.ai_advisor = None
            print("⚠️ AI策略顾问未启用，仅使用技术分析")
        
        # 策略池
        self.strategy_pool = {
            'grid': GridTradingStrategy(),
            'trend': TrendFollowingStrategy(),
            # 可以添加更多策略...
        }
        
        # 当前活跃策略
        self.active_strategy: Optional[BaseStrategy] = None
        self.active_strategy_name: str = ""
        
        # 切换历史
        self.switch_history = []
        
        # 配置
        self.min_switch_interval = 6  # 最小切换间隔（小时）
        self.last_switch_time = None
        
        # AI决策权重
        self.ai_weight = 0.6  # AI建议权重60%
        self.technical_weight = 0.4  # 技术分析权重40%
        
    def select_strategy(self, price_data: pd.DataFrame) -> BaseStrategy:
        """
        选择最适合当前市场的策略（AI + 技术分析）
        
        Args:
            price_data: OHLCV数据
        
        Returns:
            BaseStrategy: 选中的策略
        """
        # 分析市场环境
        market_state = self.market_analyzer.analyze(price_data)
        
        print(f"\n{'='*60}")
        print(f"📊 市场技术分析:")
        print(f"   状态: {market_state.regime.value}")
        print(f"   趋势强度: {market_state.trend_strength:.1f}")
        print(f"   ADX: {market_state.adx:.1f}")
        print(f"   波动率: {market_state.volatility:.2f}%")
        print(f"   置信度: {market_state.confidence:.1f}%")
        print(f"   技术建议: {market_state.recommendation}")
        
        # 技术分析推荐的策略
        technical_strategy = self._map_regime_to_strategy(market_state)
        
        # 如果启用AI，获取AI建议
        if self.use_ai and self.ai_advisor:
            print(f"\n🤖 AI策略分析中...")
            
            # 获取策略表现数据
            strategy_performance = {}
            for name, strategy in self.strategy_pool.items():
                strategy_performance[name] = strategy.get_performance_summary()
            
            # 获取AI建议
            ai_advice = self.ai_advisor.get_strategy_advice(
                market_state=market_state,
                price_data=price_data,
                current_strategy=self.active_strategy_name or None,
                strategy_performance=strategy_performance
            )
            
            print(f"\n💡 AI建议:")
            print(f"   推荐策略: {ai_advice['recommended_strategy']}")
            print(f"   AI置信度: {ai_advice['confidence']:.1f}%")
            print(f"   理由: {ai_advice['reasoning'][:100]}...")
            if ai_advice.get('risk_warning'):
                print(f"   ⚠️  风险提示: {ai_advice['risk_warning'][:80]}...")
            
            # 综合决策：AI + 技术分析
            selected_strategy = self._make_hybrid_decision(
                technical_strategy=technical_strategy,
                technical_confidence=market_state.confidence,
                ai_strategy=ai_advice['recommended_strategy'],
                ai_confidence=ai_advice['confidence'],
                ai_should_switch=ai_advice.get('should_switch', False)
            )
            
            print(f"\n🎯 综合决策: {selected_strategy}")
        else:
            # 仅使用技术分析
            selected_strategy = technical_strategy
            print(f"\n🎯 技术决策: {selected_strategy}")
        
        print(f"{'='*60}\n")
        
        # 检查是否需要切换策略
        if self._should_switch_strategy(selected_strategy, market_state):
            self._switch_strategy(selected_strategy, market_state)
        
        return self.active_strategy
    
    def _map_regime_to_strategy(self, market_state: MarketState) -> str:
        """将市场状态映射到策略"""
        regime = market_state.regime
        
        strategy_mapping = {
            MarketRegime.STRONG_TREND: 'trend',       # 强趋势 → 趋势跟随
            MarketRegime.WEAK_TREND: 'trend',         # 弱趋势 → 趋势跟随
            MarketRegime.RANGE_BOUND: 'grid',         # 震荡 → 网格交易
            MarketRegime.HIGH_VOLATILITY: 'grid',     # 高波动 → 网格交易（谨慎）
            MarketRegime.BREAKOUT_PENDING: 'trend',   # 突破前夜 → 准备趋势
            MarketRegime.UNKNOWN: None                # 未知 → 观望
        }
        
        return strategy_mapping.get(regime)
    
    def _make_hybrid_decision(self,
                             technical_strategy: str,
                             technical_confidence: float,
                             ai_strategy: str,
                             ai_confidence: float,
                             ai_should_switch: bool) -> str:
        """
        综合AI和技术分析做决策
        
        Args:
            technical_strategy: 技术分析推荐策略
            technical_confidence: 技术分析置信度
            ai_strategy: AI推荐策略
            ai_confidence: AI置信度
            ai_should_switch: AI是否建议切换
        
        Returns:
            str: 最终选择的策略
        """
        print(f"\n🔄 混合决策过程:")
        print(f"   技术分析: {technical_strategy} (置信度 {technical_confidence:.1f}%)")
        print(f"   AI建议: {ai_strategy} (置信度 {ai_confidence:.1f}%)")
        
        # 如果两者一致，直接采用
        if technical_strategy == ai_strategy:
            print(f"   ✅ 一致推荐: {ai_strategy}")
            return ai_strategy
        
        # 如果不一致，根据置信度加权
        technical_score = technical_confidence * self.technical_weight
        ai_score = ai_confidence * self.ai_weight
        
        print(f"   技术得分: {technical_score:.1f} ({self.technical_weight*100}%权重)")
        print(f"   AI得分: {ai_score:.1f} ({self.ai_weight*100}%权重)")
        
        # 特殊情况：AI强烈建议切换
        if ai_should_switch and ai_confidence > 75:
            print(f"   🔥 AI强烈建议切换到 {ai_strategy}")
            return ai_strategy
        
        # 特殊情况：技术分析极度明确
        if technical_confidence > 80 and technical_strategy:
            print(f"   📊 技术信号极度明确，采用 {technical_strategy}")
            return technical_strategy
        
        # 常规：选择得分高的
        if ai_score > technical_score:
            print(f"   🤖 采用AI建议: {ai_strategy}")
            return ai_strategy
        else:
            print(f"   📊 采用技术分析: {technical_strategy}")
            return technical_strategy
    
    def _should_switch_strategy(self, target_strategy: str,
                                market_state: MarketState) -> bool:
        """判断是否应该切换策略"""
        # 无目标策略（观望）
        if target_strategy is None:
            if self.active_strategy is not None:
                print("⚠️ 市场不明确，暂停交易")
                return True
            return False
        
        # 首次运行
        if self.active_strategy is None:
            return True
        
        # 策略相同，不切换
        if self.active_strategy_name == target_strategy:
            return False
        
        # 检查切换间隔
        if self.last_switch_time:
            time_since_switch = (datetime.now() - self.last_switch_time).total_seconds() / 3600
            if time_since_switch < self.min_switch_interval:
                print(f"⏱️ 距离上次切换仅 {time_since_switch:.1f} 小时，等待冷却")
                return False
        
        # 检查市场状态置信度
        if market_state.confidence < 60:
            print(f"⚠️ 市场状态置信度不足 ({market_state.confidence:.1f}%)，保持当前策略")
            return False
        
        # 检查当前策略表现
        if self._is_current_strategy_performing_well():
            print("✅ 当前策略表现良好，暂不切换")
            return False
        
        return True
    
    def _is_current_strategy_performing_well(self) -> bool:
        """检查当前策略表现"""
        if not self.active_strategy:
            return False
        
        perf = self.active_strategy.get_performance_summary()
        
        # 交易次数太少，无法判断
        if perf['total_trades'] < 5:
            return True
        
        # 胜率良好
        if perf['win_rate'] >= 50:
            return True
        
        # 总盈利为正
        if perf['total_pnl'] > 0:
            return True
        
        return False
    
    def _switch_strategy(self, target_strategy: str, market_state: MarketState):
        """执行策略切换"""
        # 停用当前策略
        if self.active_strategy:
            old_strategy = self.active_strategy_name
            self.active_strategy.deactivate()
            print(f"⏸️ 停用策略: {old_strategy}")
        else:
            old_strategy = "None"
        
        # 激活新策略
        if target_strategy:
            self.active_strategy = self.strategy_pool[target_strategy]
            self.active_strategy_name = target_strategy
            self.active_strategy.activate()
            print(f"✅ 激活策略: {target_strategy}")
        else:
            self.active_strategy = None
            self.active_strategy_name = ""
            print(f"⏸️ 暂停交易，观望中")
        
        # 记录切换
        self.last_switch_time = datetime.now()
        self.switch_history.append({
            'timestamp': self.last_switch_time,
            'from_strategy': old_strategy,
            'to_strategy': target_strategy or "None",
            'market_regime': market_state.regime.value,
            'confidence': market_state.confidence
        })
        
        print(f"🔄 策略切换完成: {old_strategy} → {target_strategy or 'None'}")
    
    def generate_trading_signal(self, price_data: pd.DataFrame,
                                current_position: Optional[Dict] = None) -> Optional[TradingSignal]:
        """
        生成交易信号（结合AI确认）
        
        Args:
            price_data: OHLCV数据
            current_position: 当前持仓
        
        Returns:
            TradingSignal or None
        """
        # 选择策略
        strategy = self.select_strategy(price_data)
        
        # 无活跃策略
        if strategy is None:
            return None
        
        # 生成信号
        signal = strategy.generate_signal(price_data, current_position)
        
        if signal is None:
            return None
        
        # 记录原始信号
        print(f"\n📡 策略信号: {strategy.name}")
        print(f"   类型: {signal.signal_type.value}")
        print(f"   技术置信度: {signal.confidence:.1f}%")
        if signal.stop_loss:
            print(f"   止损: {signal.stop_loss:.2f}")
        if signal.take_profit:
            print(f"   止盈: {signal.take_profit:.2f}")
        
        # 如果启用AI，进行信号确认
        if self.use_ai and self.ai_advisor and signal.signal_type.value != 'HOLD':
            print(f"\n🤖 AI信号确认中...")
            
            # 准备市场背景数据
            market_state = self.market_analyzer.analyze(price_data)
            market_context = {
                'regime': market_state.regime.value,
                'adx': market_state.adx,
                'volatility': market_state.volatility,
                'rsi': self._calculate_rsi(price_data)
            }
            
            # 准备信号数据
            signal_data = {
                'entry_price': signal.entry_price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'confidence': signal.confidence
            }
            
            # 获取AI确认
            confirmation = self.ai_advisor.get_signal_confirmation(
                signal_type=signal.signal_type.value,
                signal_data=signal_data,
                market_context=market_context
            )
            
            print(f"   AI确认: {'✅ 通过' if confirmation['confirmed'] else '❌ 拒绝'}")
            print(f"   置信度调整: {confirmation['confidence_adjustment']:+.1f}%")
            print(f"   理由: {confirmation['reasoning'][:80]}...")
            
            # 如果AI拒绝信号
            if not confirmation['confirmed']:
                print(f"   ⚠️ AI建议暂不交易")
                return None
            
            # 调整置信度
            signal.confidence = max(0, min(100, 
                signal.confidence + confirmation['confidence_adjustment']))
            
            # 应用AI的建议调整
            suggestions = confirmation.get('suggestions', {})
            if 'stop_loss_adjustment' in suggestions and suggestions['stop_loss_adjustment']:
                old_sl = signal.stop_loss
                signal.stop_loss = suggestions['stop_loss_adjustment']
                print(f"   🔧 止损调整: {old_sl:.2f} → {signal.stop_loss:.2f}")
            
            if 'take_profit_adjustment' in suggestions and suggestions['take_profit_adjustment']:
                old_tp = signal.take_profit
                signal.take_profit = suggestions['take_profit_adjustment']
                print(f"   🔧 止盈调整: {old_tp:.2f} → {signal.take_profit:.2f}")
            
            print(f"\n   ✅ 最终置信度: {signal.confidence:.1f}%")
        
        return signal
    
    def _calculate_rsi(self, price_data: pd.DataFrame, period: int = 14) -> float:
        """计算RSI"""
        try:
            close = price_data['close']
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except:
            return 50.0  # 默认中性值
    
    def should_exit_position(self, price_data: pd.DataFrame,
                            entry_price: float, position_side: str) -> bool:
        """判断是否应该退出持仓"""
        if not self.active_strategy:
            return False
        
        return self.active_strategy.should_exit(price_data, entry_price, position_side)
    
    def calculate_position_size(self, account_balance: float,
                               signal: TradingSignal) -> float:
        """计算仓位大小"""
        if not self.active_strategy:
            return 0.0
        
        return self.active_strategy.calculate_position_size(account_balance, signal)
    
    def update_strategy_performance(self, trade_result: Dict):
        """更新策略表现"""
        if self.active_strategy:
            self.active_strategy.update_performance(trade_result)
    
    def get_scheduler_status(self) -> Dict:
        """获取调度器状态"""
        status = {
            'active_strategy': self.active_strategy_name or "None",
            'total_strategies': len(self.strategy_pool),
            'last_switch_time': self.last_switch_time.isoformat() if self.last_switch_time else None,
            'switch_count': len(self.switch_history),
            'market_history': self.market_analyzer.get_regime_history(24),
            'ai_enabled': self.use_ai
        }
        
        # 各策略表现
        strategy_performance = {}
        for name, strategy in self.strategy_pool.items():
            strategy_performance[name] = strategy.get_performance_summary()
        
        status['strategy_performance'] = strategy_performance
        
        # AI相关状态
        if self.use_ai and self.ai_advisor:
            status['ai_advice_history'] = self.ai_advisor.get_advice_history(5)
            status['ai_consistency'] = self.ai_advisor.get_strategy_consistency()
        
        return status
    
    def get_switch_history(self, limit: int = 10) -> List[Dict]:
        """获取策略切换历史"""
        return self.switch_history[-limit:]
    
    def force_strategy(self, strategy_name: str):
        """强制使用指定策略"""
        if strategy_name not in self.strategy_pool:
            raise ValueError(f"策略不存在: {strategy_name}")
        
        if self.active_strategy:
            self.active_strategy.deactivate()
        
        self.active_strategy = self.strategy_pool[strategy_name]
        self.active_strategy_name = strategy_name
        self.active_strategy.activate()
        
        print(f"🔧 强制切换策略: {strategy_name}")


# 快捷函数
def create_scheduler(exchange, symbol: str = "BTC/USDT:USDT",
                    ai_api_key: Optional[str] = None,
                    use_ai: bool = True) -> StrategyScheduler:
    """创建策略调度器"""
    return StrategyScheduler(exchange, symbol, ai_api_key, use_ai)
