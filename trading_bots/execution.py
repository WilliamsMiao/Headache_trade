import time
import traceback
from datetime import datetime

from trading_bots.config import exchange, TRADE_CONFIG


def set_tp_sl_orders(symbol, position_side, position_size, stop_loss_price, take_profit_price, entry_price=None):
    """Set OKX take-profit and stop-loss conditional orders."""
    try:
        try:
            print("🔄 设置新订单前，先取消该交易对的所有旧止盈止损订单...")
            cancel_tp_sl_orders(symbol, None)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ 取消旧订单时出错（继续执行）: {e}")

        markets = exchange.load_markets()
        market = markets[symbol]
        inst_id = market['id']
        trade_side = 'sell' if position_side == 'long' else 'buy'

        order_ids = {'tp_order_id': None, 'sl_order_id': None}

        if stop_loss_price > 0:
            try:
                params = {
                    'instId': inst_id,
                    'tdMode': 'cross',
                    'side': trade_side,
                    'ordType': 'conditional',
                    'sz': str(position_size),
                    'slTriggerPx': str(stop_loss_price),
                    'slOrdPx': '-1',
                    'slTriggerPxType': 'mark',
                }
                response = exchange.request('trade/order-algo', 'private', 'POST', params)
                if response and response.get('code') == '0':
                    order_ids['sl_order_id'] = response.get('data', [{}])[0].get('algoId')
                    print(f"✅ 止损订单设置成功: {stop_loss_price:.2f} (订单ID: {order_ids['sl_order_id']})")
                else:
                    print(f"⚠️ 止损订单设置失败: {response.get('msg', '未知错误')}")
            except Exception as e:
                print(f"⚠️ 设置止损订单时出错: {e}")
                print("⚠️ 止损订单设置失败，将使用代码监控作为备用")

        if take_profit_price > 0:
            try:
                params = {
                    'instId': inst_id,
                    'tdMode': 'cross',
                    'side': trade_side,
                    'ordType': 'conditional',
                    'sz': str(position_size),
                    'tpTriggerPx': str(take_profit_price),
                    'tpOrdPx': '-1',
                    'tpTriggerPxType': 'mark',
                }
                response = exchange.request('trade/order-algo', 'private', 'POST', params)
                if response and response.get('code') == '0':
                    order_ids['tp_order_id'] = response.get('data', [{}])[0].get('algoId')
                    print(f"✅ 止盈订单设置成功: {take_profit_price:.2f} (订单ID: {order_ids['tp_order_id']})")
                else:
                    print(f"⚠️ 止盈订单设置失败: {response.get('msg', '未知错误')}")
            except Exception as e:
                print(f"⚠️ 设置止盈订单时出错: {e}")
                print("⚠️ 止盈订单设置失败，将使用代码监控作为备用")

        if order_ids['tp_order_id'] or order_ids['sl_order_id']:
            return order_ids
        return None

    except Exception as e:
        print(f"❌ 设置止盈止损订单失败: {e}")
        traceback.print_exc()
        return None


