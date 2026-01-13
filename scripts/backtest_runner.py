"""
回测执行脚本
获取历史数据、运行回测、生成报告
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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
    # 辅助：加载简易经济日历（若不存在则返回空）
    def load_economic_calendar(filepath: str = '/root/crypto_deepseek/data/economic_calendar.json') -> List[Dict]:
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    economic_events = load_economic_calendar()

    def check_event_risk(ts: pd.Timestamp, events: List[Dict], buffer_minutes: int = 30) -> bool:
        """检查当前时间附近是否有高风险事件"""
        if not events:
            return False
        for event in events:
            try:
                evt_time = pd.to_datetime(event.get('time'))
                importance = str(event.get('impact', '')).lower()
                if pd.isna(evt_time):
                    continue
                if importance and importance not in ['high', 'medium', 'low']:
                    importance = 'medium'
                if abs((ts - evt_time).total_seconds()) <= buffer_minutes * 60:
                    return True
            except Exception:
                continue
        return False

    # 导入必要的技术指标计算函数
    def calculate_indicators(df, index):
        """计算技术指标（扩展版）"""
        # 确保有足够的数据
        if index < 200:
            return None

        # 获取当前数据窗口（约50小时）
        window_df = df.iloc[max(0, index-200):index+1].copy()

        # 移动平均线
        window_df['ema_9'] = window_df['close'].ewm(span=9).mean()
        window_df['ema_21'] = window_df['close'].ewm(span=21).mean()
        window_df['ema_50'] = window_df['close'].ewm(span=50).mean()
        window_df['ema_200'] = window_df['close'].ewm(span=200).mean()
        window_df['sma_20'] = window_df['close'].rolling(20).mean()
        window_df['sma_50'] = window_df['close'].rolling(50).mean()

        # ATR
        window_df['tr'] = window_df[['high', 'low', 'close']].apply(
            lambda x: max(x['high'] - x['low'], 
                         abs(x['high'] - x['close']), 
                         abs(x['low'] - x['close'])), 
            axis=1
        )
        window_df['atr'] = window_df['tr'].rolling(14).mean()

        # RSI
        delta = window_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        window_df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = window_df['close'].ewm(span=12).mean()
        ema26 = window_df['close'].ewm(span=26).mean()
        window_df['macd'] = ema12 - ema26
        window_df['signal'] = window_df['macd'].ewm(span=9).mean()
        window_df['macd_hist'] = window_df['macd'] - window_df['signal']

        # 布林带
        window_df['bb_middle'] = window_df['close'].rolling(20).mean()
        bb_std = window_df['close'].rolling(20).std()
        window_df['bb_upper'] = window_df['bb_middle'] + (bb_std * 2)
        window_df['bb_lower'] = window_df['bb_middle'] - (bb_std * 2)

        # ADX（简化实现）
        high = window_df['high']
        low = window_df['low']
        up_move = high.diff()
        down_move = (-low.diff())
        plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
        minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move
        tr = window_df['tr']
        atr_smooth = tr.ewm(alpha=1/14, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_smooth)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, pd.NA)).fillna(0) * 100
        window_df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()

        # OBV
        obv = [0]
        for i in range(1, len(window_df)):
            if window_df['close'].iloc[i] > window_df['close'].iloc[i-1]:
                obv.append(obv[-1] + window_df['volume'].iloc[i])
            elif window_df['close'].iloc[i] < window_df['close'].iloc[i-1]:
                obv.append(obv[-1] - window_df['volume'].iloc[i])
            else:
                obv.append(obv[-1])
        window_df['obv'] = obv
        window_df['obv_sma'] = window_df['obv'].rolling(20).mean()

        # 市场宽度/多周期代理：用更长周期均线模拟 1H/4H 方向
        window_df['htf_1h'] = window_df['close'].rolling(16).mean()  # ~4小时
        window_df['htf_4h'] = window_df['close'].rolling(64).mean()  # ~16小时

        # 获取最新值
        current = window_df.iloc[-1]
        prev = window_df.iloc[-2] if len(window_df) > 1 else current

        # 成交量均线
        window_df['volume_sma'] = window_df['volume'].rolling(20).mean()
        volume_sma_value = current.get('volume_sma', current['volume'])
        if pd.isna(volume_sma_value):
            volume_sma_value = current['volume']

        return {
            'window': window_df,
            'current': current,
            'prev': prev,
            'close': current['close'],
            'sma_20': current['sma_20'],
            'sma_50': current['sma_50'],
            'ema_9': current['ema_9'],
            'ema_21': current['ema_21'],
            'ema_50': current['ema_50'],
            'ema_200': current['ema_200'],
            'atr': current['atr'],
            'rsi': current['rsi'],
            'macd': current['macd'],
            'signal': current['signal'],
            'macd_hist': current['macd_hist'],
            'adx': current['adx'],
            'bb_upper': current['bb_upper'],
            'bb_middle': current['bb_middle'],
            'bb_lower': current['bb_lower'],
            'bb_position': (current['close'] - current['bb_lower']) / (current['bb_upper'] - current['bb_lower']) if (current['bb_upper'] - current['bb_lower']) > 0 else 0.5,
            'volume': current['volume'],
            'volume_sma': volume_sma_value,
            'prev_close': prev['close'],
            'obv': current['obv'],
            'obv_sma': current['obv_sma'],
            'htf_1h': current['htf_1h'],
            'htf_4h': current['htf_4h']
        }

    def calculate_trend_score_v3(indicators: Dict) -> Dict:
        """六维趋势评分"""
        score = 0
        direction = None
        # 均线一致性
        if indicators['ema_9'] > indicators['ema_21'] > indicators['ema_50'] > indicators['ema_200']:
            score += 20
            direction = 'up'
        elif indicators['ema_9'] < indicators['ema_21'] < indicators['ema_50'] < indicators['ema_200']:
            score += 20
            direction = 'down'

        # MACD 动能
        if indicators['macd_hist'] > 0 and indicators['macd_hist'] > 0:
            score += 15
            direction = direction or 'up'
        elif indicators['macd_hist'] < 0:
            score += 15
            direction = direction or 'down'

        # ADX
        adx = indicators.get('adx', 0)
        if adx > 30:
            score += 15
        elif adx > 25:
            score += 10
        elif adx > 20:
            score += 5

        # 结构 HH/HL 或 LL/LH
        window_df = indicators['window']
        recent_high = window_df['high'].rolling(20).max().iloc[-2]
        recent_low = window_df['low'].rolling(20).min().iloc[-2]
        if indicators['close'] > recent_high and direction == 'up':
            score += 15
        if indicators['close'] < recent_low and direction == 'down':
            score += 15

        # OBV
        if indicators['obv'] > indicators['obv_sma']:
            score += 10

        # 多周期宽度（代理）
        htf_up = indicators['htf_1h'] > indicators['htf_4h']
        htf_down = indicators['htf_1h'] < indicators['htf_4h']
        mtf_aligned = False
        if direction == 'up' and htf_up:
            score += 10
            mtf_aligned = True
        if direction == 'down' and htf_down:
            score += 10
            mtf_aligned = True

        return {
            'score': score,
            'direction': direction,
            'adx': adx,
            'mtf_aligned': mtf_aligned
        }

    def get_market_context(indicators: Dict) -> Dict:
        """识别关键价位（简易枢轴点 + 心理关口）"""
        window_df = indicators['window']
        current_price = indicators['close']
        # 取前一日（约96根15m）高低收
        prior = window_df.iloc[-97:-1] if len(window_df) > 97 else window_df.iloc[:-1]
        if len(prior) == 0:
            return {'pivot': None, 'support': [], 'resistance': [], 'near_level': False, 'distance_pct': None}
        high = prior['high'].max()
        low = prior['low'].min()
        close = prior['close'].iloc[-1]
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)
        levels = [pivot, r1, s1, r2, s2]
        # 心理关口（以1000为间隔简化）
        psych_level = round(current_price / 1000) * 1000
        levels.append(psych_level)
        nearest = min(levels, key=lambda x: abs(current_price - x))
        distance_pct = abs(current_price - nearest) / current_price
        return {
            'pivot': pivot,
            'support': [s1, s2],
            'resistance': [r1, r2],
            'near_level': distance_pct <= 0.002,  # 0.2%
            'distance_pct': distance_pct,
            'nearest_level': nearest
        }

    def grade_signal(trend_score: int, adx: float, mtf_aligned: bool) -> Tuple[str, float]:
        """信号分级 -> (Grade, position_multiplier)"""
        if mtf_aligned and adx > 30 and trend_score >= 80:
            return "A", 1.0
        if mtf_aligned and adx > 25 and trend_score >= 65:
            return "B", 0.7
        return "C", 0.0

    signal_log: List[Dict] = []
    
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
        回测策略函数（V5.5 指挥官版）
        
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

        indicators = calculate_indicators(df, index)
        if indicators is None:
            return None

        current_price = indicators['close']
        atr = indicators['atr']
        rsi = indicators['rsi']
        volume = indicators.get('volume', 0)
        volume_sma = indicators.get('volume_sma', volume)
        bb_position = indicators['bb_position']
        atr_pct = atr / current_price if current_price > 0 else 0

        # 事件风险过滤
        if check_event_risk(indicators['current'].name, economic_events):
            signal_log.append({
                'ts': str(indicators['current'].name),
                'reason': 'event_risk',
                'price': float(current_price)
            })
            return None

        # 极端波动过滤
        if atr_pct < 0.005 or atr_pct > 0.030:
            return None

        trend_info = calculate_trend_score_v3(indicators)
        context = get_market_context(indicators)
        volume_ratio = volume / volume_sma if volume_sma > 0 else 1.0
        grade, pos_multiplier = grade_signal(trend_info['score'], trend_info['adx'], trend_info['mtf_aligned'])

        # 情绪过滤（贪婪/恐慌）
        if trend_info['direction'] == 'up' and rsi >= 75:
            return None
        if trend_info['direction'] == 'down' and rsi <= 25:
            return None

        # 必须靠近关键位
        if not context['near_level']:
            return None

        # 没有A级/B级则不交易
        if grade == 'C' or pos_multiplier <= 0:
            return None

        # 动态止损/止盈倍数
        if atr_pct > 0.020:
            sl_multiplier = 2.5
            tp_multiplier = 3.0
        elif atr_pct > 0.015:
            sl_multiplier = 2.0
            tp_multiplier = 2.5
        else:
            sl_multiplier = 1.8
            tp_multiplier = 2.2

        signal = None

        # 做多信号
        if trend_info['direction'] == 'up' and trend_info['score'] >= 65:
            stop_loss_price = current_price - (atr * sl_multiplier)
            take_profit_price = current_price + (atr * tp_multiplier)
            position_result = calculate_backtest_position(
                signal_data={
                    'stop_loss': stop_loss_price,
                    'take_profit': take_profit_price,
                    'trend_score': trend_info['score']
                },
                price_data=current_price,
                current_balance=current_balance,
                current_position=position,
                performance_stats=performance_stats
            )
            size = round(position_result['contract_size'] * pos_multiplier, 2)
            signal = {
                'action': 'BUY',
                'size': size,
                'leverage': position_result['optimal_leverage'],
                'stop_loss': stop_loss_price,
                'take_profit': take_profit_price,
                'trend_multiplier': position_result['trend_multiplier'],
                'grade': grade
            }

        # 做空信号
        if trend_info['direction'] == 'down' and trend_info['score'] >= 65:
            stop_loss_price = current_price + (atr * sl_multiplier)
            take_profit_price = current_price - (atr * tp_multiplier)
            position_result = calculate_backtest_position(
                signal_data={
                    'stop_loss': stop_loss_price,
                    'take_profit': take_profit_price,
                    'trend_score': trend_info['score']
                },
                price_data=current_price,
                current_balance=current_balance,
                current_position=position,
                performance_stats=performance_stats
            )
            size = round(position_result['contract_size'] * pos_multiplier, 2)
            signal = {
                'action': 'SELL',
                'size': size,
                'leverage': position_result['optimal_leverage'],
                'stop_loss': stop_loss_price,
                'take_profit': take_profit_price,
                'trend_multiplier': position_result['trend_multiplier'],
                'grade': grade
            }

        if signal:
            signal_log.append({
                'ts': str(indicators['current'].name),
                'price': float(current_price),
                'grade': grade,
                'trend_score': trend_info['score'],
                'adx': float(trend_info['adx']),
                'mtf': trend_info['mtf_aligned'],
                'near_level': context['near_level'],
                'volume_ratio': volume_ratio
            })

        return signal
    
    strategy.signal_log = signal_log
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
    # 追加信号日志，便于后续分析
    results['signal_log'] = getattr(strategy_func, 'signal_log', [])
    
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
