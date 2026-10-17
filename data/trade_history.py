"""Persist tracked spot fills and calculate realized outcomes without estimates."""
from __future__ import annotations

import json
import logging
import math
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("nexa.trade_history")
FILL_HISTORY_DAYS = 3
MAX_SEEN_FILL_IDS = 50_000


class TradeHistoryTracker:
    def __init__(self, path: Path) -> None:
        self.path = path

    def register_entry(self, inst_id: str, ord_id: str, registered_at: str) -> None:
        if not ord_id or ord_id.startswith("SIM_"):
            return
        state = self._load()
        state["tracked_orders"].setdefault(
            ord_id,
            {"inst_id": inst_id, "registered_at": registered_at, "saw_fill": False},
        )
        self._save(state)

    def sync_fills(self, fills: list[dict[str, Any]], synced_at: datetime | None = None) -> None:
        state = self._load()
        now = synced_at or datetime.now(timezone.utc)
        last_sync = _parse_datetime(state.get("last_sync_at"))
        if last_sync and now.astimezone(timezone.utc) - last_sync > timedelta(days=FILL_HISTORY_DAYS):
            state["history_gap"] = True

        seen = set(state["seen_fill_ids"])
        new_fill_ids = deque(state["seen_fill_ids"], maxlen=MAX_SEEN_FILL_IDS)
        ordered_fills = sorted(fills, key=lambda fill: _fill_timestamp(fill))

        for fill in ordered_fills:
            fill_id = _fill_id(fill)
            if not fill_id or fill_id in seen:
                continue
            side = str(fill.get("side", "")).lower()
            order_id = str(fill.get("ordId", ""))
            tracked_order = state["tracked_orders"].get(order_id)

            if side == "buy" and tracked_order and fill.get("instId") == tracked_order["inst_id"]:
                self._record_buy_fill(state, tracked_order, fill, fill_id)
            elif side == "sell":
                self._record_sell_fill(state, fill, fill_id)

            seen.add(fill_id)
            new_fill_ids.append(fill_id)

        state["seen_fill_ids"] = list(new_fill_ids)
        state["last_sync_at"] = now.astimezone(timezone.utc).isoformat()
        self._save(state)

    def summary(self, start: datetime, end: datetime) -> dict[str, Any]:
        state = self._load()
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        closed = [
            trade for trade in state["closed_trades"]
            if (closed_at := _parse_datetime(trade.get("closed_at"))) is not None
            and start_utc <= closed_at <= end_utc
        ]
        known_pnl = [
            trade for trade in closed
            if isinstance(trade.get("realized_pnl_usdt"), (int, float))
        ]
        pnls = [float(trade["realized_pnl_usdt"]) for trade in known_pnl]
        wins = sum(pnl > 0 for pnl in pnls)
        losses = sum(pnl < 0 for pnl in pnls)
        return {
            "closed_count": len(closed),
            "pnl_trade_count": len(known_pnl),
            "unknown_pnl_count": len(closed) - len(known_pnl),
            "wins": wins,
            "losses": losses,
            "breakeven": len(pnls) - wins - losses,
            "net_pnl_usdt": round(sum(pnls), 8),
            "win_rate_pct": round(wins / len(pnls) * 100, 1) if pnls else None,
            "open_positions": len(state["open_lots"]),
            "pending_entries": sum(not order["saw_fill"] for order in state["tracked_orders"].values()),
            "history_gap": bool(state.get("history_gap")),
            "last_sync_at": state.get("last_sync_at"),
        }

    def _record_buy_fill(
        self,
        state: dict[str, Any],
        tracked_order: dict[str, Any],
        fill: dict[str, Any],
        fill_id: str,
    ) -> None:
        values = _fill_values(fill)
        if values is None:
            log.error("Alış dolumu %s eksik/geçersiz alan içeriyor; PnL için lot açılamadı.", fill_id)
            return
        price, size, fee, fee_currency, timestamp = values
        base_currency, quote_currency = _currencies(str(fill["instId"]))
        fee_usdt = _fee_usdt(fee, fee_currency, price, base_currency, quote_currency)
        net_size = size + fee if fee_currency == base_currency else size
        if net_size <= 0:
            log.error("Alış dolumu %s net miktarı geçersiz.", fill_id)
            return

        fill_basis = price * size - fee_usdt if fee_usdt is not None else None
        lot = next(
            (
                item for item in state["open_lots"]
                if item["inst_id"] == str(fill["instId"])
                and item["ord_id"] == str(fill["ordId"])
            ),
            None,
        )
        if lot is None:
            state["open_lots"].append({
                "inst_id": str(fill["instId"]),
                "ord_id": str(fill["ordId"]),
                "fill_ids": [fill_id],
                "opened_at": timestamp.isoformat(),
                "remaining_qty": net_size,
                "basis_usdt": fill_basis,
                "realized_pnl_usdt": 0.0,
                "pnl_eligible": fee_usdt is not None,
            })
        else:
            lot["fill_ids"].append(fill_id)
            lot["remaining_qty"] += net_size
            if lot["basis_usdt"] is not None and fill_basis is not None:
                lot["basis_usdt"] += fill_basis
            else:
                lot["basis_usdt"] = None
                lot["pnl_eligible"] = False
        tracked_order["saw_fill"] = True

    def _record_sell_fill(self, state: dict[str, Any], fill: dict[str, Any], fill_id: str) -> None:
        values = _fill_values(fill)
        if values is None:
            log.error("Satış dolumu %s eksik/geçersiz alan içeriyor; eşleştirilemedi.", fill_id)
            return
        price, size, fee, fee_currency, timestamp = values
        inst_id = str(fill.get("instId", ""))
        base_currency, quote_currency = _currencies(inst_id)
        fee_usdt = _fee_usdt(fee, fee_currency, price, base_currency, quote_currency)
        amount_to_match = size - fee if fee_currency == base_currency else size
        net_proceeds = price * size + fee_usdt if fee_usdt is not None else None
        eligible_fee = fee_usdt is not None
        remaining_sale = amount_to_match

        for lot in state["open_lots"]:
            if remaining_sale <= 1e-12:
                break
            if lot["inst_id"] != inst_id:
                continue
            opened_at = _parse_datetime(lot["opened_at"])
            if opened_at is None or timestamp < opened_at:
                continue

            consumed = min(float(lot["remaining_qty"]), remaining_sale)
            fraction = consumed / amount_to_match
            if lot["basis_usdt"] is not None and eligible_fee and lot["pnl_eligible"]:
                allocated_basis = float(lot["basis_usdt"]) * consumed / float(
                    lot["remaining_qty"]
                )
                lot["realized_pnl_usdt"] += float(net_proceeds) * fraction - allocated_basis
                lot["basis_usdt"] = float(lot["basis_usdt"]) - allocated_basis
            else:
                lot["pnl_eligible"] = False
                lot["basis_usdt"] = None

            lot["remaining_qty"] = float(lot["remaining_qty"]) - consumed
            remaining_sale -= consumed

            if lot["remaining_qty"] <= 1e-10:
                state["closed_trades"].append({
                    "entry_ord_id": lot["ord_id"],
                    "entry_fill_ids": lot["fill_ids"],
                    "exit_fill_id": fill_id,
                    "closed_at": timestamp.isoformat(),
                    "realized_pnl_usdt": (
                        round(float(lot["realized_pnl_usdt"]), 8)
                        if lot["pnl_eligible"] else None
                    ),
                })

        state["open_lots"] = [
            lot for lot in state["open_lots"] if float(lot["remaining_qty"]) > 1e-10
        ]

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return _empty_state()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"İşlem geçmişi okunamadı: {self.path}: {error}") from error
        if not isinstance(data, dict):
            raise RuntimeError(f"İşlem geçmişi beklenen JSON nesnesi değil: {self.path}")
        state = _empty_state()
        for key in state:
            if key in data:
                state[key] = data[key]
        for key in ("tracked_orders",):
            if not isinstance(state[key], dict):
                raise RuntimeError(f"İşlem geçmişi alanı geçersiz: {key}")
        for key in ("open_lots", "closed_trades", "seen_fill_ids"):
            if not isinstance(state[key], list):
                raise RuntimeError(f"İşlem geçmişi alanı geçersiz: {key}")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as error:
            raise RuntimeError(f"İşlem geçmişi kaydedilemedi: {self.path}: {error}") from error


