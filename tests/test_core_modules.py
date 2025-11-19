#!/usr/bin/env python
"""
核心模块单元测试
测试indicators, data_manager, position_manager, risk_manager等核心功能
"""

import sys
import unittest
import pandas as pd
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from headache_trade.core.indicators import (
    calculate_rsi, calculate_atr, calculate_adx,
    calculate_macd, calculate_bollinger_bands,
    calculate_ema, calculate_sma, calculate_volume_ratio
)


class TestIndicators(unittest.TestCase):
    """测试技术指标计算"""
    
    def setUp(self):
        """准备测试数据"""
        # 创建100根K线的测试数据
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='15min')
        
        prices = 50000 + np.cumsum(np.random.randn(100) * 100)
        
        self.data = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': prices + np.random.rand(100) * 100,
            'low': prices - np.random.rand(100) * 100,
            'close': prices + np.random.randn(100) * 50,
            'volume': np.random.randint(1000, 10000, 100)
        })
    
    def test_rsi_calculation(self):
        """测试RSI计算"""
        rsi = calculate_rsi(self.data['close'], period=14)
        
        # RSI应该在0-100之间
        self.assertTrue((rsi >= 0).all() and (rsi <= 100).all())
        
        # 前面应该有NaN值
        self.assertTrue(pd.isna(rsi.iloc[0]))
        
        # 后面应该有有效值
        self.assertFalse(pd.isna(rsi.iloc[-1]))
        
        print(f"[OK] RSI测试通过: 最后值={rsi.iloc[-1]:.2f}")
    
    def test_atr_calculation(self):
        """测试ATR计算"""
        atr = calculate_atr(self.data['high'], self.data['low'], self.data['close'], period=14)
        
        # ATR应该是正数
        self.assertTrue((atr[~pd.isna(atr)] > 0).all())
        
        # 应该有合理的波动率
        last_atr = atr.iloc[-1]
        self.assertTrue(last_atr > 0 and last_atr < 1000)
        
        print(f"[OK] ATR测试通过: 最后值={last_atr:.2f}")
    
    def test_adx_calculation(self):
        """测试ADX计算"""
        adx = calculate_adx(self.data['high'], self.data['low'], self.data['close'], period=14)
        
        # ADX应该在0-100之间
        valid_adx = adx[~pd.isna(adx)]
        self.assertTrue((valid_adx >= 0).all() and (valid_adx <= 100).all())
        
        print(f"[OK] ADX测试通过: 最后值={adx.iloc[-1]:.2f}")
    
    def test_macd_calculation(self):
        """测试MACD计算"""
        macd, signal, hist = calculate_macd(self.data['close'])
        
        # 应该返回三个Series
        self.assertIsInstance(macd, pd.Series)
        self.assertIsInstance(signal, pd.Series)
        self.assertIsInstance(hist, pd.Series)
        
        # 长度应该相同
        self.assertEqual(len(macd), len(self.data))
        
        # histogram应该等于macd - signal
        diff = abs(hist - (macd - signal))
        self.assertTrue((diff[~pd.isna(diff)] < 0.01).all())
        
        print(f"[OK] MACD测试通过: MACD={macd.iloc[-1]:.2f}, Signal={signal.iloc[-1]:.2f}")
    
    def test_bollinger_bands_calculation(self):
        """测试布林带计算"""
        upper, middle, lower = calculate_bollinger_bands(self.data['close'])
        
        # 上轨应该大于中轨，中轨应该大于下轨
        valid_idx = ~pd.isna(upper)
        self.assertTrue((upper[valid_idx] >= middle[valid_idx]).all())
        self.assertTrue((middle[valid_idx] >= lower[valid_idx]).all())
        
        # 价格应该在合理范围内
        close_prices = self.data['close']
        in_range = (close_prices >= lower * 0.9) & (close_prices <= upper * 1.1)
        self.assertTrue(in_range[valid_idx].sum() > len(self.data) * 0.8)
        
        print(f"[OK] 布林带测试通过: Upper={upper.iloc[-1]:.2f}, Lower={lower.iloc[-1]:.2f}")
    
    def test_ema_calculation(self):
        """测试EMA计算"""
        ema = calculate_ema(self.data['close'], period=20)
        
        # EMA应该跟随价格
        close_prices = self.data['close']
        self.assertTrue(ema.min() >= close_prices.min() * 0.95)
        self.assertTrue(ema.max() <= close_prices.max() * 1.05)
        
        print(f"[OK] EMA测试通过: EMA={ema.iloc[-1]:.2f}, Close={close_prices.iloc[-1]:.2f}")
    
    def test_sma_calculation(self):
        """测试SMA计算"""
        sma = calculate_sma(self.data['close'], period=20)
        
        # 手动计算最后一个SMA验证
        manual_sma = self.data['close'].iloc[-20:].mean()
        self.assertAlmostEqual(sma.iloc[-1], manual_sma, places=2)
        
        print(f"[OK] SMA测试通过: SMA={sma.iloc[-1]:.2f}")
    
    def test_volume_ratio_calculation(self):
        """测试成交量比率计算"""
        vol_ratio = calculate_volume_ratio(self.data['volume'], period=20)
        
        # 成交量比率应该是正数
        valid_ratio = vol_ratio[~pd.isna(vol_ratio)]
        self.assertTrue((valid_ratio > 0).all())
        
        print(f"[OK] 成交量比率测试通过: Ratio={vol_ratio.iloc[-1]:.2f}")


