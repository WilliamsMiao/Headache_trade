"""
策略参数优化器
支持AI建议和网格搜索
"""

import json
import itertools
from typing import Dict, List, Optional, Type, Any, Tuple
import pandas as pd
import numpy as np
from .base_strategy import BaseStrategy
from .strategy_adapter import create_backtest_strategy
from scripts.backtest_engine import BacktestEngine


class StrategyOptimizer:
    """策略参数优化器"""
    
    def __init__(self, ai_client=None):
        """
        初始化优化器
        
        Args:
            ai_client: AI客户端（如DeepSeek），用于参数建议
        """
        self.ai_client = ai_client
    
    def optimize_with_ai(
        self,
        strategy_class: Type[BaseStrategy],
        backtest_results: Dict,
        current_params: Dict,
        market_analysis: Dict = None
    ) -> Dict[str, Any]:
        """
        基于回测结果使用AI建议参数调整
        
        Args:
            strategy_class: 策略类
            backtest_results: 回测结果字典
            current_params: 当前参数字典
            
        Returns:
            优化建议字典
        """
        if self.ai_client is None:
            return {
                'success': False,
                'error': 'AI客户端未配置',
                'suggestions': []
            }
        
        # 构建提示词
        strategy_name = strategy_class.__name__
        param_info = strategy_class().get_parameter_info()
        
        # 市场分析信息（如果提供）
        market_context = ""
        if market_analysis:
            market_context = f"""
当前市场状态:
- 波动率水平: {market_analysis.get('volatility_level', 'medium')}
- ATR百分比: {market_analysis.get('atr_pct', 0):.4f}
- 震荡强度: {market_analysis.get('oscillation_strength', 0):.2f} (0-1, 越高表示震荡越强)
- 趋势强度: {market_analysis.get('trend_strength', 0):.2f} (0-1, 越高表示趋势越强)
- 成交量特征: {market_analysis.get('volume_profile', 'normal')}
- 市场状态: {market_analysis.get('market_regime', 'ranging')} (ranging/trending/volatile)

请根据以上市场状态，提供针对性的参数优化建议。例如：
- 高波动市场：应调整风险控制参数（止损、仓位等）
- 强震荡市场：适合网格策略，可以增加网格数量
- 强趋势市场：应避免逆势操作，调整趋势过滤参数
"""
        
        prompt = f"""你是一个量化交易策略优化专家。请分析以下回测结果，并结合市场状态提出参数优化建议。

策略名称: {strategy_name}

当前参数:
{json.dumps(current_params, indent=2, ensure_ascii=False)}

回测结果:
- 总收益率: {backtest_results.get('total_return_pct', 0):.2f}%
- 胜率: {backtest_results.get('win_rate', 0):.2f}%
- 总交易次数: {backtest_results.get('total_trades', 0)}
- 盈利交易: {backtest_results.get('winning_trades', 0)}
- 亏损交易: {backtest_results.get('losing_trades', 0)}
{market_context}
可优化参数:
{json.dumps({k: v for k, v in param_info.items() if v.get('optimizable', False)}, indent=2, ensure_ascii=False)}

请提供3-5个具体的参数调整建议，每个建议包括：
1. 参数名称
2. 建议的新值
3. 调整原因（需结合市场状态说明）
4. 预期效果

请以JSON格式回复：
{{
    "suggestions": [
        {{
            "parameter": "参数名",
            "current_value": 当前值,
            "suggested_value": 建议值,
            "reason": "调整原因",
            "expected_effect": "预期效果"
        }}
    ],
    "overall_assessment": "整体评估",
    "confidence": 0.0-1.0
}}
"""
        
        try:
            # 调用AI
            response = self.ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的量化交易策略优化专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content if response.choices else "{}"
            
            # 解析JSON响应
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # 尝试提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = {"suggestions": [], "error": "无法解析AI响应"}
            
            return {
                'success': True,
                'suggestions': result.get('suggestions', []),
                'overall_assessment': result.get('overall_assessment', ''),
                'confidence': result.get('confidence', 0.5)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'suggestions': []
            }
    
    def grid_search(
        self,
        strategy_class: Type[BaseStrategy],
        param_ranges: Dict[str, List],
        df: pd.DataFrame,
        backtest_config: Dict = None,
        metric: str = 'sharpe_ratio',
        max_iterations: int = 100
    ) -> Dict[str, Any]:
        """
        网格搜索最优参数
        
        Args:
            strategy_class: 策略类
            param_ranges: 参数范围字典，如 {'rsi_long_min': [40, 45, 50], 'rsi_long_max': [70, 75, 80]}
            df: 历史K线数据
            backtest_config: 回测配置
            metric: 优化指标 ('sharpe_ratio', 'total_return', 'win_rate')
            max_iterations: 最大迭代次数（防止组合爆炸）
            
        Returns:
            最优参数和结果
        """
        if backtest_config is None:
            backtest_config = {
                'initial_balance': 100,
                'leverage': 6,
                'fee_rate': 0.001,
                'slippage': 0.0001,
                'verbose': False
            }
        
        # 生成参数组合
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        
        # 计算总组合数
        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)
        
        # 如果组合太多，随机采样
        if total_combinations > max_iterations:
            import random
            combinations = random.sample(
                list(itertools.product(*param_values)),
                max_iterations
            )
        else:
            combinations = list(itertools.product(*param_values))
        
        best_params = None
        best_score = float('-inf')
        best_results = None
        all_results = []
        
        print(f"开始网格搜索: {len(combinations)} 个参数组合")
        
        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))
            
            try:
                # 创建策略实例
                strategy_instance = strategy_class(**params)
                strategy_func = create_backtest_strategy(strategy_instance)
                
                # 运行回测（移除verbose参数）
                engine_config = {k: v for k, v in backtest_config.items() if k != 'verbose'}
                engine = BacktestEngine(**engine_config)
                results = engine.run(df, strategy_func, verbose=False)
                
                # 计算指标
                score = self._calculate_metric(results, metric)
                
                all_results.append({
                    'params': params,
                    'score': score,
                    'results': results
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_results = results
                
                if (i + 1) % 10 == 0:
                    print(f"进度: {i+1}/{len(combinations)}, 当前最佳分数: {best_score:.4f}")
                    
            except Exception as e:
                print(f"参数组合 {params} 执行失败: {e}")
                continue
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'best_results': best_results,
            'all_results': all_results,
            'total_combinations': len(combinations)
        }
    
    def _calculate_metric(self, results: Dict, metric: str) -> float:
        """计算优化指标"""
        if metric == 'sharpe_ratio':
            # 简化的夏普比率（需要收益率序列）
            total_return = results.get('total_return_pct', 0) / 100
            total_trades = results.get('total_trades', 1)
            if total_trades == 0:
                return 0.0
            # 假设每笔交易平均收益
            avg_return = total_return / total_trades if total_trades > 0 else 0
            # 简化的夏普比率（实际需要标准差）
            return avg_return * 100  # 简化版本
        
        elif metric == 'total_return':
            return results.get('total_return_pct', 0)
        
        elif metric == 'win_rate':
            return results.get('win_rate', 0)
        
        elif metric == 'profit_factor':
            # 盈利因子 = 总盈利 / 总亏损
            trades = results.get('trades', [])
            if not trades:
                return 0.0
            
            total_profit = sum(t.get('pnl_usdt', 0) for t in trades if t.get('pnl_usdt', 0) > 0)
            total_loss = abs(sum(t.get('pnl_usdt', 0) for t in trades if t.get('pnl_usdt', 0) < 0))
            
            if total_loss == 0:
                return float('inf') if total_profit > 0 else 0.0
            
            return total_profit / total_loss
        
        elif metric == 'max_drawdown':
            # 最大回撤（百分比）
            equity_curve = results.get('equity_curve', [])
            if not equity_curve:
                return 0.0
            
            equities = [point.get('equity', point.get('balance', 100)) for point in equity_curve]
            if not equities:
                return 0.0
            
            peak = equities[0]
            max_dd = 0.0
            
            for equity in equities:
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)
            
            return max_dd * 100  # 转换为百分比
        
        elif metric == 'calmar_ratio':
            # 卡玛比率 = 年化收益率 / 最大回撤
            total_return = results.get('total_return_pct', 0)
            max_dd = self._calculate_metric(results, 'max_drawdown')
            if max_dd == 0:
                return float('inf') if total_return > 0 else 0.0
            return total_return / max_dd
        
        else:
            return results.get('total_return_pct', 0)
    
    def _calculate_multi_objective_score(
        self,
        results: Dict,
        objectives: Dict[str, float]
    ) -> float:
        """
        计算多目标综合分数
        
        Args:
            results: 回测结果
            objectives: 目标权重字典，如 {'total_return': 0.4, 'sharpe_ratio': 0.3, 'max_drawdown': -0.3}
                       (负权重表示越小越好，如最大回撤)
        
        Returns:
            综合分数
        """
        score = 0.0
        
        for metric, weight in objectives.items():
            metric_value = self._calculate_metric(results, metric)
            
            # 归一化（简化处理）
            if metric == 'total_return':
                normalized = metric_value / 100.0  # 假设100%为满分
            elif metric == 'win_rate':
                normalized = metric_value / 100.0  # 0-100%
            elif metric == 'sharpe_ratio':
                normalized = min(metric_value / 3.0, 1.0)  # 假设3.0为满分
            elif metric == 'profit_factor':
                normalized = min(metric_value / 5.0, 1.0)  # 假设5.0为满分
            elif metric == 'max_drawdown':
                # 最大回撤：越小越好，所以用负权重
                normalized = 1.0 - min(metric_value / 50.0, 1.0)  # 假设50%为最差
            elif metric == 'calmar_ratio':
                normalized = min(metric_value / 3.0, 1.0)  # 假设3.0为满分
            else:
                normalized = metric_value / 100.0  # 默认归一化
            
            score += normalized * weight
        
        return score
    
    def multi_objective_optimize(
        self,
        strategy_class: Type[BaseStrategy],
        param_ranges: Dict[str, List],
        df: pd.DataFrame,
        objectives: Dict[str, float],
        backtest_config: Dict = None,
        max_iterations: int = 100
    ) -> Dict[str, Any]:
        """
        多目标优化
        
        Args:
            strategy_class: 策略类
            param_ranges: 参数范围字典
            df: 历史K线数据
            objectives: 目标权重字典，如 {'total_return': 0.4, 'sharpe_ratio': 0.3, 'max_drawdown': -0.3}
            backtest_config: 回测配置
            max_iterations: 最大迭代次数
            
        Returns:
            优化结果
        """
        if backtest_config is None:
            backtest_config = {
                'initial_balance': 100,
                'leverage': 6,
                'fee_rate': 0.001,
                'slippage': 0.0001,
                'verbose': False
            }
        
        # 生成参数组合
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        
        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)
        
        # 如果组合太多，随机采样
        if total_combinations > max_iterations:
            import random
            combinations = random.sample(
                list(itertools.product(*param_values)),
                max_iterations
            )
        else:
            combinations = list(itertools.product(*param_values))
        
        best_params = None
        best_score = float('-inf')
        best_results = None
        all_results = []
        
        print(f"开始多目标优化: {len(combinations)} 个参数组合")
        print(f"优化目标: {objectives}")
        
        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))
            
            try:
                # 创建策略实例
                strategy_instance = strategy_class(**params)
                strategy_func = create_backtest_strategy(strategy_instance)
                
                # 运行回测
                engine_config = {k: v for k, v in backtest_config.items() if k != 'verbose'}
                engine = BacktestEngine(**engine_config)
                results = engine.run(df, strategy_func, verbose=False)
                
                # 计算多目标分数
                score = self._calculate_multi_objective_score(results, objectives)
                
                all_results.append({
                    'params': params,
                    'score': score,
                    'results': results,
                    'metrics': {
                        metric: self._calculate_metric(results, metric)
                        for metric in objectives.keys()
                    }
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_results = results
                
                if (i + 1) % 10 == 0:
                    print(f"进度: {i+1}/{len(combinations)}, 当前最佳分数: {best_score:.4f}")
                    
            except Exception as e:
                print(f"参数组合 {params} 执行失败: {e}")
                continue
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'best_results': best_results,
            'all_results': all_results,
            'total_combinations': len(combinations),
            'objectives': objectives
        }
    
    def hybrid_optimize(
        self,
        strategy_class: Type[BaseStrategy],
        df: pd.DataFrame,
        initial_params: Dict = None,
        backtest_config: Dict = None,
        ai_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        混合优化：AI建议 + 局部网格搜索
        
        Args:
            strategy_class: 策略类
            df: 历史K线数据
            initial_params: 初始参数（如果None，使用默认参数）
            backtest_config: 回测配置
            ai_enabled: 是否启用AI建议
            
        Returns:
            优化结果
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
                'verbose': False
            }
        
        # 步骤1: 使用初始参数运行回测
        print("步骤1: 运行初始回测...")
        strategy_instance = strategy_class(**initial_params)
        strategy_func = create_backtest_strategy(strategy_instance)
        # 移除verbose参数（BacktestEngine不接受）
        engine_config = {k: v for k, v in backtest_config.items() if k != 'verbose'}
        engine = BacktestEngine(**engine_config)
        initial_results = engine.run(df, strategy_func, verbose=False)
        
        print(f"初始结果: 收益率={initial_results.get('total_return_pct', 0):.2f}%, "
              f"胜率={initial_results.get('win_rate', 0):.2f}%")
        
        # 步骤2: AI建议（如果启用）
        ai_suggestions = []
        if ai_enabled and self.ai_client:
            print("步骤2: 获取AI优化建议...")
            ai_result = self.optimize_with_ai(
                strategy_class, initial_results, initial_params
            )
            
            if ai_result.get('success'):
                ai_suggestions = ai_result.get('suggestions', [])
                print(f"AI建议: {len(ai_suggestions)} 个参数调整建议")
        
        # 步骤3: 基于AI建议构建局部搜索范围
        param_ranges = {}
        param_info = strategy_class().get_parameter_info()
        
        for suggestion in ai_suggestions:
            param_name = suggestion.get('parameter')
            suggested_value = suggestion.get('suggested_value')
            current_value = suggestion.get('current_value', initial_params.get(param_name))
            
            if param_name in param_info and param_info[param_name].get('optimizable'):
                param_def = param_info[param_name]
                param_type = param_def.get('type', type(suggested_value))
                
                # 在建议值附近创建搜索范围
                if param_type == int or param_type == float:
                    # 生成建议值±20%的范围
                    if isinstance(suggested_value, (int, float)) and isinstance(current_value, (int, float)):
                        range_size = abs(suggested_value - current_value) * 0.2
                        if range_size == 0:
                            range_size = abs(current_value) * 0.1 if current_value != 0 else 1
                        
                        if param_type == int:
                            values = [
                                int(max(param_def.get('min', suggested_value - 10), 
                                       suggested_value - range_size)),
                                int(suggested_value),
                                int(min(param_def.get('max', suggested_value + 10),
                                       suggested_value + range_size))
                            ]
                            values = [v for v in values if param_def.get('min', 0) <= v <= param_def.get('max', 1000)]
                        else:
                            values = [
                                max(param_def.get('min', suggested_value * 0.5),
                                   suggested_value - range_size),
                                suggested_value,
                                min(param_def.get('max', suggested_value * 2),
                                   suggested_value + range_size)
                            ]
                        
                        if len(set(values)) > 1:  # 确保有多个不同的值
                            param_ranges[param_name] = sorted(set(values))
        
        # 步骤4: 局部网格搜索
        if param_ranges:
            print(f"步骤3: 局部网格搜索 ({len(param_ranges)} 个参数)...")
            grid_result = self.grid_search(
                strategy_class, param_ranges, df, backtest_config,
                metric='total_return', max_iterations=50
            )
            
            best_params = grid_result.get('best_params', initial_params)
            best_results = grid_result.get('best_results', initial_results)
        else:
            print("步骤3: 跳过网格搜索（无有效参数范围）")
            best_params = initial_params
            best_results = initial_results
        
        return {
            'initial_params': initial_params,
            'initial_results': initial_results,
            'ai_suggestions': ai_suggestions,
            'best_params': best_params,
            'best_results': best_results,
            'improvement': {
                'return': best_results.get('total_return_pct', 0) - initial_results.get('total_return_pct', 0),
                'win_rate': best_results.get('win_rate', 0) - initial_results.get('win_rate', 0)
            }
        }
