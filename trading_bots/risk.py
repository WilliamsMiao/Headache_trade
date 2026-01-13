from datetime import datetime

from trading_bots.config import (
    PROTECTION_LEVELS,
    LOCK_STOP_LOSS_PROFIT_THRESHOLD,
    LOCK_STOP_LOSS_BUFFER,
    LOCK_STOP_LOSS_RATIO,
    LOCK_STOP_LOSS_RATIOS,
)


class ProtectionOrbit:
    """
    保护轨道系统 - 管理双轨道（止盈轨道 + 止损轨道）
    根据盈利水平和持仓时间自动切换保护级别
    """

    def __init__(self, entry_price, atr, position_side):
        self.entry_price = entry_price
        self.atr = atr
        self.position_side = position_side
        self.current_level = 'defensive'
        self.entry_time = datetime.now()

        self.upper_orbit = self.calculate_upper_orbit()
        self.lower_orbit = self.calculate_lower_orbit()

        print(f"🛡️ 保护轨道初始化: 入场价={entry_price:.2f}, ATR={atr:.2f}, 级别={self.current_level}")
        print(f"   - 止盈轨道: {self.upper_orbit:.2f}")
        print(f"   - 止损轨道: {self.lower_orbit:.2f}")

    def update_orbits(self, current_price, time_elapsed, profit_pct, volatility=0.5, trend_strength=0.5):
        new_level = self._determine_protection_level(time_elapsed, profit_pct)

        if new_level != self.current_level:
            print(
                f"🔄 保护级别切换: {self.current_level} → {new_level} (盈利: {profit_pct:.2f}%, 持仓时间: {time_elapsed:.0f}秒)"
            )
            self.current_level = new_level

        old_upper = self.upper_orbit
        old_lower = self.lower_orbit

        self.upper_orbit = self.calculate_upper_orbit()
        self.lower_orbit = self.calculate_lower_orbit()

        if abs(self.upper_orbit - old_upper) > self.atr * 0.1 or abs(self.lower_orbit - old_lower) > self.atr * 0.1:
            print(
                f"📊 轨道更新: 止盈 {old_upper:.2f} → {self.upper_orbit:.2f}, 止损 {old_lower:.2f} → {self.lower_orbit:.2f}"
            )

    def _determine_protection_level(self, time_elapsed, profit_pct):
        if time_elapsed < PROTECTION_LEVELS['defensive']['activation_time'] or profit_pct < 0:
            return 'defensive'

        if profit_pct >= PROTECTION_LEVELS['aggressive']['min_profit_required']:
            return 'aggressive'

        if profit_pct >= PROTECTION_LEVELS['balanced']['min_profit_required']:
            return 'balanced'

        return 'defensive'

    def calculate_upper_orbit(self):
        config = PROTECTION_LEVELS[self.current_level]
        multiplier = config['take_profit_multiplier']

        if self.position_side == 'long':
            return self.entry_price + (self.atr * multiplier)
        return self.entry_price - (self.atr * multiplier)

    def calculate_lower_orbit(self):
        config = PROTECTION_LEVELS[self.current_level]
        multiplier = config['stop_loss_multiplier']

        if self.position_side == 'long':
            return self.entry_price - (self.atr * multiplier)
        return self.entry_price + (self.atr * multiplier)

    def get_current_level(self):
        return self.current_level

    def get_orbits(self):
        return {
            'upper_orbit': self.upper_orbit,
            'lower_orbit': self.lower_orbit,
            'level': self.current_level,
        }


class DynamicTakeProfit:
    """动态止盈计算"""

    def calculate_take_profit(self, entry_price, current_price, atr, market_condition='normal', profit_pct=0):
        if entry_price > 0:
            base_profit = abs((current_price - entry_price) / entry_price)
        else:
            base_profit = 0

        if base_profit < 0.001:
            take_profit = entry_price + (atr * 1.0) if current_price > entry_price else entry_price - (atr * 1.0)
        elif base_profit < 0.005:
            take_profit = current_price + (atr * 1.5) if current_price > entry_price else current_price - (atr * 1.5)
        else:
            take_profit = current_price + (atr * 1.8) if current_price > entry_price else current_price - (atr * 1.8)

        if market_condition == 'volatile':
            take_profit = take_profit + (atr * 0.2) if current_price > entry_price else take_profit - (atr * 0.2)
        elif market_condition == 'stable':
            take_profit = take_profit - (atr * 0.1) if current_price > entry_price else take_profit + (atr * 0.1)

        return take_profit


class ProgressiveProtection:
    """渐进式保护"""

    def calculate_dynamic_levels(self, current_profit, volatility, trend_strength):
        if current_profit > 0.01:
            stop_multiplier = 0.6 + (0.4 * trend_strength)
            take_profit_multiplier = 1.2 + (0.8 * trend_strength)
        else:
            stop_multiplier = 1.5 - (0.5 * volatility)
            take_profit_multiplier = 0.8 + (0.4 * trend_strength)

        stop_multiplier = max(0.5, min(2.0, stop_multiplier))
        take_profit_multiplier = max(0.5, min(2.5, take_profit_multiplier))
        return stop_multiplier, take_profit_multiplier


class RiskRewardOptimizer:
    """风险收益优化器"""

    def calculate_risk_reward_ratio(self, position_data):
        entry_price = position_data.get('entry_price', 0)
        stop_loss = position_data.get('stop_loss', 0)
        take_profit = position_data.get('take_profit', 0)
        position_side = position_data.get('position_side', 'long')

        if entry_price == 0:
            return 0

        if position_side == 'long':
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
        else:
            risk = abs(stop_loss - entry_price)
            reward = abs(entry_price - take_profit)

        if risk == 0:
            return 0
        return reward / risk

    def optimize_protection_levels(self, position_data, market_conditions):
        current_rr_ratio = self.calculate_risk_reward_ratio(position_data)

        if current_rr_ratio < 1.5:
            return self._adjust_for_better_rr(position_data, 'aggressive')
        if current_rr_ratio > 3:
            return self._adjust_for_better_rr(position_data, 'conservative')
        return self._maintain_current_levels(position_data)

    def _adjust_for_better_rr(self, position_data, strategy):
        entry_price = position_data.get('entry_price', 0)
        atr = position_data.get('atr', entry_price * 0.01)
        position_side = position_data.get('position_side', 'long')

        if strategy == 'aggressive':
            if position_side == 'long':
                stop_loss = entry_price - (atr * 1.0)
                take_profit = entry_price + (atr * 2.5)
            else:
                stop_loss = entry_price + (atr * 1.0)
                take_profit = entry_price - (atr * 2.5)
        else:
            if position_side == 'long':
                stop_loss = entry_price - (atr * 1.8)
                take_profit = entry_price + (atr * 2.0)
            else:
                stop_loss = entry_price + (atr * 1.8)
                take_profit = entry_price - (atr * 2.0)

        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'strategy': strategy,
        }

    def _maintain_current_levels(self, position_data):
        return {
            'stop_loss': position_data.get('stop_loss', 0),
            'take_profit': position_data.get('take_profit', 0),
            'strategy': 'maintain',
        }


__all__ = [
    'ProtectionOrbit',
    'DynamicTakeProfit',
    'ProgressiveProtection',
    'RiskRewardOptimizer',
]