class TestDataIntegrity(unittest.TestCase):
    """测试数据完整性"""
    
    def setUp(self):
        """加载实际数据文件"""
        data_file = Path("data/binance_BTC_USDT_15m_90d.csv")
        if data_file.exists():
            self.data = pd.read_csv(data_file)
            self.has_data = True
        else:
            self.has_data = False
    
    def test_data_file_exists(self):
        """测试数据文件是否存在"""
        if not self.has_data:
            self.skipTest("数据文件不存在，跳过测试")
        
        self.assertTrue(len(self.data) > 0)
        print(f"[OK] 数据文件测试通过: {len(self.data)}行")
    
    def test_required_columns(self):
        """测试必需列是否存在"""
        if not self.has_data:
            self.skipTest("数据文件不存在，跳过测试")
        
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            self.assertIn(col, self.data.columns)
        
        print(f"[OK] 数据列测试通过: {list(self.data.columns)}")
    
    def test_no_missing_values(self):
        """测试关键列是否有缺失值"""
        if not self.has_data:
            self.skipTest("数据文件不存在，跳过测试")
        
        key_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in key_cols:
            missing = self.data[col].isna().sum()
            self.assertEqual(missing, 0, f"{col}列有{missing}个缺失值")
        
        print("[OK] 数据完整性测试通过: 无缺失值")
    
    def test_price_validity(self):
        """测试价格数据有效性"""
        if not self.has_data:
            self.skipTest("数据文件不存在，跳过测试")
        
        # high >= low
        self.assertTrue((self.data['high'] >= self.data['low']).all())
        
        # high >= open, close
        self.assertTrue((self.data['high'] >= self.data['open']).all())
        self.assertTrue((self.data['high'] >= self.data['close']).all())
        
        # low <= open, close
        self.assertTrue((self.data['low'] <= self.data['open']).all())
        self.assertTrue((self.data['low'] <= self.data['close']).all())
        
        print("[OK] 价格有效性测试通过")


class TestRiskManagement(unittest.TestCase):
    """测试风险管理功能"""
    
    def test_position_size_calculation(self):
        """测试仓位大小计算"""
        from headache_trade.strategies import MomentumStrategy
        
        strategy = MomentumStrategy()
        strategy.activate()
        
        # 模拟信号
        class MockSignal:
            signal_type = None
            confidence = 80
            stop_loss = 50000
            take_profit = 52000
            entry_price = 51000
        
        signal = MockSignal()
        account_balance = 10000
        
        position_size = strategy.calculate_position_size(account_balance, signal)
        
        # 仓位应该是正数且合理
        self.assertTrue(position_size > 0)
        self.assertTrue(position_size < account_balance)
        
        print(f"[OK] 仓位计算测试通过: {position_size:.4f} BTC")
    
    def test_risk_limits(self):
        """测试风险限制"""
        from headache_trade.strategies.momentum import MomentumStrategy
        
        strategy = MomentumStrategy()
        
        # 测试风险百分比限制
        self.assertTrue(strategy.risk_per_trade > 0)
        self.assertTrue(strategy.risk_per_trade < 0.1)  # 不应超过10%
        
        print(f"[OK] 风险限制测试通过: {strategy.risk_per_trade*100}%")


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestIndicators))
    suite.addTests(loader.loadTestsFromTestCase(TestDataIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskManagement))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回是否所有测试通过
    return result.wasSuccessful()


if __name__ == '__main__':
    print("\n" + "="*70)
    print("核心模块单元测试")
    print("="*70 + "\n")
    
    success = run_tests()
    
    print("\n" + "="*70)
    if success:
        print("[SUCCESS] 所有单元测试通过!")
        exit(0)
    else:
        print("[FAIL] 部分测试失败")
        exit(1)
