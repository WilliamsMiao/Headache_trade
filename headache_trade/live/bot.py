"""
多策略自适应交易机器人
整合市场分析、策略调度、风险管理
"""

import ccxt
import pandas as pd
import time
from datetime import datetime
from typing import Optional, Dict

from ..utils.logger import TradingLogger, get_logger
from ..utils.config import ConfigManager, get_config
from ..strategies import (
    BreakoutStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    TrendFollowingStrategy,
    GridTradingStrategy,
    SignalType
)
from ..ai.regime_detector import MarketRegimeDetector, MarketRegime


class MultiStrategyBot:
    """多策略自适应交易机器人"""
    
    def __init__(self, config_path: str = "config/config_example.json"):
        # 加载配置
        self.config_manager = ConfigManager()
        
        # 如果提供了配置路径，尝试加载
        if config_path:
            try:
                import json
                from pathlib import Path
                with open(Path(config_path), 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 更新配置
                    for key, value in loaded_config.items():
                        self.config_manager.config[key] = value
            except Exception as e:
                print(f"[WARN] 无法加载配置文件 {config_path}: {e}")
        
        self.config = self.config_manager.config
        
        # 初始化日志
        self.logger = TradingLogger()
        self.log = get_logger()
        
        # 初始化交易所
        self.exchange = self._init_exchange()
        
        # 交易对
        self.symbol = self.config.get('symbol', 'BTC/USDT:USDT')
        
        # 初始化策略
        self.strategies = {
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'breakout': BreakoutStrategy(),
            'trend_following': TrendFollowingStrategy(),
            'grid': GridTradingStrategy()
        }
        
        # 激活所有策略
        for strategy in self.strategies.values():
            strategy.activate()
        
        # 市场状态检测器
        self.regime_detector = MarketRegimeDetector()
        
        # 当前活跃策略
        self.active_strategy_name = 'momentum'
        self.active_strategy = self.strategies[self.active_strategy_name]
        self.strategy_switch_count = 0
        
        # 账户信息
        self.account_balance = 0.0
        self.current_position: Optional[Dict] = None
        
        # 运行控制
        self.is_running = False
        self.check_interval = self.config.get('check_interval', 60)  # 秒
        
        self.log.info("多策略交易机器人初始化完成")
    
    def select_best_strategy(self, price_data: pd.DataFrame) -> str:
        """根据市场状态选择最佳策略"""
        regime_result = self.regime_detector.detect_regime(price_data)
        
        # 根据市场状态和趋势方向选择策略
        if regime_result.regime == 'trending':
            if regime_result.trend_direction == 'up':
                recommended_strategy = 'momentum'
            elif regime_result.trend_direction == 'down':
                recommended_strategy = 'mean_reversion'
            else:
                recommended_strategy = 'trend_following'
        elif regime_result.regime == 'ranging':
            recommended_strategy = 'grid'
        elif regime_result.regime == 'volatile':
            recommended_strategy = 'breakout'
        else:  # neutral
            recommended_strategy = 'momentum'
        
        if recommended_strategy != self.active_strategy_name:
            self.log.info(f"策略切换: {self.active_strategy_name} → {recommended_strategy} (市场: {regime_result.regime}, 趋势: {regime_result.trend_direction})")
            self.active_strategy_name = recommended_strategy
            self.active_strategy = self.strategies[recommended_strategy]
            self.strategy_switch_count += 1
        
        return recommended_strategy
    
    def generate_trading_signal(self, price_data: pd.DataFrame, current_position: Optional[Dict] = None):
        """生成交易信号"""
        # 选择最佳策略
        self.select_best_strategy(price_data)
        
        # 生成信号
        return self.active_strategy.generate_signal(price_data, current_position)
    
    def calculate_position_size(self, account_balance: float, signal) -> float:
        """计算仓位大小"""
        return self.active_strategy.calculate_position_size(account_balance, signal)
    
    def _init_exchange(self) -> ccxt.Exchange:
        """初始化交易所连接"""
        exchange_id = self.config.get('exchange', 'binance')
        
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({
            'apiKey': self.config.get('api_key'),
            'secret': self.config.get('api_secret'),
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # 设置代理（如果需要）
        if self.config.get('proxy'):
            exchange.proxies = {
                'http': self.config.get('proxy'),
                'https': self.config.get('proxy')
            }
        
        return exchange
    
    def fetch_market_data(self, timeframe: str = '1h', limit: int = 500) -> pd.DataFrame:
        """获取市场数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            self.log.error(f"获取市场数据失败: {e}")
            return None
    
    def update_account_info(self):
        """更新账户信息"""
        try:
            balance = self.exchange.fetch_balance()
            self.account_balance = balance['USDT']['free']
            
            # 获取当前持仓
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                if float(pos['contracts']) > 0:
                    self.current_position = {
                        'side': pos['side'],
                        'size': float(pos['contracts']),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unrealizedPnl'])
                    }
                    return
            
            self.current_position = None
            
        except Exception as e:
            self.log.error(f"更新账户信息失败: {e}")
    
    def execute_trade(self, signal):
        """执行交易"""
        try:
            current_price = self.exchange.fetch_ticker(self.symbol)['last']
            
            # 计算仓位大小
            position_size = self.calculate_position_size(self.account_balance, signal)
            
            if position_size == 0:
                self.log.warning("仓位计算为0，跳过交易")
                return
            
            # 执行订单
            side = 'buy' if signal.signal_type.value in ['LONG', 'BUY', 'long', 'buy'] else 'sell'
            
            order = self.exchange.create_market_order(
                symbol=self.symbol,
                side=side,
                amount=position_size
            )
            
            # 记录交易
            self.logger.log_trade(
                action='OPEN',
                symbol=self.symbol,
                side=side,
                amount=position_size,
                price=current_price,
                strategy=self.active_strategy_name,
                confidence=signal.confidence,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit
            )
            
            # 设置止损止盈
            if signal.stop_loss:
                self._set_stop_loss(signal.stop_loss, position_size, side)
            
            if signal.take_profit:
                self._set_take_profit(signal.take_profit, position_size, side)
            
            print(f"\n[OK] 交易执行成功:")
            print(f"   策略: {self.active_strategy_name}")
            print(f"   方向: {side.upper()}")
            print(f"   价格: {current_price:.2f}")
            print(f"   数量: {position_size:.4f}")
            print(f"   止损: {signal.stop_loss:.2f if signal.stop_loss else 'N/A'}")
            print(f"   止盈: {signal.take_profit:.2f if signal.take_profit else 'N/A'}")
            
        except Exception as e:
            self.log.error(f"交易执行失败: {e}")
    
    def _set_stop_loss(self, stop_price: float, amount: float, side: str):
        """设置止损单"""
        try:
            stop_side = 'sell' if side == 'buy' else 'buy'
            self.exchange.create_order(
                symbol=self.symbol,
                type='stop_market',
                side=stop_side,
                amount=amount,
                params={'stopPrice': stop_price}
            )
        except Exception as e:
            self.log.error(f"设置止损失败: {e}")
    
    def _set_take_profit(self, tp_price: float, amount: float, side: str):
        """设置止盈单"""
        try:
            tp_side = 'sell' if side == 'buy' else 'buy'
            self.exchange.create_order(
                symbol=self.symbol,
                type='take_profit_market',
                side=tp_side,
                amount=amount,
                params={'stopPrice': tp_price}
            )
        except Exception as e:
            self.log.error(f"设置止盈失败: {e}")
    
    def check_exit_conditions(self, price_data: pd.DataFrame):
        """检查退出条件"""
        if not self.current_position:
            return
        
        should_exit = self.active_strategy.should_exit(
            price_data,
            self.current_position['entry_price'],
            self.current_position['side']
        )
        
        if should_exit:
            self._close_position()
    
    def _close_position(self):
        """平仓"""
        try:
            if not self.current_position:
                return
            
            side = 'sell' if self.current_position['side'] == 'long' else 'buy'
            
            order = self.exchange.create_market_order(
                symbol=self.symbol,
                side=side,
                amount=self.current_position['size']
            )
            
            # 记录交易结果
            trade_result = {
                'exit_price': order['price'],
                'pnl': self.current_position['unrealized_pnl'],
                'is_win': self.current_position['unrealized_pnl'] > 0
            }
            
            self.active_strategy.update_performance(trade_result)
            
            self.log.info(f"平仓完成: PnL = {trade_result['pnl']:.2f} USDT")
            print(f"\n📊 平仓: {'[OK] 盈利' if trade_result['is_win'] else '[FAIL] 亏损'} {abs(trade_result['pnl']):.2f} USDT")
            
            self.current_position = None
            
        except Exception as e:
            self.log.error(f"平仓失败: {e}")
    
    def run_once(self):
        """执行一次交易循环"""
        try:
            # 更新账户信息
            self.update_account_info()
            
            # 获取市场数据
            price_data = self.fetch_market_data()
            if price_data is None:
                return
            
            print(f"\n{'='*60}")
            print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"💰 账户余额: {self.account_balance:.2f} USDT")
            
            if self.current_position:
                print(f"[BACKUP] 当前持仓: {self.current_position['side'].upper()}")
                print(f"   入场价: {self.current_position['entry_price']:.2f}")
                print(f"   数量: {self.current_position['size']:.4f}")
                print(f"   浮盈: {self.current_position['unrealized_pnl']:.2f} USDT")
            else:
                print(f"[BACKUP] 当前持仓: 无")
            
            # 检查退出条件
            self.check_exit_conditions(price_data)
            
            # 如果有持仓，暂不开新仓
            if self.current_position:
                print("⏸️ 已有持仓，暂不开新仓")
                return
            
            # 生成交易信号
            signal = self.generate_trading_signal(price_data, self.current_position)
            
            # 执行交易
            if signal and signal.signal_type.value != 'HOLD' and signal.signal_type != SignalType.HOLD:
                self.execute_trade(signal)
            else:
                print("⏸️ 无交易信号，观望中")
            
        except Exception as e:
            self.log.error(f"交易循环错误: {e}")
    
    def run(self):
        """启动交易机器人"""
        self.is_running = True
        self.log.info("交易机器人启动")
        
        print("\n" + "="*60)
        print("[START] 多策略自适应交易机器人启动")
        print(f"📈 交易对: {self.symbol}")
        print(f"⏱️ 检查间隔: {self.check_interval}秒")
        print("="*60 + "\n")
        
        while self.is_running:
            try:
                self.run_once()
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n收到停止信号，正在关闭...")
                self.stop()
                break
            except Exception as e:
                self.log.error(f"运行错误: {e}")
                time.sleep(self.check_interval)
    
    def stop(self):
        """停止交易机器人"""
        self.is_running = False
        
        # 打印最终状态
        print("\n" + "="*60)
        print("📊 最终状态:")
        print(f"   活跃策略: {self.active_strategy_name}")
        print(f"   策略切换次数: {self.strategy_switch_count}")
        print("\n策略表现:")
        for name, strategy in self.strategies.items():
            perf = strategy.get_performance_summary()
            print(f"\n   {name.upper()}:")
            print(f"      总交易: {perf['total_trades']}")
            print(f"      胜率: {perf['win_rate']:.1f}%")
            print(f"      总盈亏: {perf['total_pnl']:.2f} USDT")
            print(f"      最大回撤: {perf['max_drawdown']:.2f}%")
        print("="*60)
        
        self.log.info("交易机器人已停止")


def main():
    """主函数"""
    # 创建交易机器人
    bot = MultiStrategyBot()
    
    # 启动
    bot.run()


if __name__ == "__main__":
    main()
