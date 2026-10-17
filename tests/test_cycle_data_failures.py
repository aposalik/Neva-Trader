from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import main
from models import PillarResult, Status


class FailingBalanceClient:
    def balances(self):
        raise main.OKXCLIError("temporary API failure")

    def ticker(self, inst_id):
        return {"last": 20.0, "bid": 19.99, "ask": 20.01, "ts": 0}

    def instrument(self, inst_id):
        return {"lotSz": 0.1, "tickSz": 0.01, "minSz": 0.1}

    def open_orders(self, inst_id):
        return []

    def open_algo_orders(self, inst_id):
        return []

    def candles(self, inst_id, bar, limit):
        return []

    def spot_fills(self, inst_id):
        return []


class BuySignalEngine:
    def evaluate(self, **kwargs):
        return "BUY", [], [
            PillarResult(name="Test", status=Status.PASS, reason="OK"),
        ]


class NeverExecute:
    def execute_plan(self, *args, **kwargs):
        raise AssertionError("An order must not be executed with missing account data")


class CaptureUI:
    def render_cycle(self, decision, balance_usdt, pair, mode_str):
        self.balance_usdt = balance_usdt


def test_cycle_blocks_trade_when_balance_cannot_be_read(monkeypatch, tmp_path):
    engine = main.NexaTraderEngine.__new__(main.NexaTraderEngine)
    engine.config = {"technical": {}}
    engine.mock_data = {}
    engine.okx = FailingBalanceClient()
    engine.inst_id = "AVAX-USDT"
    engine.signal_engine = BuySignalEngine()
    engine.guardrail = SimpleNamespace(
        validate_execution=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Guardrails must not run with missing account data")
        ),
    )
    engine.executor = NeverExecute()
    engine.trade_history = main.TradeHistoryTracker(tmp_path / "trade_history.json")
    engine.is_demo = True
    engine.dry_run = True
    engine.ui = CaptureUI()

    passing = PillarResult(name="Test", status=Status.PASS, reason="OK")
    monkeypatch.setattr(main, "fetch_onchain_metrics", lambda *args: passing)
    monkeypatch.setattr(main, "fetch_news_sentiment", lambda *args: passing)
    monkeypatch.setattr(main, "fetch_macro_status", lambda **kwargs: passing)
    monkeypatch.setattr(main, "evaluate_technical_strategy", lambda *args: passing)
    monkeypatch.setattr(main, "append_jsonl", lambda *args: None)
    monkeypatch.setattr(main, "refresh_history_review", lambda: True)
    monkeypatch.setitem(sys.modules, "export_reports", SimpleNamespace(export_decisions=lambda *args: None))

    decision = engine.run_single_cycle()

    assert decision.action == "BLOCKED"
    assert decision.plan is None
    assert decision.execution is None
    assert decision.market["price"] == 20.0
    assert "temporary API failure" in " ".join(decision.reasons)
    assert engine.ui.balance_usdt is None
