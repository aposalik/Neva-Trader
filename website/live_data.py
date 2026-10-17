"""Sanitized, cached OKX demo-account and live-market data for the local web UI."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from data_snapshot import CONFIG_PATH, PROJECT_ROOT, _load_json

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.okx_client import OKXCLIError, OKXClient  # noqa: E402

TRADE_HISTORY_PATH = PROJECT_ROOT / "trade_history.json"
_CACHE_TTL_SECONDS = 12
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_last_success: dict[str, Any] | None = None

_ALLOWED_BARS = {"1m", "5m", "15m", "30m", "1H", "4H", "1D"}


def _safe_error(error: Exception) -> str:
    text = str(error)
    if "Error:" in text:
        text = text.split("Error:", 1)[1].splitlines()[0].strip()
    else:
        lines = [line.strip() for line in text.splitlines() if line.strip() and "UNDICI-EHPA" not in line and not line.startswith("(node:")]
        text = lines[0] if lines else error.__class__.__name__
    return text[:180]


def _sanitize_candles(rows: list[list[str]]) -> list[dict[str, Any]]:
    candles: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 6:
            continue
        try:
            candles.append({
                "ts": int(float(row[0])),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "confirmed": str(row[8]) == "1" if len(row) > 8 else True,
            })
        except (TypeError, ValueError):
            continue
    candles.sort(key=lambda item: item["ts"])
    return candles


def _trade_summary(last_price: float | None) -> dict[str, Any]:
    data = _load_json(TRADE_HISTORY_PATH, {})
    open_lots = data.get("open_lots") if isinstance(data.get("open_lots"), list) else []
    closed = data.get("closed_trades") if isinstance(data.get("closed_trades"), list) else []
    realized_values = [
        float(item["realized_pnl_usdt"])
        for item in closed
        if isinstance(item, dict) and isinstance(item.get("realized_pnl_usdt"), (int, float))
    ]
    unrealized: float | None = 0.0 if last_price is not None else None
    if last_price is not None:
        for lot in open_lots:
            try:
                basis = lot.get("basis_usdt")
                quantity = float(lot.get("remaining_qty", 0))
                if not isinstance(basis, (int, float)):
                    unrealized = None
                    break
                unrealized += quantity * last_price - float(basis)
            except (TypeError, ValueError):
                unrealized = None
                break
    realized = sum(realized_values)
    return {
        "realizedPnlUsdt": round(realized, 8),
        "unrealizedPnlUsdt": round(unrealized, 8) if unrealized is not None else None,
        "netPnlUsdt": round(realized + unrealized, 8) if unrealized is not None else round(realized, 8),
        "openLots": len(open_lots),
        "closedTrades": len(closed),
        "pnlTradeCount": len(realized_values),
        "lastSyncAt": data.get("last_sync_at"),
        "historyGap": bool(data.get("history_gap")),
    }


def _sanitize_fills(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows[:limit]:
        try:
            output.append({
                "side": str(row.get("side", "")).upper(),
                "price": float(row.get("fillPx", 0)),
                "size": float(row.get("fillSz", 0)),
                "fee": float(row.get("fee", 0) or 0),
                "feeCurrency": str(row.get("feeCcy", "")),
                "timestamp": int(float(row.get("ts", 0))),
            })
        except (TypeError, ValueError):
            continue
    return output


def _call(name: str, function: Callable[[], Any]) -> tuple[str, Any, str | None]:
    try:
        return name, function(), None
    except (OKXCLIError, RuntimeError, ValueError) as error:
        return name, None, _safe_error(error)


def _fetch(bar: str, limit: int) -> dict[str, Any]:
    global _last_success
    config = _load_json(CONFIG_PATH, {})
    instrument = str(config.get("instrument", "AVAX-USDT"))
    is_demo = bool((config.get("execution") or {}).get("is_demo", True))
    cli = config.get("cli") or {}
    client = OKXClient(
        demo=is_demo,
        timeout=min(int(cli.get("timeout_sec", 25)), 12),
        max_retries=1,
    )

    jobs: dict[str, Callable[[], Any]] = {
        "ticker": lambda: client.ticker(instrument),
        "candles": lambda: client.candles(instrument, bar, limit),
        "balances": client.balances,
        "fills": lambda: client.spot_fills(instrument),
        "orders": lambda: client.open_orders(instrument),
        "algoOrders": lambda: client.open_algo_orders(instrument),
    }
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="nexa-okx") as pool:
        futures = [pool.submit(_call, name, function) for name, function in jobs.items()]
        for future in as_completed(futures):
            name, value, error = future.result()
            if error:
                errors[name] = error
            else:
                results[name] = value

    ticker = results.get("ticker") if isinstance(results.get("ticker"), dict) else {}
    last_price = ticker.get("last") if isinstance(ticker.get("last"), (int, float)) else None
    balances = results.get("balances") if isinstance(results.get("balances"), dict) else {}
    usdt = balances.get("USDT") if isinstance(balances.get("USDT"), dict) else {}
    avax = balances.get("AVAX") if isinstance(balances.get("AVAX"), dict) else {}
    usdt_total = usdt.get("total") if isinstance(usdt.get("total"), (int, float)) else None
    avax_total = avax.get("total") if isinstance(avax.get("total"), (int, float)) else None
    avax_value = avax_total * last_price if avax_total is not None and last_price is not None else None
    portfolio_value = usdt_total + avax_value if usdt_total is not None and avax_value is not None else usdt_total
    trade_summary = _trade_summary(last_price)

    payload = {
        "ok": bool(ticker) or bool(balances),
        "environment": "DEMO" if is_demo else "LIVE",
        "isScriptedScenario": False,
        "marketDataStatus": "LIVE" if ticker and results.get("candles") is not None else "UNAVAILABLE",
        "accountDataStatus": "OKX_DEMO" if is_demo and balances else ("OKX_LIVE" if balances else "UNAVAILABLE"),
        "instrument": instrument,
        "bar": bar,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ticker": ticker,
        "candles": _sanitize_candles(results.get("candles") or []),
        "wallet": {
            "usdtAvailable": usdt.get("avail") if isinstance(usdt.get("avail"), (int, float)) else None,
            "usdtTotal": usdt_total,
            "avaxAvailable": avax.get("avail") if isinstance(avax.get("avail"), (int, float)) else None,
            "avaxTotal": avax_total,
            "avaxValueUsdt": round(avax_value, 8) if avax_value is not None else None,
            "portfolioValueUsdt": round(portfolio_value, 8) if portfolio_value is not None else None,
            **trade_summary,
        },
        "activity": {
            "openOrders": len(results.get("orders") or []),
            "openProtectionOrders": len(results.get("algoOrders") or []),
            "recentFills": _sanitize_fills(results.get("fills") or []),
        },
        "errors": errors,
    }
    if payload["ok"]:
        _last_success = payload
    elif _last_success is not None:
        payload["lastSuccessfulAt"] = _last_success.get("generatedAt")
    return payload


def build_live_snapshot(bar: str = "15m", limit: int = 100, force: bool = False) -> dict[str, Any]:
    normalized_bar = bar if bar in _ALLOWED_BARS else "15m"
    normalized_limit = max(20, min(int(limit), 200))
    key = f"{normalized_bar}:{normalized_limit}"
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and not force and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
    payload = _fetch(normalized_bar, normalized_limit)
    with _cache_lock:
        _cache[key] = (time.monotonic(), payload)
    return payload