def cancel_tp_sl_orders(symbol, order_ids=None):
    """Cancel OKX conditional TP/SL orders."""
    try:
        markets = exchange.load_markets()
        market = markets[symbol]
        inst_id = market['id']

        if order_ids:
            cancelled = False
            if order_ids.get('tp_order_id'):
                try:
                    cancel_params = [{'algoId': order_ids['tp_order_id'], 'instId': inst_id}]
                    response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                    if response and response.get('code') == '0':
                        data = response.get('data', [])
                        if data and data[0].get('sCode', '0') == '0':
                            print(f"✅ 止盈订单已取消: {order_ids['tp_order_id']}")
                            cancelled = True
                        else:
                            print(f"❌ 取消止盈订单失败: {data[0].get('sMsg', '未知错误') if data else '未知错误'}")
                    elif response and response.get('code') == '404':
                        print(f"⚠️ 止盈订单不存在: {order_ids['tp_order_id']}")
                    else:
                        print(f"❌ 取消止盈订单失败: {response.get('msg', '未知错误') if response else '未知错误'}")
                except Exception as e:
                    if '404' in str(e) or 'Not Found' in str(e):
                        print(f"⚠️ 止盈订单不存在: {order_ids['tp_order_id']} - {e}")
                    else:
                        print(f"❌ 取消止盈订单失败: {e}")

            if order_ids.get('sl_order_id'):
                try:
                    cancel_params = [{'algoId': order_ids['sl_order_id'], 'instId': inst_id}]
                    response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                    if response and response.get('code') == '0':
                        data = response.get('data', [])
                        if data and data[0].get('sCode', '0') == '0':
                            print(f"✅ 止损订单已取消: {order_ids['sl_order_id']}")
                            cancelled = True
                        else:
                            print(f"❌ 取消止损订单失败: {data[0].get('sMsg', '未知错误') if data else '未知错误'}")
                    elif response and response.get('code') == '404':
                        print(f"⚠️ 止损订单不存在: {order_ids['sl_order_id']}")
                    else:
                        print(f"❌ 取消止损订单失败: {response.get('msg', '未知错误') if response else '未知错误'}")
                except Exception as e:
                    if '404' in str(e) or 'Not Found' in str(e):
                        print(f"⚠️ 止损订单不存在: {order_ids['sl_order_id']} - {e}")
                    else:
                        print(f"❌ 取消止损订单失败: {e}")
            return cancelled

        cancelled_count = 0
        failed_count = 0
        orders = []
        params = {'instType': 'SWAP', 'instId': inst_id, 'ordType': 'conditional'}
        try:
            response = exchange.request('trade/orders-algo-pending', 'private', 'GET', params)
            if response and response.get('code') == '0':
                orders = response.get('data', [])
        except Exception as e1:
            try:
                response = exchange.request('trade/orders-algo-pending', 'private', 'GET', {'instType': 'SWAP'})
                if response and response.get('code') == '0':
                    all_orders = response.get('data', [])
                    orders = [o for o in all_orders if o.get('instId') == inst_id]
            except Exception as e2:
                print(f"⚠️ 查询策略订单失败: {e1}, {e2}")
                return True

        for order in orders:
            algo_id = order.get('algoId')
            if algo_id:
                try:
                    cancel_params = [{'algoId': algo_id, 'instId': inst_id}]
                    cancel_response = exchange.request('trade/cancel-algos', 'private', 'POST', {'data': cancel_params})
                    if cancel_response:
                        if cancel_response.get('code') == '0':
                            data = cancel_response.get('data', [])
                            if data and data[0].get('sCode', '0') == '0':
                                cancelled_count += 1
                            else:
                                failed_count += 1
                        elif cancel_response.get('code') == '404':
                            failed_count += 1
                        else:
                            failed_count += 1
                except Exception as e:
                    failed_count += 1 if '404' in str(e) or 'Not Found' in str(e) else 1

        if cancelled_count > 0:
            print(f"✅ 已取消 {cancelled_count} 个策略订单")
            if failed_count > 0:
                print(f"⚠️ {failed_count} 个订单取消失败（可能已不存在）")
            return True
        if failed_count > 0:
            print(f"ℹ️ 尝试取消 {failed_count} 个订单，但都失败（可能已不存在）")
        else:
            print("ℹ️ 没有找到需要取消的策略订单")
        return True

    except Exception as e:
        print(f"❌ 取消止盈止损订单失败: {e}")
        return False


def update_tp_sl_orders(symbol, position_side, position_size, stop_loss_price, take_profit_price, old_order_ids=None):
    """Update TP/SL orders by cancelling old and creating new ones."""
    try:
        try:
            actual_position = get_current_position()
            if not actual_position or actual_position['size'] <= 0:
                print("⚠️ 更新止盈止损订单时检测到实际无持仓，取消操作，避免创建残留订单")
                if old_order_ids:
                    cancel_tp_sl_orders(symbol, old_order_ids)
                return None
            if actual_position['side'] != position_side:
                print(
                    f"⚠️ 更新止盈止损订单时检测到持仓方向不匹配（实际: {actual_position['side']}, 预期: {position_side}），取消操作"
                )
                if old_order_ids:
                    cancel_tp_sl_orders(symbol, old_order_ids)
                return None
        except Exception as e:
            print(f"⚠️ 验证实际持仓时出错，继续执行订单更新: {e}")

        if old_order_ids:
            cancel_tp_sl_orders(symbol, old_order_ids)
            time.sleep(0.5)

        return set_tp_sl_orders(symbol, position_side, position_size, stop_loss_price, take_profit_price)

    except Exception as e:
        print(f"❌ 更新止盈止损订单失败: {e}")
        return None


def get_current_position():
    """Fetch current OKX position for configured symbol."""
    try:
        positions = exchange.fetch_positions([TRADE_CONFIG['symbol']])
        for pos in positions:
            if pos['symbol'] == TRADE_CONFIG['symbol']:
                contracts = float(pos['contracts']) if pos['contracts'] else 0
                if contracts > 0:
                    return {
                        'side': pos['side'],
                        'size': contracts,
                        'entry_price': float(pos['entryPrice']) if pos['entryPrice'] else 0,
                        'unrealized_pnl': float(pos['unrealizedPnl']) if pos['unrealizedPnl'] else 0,
                        'leverage': float(pos['leverage']) if pos['leverage'] else TRADE_CONFIG['leverage'],
                        'symbol': pos['symbol'],
                    }
        return None
    except Exception as e:
        print(f"获取持仓失败: {e}")
        traceback.print_exc()
        return None


__all__ = [
    'set_tp_sl_orders',
    'cancel_tp_sl_orders',
    'update_tp_sl_orders',
    'get_current_position',
]
