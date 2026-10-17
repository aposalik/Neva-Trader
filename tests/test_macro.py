"""Makro ekonomik takvim blackout testleri."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from data import macro
from models import Status


def test_tradingview_calendar_event_blocks_trading(tmp_path, monkeypatch):
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    calendar_path = tmp_path / "takvim_verileri.json"
    calendar_path.write_text(
        json.dumps({
            "yuksek_etkili_haberler": [{
                "tarih_utc": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
                "ulke": "US",
                "baslik": "Core Inflation Rate",
            }]
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(macro, "now_utc", lambda: now)

    result = macro.fetch_macro_status(
        okx=None,
        config={"pillars": {"macro": {"source": "mock", "blackout_minutes": 30}}},
        mock_data={"macro": {"events": []}},
        calendar_path=calendar_path,
    )

    assert result.status == Status.FAIL
    assert result.metrics["blackout"] is True
    assert "US - Core Inflation Rate" in result.reason
