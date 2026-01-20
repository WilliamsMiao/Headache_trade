"""
Market Analyst Skill - 市场数据分析师
负责多时间框架技术分析、市场情绪分析、异常检测
"""

import sys
import os
from typing import Dict, Any, List
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_skills.base_skill import BaseSkill, SkillResult, SkillStatus
from ai_skills.config import AISkillsConfig
from trading_bots.indicators import (
    calculate_technical_indicators,
    get_market_trend,
    detect_market_regime,
    get_support_resistance_levels,
    calculate_volatility
)
from trading_bots.config import exchange, TRADE_CONFIG
from trading_bots.signals import get_sentiment_indicators
from strategies.market_analyzer import MarketAnalyzer


class MarketAnalystSkill(BaseSkill):
    """市场分析师技能"""
    
    def __init__(self):
        config = AISkillsConfig.get_skill_config('market_analyst')
        super().__init__(
            name='market_analyst',
            timeout=config['timeout'],
            enabled=config['enabled'],
            priority=config['priority']
        )
        self.market_analyzer = MarketAnalyzer()
        self.timeframes = AISkillsConfig.TIMEFRAMES if AISkillsConfig.MULTI_TIMEFRAME_ENABLED else [TRADE_CONFIG['timeframe']]
    
    def get_required_inputs(self) -> List[str]:
        """获取所需的输入字段"""
        return ['market_data']  # 至少需要基础市场数据
    
    def get_output_schema(self) -> Dict[str, Any]:
        """获取输出数据格式定义"""
        return {
            'trend_strength': {
                'type': 'float',
                'range': [0, 10],
                'description': '趋势强度评分'
            },
            'volatility': {
                'type': 'float',
                'description': '波动率（ATR百分比）'
            },
            'sentiment_score': {
                'type': 'float',
                'range': [-1, 1],
                'description': '市场情绪得分'
            },
            'anomaly_flags': {
                'type': 'list',
                'description': '异常标志列表'
            },
            'market_regime': {
                'type': 'string',
                'values': ['trending', 'ranging', 'volatile'],
                'description': '市场状态'
            },
            'confidence': {
                'type': 'float',
                'range': [0, 1],
                'description': '分析置信度'
            },
            'multi_timeframe_analysis': {
                'type': 'dict',
                'description': '多时间框架分析结果'
            }
        }
    
    def execute(
        self,
        context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> SkillResult:
        """执行市场分析"""
        try:
            market_data = input_data.get('market_data', {})
            
            # 1. 基础技术分析（主时间框架）
            primary_analysis = self._analyze_primary_timeframe(market_data)
            
            # 2. 多时间框架分析
            multi_tf_analysis = {}
            if AISkillsConfig.MULTI_TIMEFRAME_ENABLED:
                multi_tf_analysis = self._analyze_multi_timeframes(market_data)
            
            # 3. 市场情绪分析
            sentiment_score = self._analyze_sentiment()
            
            # 4. 异常检测
            anomaly_flags = self._detect_anomalies(market_data, primary_analysis)
            
            # 5. 综合市场状态判断
            market_regime = self._determine_market_regime(primary_analysis, multi_tf_analysis)
            
            # 6. 计算置信度
            confidence = self._calculate_confidence(primary_analysis, sentiment_score, anomaly_flags)
            
            # 7. 构建输出
            output = {
                'trend_strength': primary_analysis.get('trend_strength', 0.0),
                'volatility': primary_analysis.get('volatility', 0.0),
                'sentiment_score': sentiment_score,
                'anomaly_flags': anomaly_flags,
                'market_regime': market_regime,
                'confidence': confidence,
                'multi_timeframe_analysis': multi_tf_analysis,
                'primary_analysis': primary_analysis,
                'timestamp': pd.Timestamp.now().isoformat()
            }
            
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.SUCCESS,
                output=output,
                confidence=confidence
            )
            
        except Exception as e:
            return SkillResult(
                skill_name=self.name,
                status=SkillStatus.FAILED,
                error=f"市场分析失败: {str(e)}"
            )
    
    def _analyze_primary_timeframe(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析主时间框架"""
        try:
            # 获取K线数据
            if 'full_data' in market_data:
                df = market_data['full_data']
            elif 'kline_data' in market_data:
                # 转换为DataFrame
                kline_data = market_data['kline_data']
                df = pd.DataFrame(kline_data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = calculate_technical_indicators(df)
            else:
                # 从交易所获取
                ohlcv = exchange.fetch_ohlcv(
                    TRADE_CONFIG['symbol'],
                    TRADE_CONFIG['timeframe'],
                    limit=TRADE_CONFIG['data_points']
                )
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = calculate_technical_indicators(df)
            
            # 使用MarketAnalyzer分析
            if len(df) > 50:
                analysis = self.market_analyzer.analyze_market(df, len(df) - 1)
            else:
                analysis = self.market_analyzer._get_default_analysis()
            
            # 计算趋势强度（0-10）
            trend_info = get_market_trend(df)
            trend_strength = self._calculate_trend_strength_score(trend_info, df)
            
            # 计算波动率
            volatility = calculate_volatility(df)
            atr_pct = analysis.get('atr_pct', 0.0)
            
            # 获取支撑阻力位
            levels = get_support_resistance_levels(df)
            
            return {
                'trend_strength': trend_strength,
                'volatility': atr_pct,
                'volatility_annualized': volatility,
                'trend_direction': trend_info.get('overall', '震荡整理'),
                'trend_info': trend_info,
                'market_regime': analysis.get('market_regime', 'ranging'),
                'oscillation_strength': analysis.get('oscillation_strength', 0.5),
                'volume_profile': analysis.get('volume_profile', 'normal'),
                'support_resistance': levels,
                'current_price': float(df['close'].iloc[-1]),
                'rsi': float(df['rsi'].iloc[-1]) if 'rsi' in df.columns else 50.0,
                'bb_position': float(df['bb_position'].iloc[-1]) if 'bb_position' in df.columns else 0.5
            }
        except Exception as e:
            print(f"⚠️ 主时间框架分析失败: {e}")
            return {
                'trend_strength': 5.0,
                'volatility': 0.01,
                'trend_direction': '震荡整理',
                'market_regime': 'ranging',
                'error': str(e)
            }
    
    def _analyze_multi_timeframes(self, market_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """多时间框架分析"""
        results = {}
        
        for tf in self.timeframes:
            try:
                # 获取不同时间框架的数据
                ohlcv = exchange.fetch_ohlcv(
                    TRADE_CONFIG['symbol'],
                    tf,
                    limit=min(200, TRADE_CONFIG['data_points'])
                )
                
                if not ohlcv:
                    continue
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = calculate_technical_indicators(df)
                
                if len(df) < 20:
                    continue
                
                # 分析该时间框架
                trend_info = get_market_trend(df)
                trend_strength = self._calculate_trend_strength_score(trend_info, df)
                regime = detect_market_regime(df)
                
                results[tf] = {
                    'trend_strength': trend_strength,
                    'trend_direction': trend_info.get('overall', '震荡整理'),
                    'market_regime': regime,
                    'current_price': float(df['close'].iloc[-1]),
                    'rsi': float(df['rsi'].iloc[-1]) if 'rsi' in df.columns else 50.0
                }
            except Exception as e:
                print(f"⚠️ 时间框架 {tf} 分析失败: {e}")
                continue
        
        return results
    
    def _calculate_trend_strength_score(self, trend_info: Dict[str, Any], df: pd.DataFrame) -> float:
        """计算趋势强度评分（0-10）"""
        score = 0.0
        
        # 基础趋势方向（0-3分）
        overall = trend_info.get('overall', '震荡整理')
        if '强势上涨' in overall or '强势下跌' in overall:
            score += 3.0
        elif '上涨' in overall or '下跌' in overall:
            score += 1.5
        
        # 趋势强度（0-2分）
        trend_strength = trend_info.get('trend_strength', '弱')
        if trend_strength == '强':
            score += 2.0
        elif trend_strength == '中':
            score += 1.0
        
        # MACD信号（0-2分）
        if 'macd' in trend_info:
            macd = trend_info['macd']
            if (overall == '强势上涨' and macd == 'bullish') or \
               (overall == '强势下跌' and macd == 'bearish'):
                score += 2.0
            elif macd == 'bullish' or macd == 'bearish':
                score += 1.0
        
        # RSI位置（0-1.5分）
        rsi = trend_info.get('rsi_level', 50)
        if overall == '强势上涨' and 40 < rsi < 70:
            score += 1.5
        elif overall == '强势下跌' and 30 < rsi < 60:
            score += 1.5
        elif 30 < rsi < 70:
            score += 0.5
        
        # 布林带位置（0-1.5分）
        bb_position = trend_info.get('bb_position', 0.5)
        if overall == '强势上涨' and bb_position > 0.5:
            score += 1.5
        elif overall == '强势下跌' and bb_position < 0.5:
            score += 1.5
        
        return min(10.0, max(0.0, score))
    
    def _analyze_sentiment(self) -> float:
        """分析市场情绪"""
        if not AISkillsConfig.SENTIMENT_ANALYSIS_ENABLED:
            return 0.0
        
        try:
            sentiment_data = get_sentiment_indicators()
            if sentiment_data:
                # 将情绪数据转换为-1到1的得分
                net_sentiment = sentiment_data.get('net_sentiment', 0.0)
                # 归一化到-1到1
                sentiment_score = max(-1.0, min(1.0, net_sentiment))
                return sentiment_score
        except Exception as e:
            print(f"⚠️ 市场情绪分析失败: {e}")
        
        return 0.0  # 默认中性
    
    def _detect_anomalies(
        self,
        market_data: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> List[str]:
        """检测市场异常"""
        anomalies = []
        
        try:
            # 1. 价格突变检测
            if 'price_change' in market_data:
                price_change = abs(market_data['price_change'])
                if price_change > 5.0:  # 5%以上变化
                    anomalies.append(f'价格突变: {price_change:.2f}%')
            
            # 2. 波动率异常
            volatility = analysis.get('volatility', 0.0)
            if volatility > 0.03:  # 3%以上波动率
                anomalies.append(f'高波动率: {volatility:.2%}')
            elif volatility < 0.001:  # 0.1%以下波动率
                anomalies.append(f'极低波动率: {volatility:.2%}')
            
            # 3. 成交量异常
            if 'volume' in market_data:
                volume = market_data['volume']
                if 'volume_ratio' in analysis:
                    volume_ratio = analysis.get('volume_ratio', 1.0)
                    if volume_ratio > 3.0:
                        anomalies.append(f'异常高成交量: {volume_ratio:.2f}x')
                    elif volume_ratio < 0.3:
                        anomalies.append(f'异常低成交量: {volume_ratio:.2f}x')
            
            # 4. RSI极端值
            rsi = analysis.get('rsi', 50.0)
            if rsi > 80:
                anomalies.append(f'RSI极度超买: {rsi:.1f}')
            elif rsi < 20:
                anomalies.append(f'RSI极度超卖: {rsi:.1f}')
            
            # 5. 流动性检测（基于价格变化和成交量）
            if 'price_change' in market_data and 'volume' in market_data:
                price_change = abs(market_data['price_change'])
                if price_change > 2.0 and market_data['volume'] < 1000:  # 假设阈值
                    anomalies.append('疑似流动性枯竭')
        
        except Exception as e:
            print(f"⚠️ 异常检测失败: {e}")
        
        return anomalies
    
    def _determine_market_regime(
        self,
        primary_analysis: Dict[str, Any],
        multi_tf_analysis: Dict[str, Dict[str, Any]]
    ) -> str:
        """综合判断市场状态"""
        # 优先使用主时间框架的判断
        regime = primary_analysis.get('market_regime', 'ranging')
        
        # 如果有多时间框架分析，考虑一致性
        if multi_tf_analysis:
            regimes = [tf_data.get('market_regime', 'ranging') for tf_data in multi_tf_analysis.values()]
            # 如果大多数时间框架一致，使用该状态
            if regimes:
                from collections import Counter
                most_common = Counter(regimes).most_common(1)
                if most_common and most_common[0][1] >= len(regimes) * 0.6:
                    regime = most_common[0][0]
        
        return regime
    
    def _calculate_confidence(
        self,
        primary_analysis: Dict[str, Any],
        sentiment_score: float,
        anomaly_flags: List[str]
    ) -> float:
        """计算分析置信度（0-1）"""
        confidence = 0.7  # 基础置信度
        
        # 异常越多，置信度越低
        if anomaly_flags:
            confidence -= len(anomaly_flags) * 0.1
        
        # 趋势强度越高，置信度越高
        trend_strength = primary_analysis.get('trend_strength', 5.0)
        if trend_strength > 7:
            confidence += 0.15
        elif trend_strength > 5:
            confidence += 0.1
        
        # 有情绪数据时，置信度略增
        if abs(sentiment_score) > 0.1:
            confidence += 0.05
        
        return max(0.0, min(1.0, confidence))
