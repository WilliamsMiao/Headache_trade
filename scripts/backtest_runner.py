"""
回测执行脚本
获取历史数据、运行回测、生成报告
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import ccxt
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.backtest_engine import BacktestEngine
from scripts.backtest_analyzer import BacktestAnalyzer

# 加载环境变量
load_dotenv()

# 数据文件路径
DATA_DIR = '/root/crypto_deepseek/data/backtest/data'
REPORTS_DIR = '/root/crypto_deepseek/data/backtest/reports'
CONFIGS_DIR = '/root/crypto_deepseek/data/backtest/configs'


def fetch_historical_data(symbol: str = 'BTC/USDT:USDT', timeframe: str = '15m', 
                         days: int = 30, save_path: str = None) -> pd.DataFrame:
    """
    获取历史K线数据
    
    Args:
        symbol: 交易对
        timeframe: 时间周期
        days: 天数
        save_path: 保存路径
        
    Returns:
        DataFrame with OHLCV data
    """
    print(f"\n{'='*60}")
    print(f"📥 开始获取历史数据")
    print(f"{'='*60}")
    print(f"交易对: {symbol}")
    print(f"时间周期: {timeframe}")
    print(f"数据天数: {days}天")
    
    try:
        # 初始化交易所
        exchange = ccxt.okx({
            'options': {'defaultType': 'swap'},
            'apiKey': os.getenv('OKX_API_KEY'),
            'secret': os.getenv('OKX_SECRET'),
            'password': os.getenv('OKX_PASSWORD'),
        })
        
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        since = int(start_time.timestamp() * 1000)
        
        print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("正在获取数据...")
        
        # 获取K线数据（批量获取）
        all_ohlcv = []
        current_since = since
        limit = 300  # 每次获取300根K线
        
        while True:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=limit)
            if not ohlcv:
                break
            
            all_ohlcv.extend(ohlcv)
            
            # 更新since到最后一根K线的时间
            last_timestamp = ohlcv[-1][0]
            if last_timestamp >= int(end_time.timestamp() * 1000):
                break
            current_since = last_timestamp + 1
            
            print(f"已获取 {len(all_ohlcv)} 根K线...", end='\r')
        
        print(f"\n✅ 成功获取 {len(all_ohlcv)} 根K线数据")
        
        # 转换为DataFrame
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # 保存数据
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            df.to_json(save_path, orient='records', date_format='iso', indent=2)
            print(f"✅ 数据已保存至: {save_path}")
        
        return df
        
    except Exception as e:
        print(f"❌ 获取数据失败: {str(e)}")
        raise


def load_historical_data(filepath: str) -> pd.DataFrame:
    """加载历史数据"""
    print(f"📂 加载历史数据: {filepath}")
    df = pd.read_json(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"✅ 成功加载 {len(df)} 根K线数据")
    return df


def create_strategy_function():
    """
    创建策略函数（简化版本，用于回测）
    这个函数模拟实盘策略的核心逻辑
    """
    # 导入必要的技术指标计算函数
    def calculate_indicators(df, index):
        """计算技术指标"""
        # 确保有足够的数据
        if index < 96:
            return None
        
        # 获取当前数据窗口
        window_df = df.iloc[max(0, index-96):index+1].copy()
        
        # 计算移动平均线
        window_df['sma_20'] = window_df['close'].rolling(20).mean()
        window_df['sma_50'] = window_df['close'].rolling(50).mean()
        
        # 计算ATR
        window_df['tr'] = window_df[['high', 'low', 'close']].apply(
            lambda x: max(x['high'] - x['low'], 
                         abs(x['high'] - x['close']), 
                         abs(x['low'] - x['close'])), 
            axis=1
        )
        window_df['atr'] = window_df['tr'].rolling(14).mean()
        
        # 计算RSI
        delta = window_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        window_df['rsi'] = 100 - (100 / (1 + rs))
        
        # 计算MACD
        ema12 = window_df['close'].ewm(span=12).mean()
        ema26 = window_df['close'].ewm(span=26).mean()
        window_df['macd'] = ema12 - ema26
        window_df['signal'] = window_df['macd'].ewm(span=9).mean()
        
        # 计算布林带
        window_df['bb_middle'] = window_df['close'].rolling(20).mean()
        bb_std = window_df['close'].rolling(20).std()
        window_df['bb_upper'] = window_df['bb_middle'] + (bb_std * 2)
        window_df['bb_lower'] = window_df['bb_middle'] - (bb_std * 2)
        
        # 获取最新值
        current = window_df.iloc[-1]
        prev = window_df.iloc[-2] if len(window_df) > 1 else current
        
        # 🔧 优化v4：添加成交量指标
        window_df['volume_sma'] = window_df['volume'].rolling(20).mean()
        
        # 处理NaN值
        volume_sma_value = current.get('volume_sma', current['volume'])
        if pd.isna(volume_sma_value):
            volume_sma_value = current['volume']
        
        return {
            'close': current['close'],
            'sma_20': current['sma_20'],
            'sma_50': current['sma_50'],
            'atr': current['atr'],
            'rsi': current['rsi'],
            'macd': current['macd'],
            'signal': current['signal'],
            'bb_upper': current['bb_upper'],
            'bb_middle': current['bb_middle'],
            'bb_lower': current['bb_lower'],
            'bb_position': (current['close'] - current['bb_lower']) / (current['bb_upper'] - current['bb_lower']) if (current['bb_upper'] - current['bb_lower']) > 0 else 0.5,
            'volume': current['volume'],
            'volume_sma': volume_sma_value,
            'prev_close': prev['close']
        }
    
    def calculate_backtest_position(signal_data, price_data, current_balance, 
                                    current_position, performance_stats):
        """
        回测版智能仓位计算（移植自生产环境）
        
        核心逻辑：
        1. 基于止损距离和3%最大亏损反推仓位
        2. 动态杠杆（根据胜率1-10倍）
        3. 趋势强度乘数（1.5x/1.2x/1.0x/0.5x）
        4. 资金利用率控制（50-60%）
        
        Args:
            signal_data: 信号数据（包含止损止盈和趋势分数）
            price_data: 当前价格
            current_balance: 当前账户余额
            current_position: 当前持仓信息
            performance_stats: 性能统计（用于计算胜率）
        
        Returns:
            dict: {'contract_size': float, 'optimal_leverage': int, 'trend_multiplier': float}
        """
        # 1. 计算止损距离
        stop_loss = signal_data.get('stop_loss', 0)
        current_price = price_data
        if stop_loss > 0:
            stop_loss_distance_pct = abs(stop_loss - current_price) / current_price
        else:
            stop_loss_distance_pct = 0.01  # 默认1%
        
        # 2. 风险反推：3%最大亏损
        max_acceptable_loss = current_balance * 0.03
        max_safe_trade_amount = max_acceptable_loss / stop_loss_distance_pct
        
        # 3. 转换为合约张数
        contract_size = 0.01  # BTC合约大小
        contract_value_per_unit = current_price * contract_size
        max_safe_contract_size = max_safe_trade_amount / contract_value_per_unit
        
        # 4. 动态杠杆（根据胜率）
        win_rate = performance_stats.get('win_rate', 0)
        if win_rate >= 0.5:  # 胜率>=50%
            dynamic_leverage = min(8 + int((win_rate - 0.5) * 10), 10)
        elif win_rate >= 0.4:  # 40-50%
            dynamic_leverage = 6 + int((win_rate - 0.4) * 10)
        else:  # <40%
            dynamic_leverage = max(3, int(win_rate * 10)) if win_rate > 0 else 3
        
        # 5. 趋势强度乘数
        trend_score = signal_data.get('trend_score', 5)
        if trend_score >= 8:
            trend_multiplier = 1.5  # 强趋势
        elif trend_score >= 6:
            trend_multiplier = 1.2  # 中等趋势
        elif trend_score >= 4:
            trend_multiplier = 1.0  # 正常
        else:
            trend_multiplier = 0.5  # 弱势
        
        # 6. 应用趋势乘数
        optimal_contract_size = max_safe_contract_size * trend_multiplier
        
        # 7. 资金利用率控制（50-60%）
        max_utilization = 0.60
        current_margin = (optimal_contract_size * contract_value_per_unit) / dynamic_leverage
        current_utilization = current_margin / current_balance if current_balance > 0 else 0
        
        if current_utilization > max_utilization:
            max_margin = current_balance * max_utilization
            optimal_contract_size = (max_margin * dynamic_leverage) / contract_value_per_unit
        
        # 8. 确保最小仓位
        optimal_contract_size = max(optimal_contract_size, 0.01)
        optimal_contract_size = round(optimal_contract_size, 2)
        
        return {
            'contract_size': optimal_contract_size,
            'optimal_leverage': dynamic_leverage,
            'trend_multiplier': trend_multiplier,
            'utilization': current_utilization
        }
    
    def strategy(index, df, position, current_balance, performance_stats):
        """
        回测策略函数
        
        Args:
            index: 当前K线索引
            df: 完整的历史数据
            position: 当前持仓（如果有）
            current_balance: 当前账户余额
            performance_stats: 性能统计（用于动态调整）
            
        Returns:
            交易信号字典或None
        """
        # 如果已有持仓，不产生新信号
        if position is not None:
            return None
        
        # 计算指标
        indicators = calculate_indicators(df, index)
        if indicators is None:
            return None
        
        current_price = indicators['close']
        atr = indicators['atr']
        rsi = indicators['rsi']
        macd = indicators['macd']
        signal_line = indicators['signal']
        sma_20 = indicators['sma_20']
        sma_50 = indicators['sma_50']
        bb_position = indicators['bb_position']
        volume = indicators.get('volume', 0)
        volume_sma = indicators.get('volume_sma', volume)
        prev_close = indicators.get('prev_close', current_price)
        
        # 🔧 优化v4：成交量和回调分析
        volume_ratio = volume / volume_sma if volume_sma > 0 else 1.0
        price_change_pct = (current_price - prev_close) / prev_close if prev_close > 0 else 0
        
        # 判断是否在回调（更精确的买点/卖点）
        is_pullback_for_long = (
            price_change_pct < -0.003 and  # 当前下跌>0.3%
            current_price > sma_20 and  # 但仍在均线上方
            rsi < 60  # RSI未超买
        )
        
        is_pullback_for_short = (
            price_change_pct > 0.003 and  # 当前上涨>0.3%
            current_price < sma_20 and  # 但仍在均线下方
            rsi > 40  # RSI未超卖
        )
        
        # 🔧 优化v3.1：市场环境过滤 - 检查ATR相对波动性（放宽条件）
        atr_pct = atr / current_price if current_price > 0 else 0
        
        # 只排除极端情况
        if atr_pct < 0.005:  # ATR<0.5%，极低波动
            return None  # 市场几乎不动，不交易
        
        if atr_pct > 0.030:  # ATR>3.0%，极高波动
            return None  # 市场过于混乱，不交易
        
        # 简化的趋势判断（更宽松的条件）
        trend_score = 0
        primary_trend = None
        
        # 均线趋势（强趋势判断）
        sma_diff_pct = abs((sma_20 - sma_50) / sma_50)
        if current_price > sma_20 > sma_50 and sma_diff_pct > 0.005:
            trend_score += 4
            primary_trend = "up"
        elif current_price < sma_20 < sma_50 and sma_diff_pct > 0.005:
            trend_score += 4
            primary_trend = "down"
        
        # MACD趋势确认
        if macd > signal_line:
            trend_score += 2
            if primary_trend is None:
                primary_trend = "up"
        elif macd < signal_line:
            trend_score += 2
            if primary_trend is None:
                primary_trend = "down"
        
        # 价格动量
        price_momentum_pct = abs((current_price - sma_20) / sma_20)
        if price_momentum_pct > 0.008:  # 价格偏离均线超过0.8%
            trend_score += 2
        
        # 🔧 优化v4：成交量确认（放量增加趋势分数）
        if volume_ratio > 1.3:  # 成交量放大30%
            trend_score += 1
        elif volume_ratio > 1.5:  # 成交量放大50%
            trend_score += 2
        
        # 🔧 优化v3.1：市场环境识别 - 更灵活的判断逻辑
        # 计算价格偏离均线的程度
        deviation_from_sma20 = abs((current_price - sma_20) / sma_20) if sma_20 > 0 else 0
        deviation_from_sma50 = abs((current_price - sma_50) / sma_50) if sma_50 > 0 else 0
        
        # 计算均线间距（判断趋势强度）
        sma_gap = abs((sma_20 - sma_50) / sma_50) if sma_50 > 0 else 0
        
        # 市场环境判断（放宽条件）
        # 明确的趋势市场
        is_strong_trending = (
            trend_score >= 8 or  # 非常强的趋势
            (trend_score >= 6 and sma_gap > 0.008)  # 中等趋势但均线分离明显
        )
        
        # 中等趋势市场（也可以交易，但更保守）
        is_moderate_trending = (
            trend_score >= 6 and 
            primary_trend is not None
        )
        
        # 震荡市场（均线粘合，无明确趋势）
        is_ranging_market = (
            trend_score < 6 and
            sma_gap < 0.010  # 均线间距<1%
        )
        
        # 🔧 优化v4：动态止损倍数（根据市场波动性调整）
        if atr_pct > 0.020:  # 高波动(>2%)
            sl_multiplier = 2.5
            tp_multiplier_strong = 3.0
            tp_multiplier_moderate = 2.5
        elif atr_pct > 0.015:  # 中高波动(1.5%-2%)
            sl_multiplier = 2.0
            tp_multiplier_strong = 2.5
            tp_multiplier_moderate = 2.0
        else:  # 正常波动(<1.5%)
            sl_multiplier = 1.8
            tp_multiplier_strong = 2.3
            tp_multiplier_moderate = 1.8
        
        # 震荡市场使用更紧的止损
        sl_multiplier_range = max(1.2, sl_multiplier * 0.65)
        
        # 生成交易信号
        signal = None
        
        # ==================== 策略1：强趋势市场（激进） ====================
        if is_strong_trending and primary_trend is not None:
            # 布林带位置过滤：避开中部
            if 0.35 <= bb_position <= 0.65:
                return None
            
            # 🔧 优化v4+v5：优先在回调时入场（更好的买卖点）+ 动态仓位
            if primary_trend == "up":
                # 做多：优先等待回调或成交量放大
                if is_pullback_for_long or volume_ratio > 1.3:
                    # 计算止损止盈
                    stop_loss_price = current_price - (atr * sl_multiplier)
                    take_profit_price = current_price + (atr * tp_multiplier_strong)
                    
                    # 计算动态仓位
                    position_result = calculate_backtest_position(
                        signal_data={
                            'stop_loss': stop_loss_price,
                            'take_profit': take_profit_price,
                            'trend_score': trend_score
                        },
                        price_data=current_price,
                        current_balance=current_balance,
                        current_position=position,
                        performance_stats=performance_stats
                    )
                    
                    signal = {
                        'action': 'BUY',
                        'size': position_result['contract_size'],
                        'leverage': position_result['optimal_leverage'],
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price,
                        'trend_multiplier': position_result['trend_multiplier']
                    }
            elif primary_trend == "down":
                # 做空：优先等待回调或成交量放大
                if is_pullback_for_short or volume_ratio > 1.3:
                    # 计算止损止盈
                    stop_loss_price = current_price + (atr * sl_multiplier)
                    take_profit_price = current_price - (atr * tp_multiplier_strong)
                    
                    # 计算动态仓位
                    position_result = calculate_backtest_position(
                        signal_data={
                            'stop_loss': stop_loss_price,
                            'take_profit': take_profit_price,
                            'trend_score': trend_score
                        },
                        price_data=current_price,
                        current_balance=current_balance,
                        current_position=position,
                        performance_stats=performance_stats
                    )
                    
                    signal = {
                        'action': 'SELL',
                        'size': position_result['contract_size'],
                        'leverage': position_result['optimal_leverage'],
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price,
                        'trend_multiplier': position_result['trend_multiplier']
                    }
        
        # ==================== 策略2：中等趋势市场（保守） ====================
        elif is_moderate_trending and not is_strong_trending and primary_trend is not None:
            # 更严格的过滤
            if 0.3 <= bb_position <= 0.7:
                return None
            
            # 🔧 优化v4+v5：中等趋势需要更严格的确认 + 动态仓位
            # RSI确认 + (回调或成交量放大)
            if primary_trend == "up" and rsi > 50:
                if is_pullback_for_long or volume_ratio > 1.4:
                    # 计算止损止盈
                    stop_loss_price = current_price - (atr * sl_multiplier)
                    take_profit_price = current_price + (atr * tp_multiplier_moderate)
                    
                    # 计算动态仓位
                    position_result = calculate_backtest_position(
                        signal_data={
                            'stop_loss': stop_loss_price,
                            'take_profit': take_profit_price,
                            'trend_score': trend_score
                        },
                        price_data=current_price,
                        current_balance=current_balance,
                        current_position=position,
                        performance_stats=performance_stats
                    )
                    
                    signal = {
                        'action': 'BUY',
                        'size': position_result['contract_size'],
                        'leverage': position_result['optimal_leverage'],
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price,
                        'trend_multiplier': position_result['trend_multiplier']
                    }
            elif primary_trend == "down" and rsi < 50:
                if is_pullback_for_short or volume_ratio > 1.4:
                    # 计算止损止盈
                    stop_loss_price = current_price + (atr * sl_multiplier)
                    take_profit_price = current_price - (atr * tp_multiplier_moderate)
                    
                    # 计算动态仓位
                    position_result = calculate_backtest_position(
                        signal_data={
                            'stop_loss': stop_loss_price,
                            'take_profit': take_profit_price,
                            'trend_score': trend_score
                        },
                        price_data=current_price,
                        current_balance=current_balance,
                        current_position=position,
                        performance_stats=performance_stats
                    )
                    
                    signal = {
                        'action': 'SELL',
                        'size': position_result['contract_size'],
                        'leverage': position_result['optimal_leverage'],
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price,
                        'trend_multiplier': position_result['trend_multiplier']
                    }
        
        # ==================== 策略3：震荡市场（均值回归） ====================
        elif is_ranging_market:
            bb_upper = indicators['bb_upper']
            bb_middle = indicators['bb_middle']
            bb_lower = indicators['bb_lower']
            
            # 做多：价格超卖，预期反弹
            if bb_position < 0.25 and rsi < 40:
                # 计算止损止盈
                stop_loss_price = current_price - (atr * sl_multiplier_range)
                take_profit_price = bb_middle
                
                # 计算动态仓位（震荡市用较低trend_score）
                position_result = calculate_backtest_position(
                    signal_data={
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price,
                        'trend_score': trend_score  # 通常<6，使用0.5倍乘数
                    },
                    price_data=current_price,
                    current_balance=current_balance,
                    current_position=position,
                    performance_stats=performance_stats
                )
                
                signal = {
                    'action': 'BUY',
                    'size': position_result['contract_size'],
                    'leverage': position_result['optimal_leverage'],
                    'stop_loss': stop_loss_price,
                    'take_profit': take_profit_price,
                    'trend_multiplier': position_result['trend_multiplier']
                }
            
            # 做空：价格超买，预期回落
            elif bb_position > 0.75 and rsi > 60:
                # 计算止损止盈
                stop_loss_price = current_price + (atr * sl_multiplier_range)
                take_profit_price = bb_middle
                
                # 计算动态仓位（震荡市用较低trend_score）
                position_result = calculate_backtest_position(
                    signal_data={
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price,
                        'trend_score': trend_score  # 通常<6，使用0.5倍乘数
                    },
                    price_data=current_price,
                    current_balance=current_balance,
                    current_position=position,
                    performance_stats=performance_stats
                )
                
                signal = {
                    'action': 'SELL',
                    'size': position_result['contract_size'],
                    'leverage': position_result['optimal_leverage'],
                    'stop_loss': stop_loss_price,
                    'take_profit': take_profit_price,
                    'trend_multiplier': position_result['trend_multiplier']
                }
        
        return signal
    
    return strategy


def run_backtest(df: pd.DataFrame, config: Dict = None) -> Dict:
    """
    运行回测
    
    Args:
        df: 历史K线数据
        config: 回测配置
        
    Returns:
        回测结果
    """
    if config is None:
        config = {
            'initial_balance': 100,
            'leverage': 6,
            'fee_rate': 0.001,
            'slippage': 0.0001,
            'funding_rate': 0.0001  # 默认0.01%每8小时
        }
    
    # 创建回测引擎
    engine = BacktestEngine(
        initial_balance=config['initial_balance'],
        leverage=config.get('leverage', 6),
        fee_rate=config.get('fee_rate', 0.001),
        slippage=config.get('slippage', 0.0001),
        dynamic_leverage=config.get('dynamic_leverage', False),
        funding_rate=config.get('funding_rate', 0.0001)  # 资金费率
    )
    
    # 创建策略函数
    strategy_func = create_strategy_function()
    
    # 运行回测
    results = engine.run(df, strategy_func, verbose=True)
    
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='回测执行工具')
    parser.add_argument('--fetch-data', action='store_true', help='获取历史数据')
    parser.add_argument('--days', type=int, default=30, help='数据天数（默认30天）')
    parser.add_argument('--config', type=str, help='配置文件名（如baseline）')
    parser.add_argument('--data-file', type=str, help='指定数据文件路径')
    
    args = parser.parse_args()
    
    # 数据文件路径
    data_file = args.data_file or f"{DATA_DIR}/historical_15m_{args.days}d.json"
    
    # 1. 获取或加载历史数据
    if args.fetch_data:
        df = fetch_historical_data(
            symbol='BTC/USDT:USDT',
            timeframe='15m',
            days=args.days,
            save_path=data_file
        )
    else:
        if not os.path.exists(data_file):
            print(f"❌ 数据文件不存在: {data_file}")
            print("💡 请先运行: python scripts/backtest_runner.py --fetch-data --days 30")
            return
        df = load_historical_data(data_file)
    
    # 2. 加载配置
    config = {
        'initial_balance': 100,
        'leverage': 6,
        'fee_rate': 0.001,
        'slippage': 0.0001
    }
    
    if args.config:
        config_file = f"{CONFIGS_DIR}/{args.config}.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                config.update(user_config)
            print(f"✅ 已加载配置: {config_file}")
    
    # 3. 运行回测
    results = run_backtest(df, config)
    
    # 4. 分析结果
    analyzer = BacktestAnalyzer(results)
    
    # 5. 生成报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    config_name = args.config or 'default'
    report_file = f"{REPORTS_DIR}/backtest_report_{config_name}_{timestamp}.md"
    
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_text = analyzer.generate_report(filepath=report_file)
    
    # 打印报告
    print("\n" + report_text)
    
    # 保存结果数据
    results_file = f"{REPORTS_DIR}/backtest_results_{config_name}_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        # 转换datetime为字符串
        results_copy = results.copy()
        for trade in results_copy['trades']:
            if 'entry_time' in trade:
                trade['entry_time'] = str(trade['entry_time'])
            if 'exit_time' in trade:
                trade['exit_time'] = str(trade['exit_time'])
        for point in results_copy['equity_curve']:
            if 'timestamp' in point:
                point['timestamp'] = str(point['timestamp'])
        json.dump(results_copy, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 结果数据已保存至: {results_file}")
    
    # 创建最新报告的软链接
    latest_report = f"{REPORTS_DIR}/backtest_report_latest.md"
    if os.path.exists(latest_report):
        os.remove(latest_report)
    os.symlink(os.path.basename(report_file), latest_report)
    print(f"✅ 最新报告链接: {latest_report}")


if __name__ == '__main__':
    main()
