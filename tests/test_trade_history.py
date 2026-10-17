from __future__ import annotations

from datetime import datetime, timezone

from data.trade_history import TradeHistoryTracker


def _fill(
    trade_id: str,
    order_id: str,
    side: str,
    price: float,
    size: float,
    fee: float,
    timestamp: datetime,
) -> dict:
    return {
        "tradeId": trade_id,
        "ordId": order_id,
        "instId": "AVAX-USDT",
        "side": side,
        "fillPx": str(price),
        "fillSz": str(size),
        "fee": str(fee),
        "feeCcy": "USDT",
        "ts": str(int(timestamp.timestamp() * 1000)),
    }


def test_tracker_calculates_fee_adjusted_realized_pnl_and_deduplicates(tmp_path):
    path = tmp_path / "trade_history.json"
    tracker = TradeHistoryTracker(path)
    opened_at = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    closed_at = datetime(2026, 10, 17, 11, 0, tzinfo=timezone.utc)
    tracker.register_entry("AVAX-USDT", "buy-order-1", opened_at.isoformat())

    fills = [
        _fill("buy-fill", "buy-order-1", "buy", 10, 2, -0.01, opened_at),
        _fill("sell-fill", "sell-order-1", "sell", 12, 2, -0.02, closed_at),
    ]
    tracker.sync_fills(
        fills,
        synced_at=datetime(2026, 10, 17, 11, 1, tzinfo=timezone.utc),
    )
    tracker.sync_fills(
        fills,
        synced_at=datetime(2026, 10, 17, 11, 2, tzinfo=timezone.utc),
    )

    summary = tracker.summary(
        datetime(2026, 10, 16, tzinfo=timezone.utc),
        datetime(2026, 10, 18, tzinfo=timezone.utc),
    )
    assert summary["closed_count"] == 1
    assert summary["pnl_trade_count"] == 1
    assert summary["wins"] == 1
    assert summary["net_pnl_usdt"] == 3.97
    assert summary["open_positions"] == 0


def test_tracker_only_uses_buy_orders_registered_by_the_application(tmp_path):
    tracker = TradeHistoryTracker(tmp_path / "trade_history.json")
    timestamp = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    tracker.sync_fills(
        [_fill("manual-buy", "manual-order", "buy", 10, 2, -0.01, timestamp)],
        synced_at=timestamp,
    )

    summary = tracker.summary(
        datetime(2026, 10, 16, tzinfo=timezone.utc),
        datetime(2026, 10, 18, tzinfo=timezone.utc),
    )
    assert summary["open_positions"] == 0
    assert summary["closed_count"] == 0


def test_tracker_groups_multiple_fills_of_one_order_into_one_trade(tmp_path):
    tracker = TradeHistoryTracker(tmp_path / "trade_history.json")
    opened_at = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    closed_at = datetime(2026, 10, 17, 11, 0, tzinfo=timezone.utc)
    tracker.register_entry("AVAX-USDT", "buy-order-1", opened_at.isoformat())
    fills = [
        _fill("buy-fill-1", "buy-order-1", "buy", 10, 1, 0, opened_at),
        _fill("buy-fill-2", "buy-order-1", "buy", 11, 1, 0, opened_at),
        _fill("sell-fill-1", "sell-order-1", "sell", 12, 1, 0, closed_at),
        _fill("sell-fill-2", "sell-order-2", "sell", 13, 1, 0, closed_at),
    ]
    tracker.sync_fills(
        fills,
        synced_at=datetime(2026, 10, 17, 11, 1, tzinfo=timezone.utc),
    )

    summary = tracker.summary(
        datetime(2026, 10, 16, tzinfo=timezone.utc),
        datetime(2026, 10, 18, tzinfo=timezone.utc),
    )
    assert summary["closed_count"] == 1
    assert summary["net_pnl_usdt"] == 4


def test_tracker_flags_gaps_longer_than_okx_fill_history_window(tmp_path):
    tracker = TradeHistoryTracker(tmp_path / "trade_history.json")
    first_sync = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    tracker.sync_fills([], synced_at=first_sync)
    tracker.sync_fills([], synced_at=datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc))

    summary = tracker.summary(
        datetime(2026, 10, 16, tzinfo=timezone.utc),
        datetime(2026, 10, 22, tzinfo=timezone.utc),
    )
    assert summary["history_gap"] is True
