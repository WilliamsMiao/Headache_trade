"""Shared AI guidance state loader/saver.

The "Commander" updates a small JSON blob. The "Soldier" reads it fast and
non-blocking. This avoids blocking the main trading loop on API latency.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

DEFAULT_GUIDANCE = {
    "bias": "NEUTRAL",  # NEUTRAL | BULLISH | BEARISH
    "volatility_mode": "STANDARD",  # STANDARD | HIGH_RISK | DEFENSIVE
    "reason": "Default fallback guidance",
    "last_updated": "1970-01-01T00:00:00Z",
}

GUIDANCE_PATH = Path(os.getenv("GUIDANCE_PATH", "data/guidance.json"))


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def load_guidance(path: Path = GUIDANCE_PATH) -> Dict[str, Any]:
    """Load guidance with safe defaults."""
    raw = _load_json(path)
    guidance = {**DEFAULT_GUIDANCE, **raw}
    # Normalize strings to upper-case tokens
    guidance["bias"] = str(guidance.get("bias", "NEUTRAL")).upper()
    guidance["volatility_mode"] = str(guidance.get("volatility_mode", "STANDARD")).upper()
    if "last_updated" not in guidance or not guidance["last_updated"]:
        guidance["last_updated"] = DEFAULT_GUIDANCE["last_updated"]
    return guidance


def save_guidance(guidance: Dict[str, Any], path: Path = GUIDANCE_PATH) -> None:
    guidance = {**DEFAULT_GUIDANCE, **guidance}
    if "last_updated" not in guidance or not guidance["last_updated"]:
        guidance["last_updated"] = datetime.utcnow().isoformat() + "Z"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(guidance, f, ensure_ascii=False, indent=2)


__all__ = ["load_guidance", "save_guidance", "GUIDANCE_PATH", "DEFAULT_GUIDANCE"]
