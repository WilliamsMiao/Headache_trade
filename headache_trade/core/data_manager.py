"""
数据管理器 - 统一的历史数据管理
职责：下载、缓存、加载历史数据
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Optional, List


class DataManager:
    """历史数据管理器"""
    
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.cache_index_file = self.data_dir / 'data_index.json'
        self.cache_index = self._load_cache_index()
    
    def _load_cache_index(self) -> dict:
        """加载缓存索引"""
        if self.cache_index_file.exists():
            with open(self.cache_index_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_cache_index(self):
        """保存缓存索引"""
        with open(self.cache_index_file, 'w') as f:
            json.dump(self.cache_index, f, indent=2)
    
    def _get_cache_key(self, exchange: str, symbol: str, timeframe: str, days: int) -> str:
        """生成缓存键"""
        return f"{exchange}_{symbol.replace('/', '_')}_{timeframe}_{days}d"
    
    def fetch_data(
        self,
        exchange: str = 'binance',
        symbol: str = 'BTC/USDT',
        timeframe: str = '15m',
        days: int = 90,
        force_download: bool = False
    ) -> pd.DataFrame:
        """
        获取历史数据（自动缓存）
        
        Args:
            exchange: 交易所名称
            symbol: 交易对
            timeframe: 时间周期
            days: 天数
            force_download: 强制重新下载
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        
        cache_key = self._get_cache_key(exchange, symbol, timeframe, days)
        cache_file = self.data_dir / f'{cache_key}.csv'
        
        # 检查缓存
        if not force_download and cache_file.exists():
            cache_info = self.cache_index.get(cache_key, {})
            cache_date = cache_info.get('date')
            
            # 如果缓存是今天的，直接使用
            if cache_date == datetime.now().strftime('%Y-%m-%d'):
                print(f"[DataManager] Using cached data: {cache_file.name}")
                return pd.read_csv(cache_file)
            else:
                print(f"[DataManager] Cache expired, re-downloading...")
        
        # 下载新数据
        print(f"[DataManager] Downloading {days} days of {symbol} {timeframe} data from {exchange}...")
        
        try:
            exchange_obj = getattr(ccxt, exchange)({'enableRateLimit': True})
            
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            since = int(start_time.timestamp() * 1000)
            end = int(end_time.timestamp() * 1000)
            
            all_ohlcv = []
            batch = 0
            
            while since < end:
                ohlcv = exchange_obj.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                
                if not ohlcv:
                    break
                
                all_ohlcv.extend(ohlcv)
                batch += 1
                since = ohlcv[-1][0] + 1
                
                if batch % 5 == 0:
                    print(f"[DataManager] Progress: {len(all_ohlcv)} candles fetched...")
            
            # 转换为DataFrame
            df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 保存缓存
            df.to_csv(cache_file, index=False)
            
            # 更新索引
            self.cache_index[cache_key] = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'file': cache_file.name,
                'candles': len(df),
                'period': f"{df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}"
            }
            self._save_cache_index()
            
            print(f"[DataManager] Downloaded and cached {len(df)} candles")
            return df
            
        except Exception as e:
            print(f"[DataManager] Error downloading data: {e}")
            
            # 如果有旧缓存，使用旧缓存
            if cache_file.exists():
                print(f"[DataManager] Using old cache as fallback")
                return pd.read_csv(cache_file)
            
            raise
    
    def list_cached_data(self) -> List[dict]:
        """列出所有缓存的数据"""
        return [
            {
                'key': key,
                **info
            }
            for key, info in self.cache_index.items()
        ]
    
    def clear_cache(self, cache_key: Optional[str] = None):
        """清除缓存"""
        if cache_key:
            # 清除特定缓存
            if cache_key in self.cache_index:
                cache_file = self.data_dir / self.cache_index[cache_key]['file']
                if cache_file.exists():
                    cache_file.unlink()
                del self.cache_index[cache_key]
                self._save_cache_index()
                print(f"[DataManager] Cleared cache: {cache_key}")
        else:
            # 清除所有缓存
            for file in self.data_dir.glob('*.csv'):
                file.unlink()
            self.cache_index = {}
            self._save_cache_index()
            print(f"[DataManager] Cleared all cache")


if __name__ == '__main__':
    # 测试
    dm = DataManager()
    
    print("\n=== Cached Data ===")
    for item in dm.list_cached_data():
        print(f"  {item['key']}: {item['candles']} candles")
    
    print("\n=== Fetching Data ===")
    df = dm.fetch_data(
        exchange='binance',
        symbol='BTC/USDT',
        timeframe='15m',
        days=90
    )
    
    print(f"\nLoaded {len(df)} candles")
    print(f"Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
