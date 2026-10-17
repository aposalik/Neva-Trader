"""Decision-log analysis and evidence-based user recommendations."""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from data.trade_history import TradeHistoryTracker

log = logging.getLogger("nexa.history")
TR_TZ = timezone(timedelta(hours=3))


def analyze_history(
    log_path: Path,
    days: int = 30,
    now: datetime | None = None,
    trade_history_path: Path | None = None,
) -> dict[str, Any]:
    """Summarize recent decisions without inferring unrecorded trade outcomes."""
    if days < 1:
        raise ValueError("Analiz dönemi en az 1 gün olmalı.")
    if not log_path.exists():
        raise FileNotFoundError(f"Karar kayıt dosyası bulunamadı: {log_path}")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    current_time = current_time.astimezone(timezone.utc)
    cutoff = current_time - timedelta(days=days)

    records: list[dict[str, Any]] = []
    invalid_lines = 0
    unreadable_timestamps = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as source:
        for line_number, raw_line in enumerate(source, 1):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as error:
                invalid_lines += 1
                log.warning("Karar kaydı satır %d okunamadı: %s", line_number, error)
                continue
            if not isinstance(record, dict):
                invalid_lines += 1
                log.warning("Karar kaydı satır %d JSON nesnesi değil.", line_number)
                continue

            timestamp = _parse_timestamp(record.get("timestamp"))
            if timestamp is None:
                unreadable_timestamps += 1
                continue
            if cutoff <= timestamp <= current_time:
                records.append(record)

    actions = Counter(str(record.get("action", "UNKNOWN")).upper() for record in records)
    failed_pillars: Counter[str] = Counter()
    pillar_statuses: dict[str, Counter[str]] = {}
    data_sources: Counter[str] = Counter()
    execution_statuses: Counter[str] = Counter()

    for record in records:
        execution = record.get("execution")
        pillars = record.get("pillars", [])
        if not isinstance(pillars, list):
            log.warning("Karar kaydındaki pillars alanı liste değil; kayıt atlandı.")
            pillars = []
        for pillar in pillars:
            if not isinstance(pillar, dict):
                continue
            name = str(pillar.get("name", "Bilinmeyen ayak"))
            status = str(pillar.get("status", "")).upper()
            if status not in {"PASS", "FAIL", "NEUTRAL"}:
                continue
            pillar_statuses.setdefault(name, Counter())[status] += 1
            if status == "FAIL":
                failed_pillars[name] += 1
            source = pillar.get("source")
            if source:
                data_sources[str(source).upper()] += 1

        if isinstance(execution, dict):
            status = execution.get("status")
            if status:
                execution_statuses[str(status).upper()] += 1

    trades = (
        TradeHistoryTracker(trade_history_path).summary(cutoff, current_time)
        if trade_history_path is not None else _empty_trade_summary()
    )
    recommendations = _recommendations(
        record_count=len(records),
        actions=actions,
        failed_pillars=failed_pillars,
        data_sources=data_sources,
        trades=trades,
    )

    return {
        "days": days,
        "start": cutoff,
        "end": current_time,
        "record_count": len(records),
        "invalid_lines": invalid_lines,
        "unreadable_timestamps": unreadable_timestamps,
        "actions": actions,
        "failed_pillars": failed_pillars,
        "pillar_statuses": pillar_statuses,
        "data_sources": data_sources,
        "execution_statuses": execution_statuses,
        "trades": trades,
        "pnl_recorded": trades["pnl_trade_count"] > 0,
        "recommendations": recommendations,
    }


