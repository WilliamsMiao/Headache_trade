"""AI Commander: produces slow, high-level guidance for the soldier loop.

Runs independently from the fast per-candle execution. It periodically calls
DeepSeek to infer macro bias and risk posture, then writes a compact guidance
file the soldier reads synchronously.
"""

import os
import time
import traceback
from datetime import datetime
from pathlib import Path

from trading_bots.guidance import save_guidance
from trading_bots.main_bot import get_btc_ohlcv_enhanced
from trading_bots.signals import analyze_with_deepseek_trend_king_with_retry


LOG_PATH = Path(os.getenv("COMMANDER_LOG_PATH", "logs/commander.log"))
MAX_LOG_BYTES = 512_000
LOG_BACKUPS = 3


def rotate_log(path: Path, max_bytes: int = MAX_LOG_BYTES, backups: int = LOG_BACKUPS):
    if not path.exists() or path.stat().st_size < max_bytes:
        return
    for idx in range(backups - 1, 0, -1):
        older = path.with_suffix(path.suffix + f".{idx}")
        newer = path.with_suffix(path.suffix + f".{idx + 1}")
        if older.exists():
            older.rename(newer)
    rotated = path.with_suffix(path.suffix + ".1")
    path.rename(rotated)


def log(msg: str):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(LOG_PATH)
    timestamp = datetime.utcnow().isoformat() + "Z"
    line = f"[{timestamp}] {msg}"
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def to_guidance(signal_data):
    """Translate DeepSeek response into commander guidance tokens."""
    signal = signal_data.get("signal", "HOLD")
    risk_assessment = str(signal_data.get("risk_assessment", "中风险"))

    if signal == "BUY":
        bias = "BULLISH"
    elif signal == "SELL":
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    if "高风险" in risk_assessment:
        vol_mode = "DEFENSIVE"
    elif "低风险" in risk_assessment:
        vol_mode = "STANDARD"
    else:
        vol_mode = "STANDARD"

    return {
        "bias": bias,
        "volatility_mode": vol_mode,
        "reason": signal_data.get("reason", "AI commander refresh"),
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


def update_guidance_once():
    try:
        price_data = get_btc_ohlcv_enhanced()
        if not price_data:
            log("Commander: 获取行情失败，保持当前指导")
            return

        signal_data = analyze_with_deepseek_trend_king_with_retry(price_data)
        guidance = to_guidance(signal_data)
        save_guidance(guidance)
        log(f"Commander 更新: bias={guidance['bias']} vol={guidance['volatility_mode']}")
    except Exception as exc:
        log(f"Commander 异常: {exc}")
        traceback.print_exc()


def main():
    interval_min = int(os.getenv("COMMANDER_INTERVAL_MINUTES", "60"))
    log(f"AI Commander 启动，刷新间隔: {interval_min} 分钟")
    while True:
        update_guidance_once()
        time.sleep(max(60, interval_min * 60))


if __name__ == "__main__":
    main()
