#!/usr/bin/env python3
"""
查询OKX API获取完整交易记录并分析
"""
import sys
import os
sys.path.append('/root/crypto_deepseek/trading_bots')

import ccxt
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

load_dotenv()

# 初始化OKX交易所
exchange = ccxt.okx({
    'options': {
        'defaultType': 'swap',
    },
    'apiKey': os.getenv('OKX_API_KEY'),
    'secret': os.getenv('OKX_SECRET'),
    'password': os.getenv('OKX_PASSWORD'),
})

symbol = 'BTC/USDT:USDT'

print("=" * 80)
print("查询OKX交易记录分析")
print("=" * 80)

try:
    # 查询最近100笔交易记录
    print(f"\n正在查询 {symbol} 的交易记录...")
    trades = exchange.fetch_my_trades(symbol, limit=100)
    
    if not trades:
        print("❌ 没有找到交易记录")
        sys.exit(1)
    
    print(f"✅ 找到 {len(trades)} 笔交易记录\n")
    
    # 按时间排序（最新的在前）
    trades = sorted(trades, key=lambda x: x['timestamp'], reverse=True)
    
    # 分析最近24小时的交易
    now = datetime.now()
    one_day_ago = now - timedelta(days=1)
    
    recent_trades = []
    for trade in trades:
        trade_time = datetime.fromtimestamp(trade['timestamp'] / 1000)
        if trade_time >= one_day_ago:
            recent_trades.append(trade)
    
    print(f"📊 最近24小时的交易: {len(recent_trades)} 笔\n")
    
    # 显示最近20笔交易
    print("=" * 80)
    print("最近20笔交易记录:")
    print("=" * 80)
    print(f"{'时间':<20} {'方向':<6} {'价格':<12} {'数量':<12} {'成本(USDT)':<12} {'手续费':<10}")
    print("-" * 80)
    
    for trade in trades[:20]:
        trade_time = datetime.fromtimestamp(trade['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        side = trade['side'].upper()
        price = float(trade['price'])
        amount = float(trade['amount'])
        cost = float(trade['cost'])
        fee = trade.get('fee', {})
        fee_cost = fee.get('cost', 0) if fee else 0
        
        print(f"{trade_time:<20} {side:<6} {price:<12.2f} {amount:<12.4f} {cost:<12.2f} {fee_cost:<10.6f}")
    
    # 分析交易方向
    print("\n" + "=" * 80)
    print("交易方向分析:")
    print("=" * 80)
    
    buy_trades = [t for t in recent_trades if t['side'] == 'buy']
    sell_trades = [t for t in recent_trades if t['side'] == 'sell']
    
    buy_total = sum(float(t['cost']) for t in buy_trades)
    sell_total = sum(float(t['cost']) for t in sell_trades)
    
    print(f"买入交易: {len(buy_trades)} 笔, 总金额: {buy_total:.2f} USDT")
    print(f"卖出交易: {len(sell_trades)} 笔, 总金额: {sell_total:.2f} USDT")
    print(f"净交易量: {abs(buy_total - sell_total):.2f} USDT")
    
    # 分析交易频率
    print("\n" + "=" * 80)
    print("交易频率分析:")
    print("=" * 80)
    
    if recent_trades:
        time_span = (recent_trades[0]['timestamp'] - recent_trades[-1]['timestamp']) / 1000 / 3600  # 小时
        if time_span > 0:
            trades_per_hour = len(recent_trades) / time_span
            print(f"交易时间跨度: {time_span:.2f} 小时")
            print(f"平均交易频率: {trades_per_hour:.2f} 笔/小时")
    
    # 分析交易金额分布
    print("\n" + "=" * 80)
    print("交易金额分布:")
    print("=" * 80)
    
    costs = [float(t['cost']) for t in recent_trades]
    if costs:
        print(f"最小交易金额: {min(costs):.2f} USDT")
        print(f"最大交易金额: {max(costs):.2f} USDT")
        print(f"平均交易金额: {sum(costs)/len(costs):.2f} USDT")
        print(f"总交易金额: {sum(costs):.2f} USDT")
    
    # 尝试分析完整的交易对（开仓+平仓）
    print("\n" + "=" * 80)
    print("完整交易对分析（尝试配对开仓和平仓）:")
    print("=" * 80)
    
    # 简化的配对逻辑：按时间顺序，配对相邻的buy和sell
    complete_trades = []
    i = 0
    while i < len(recent_trades) - 1:
        trade1 = recent_trades[i]
        trade2 = recent_trades[i + 1]
        
        # 如果一个是buy，一个是sell，可能是完整的交易对
        if trade1['side'] != trade2['side']:
            entry = trade1 if trade1['side'] == 'buy' else trade2
            exit = trade2 if trade1['side'] == 'buy' else trade1
            
            # 计算盈亏（简化版本，不考虑手续费）
            if entry['side'] == 'buy':
                pnl_pct = ((float(exit['price']) - float(entry['price'])) / float(entry['price'])) * 100
            else:
                pnl_pct = ((float(entry['price']) - float(exit['price'])) / float(entry['price'])) * 100
            
            complete_trades.append({
                'entry_time': datetime.fromtimestamp(entry['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'exit_time': datetime.fromtimestamp(exit['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'entry_price': float(entry['price']),
                'exit_price': float(exit['price']),
                'side': entry['side'],
                'amount': float(entry['amount']),
                'pnl_pct': pnl_pct
            })
            i += 2
        else:
            i += 1
    
    if complete_trades:
        print(f"\n找到 {len(complete_trades)} 个可能的完整交易对:\n")
        print(f"{'入场时间':<20} {'出场时间':<20} {'方向':<6} {'入场价':<12} {'出场价':<12} {'盈亏%':<10}")
        print("-" * 100)
        
        wins = 0
        losses = 0
        total_pnl = 0
        
        for trade in complete_trades[:20]:  # 显示前20个
            pnl_sign = '+' if trade['pnl_pct'] > 0 else ''
            print(f"{trade['entry_time']:<20} {trade['exit_time']:<20} {trade['side']:<6} "
                  f"{trade['entry_price']:<12.2f} {trade['exit_price']:<12.2f} "
                  f"{pnl_sign}{trade['pnl_pct']:<9.2f}%")
            
            if trade['pnl_pct'] > 0:
                wins += 1
            else:
                losses += 1
            total_pnl += trade['pnl_pct']
        
        if complete_trades:
            print(f"\n统计:")
            print(f"盈利交易: {wins} 笔")
            print(f"亏损交易: {losses} 笔")
            if wins + losses > 0:
                win_rate = wins / (wins + losses) * 100
                print(f"胜率: {win_rate:.1f}%")
            print(f"平均盈亏: {total_pnl/len(complete_trades):.2f}%")
    else:
        print("未找到完整的交易对（可能是频繁加仓减仓导致）")
    
    # 保存详细数据到文件
    output_file = '/root/crypto_deepseek/data/trade_analysis.json'
    output_data = {
        'query_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_trades': len(trades),
        'recent_24h_trades': len(recent_trades),
        'recent_trades': [
            {
                'timestamp': datetime.fromtimestamp(t['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'side': t['side'],
                'price': float(t['price']),
                'amount': float(t['amount']),
                'cost': float(t['cost']),
                'fee': t.get('fee', {}).get('cost', 0) if t.get('fee') else 0
            }
            for t in recent_trades
        ],
        'complete_trades': complete_trades[:50]  # 保存前50个
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 详细数据已保存到: {output_file}")
    
except Exception as e:
    print(f"❌ 查询失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

