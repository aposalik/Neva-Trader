from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WEBSITE_DIR = Path(__file__).resolve().parents[1] / "website"
if str(WEBSITE_DIR) not in sys.path:
    sys.path.insert(0, str(WEBSITE_DIR))

import agent_control  # noqa: E402
import live_data  # noqa: E402


def _config(path: Path) -> None:
    path.write_text(json.dumps({
        "execution": {"is_demo": True},
        "risk": {
            "position_size_pct": 5.0,
            "stop_loss_pct": 1.0,
            "take_profit_pct": 2.0,
            "risk_reward_ratio": 2.0,
            "max_daily_trades": 4,
            "max_daily_loss_pct": 3.0,
            "max_spread_pct": 0.15,
        },
    }), encoding="utf-8")


def test_save_rules_validates_and_persists_atomically(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    _config(config_path)
    monkeypatch.setattr(agent_control, "CONFIG_PATH", config_path)
    monkeypatch.setattr(agent_control, "agent_status", lambda: {"running": False})

    result = agent_control.save_rules({
        "positionSizePct": 6.5,
        "stopLossPct": 1.25,
        "takeProfitPct": 2.5,
        "maxDailyTrades": 5,
        "maxDailyLossPct": 3.5,
    })

    saved = json.loads(config_path.read_text(encoding="utf-8"))["risk"]
    assert saved["position_size_pct"] == 6.5
    assert saved["risk_reward_ratio"] == 2.0
    assert result["maxDailyTrades"] == 5
    assert not config_path.with_suffix(".json.tmp").exists()


def test_save_rules_rejects_changes_while_agent_runs(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    _config(config_path)
    monkeypatch.setattr(agent_control, "CONFIG_PATH", config_path)
    monkeypatch.setattr(agent_control, "agent_status", lambda: {"running": True})

    with pytest.raises(agent_control.ControlError, match="ajanı durdurun"):
        agent_control.save_rules({})


def test_save_rules_rejects_unsafe_range(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    _config(config_path)
    monkeypatch.setattr(agent_control, "CONFIG_PATH", config_path)
    monkeypatch.setattr(agent_control, "agent_status", lambda: {"running": False})

    with pytest.raises(agent_control.ControlError, match="0.1–20.0"):
        agent_control.save_rules({
            "positionSizePct": 75,
            "stopLossPct": 1,
            "takeProfitPct": 2,
            "maxDailyTrades": 4,
            "maxDailyLossPct": 3,
        })


def test_candles_are_sanitized_and_sorted():
    rows = [
        ["2000", "10", "12", "9", "11", "100", "0", "0", "1"],
        ["1000", "8", "11", "7", "10", "80", "0", "0", "1"],
        ["bad"],
    ]
    result = live_data._sanitize_candles(rows)
    assert [item["ts"] for item in result] == [1000, 2000]
    assert result[-1]["close"] == 11.0
    assert set(result[-1]) == {"ts", "open", "high", "low", "close", "volume", "confirmed"}
