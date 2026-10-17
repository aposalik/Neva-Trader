from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from data.history import analyze_history, format_history_report
from main import refresh_history_review


def _record(timestamp: str, action: str, pillar_status: str, source: str = "LIVE") -> dict:
    return {
        "timestamp": timestamp,
        "action": action,
        "pillars": [
            {"name": "Teknik Analiz", "status": pillar_status, "source": source},
        ],
        "execution": None,
    }


def test_history_analysis_summarizes_vetoes_and_discloses_missing_pnl(tmp_path):
    log_path = tmp_path / "decisions.log"
    records = [
        _record("17.10.2026 10:00 TRT", "NO_TRADE", "FAIL"),
        _record("17.10.2026 11:00 TRT", "BUY", "PASS", "SIMULATED"),
    ]
    log_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    result = analyze_history(
        log_path,
        days=30,
        now=datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc),
    )
    report = format_history_report(result)

    assert result["record_count"] == 2
    assert result["actions"]["NO_TRADE"] == 1
    assert result["failed_pillars"]["Teknik Analiz"] == 1
    assert result["pillar_statuses"]["Teknik Analiz"]["FAIL"] == 1
    assert result["pillar_statuses"]["Teknik Analiz"]["PASS"] == 1
    assert result["data_sources"]["SIMULATED"] == 1
    assert result["pnl_recorded"] is False
    assert "Henüz PnL'si doğrulanmış kapanmış işlem yok" in report
    assert "kârlılık" in report


def test_history_analysis_skips_malformed_lines_and_excludes_old_records(tmp_path):
    log_path = tmp_path / "decisions.log"
    recent = _record("17.10.2026 11:00 TRT", "BUY", "PASS")
    old = _record("01.09.2026 11:00 TRT", "NO_TRADE", "FAIL")
    log_path.write_text(
        f"{json.dumps(recent)}\nnot-json\n{json.dumps(old)}\n",
        encoding="utf-8",
    )

    result = analyze_history(
        log_path,
        days=7,
        now=datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc),
    )

    assert result["record_count"] == 1
    assert result["invalid_lines"] == 1
    assert result["actions"]["BUY"] == 1
    assert "NO_TRADE" not in result["actions"]


def test_history_analysis_rejects_invalid_period(tmp_path):
    log_path = tmp_path / "decisions.log"
    log_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="en az 1 gün"):
        analyze_history(log_path, days=0)


def test_history_analysis_does_not_treat_order_metadata_as_realized_pnl(tmp_path):
    log_path = tmp_path / "decisions.log"
    record = _record("17.10.2026 11:00 TRT", "BUY", "PASS")
    record["execution"] = {"realized_pnl_usdt": 1.25}
    log_path.write_text(json.dumps(record), encoding="utf-8")

    result = analyze_history(
        log_path,
        days=7,
        now=datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc),
    )

    assert result["pnl_recorded"] is False
    assert any("PnL'si doğrulanmış kapanmış işlem yok" in item for item in result["recommendations"])


def test_history_analysis_reports_missing_log(tmp_path):
    with pytest.raises(FileNotFoundError, match="bulunamadı"):
        analyze_history(tmp_path / "missing.log")


def test_refresh_history_review_displays_and_writes_report(tmp_path, monkeypatch, capsys):
    import main

    log_path = tmp_path / "decisions.log"
    record = _record("17.10.2026 11:00 TRT", "NO_TRADE", "FAIL")
    log_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    report_path = tmp_path / "reports" / "history_analysis.md"

    monkeypatch.setattr(main, "AUDIT_LOG_PATH", log_path)
    monkeypatch.setattr(main, "HISTORY_REPORT_PATH", report_path)
    monkeypatch.setattr(main, "TRADE_HISTORY_PATH", tmp_path / "trade_history.json")
    monkeypatch.setattr(main, "REPORTS_DIR", report_path.parent)

    assert refresh_history_review(display=True) is True

    output = capsys.readouterr().out
    assert "GEÇMİŞ KARAR ANALİZİ" in output
    assert "NO_TRADE: 1" in output
    assert "SİNYAL AYAKLARI (ANALİZ TURU SAYISI)" in output
    assert "FAIL" in output
    assert "ÖNERİLER" in output
    assert report_path.name in output
    assert report_path.read_text(encoding="utf-8").startswith("# Geçmiş Karar Analizi")


def test_history_report_counts_each_pillar_status(tmp_path):
    log_path = tmp_path / "decisions.log"
    record = _record("17.10.2026 11:00 TRT", "NO_TRADE", "FAIL")
    record["pillars"] = [
        {"name": "Teknik", "status": "FAIL", "source": "LIVE"},
        {"name": "Onchain", "status": "PASS", "source": "LIVE"},
        {"name": "News", "status": "NEUTRAL", "source": "FALLBACK"},
    ]
    log_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = analyze_history(
        log_path,
        days=7,
        now=datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc),
    )
    report = format_history_report(result)

    assert result["pillar_statuses"]["Teknik"] == {"FAIL": 1}
    assert result["pillar_statuses"]["Onchain"] == {"PASS": 1}
    assert result["pillar_statuses"]["News"] == {"NEUTRAL": 1}
    assert "Onchain: PASS 1, FAIL 0, NEUTRAL 0" in report
