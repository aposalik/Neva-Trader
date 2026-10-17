"""Build the read-only website snapshot from Nexa-Trader audit files."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "decisions.log"
CONFIG_PATH = PROJECT_ROOT / "config.json"
STATE_PATH = PROJECT_ROOT / "state.json"


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _load_records(limit: int = 1000) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Website intentionally excludes scripted/demo scenarios and simulated pillars.
        if record.get("scenario"):
            continue
        pillars = record.get("pillars") or []
        if any(str(p.get("source", "")).upper() == "SIMULATED" for p in pillars):
            continue
        records.append(record)
    return records


def _pillar_key(name: str) -> str:
    lowered = name.lower()
    if "teknik" in lowered:
        return "technical"
    if "on-chain" in lowered:
        return "onchain"
    if "haber" in lowered:
        return "news"
    if "makro" in lowered:
        return "macro"
    return "other"


def _clean_pillar(pillar: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": _pillar_key(str(pillar.get("name", ""))),
        "name": pillar.get("name", "Signal"),
        "status": pillar.get("status", "NEUTRAL"),
        "source": pillar.get("source_label") or pillar.get("source", "UNKNOWN"),
        "reason": pillar.get("reason", "No explanation recorded."),
        "metrics": pillar.get("metrics") or {},
    }


def _clean_decision(record: dict[str, Any]) -> dict[str, Any]:
    market = record.get("market") or {}
    return {
        "timestamp": record.get("timestamp", "—"),
        "action": record.get("action", "NO_TRADE"),
        "reasons": record.get("reasons") or [],
        "pillars": [_clean_pillar(p) for p in record.get("pillars") or []],
        "market": {
            "price": market.get("price"),
            "bid": market.get("bid"),
            "ask": market.get("ask"),
        },
    }


def build_snapshot() -> dict[str, Any]:
    records = _load_records()
    clean = [_clean_decision(record) for record in records]
    latest = clean[-1] if clean else None
    config = _load_json(CONFIG_PATH, {})
    state = _load_json(STATE_PATH, {})
    actions = Counter(item["action"] for item in clean)
    pillar_totals: dict[str, Counter[str]] = {
        key: Counter() for key in ("technical", "onchain", "news", "macro")
    }
    source_totals: Counter[str] = Counter()
    for decision in clean:
        for pillar in decision["pillars"]:
            key = pillar["key"]
            if key in pillar_totals:
                pillar_totals[key][pillar["status"]] += 1
            source_totals[pillar["source"]] += 1

    chart = []
    for decision in clean[-48:]:
        price = decision["market"].get("price")
        if isinstance(price, (int, float)):
            chart.append({"timestamp": decision["timestamp"], "price": price})

    risk = config.get("risk") or {}
    return {
        "instrument": config.get("instrument", "AVAX-USDT"),
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "latest": latest,
        "history": list(reversed(clean[-10:])),
        "chart": chart,
        "summary": {
            "total": len(clean),
            "actions": dict(actions),
            "pillarTotals": {key: dict(value) for key, value in pillar_totals.items()},
            "sources": dict(source_totals),
        },
        "risk": {
            "positionSizePct": risk.get("position_size_pct", 5.0),
            "stopLossPct": risk.get("stop_loss_pct", 1.0),
            "takeProfitPct": risk.get("take_profit_pct", 2.0),
            "riskRewardRatio": risk.get("risk_reward_ratio", 2.0),
            "maxDailyTrades": risk.get("max_daily_trades", 4),
            "maxDailyLossPct": risk.get("max_daily_loss_pct", 3.0),
            "maxSpreadPct": risk.get("max_spread_pct", 0.15),
        },
        "session": {
            "date": state.get("date"),
            "tradesCount": state.get("trades_count", 0),
            "dailyLossPct": state.get("daily_loss_pct", 0.0),
        },
    }


def write_static_snapshot(path: Path | None = None) -> Path:
    target = path or (Path(__file__).resolve().parent / "assets" / "snapshot.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(write_static_snapshot())
