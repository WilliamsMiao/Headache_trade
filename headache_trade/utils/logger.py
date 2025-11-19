"""
结构化日志系统
使用loguru提供完善的日志功能
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional


class TradingLogger:
    """交易日志管理器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not TradingLogger._initialized:
            self._setup_logger()
            TradingLogger._initialized = True
    
    def _setup_logger(self):
        """配置日志系统"""
        # 移除默认处理器
        logger.remove()
        
        # 创建日志目录
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 控制台输出（彩色，INFO及以上）
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True,
        )
        
        # 通用日志文件（按日期轮转，保留30天）
        logger.add(
            "logs/trading_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="00:00",  # 每天午夜轮转
            retention="30 days",  # 保留30天
            compression="zip",  # 压缩旧日志
            encoding="utf-8",
        )
        
        # 错误日志文件（单独记录）
        logger.add(
            "logs/error_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
            level="ERROR",
            rotation="00:00",
            retention="90 days",  # 错误日志保留更久
            compression="zip",
            encoding="utf-8",
            backtrace=True,  # 显示完整堆栈
            diagnose=True,   # 显示变量值
        )
        
        # 交易日志文件（重要交易操作）
        logger.add(
            "logs/trades_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
            level="SUCCESS",
            rotation="00:00",
            retention="365 days",  # 交易记录保留1年
            compression="zip",
            encoding="utf-8",
            filter=lambda record: "TRADE" in record["extra"],
        )
        
        # 按大小轮转（防止单个文件过大）
        logger.add(
            "logs/trading_all.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="50 MB",  # 50MB轮转
            retention=10,  # 保留10个备份
            compression="zip",
            encoding="utf-8",
        )
        
        logger.info("📝 日志系统已初始化")
    
    @staticmethod
    def get_logger():
        """获取logger实例"""
        return logger
    
    @staticmethod
    def log_trade(action: str, symbol: str, side: str, amount: float, 
                  price: Optional[float] = None, **kwargs):
        """
        记录交易操作
        
        Args:
            action: 操作类型（OPEN/CLOSE/UPDATE）
            symbol: 交易对
            side: 方向（long/short/buy/sell）
            amount: 数量
            price: 价格
            **kwargs: 其他参数
        """
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        
        msg = f"🔔 TRADE | {action} | {symbol} | {side} | Amount: {amount}"
        if price:
            msg += f" | Price: {price}"
        if extra_info:
            msg += f" | {extra_info}"
        
        logger.bind(TRADE=True).success(msg)
    
    @staticmethod
    def log_signal(signal: str, confidence: float, symbol: str, **kwargs):
        """
        记录交易信号
        
        Args:
            signal: 信号类型（buy/sell/hold）
            confidence: 置信度
            symbol: 交易对
            **kwargs: 其他参数
        """
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        
        msg = f"📊 SIGNAL | {signal.upper()} | {symbol} | Confidence: {confidence}%"
        if extra_info:
            msg += f" | {extra_info}"
        
        logger.info(msg)
    
    @staticmethod
    def log_position(position: dict):
        """
        记录持仓信息
        
        Args:
            position: 持仓字典
        """
        if not position:
            logger.info("📦 POSITION | 无持仓")
            return
        
        msg = (f"📦 POSITION | {position['symbol']} | {position['side']} | "
               f"Size: {position['size']} | Entry: {position['entry_price']} | "
               f"PnL: {position.get('unrealized_pnl', 0):.2f} USDT")
        
        logger.info(msg)
    
    @staticmethod
    def log_risk(stop_loss: float, take_profit: float, risk_reward: float, **kwargs):
        """
        记录风险参数
        
        Args:
            stop_loss: 止损价
            take_profit: 止盈价
            risk_reward: 风险回报比
            **kwargs: 其他参数
        """
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        
        msg = f"🛡️ RISK | SL: {stop_loss} | TP: {take_profit} | RR: 1:{risk_reward:.2f}"
        if extra_info:
            msg += f" | {extra_info}"
        
        logger.info(msg)
    
    @staticmethod
    def log_api_call(api_name: str, success: bool, duration: Optional[float] = None, **kwargs):
        """
        记录API调用
        
        Args:
            api_name: API名称
            success: 是否成功
            duration: 耗时（秒）
            **kwargs: 其他参数
        """
        status = "✅" if success else "❌"
        msg = f"{status} API | {api_name}"
        
        if duration:
            msg += f" | {duration:.2f}s"
        
        if kwargs:
            extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
            msg += f" | {extra_info}"
        
        if success:
            logger.debug(msg)
        else:
            logger.warning(msg)
    
    @staticmethod
    def log_performance(win_rate: float, total_pnl: float, trades_count: int, **kwargs):
        """
        记录性能统计
        
        Args:
            win_rate: 胜率
            total_pnl: 总盈亏
            trades_count: 交易次数
            **kwargs: 其他参数
        """
        extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
        
        msg = (f"📈 PERFORMANCE | Win Rate: {win_rate:.1f}% | "
               f"Total PnL: {total_pnl:.2f} USDT | Trades: {trades_count}")
        
        if extra_info:
            msg += f" | {extra_info}"
        
        logger.info(msg)


# 全局logger实例
trading_logger = TradingLogger()
log = trading_logger.get_logger()


# 便捷函数
def setup_logger():
    """初始化日志系统"""
    global trading_logger
    trading_logger = TradingLogger()
    return trading_logger.get_logger()


def get_logger():
    """获取logger实例"""
    return trading_logger.get_logger()


# 兼容性装饰器（用于替换print）
class LoggerProxy:
    """日志代理类（可以像print一样使用）"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def __call__(self, *args, **kwargs):
        """支持print风格调用"""
        message = " ".join(str(arg) for arg in args)
        self.logger.info(message)
    
    def info(self, msg):
        self.logger.info(msg)
    
    def debug(self, msg):
        self.logger.debug(msg)
    
    def warning(self, msg):
        self.logger.warning(msg)
    
    def error(self, msg):
        self.logger.error(msg)
    
    def success(self, msg):
        self.logger.success(msg)
    
    def critical(self, msg):
        self.logger.critical(msg)


# 创建全局代理
logger_proxy = LoggerProxy()


# 导出
__all__ = [
    'TradingLogger',
    'setup_logger',
    'get_logger',
    'log',
    'logger_proxy',
    'trading_logger',
]
