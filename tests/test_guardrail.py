"""Pozisyon boyutlandırıcı ve Guardrail kural denetimi birim testleri."""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from models import PillarResult, Source, Status
from risk.guardrail import GuardrailManager
from risk.position_sizer import calculate_order_plan


@pytest.fixture
def sample_config():
    return {
        "instrument": "AVAX-USDT",
        "risk": {
            "position_size_pct": 5.0,
            "stop_loss_pct": 1.2,
            "risk_reward_ratio": 2.0,
            "max_daily_trades": 4,
            "max_daily_loss_pct": 3.0,
            "max_spread_pct": 0.15,
            "min_position_usdt": 5.0,
        },
        "execution": {
            "fee_pct": 0.1,
        },
    }


@pytest.fixture
def sample_instrument():
    return {
        "lotSz": 0.000001,
        "tickSz": 0.001,
        "minSz": 0.1,
    }


def test_position_sizer_exact_rr(sample_config, sample_instrument):
    plan = calculate_order_plan(
        balance_usdt=5000.0,
        entry_price=10.0,
        config=sample_config,
        instrument=sample_instrument,
    )

    # %5 bakiye = $250
    assert plan.notional_usdt == 250.0
    assert plan.size == 25.0
    # Stop-Loss: %1.2 -> 10.0 * (1 - 0.012) = 9.880
    assert plan.sl_price == 9.880
    # Take-Profit: %2.4 -> 10.0 * (1 + 0.024) = 10.240
    assert plan.tp_price == 10.240
    assert plan.take_profit_pct == 2.4
    assert plan.risk_reward_ratio == 2.0
    # Net R/R komisyon sonrası > 1.5 olmalı
    assert plan.net_rr_after_fees > 1.5


def test_guardrail_spread_block(sample_config, sample_instrument):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        state_path = Path(tf.name)

    gm = GuardrailManager(sample_config, state_path)
    plan = calculate_order_plan(5000.0, 10.0, sample_config, sample_instrument)

    # Aşırı geniş spread: bid=10.0, ask=10.1 (%1.0 spread > %0.15 limit)
    ticker = {"bid": 10.0, "ask": 10.1, "last": 10.0}
    macro_ok = PillarResult(name="Macro", status=Status.PASS, reason="OK")

    allowed, reason = gm.validate_execution(
        plan=plan,
        balance_usdt=5000.0,
        ticker_data=ticker,
        instrument=sample_instrument,
        open_orders=[],
        open_algo_orders=[],
        base_asset_balance=0.0,
        macro_result=macro_ok,
    )
    assert allowed is False
    assert "Alış-Satış makası aşırı geniş" in reason


def test_guardrail_open_position_block(sample_config, sample_instrument):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        state_path = Path(tf.name)

    gm = GuardrailManager(sample_config, state_path)
    plan = calculate_order_plan(5000.0, 10.0, sample_config, sample_instrument)
    ticker = {"bid": 10.0, "ask": 10.005, "last": 10.0}
    macro_ok = PillarResult(name="Macro", status=Status.PASS, reason="OK")

    # Mevcut açık emir varsa bloke etmeli
    allowed, reason = gm.validate_execution(
        plan=plan,
        balance_usdt=5000.0,
        ticker_data=ticker,
        instrument=sample_instrument,
        open_orders=[{"ordId": "123"}],
        open_algo_orders=[],
        base_asset_balance=0.0,
        macro_result=macro_ok,
    )
    assert allowed is False
    assert "bekleyen spot emir mevcut" in reason


def test_guardrail_kill_switch_block(sample_config, sample_instrument):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        state_path = Path(tf.name)

    gm = GuardrailManager(sample_config, state_path)
    # Günlük zarar %3.5 yap (%3.0 limit aşılmış)
    gm.record_trade_closed(pnl_usdt=-175.0, balance_usdt=5000.0)

    plan = calculate_order_plan(5000.0, 10.0, sample_config, sample_instrument)
    ticker = {"bid": 10.0, "ask": 10.005, "last": 10.0}
    macro_ok = PillarResult(name="Macro", status=Status.PASS, reason="OK")

    allowed, reason = gm.validate_execution(
        plan=plan,
        balance_usdt=5000.0,
        ticker_data=ticker,
        instrument=sample_instrument,
        open_orders=[],
        open_algo_orders=[],
        base_asset_balance=0.0,
        macro_result=macro_ok,
    )
    assert allowed is False
    assert "Kill-Switch devrede" in reason