def _empty_state() -> dict[str, Any]:
    return {
        "tracked_orders": {},
        "open_lots": [],
        "closed_trades": [],
        "seen_fill_ids": [],
        "last_sync_at": None,
        "history_gap": False,
    }


def _fill_values(
    fill: dict[str, Any],
) -> tuple[float, float, float, str, datetime] | None:
    try:
        price = float(fill["fillPx"])
        size = float(fill["fillSz"])
        fee = float(fill.get("fee", 0) or 0)
        timestamp = datetime.fromtimestamp(float(fill["ts"]) / 1000, timezone.utc)
        fee_currency = str(fill.get("feeCcy", "")).upper()
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(number) for number in (price, size, fee)) or price <= 0 or size <= 0:
        return None
    return price, size, fee, fee_currency, timestamp


def _fee_usdt(
    fee: float,
    fee_currency: str,
    price: float,
    base_currency: str,
    quote_currency: str,
) -> float | None:
    if fee == 0:
        return 0.0
    if fee_currency == "USDT" or fee_currency == quote_currency == "USDT":
        return fee
    if fee_currency == base_currency:
        return fee * price
    return None


def _currencies(inst_id: str) -> tuple[str, str]:
    parts = inst_id.split("-")
    if len(parts) < 2:
        return "", ""
    return parts[0].upper(), parts[-1].upper()


def _fill_id(fill: dict[str, Any]) -> str:
    trade_id = fill.get("tradeId")
    if trade_id:
        return f"{fill.get('instId', '')}:{trade_id}"
    required = ("instId", "ordId", "side", "ts", "fillPx", "fillSz")
    if all(fill.get(key) is not None for key in required):
        return ":".join(str(fill[key]) for key in required)
    return ""


def _fill_timestamp(fill: dict[str, Any]) -> float:
    try:
        return float(fill.get("ts", 0))
    except (TypeError, ValueError):
        return 0.0


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
