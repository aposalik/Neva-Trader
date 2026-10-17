from __future__ import annotations

import pytest
from types import SimpleNamespace

from data import okx_client
from data.okx_client import OKXClient
from execution import executor
from execution.executor import OKXExecutor


def test_okx_client_supports_legacy_is_demo_parameter(monkeypatch):
    monkeypatch.setattr(okx_client.shutil, "which", lambda _: "okx")

    client = OKXClient(is_demo=False)

    assert client.demo is False
    assert client.trade_flags[0] == "--live"


def test_okx_subprocess_bypasses_interfering_proxy(monkeypatch):
    monkeypatch.setattr(okx_client.shutil, "which", lambda _: "okx")
    monkeypatch.setenv("HTTP_PROXY", "http://local-proxy.invalid")
    monkeypatch.setenv("HTTPS_PROXY", "http://local-proxy.invalid")
    captured = {}

    def fake_run(*args, **kwargs):
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout='[{"last":"9.5"}]', stderr="")

    monkeypatch.setattr(okx_client.subprocess, "run", fake_run)
    client = OKXClient(is_demo=True, max_retries=1)

    assert client._run(["market", "ticker", "AVAX-USDT"])[0]["last"] == "9.5"
    assert "HTTP_PROXY" not in captured["env"]
    assert "HTTPS_PROXY" not in captured["env"]


def test_legacy_balance_and_ticker_helpers():
    client = object.__new__(OKXClient)
    client.balances = lambda: {
        "USDT": {"avail": 12.5, "total": 15.0},
        "AVAX": {"avail": 2.0, "total": 2.0},
    }
    client.ticker = lambda inst_id: {"last": 9.87}

    assert client.get_balances() == {"USDT": 12.5, "AVAX": 2.0}
    assert client.get_ticker_price() == 9.87


def test_legacy_order_helper_rejects_live_mode():
    with pytest.raises(ValueError, match="yalnızca demo modunda"):
        OKXExecutor(is_demo=False)


def test_legacy_order_helper_converts_usdt_amount_to_base_size(monkeypatch):
    captured = {}

    class FakeOKXClient:
        def __init__(self, demo):
            assert demo is True

        def ticker(self, inst_id):
            return {"last": 10.0}

    class FakeOrderExecutor:
        def __init__(self, okx, config):
            pass

        def execute_plan(self, plan):
            captured["plan"] = plan
            return {"success": True}

    monkeypatch.setattr(executor, "OKXClient", FakeOKXClient)
    monkeypatch.setattr(executor, "OrderExecutor", FakeOrderExecutor)

    result = OKXExecutor().place_spot_buy(
        inst_id="AVAX-USDT",
        size=10.0,
        tp_trigger=10.24,
        sl_trigger=9.88,
    )

    assert result["success"] is True
    assert captured["plan"].size == 1.0
    assert captured["plan"].notional_usdt == 10.0
