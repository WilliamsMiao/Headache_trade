## Plan: Unify Trading Logic for True Backtesting

The research confirms a critical issue: **The Backtest System and Production Bot are completely decoupled.** They use different code for indicators and signals. Testing the current backtester provides zero guarantee about production performance.

To fix this, implement a "Unified Strategy Interface" pattern. This ensures that Backtest and Production call the exact same Python function to make decisions.

### Steps
1. **Create `trading_bots/base_strategy.py`**
   - Define `abstract class BaseStrategy` with `calculate_indicators(df)` and `generate_signal(context)`.
   - Define `class MarketContext` payload (OHLCV, balance, positions) to decouple from CCXT.

2. **Move Logic to `trading_bots/strategies/trend_king.py`**
   - Create a concrete strategy class `TrendKingStrategy`.
   - Migrate logic from `main_bot.py` (loops/executions) and `signals.py` (logic) into this class.
   - **Crucial:** Ensure it uses `trading_bots.indicators` so math is identical.

3. **Refactor `trading_bots/main_bot.py` (Production)**
   - Initialize `TrendKingStrategy`.
   - In the main loop, build `MarketContext` from live CCXT data, call `strategy.generate_signal()`, and execute the result.

4. **Refactor `scripts/backtest_engine.py` (Backtest)**
   - Remove local indicator/signal functions.
   - Initialize `TrendKingStrategy`.
   - In the loop, build `MarketContext` from historical JSON, call `strategy.generate_signal()`, and simulate the result.

### Further Considerations
1. **AI Integration**: Production calls DeepSeek API; backtesting with live API is slow/expensive. Add a `mock_ai=True` flag or support a "Slow Backtest" that actually calls the API.
2. **Config Injection**: Ensure `TRADE_CONFIG` is injectable so the optimizer can tune it dynamically.

This plan guarantees that if the backtest says "BUY", the production bot would have done the same in that situation.