def format_history_report(analysis: dict[str, Any]) -> str:
    """Render a human-readable history summary and recommendations."""
    lines = [
        "# Geçmiş Karar Analizi",
        "",
        f"- Dönem: {analysis['start'].astimezone(TR_TZ):%d.%m.%Y %H:%M} — "
        f"{analysis['end'].astimezone(TR_TZ):%d.%m.%Y %H:%M} TRT "
        f"({analysis['days']} gün)",
        f"- İncelenen karar kaydı: {analysis['record_count']}",
        f"- Kararlar: {_format_counter(analysis['actions'])}",
        f"- Hata nedeniyle atlanan satır: {analysis['invalid_lines']}",
        f"- Zamanı okunamayan kayıt: {analysis['unreadable_timestamps']}",
        "",
        "## Sinyal ayaklarının durumları (analiz turu sayısı)",
        "",
    ]

    if analysis["pillar_statuses"]:
        for name, statuses in sorted(
            analysis["pillar_statuses"].items(),
            key=lambda item: sum(item[1].values()),
            reverse=True,
        ):
            lines.append(
                f"- {name}: PASS {statuses['PASS']}, FAIL {statuses['FAIL']}, "
                f"NEUTRAL {statuses['NEUTRAL']}"
            )
    else:
        lines.append("- Sinyal ayağı durumu kaydı yok.")

    lines.extend(["", "## Veri kaynakları", ""])
    if analysis["data_sources"]:
        lines.extend(f"- {source}: {count}" for source, count in analysis["data_sources"].most_common())
    else:
        lines.append("- Sinyal kaynağı bilgisi bulunamadı.")

    if analysis["execution_statuses"]:
        lines.extend(["", "## Emir yanıtları", ""])
        lines.extend(
            f"- {status}: {count}"
            for status, count in analysis["execution_statuses"].most_common()
        )

    trades = analysis["trades"]
    lines.extend(["", "## Gerçekleşmiş işlem sonuçları", ""])
    if trades["closed_count"]:
        lines.append(
            f"- Kapanan işlem: {trades['closed_count']} "
            f"(kâr: {trades['wins']}, zarar: {trades['losses']}, "
            f"başabaş: {trades['breakeven']})"
        )
        if trades["pnl_trade_count"]:
            lines.append(
                f"- Ücret sonrası PnL'si hesaplanan: {trades['pnl_trade_count']}"
            )
            lines.append(f"- Net gerçekleşmiş PnL: {trades['net_pnl_usdt']:.4f} USDT")
            lines.append(f"- Kazanç oranı: %{trades['win_rate_pct']:.1f}")
        if trades["unknown_pnl_count"]:
            lines.append(
                f"- Dolumu görülen fakat ücreti/alış maliyeti doğrulanamayan: "
                f"{trades['unknown_pnl_count']}"
            )
    else:
        lines.append("- Henüz PnL'si doğrulanmış kapanmış işlem yok.")
    lines.append(f"- İzlenen açık pozisyon lotu: {trades['open_positions']}")
    if trades["pending_entries"]:
        lines.append(
            f"- Dolum bekleyen takipli giriş emri: {trades['pending_entries']}"
        )
    if trades["history_gap"]:
        lines.append(
            "- UYARI: Dolum geçmişi senkronizasyonu 3 günden uzun süre kesilmiş; "
            "aralıkta gerçekleşen kapanışlar eksik olabilir."
        )

    lines.extend(["", "## Öneriler", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(analysis["recommendations"], 1))
    lines.extend([
        "",
        "> Bu rapor geçmiş karar ve kayıt örüntülerini özetler; kârlılık veya gelecek getirisi tahmini değildir.",
    ])
    return "\n".join(lines) + "\n"


def _recommendations(
    record_count: int,
    actions: Counter[str],
    failed_pillars: Counter[str],
    data_sources: Counter[str],
    trades: dict[str, Any],
) -> list[str]:
    recommendations: list[str] = []

    if record_count < 10:
        recommendations.append(
            "Örüntüleri yorumlamak için kayıt sayısı sınırlı; en az 10 gerçek analiz kaydı biriktirdikten sonra tekrar inceleyin."
        )

    if failed_pillars:
        name, count = failed_pillars.most_common(1)[0]
        recommendations.append(
            f"En sık FAIL olan ayak “{name}” ({count} kayıt). Bu ayağın veri kaynağını ve veto nedenlerini gözden geçirin; "
            "tek başına bu sayıya dayanarak eşikleri gevşetmeyin."
        )

    non_live_count = sum(
        count for source, count in data_sources.items() if source in {"MOCK", "FALLBACK", "SIMULATED"}
    )
    total_sources = sum(data_sources.values())
    if total_sources and non_live_count / total_sources >= 0.2:
        recommendations.append(
            f"Sinyal kaynaklarının %{non_live_count / total_sources * 100:.0f} kadarı MOCK/FALLBACK/SIMULATED. "
            "Strateji değerlendirmesinden önce canlı kaynak erişimini ve demo/simülasyon kayıtlarını ayrı doğrulayın."
        )

    blocked_or_rejected = actions.get("BLOCKED", 0) + actions.get("NO_TRADE", 0)
    if record_count and blocked_or_rejected / record_count >= 0.7:
        recommendations.append(
            "Kararların en az %70'i BLOCKED/NO_TRADE. Reddedilme gerekçelerini (guardrail, teknik ve makro) "
            "ayrı inceleyin; güvenlik kurallarını otomatik olarak kaldırmayın."
        )

    if trades["pnl_trade_count"] == 0:
        recommendations.append(
            "Henüz PnL'si doğrulanmış kapanmış işlem yok. Sistem gerçek spot dolumlarını izler; "
            "alış, kapanış ve ücret verileri eşleşmeden kazanma oranı hesaplanmaz."
        )
    else:
        recommendations.append(
            f"{trades['pnl_trade_count']} kapanmış işlemin ücret sonrası PnL'si gerçek spot dolumlarından "
            "hesaplandı; eşleştirme izlenen alımlar ile satışları FIFO sırasıyla bağlar. "
            "Aynı paritede uygulama dışında işlem yapılıyorsa sonuçların atfı kesin olmayabilir."
        )

    if trades["history_gap"]:
        recommendations.append(
            "OKX CLI dolum geçmişini varsayılan olarak son 3 günle sınırlar ve senkronizasyon daha uzun süre "
            "kesilmiş. Bu dönemde kaçırılmış kapanışlar olabilir; kârlılık toplamını eksiksiz kabul etmeyin."
        )

    if not recommendations:
        recommendations.append(
            "Belirgin bir kayıt örüntüsü saptanmadı. Yeni karar kayıtlarını düzenli inceleyin ve gerçekleşmiş işlem "
            "sonuçlarını kaydetmeye devam edin."
        )
    return recommendations


def _empty_trade_summary() -> dict[str, Any]:
    return {
        "closed_count": 0,
        "pnl_trade_count": 0,
        "unknown_pnl_count": 0,
        "wins": 0,
        "losses": 0,
        "breakeven": 0,
        "net_pnl_usdt": 0.0,
        "win_rate_pct": None,
        "open_positions": 0,
        "pending_entries": 0,
        "history_gap": False,
        "last_sync_at": None,
    }


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "yok"
    return ", ".join(f"{key}: {value}" for key, value in counter.most_common())


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw_value = value.strip()
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(raw_value, "%d.%m.%Y %H:%M TRT").replace(tzinfo=TR_TZ)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TR_TZ)
    return parsed.astimezone(timezone.utc)
