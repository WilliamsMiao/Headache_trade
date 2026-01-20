"""
自适应参数优化器
根据市场条件优化参数，支持市场感知的参数优化
"""

import pandas as pd
from typing import Dict, List, Optional, Type, Any
from .base_strategy import BaseStrategy
from .market_analyzer import MarketAnalyzer
from .optimizer import StrategyOptimizer


class AdaptiveOptimizer:
    """自适应参数优化器，根据市场条件优化参数"""
    
    def __init__(self, market_analyzer: MarketAnalyzer = None, base_optimizer: StrategyOptimizer = None):
        """
        初始化自适应优化器
        
        Args:
            market_analyzer: 市场分析器实例
            base_optimizer: 基础优化器实例
        """
        self.market_analyzer = market_analyzer or MarketAnalyzer()
        self.base_optimizer = base_optimizer or StrategyOptimizer()
    
    def optimize_with_market_awareness(
        self,
        strategy_class: Type[BaseStrategy],
        df: pd.DataFrame,
        initial_params: Dict = None,
        backtest_config: Dict = None
    ) -> Dict[str, Any]:
        """
        市场感知的参数优化
        
        步骤：
        1. 分析历史数据的市场状态分布
        2. 为不同市场状态生成参数建议
        3. 使用基础优化器进一步优化
        4. 返回市场状态到参数的映射
        
        Args:
            strategy_class: 策略类
            df: 历史K线数据
            initial_params: 初始参数
            backtest_config: 回测配置
            
        Returns:
            优化结果字典
        """
        if initial_params is None:
            strategy_instance = strategy_class()
            initial_params = strategy_instance.get_parameters()
        
        if backtest_config is None:
            backtest_config = {
                'initial_balance': 100,
                'leverage': 6,
                'fee_rate': 0.001,
                'slippage': 0.0001,
                'funding_rate': 0.0001,
                'verbose': False
            }
        
        # 步骤1: 分析市场状态分布
        print("步骤1: 分析市场状态分布...")
        market_states = self.market_analyzer.analyze_market_states(df)
        
        state_summary = {
            state: len(indices) for state, indices in market_states.items()
        }
        print(f"   市场状态分布: {state_summary}")
        
        # 步骤2: 为每种市场状态优化参数
        print("\n步骤2: 为不同市场状态优化参数...")
        optimized_params_by_state = {}
        optimization_results = {}
        
        for state, indices in market_states.items():
            if len(indices) < 50:  # 数据太少跳过
                print(f"   跳过 {state} 状态（数据量不足: {len(indices)}）")
                continue
            
            print(f"\n   优化 {state} 状态（{len(indices)} 根K线）...")
            state_df = df.iloc[indices].reset_index(drop=True)
            
            try:
                # 使用基础优化器优化该状态下的参数
                result = self.base_optimizer.hybrid_optimize(
                    strategy_class=strategy_class,
                    df=state_df,
                    initial_params=initial_params.copy(),
                    backtest_config=backtest_config,
                    ai_enabled=False  # 先不使用AI，加快速度
                )
                
                optimized_params_by_state[state] = result['best_params']
                optimization_results[state] = {
                    'best_params': result['best_params'],
                    'best_results': result['best_results'],
                    'improvement': result.get('improvement', {})
                }
                
                if result['best_results']:
                    ret = result['best_results'].get('total_return_pct', 0)
                    win_rate = result['best_results'].get('win_rate', 0)
                    trades = result['best_results'].get('total_trades', 0)
                    print(f"     最佳参数收益率: {ret:.2f}%, 胜率: {win_rate:.2f}%, 交易次数: {trades}")
                
            except Exception as e:
                print(f"     {state} 状态优化失败: {e}")
                continue
        
        # 步骤3: 生成推荐
        print("\n步骤3: 生成参数推荐...")
        recommendation = self._generate_recommendation(
            optimized_params_by_state,
            market_states,
            initial_params
        )
        
        return {
            'market_states': market_states,
            'state_summary': state_summary,
            'optimized_params_by_state': optimized_params_by_state,
            'optimization_results': optimization_results,
            'recommendation': recommendation,
            'initial_params': initial_params
        }
    
    def _generate_recommendation(
        self,
        optimized_params_by_state: Dict[str, Dict],
        market_states: Dict[str, List[int]],
        initial_params: Dict
    ) -> Dict[str, Any]:
        """
        生成参数推荐
        
        Args:
            optimized_params_by_state: 各市场状态的最优参数
            market_states: 市场状态分布
            initial_params: 初始参数
            
        Returns:
            推荐字典
        """
        if not optimized_params_by_state:
            return {
                'recommended_params': initial_params,
                'reason': '无足够数据生成推荐，使用初始参数'
            }
        
        # 计算各状态的权重（基于数据量）
        total_samples = sum(len(indices) for indices in market_states.values())
        state_weights = {
            state: len(indices) / total_samples
            for state, indices in market_states.items()
            if state in optimized_params_by_state
        }
        
        # 加权平均参数（对于数值型参数）
        recommended_params = {}
        param_types = {}
        
        # 先确定参数类型
        for state, params in optimized_params_by_state.items():
            for param_name, param_value in params.items():
                if param_name not in param_types:
                    param_types[param_name] = type(param_value)
        
        # 计算加权平均
        for param_name, param_type in param_types.items():
            if param_type in (int, float):
                # 数值型：加权平均
                weighted_sum = 0.0
                total_weight = 0.0
                
                for state, params in optimized_params_by_state.items():
                    if param_name in params and state in state_weights:
                        weight = state_weights[state]
                        weighted_sum += params[param_name] * weight
                        total_weight += weight
                
                if total_weight > 0:
                    if param_type == int:
                        recommended_params[param_name] = int(round(weighted_sum / total_weight))
                    else:
                        recommended_params[param_name] = weighted_sum / total_weight
                else:
                    recommended_params[param_name] = initial_params.get(param_name)
            else:
                # 非数值型：使用最常见的值
                values = [
                    params.get(param_name)
                    for params in optimized_params_by_state.values()
                    if param_name in params
                ]
                if values:
                    # 使用第一个值（或可以统计最频繁的值）
                    recommended_params[param_name] = values[0]
                else:
                    recommended_params[param_name] = initial_params.get(param_name)
        
        # 生成推荐理由
        reasons = []
        for state, weight in sorted(state_weights.items(), key=lambda x: x[1], reverse=True):
            if state in optimized_params_by_state:
                reasons.append(f"{state}状态（权重{weight:.1%}）")
        
        return {
            'recommended_params': recommended_params,
            'state_weights': state_weights,
            'reason': f"基于市场状态分布推荐，主要考虑: {', '.join(reasons[:3])}",
            'param_changes': self._compare_params(initial_params, recommended_params)
        }
    
    def _compare_params(self, initial: Dict, recommended: Dict) -> Dict[str, Dict]:
        """比较初始参数和推荐参数"""
        changes = {}
        for param_name in set(initial.keys()) | set(recommended.keys()):
            initial_val = initial.get(param_name)
            recommended_val = recommended.get(param_name)
            
            if initial_val != recommended_val:
                if isinstance(initial_val, (int, float)) and isinstance(recommended_val, (int, float)):
                    change_pct = ((recommended_val - initial_val) / initial_val * 100) if initial_val != 0 else 0
                    changes[param_name] = {
                        'initial': initial_val,
                        'recommended': recommended_val,
                        'change_pct': change_pct
                    }
                else:
                    changes[param_name] = {
                        'initial': initial_val,
                        'recommended': recommended_val
                    }
        return changes
    
    def get_params_for_current_market(
        self,
        df: pd.DataFrame,
        current_index: int,
        optimized_params_by_state: Dict[str, Dict],
        default_params: Dict
    ) -> Dict:
        """
        根据当前市场状态获取最优参数
        
        Args:
            df: 历史数据
            current_index: 当前K线索引
            optimized_params_by_state: 各状态的最优参数
            default_params: 默认参数（回退）
            
        Returns:
            当前市场状态下的最优参数
        """
        try:
            market_analysis = self.market_analyzer.analyze_market(df, current_index)
            current_regime = market_analysis.get('market_regime', 'ranging')
            
            if current_regime in optimized_params_by_state:
                return optimized_params_by_state[current_regime]
            else:
                return default_params
        except Exception:
            return default_params
