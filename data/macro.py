"""Makroekonomik Takvim ve Blackout Kontrolcüsü (4. Ayak).

1. OKX ATK yerleşik economic-calendar API'sini (3 yıldızlı ABD/Almanya/Euro Bölgesi) sorgular.
2. events.json dosyasından elle eklenmiş etkinlikleri okur.
3. --simulate-event "US CPI in 10m" bayrağı verilmişse sanal olay enjekte eder.
4. Olay zamanından ±blackout_minutes (varsayılan ±30 dk) içindeyse işlem kilitlenir (FAIL).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from data.okx_client import OKXClient, OKXCLIError
from models import PillarResult, Source, Status
from utils import fmt_tr, load_json, ms_to_dt, now_utc, to_float

log = logging.getLogger("nexa.macro")


def fetch_macro_status(
    okx: OKXClient,
    config: dict[str, Any],
    mock_data: dict[str, Any],
    events_path: Path | None = None,
    simulate_event_str: str | None = None,
    force_mock: bool = False,
) -> PillarResult:
    """Makro takvim ve blackout durumunu denetler (4. Ayak)."""
    cfg = config.get("pillars", {}).get("macro", {})
    blackout_min = int(cfg.get("blackout_minutes", 30))
    regions = cfg.get("regions", ["united_states", "germany", "euro_area"])
    importance = int(cfg.get("importance", 3))
    now = now_utc()

    # 1. Simüle Olay Kontrolü (--simulate-event "US CPI in 8m")
    if simulate_event_str:
        sim_result = _handle_simulated_event(simulate_event_str, now, blackout_min)
        if sim_result:
            return sim_result

    # 2. Manuel events.json Kontrolü
    manual_events: list[dict[str, Any]] = []
    if events_path and events_path.exists():
        try:
            m_data = load_json(events_path)
            manual_events = m_data.get("events", [])
        except Exception as e:
            log.warning("events.json okunamadı: %s", e)

    # 3. Canlı OKX Takvimini Sorgula
    live_events: list[dict[str, Any]] = []
    is_fallback = False

    if not force_mock and cfg.get("source") != "mock":
        try:
            # -1 saat ile +24 saat aralığındaki olaylar
            newer_than_ms = int((now - timedelta(hours=1)).timestamp() * 1000)
            older_than_ms = int((now + timedelta(hours=24)).timestamp() * 1000)

            for region in regions:
                evs = okx.economic_calendar(
                    region=region,
                    importance=importance,
                    newer_than_ms=newer_than_ms,
                    older_than_ms=older_than_ms,
                    limit=20,
                )
                live_events.extend(evs)
        except OKXCLIError as e:
            log.warning("OKX economic-calendar sorgusu başarısız (%s), fallback devreye giriyor.", e)
            is_fallback = True
            live_events = mock_data.get("macro", {}).get("events", [])
    else:
        live_events = mock_data.get("macro", {}).get("events", [])

    # Tüm olayları birleştir ve zamanlarına göre blackout denetimi yap
    all_events = _normalize_events(live_events, manual_events)
    active_blackout_event = None
    min_diff_sec = float("inf")
    closest_event_name = ""

    for ev in all_events:
        ev_time = ev["time_utc"]
        ev_name = f"{ev['region']} - {ev['event']}"
        diff_sec = (ev_time - now).total_seconds()
        abs_diff_sec = abs(diff_sec)

        # ±blackout_min içinde mi?
        if abs_diff_sec <= blackout_min * 60:
            active_blackout_event = (ev_name, diff_sec, ev_time)
            break

        # Gelecekteki en yakın olayı takip et
        if diff_sec > 0 and diff_sec < min_diff_sec:
            min_diff_sec = diff_sec
            closest_event_name = f"{ev_name} ({fmt_tr(ev_time)})"

    source = Source.FALLBACK if is_fallback else (Source.MOCK if cfg.get("source") == "mock" else Source.LIVE)

    if active_blackout_event:
        name, diff_sec, ev_time = active_blackout_event
        mins = int(abs(diff_sec) / 60)
        time_msg = f"{mins} dk sonra" if diff_sec >= 0 else f"{mins} dk önce gerçekleşti"
        reason = f"BLACKOUT AKTİF: {name} ({time_msg}) | ±{blackout_min} dk işlem yasağı."
        return PillarResult(
            name="Makro Takvim (Blackout Guard)",
            status=Status.FAIL,
            reason=reason,
            source=source,
            metrics={"blackout": True, "event": name, "event_time": fmt_tr(ev_time)},
        )

    # Blackout yok -> PASS
    next_info = f"En yakın 3 yıldızlı olay: {closest_event_name}" if closest_event_name else "Önümüzdeki 24s kritik olay yok."
    return PillarResult(
        name="Makro Takvim (Blackout Guard)",
        status=Status.PASS,
        reason=f"Piyasa sakin, blackout penceresinde olay yok. {next_info}",
        source=source,
        metrics={"blackout": False, "next_event": closest_event_name or "Yok"},
    )


def _handle_simulated_event(sim_str: str, now: datetime, blackout_min: int) -> PillarResult | None:
    """--simulate-event argümanını işler (Örn: 'US CPI in 8m' veya 'FOMC in 15m')."""
    match = re.search(r"(\d+)\s*m", sim_str.lower())
    offset_min = int(match.group(1)) if match else 5
    sim_time = now + timedelta(minutes=offset_min)

    if offset_min <= blackout_min:
        return PillarResult(
            name="Makro Takvim (SİMÜLASYON)",
            status=Status.FAIL,
            reason=f"[SIMULATED BLACKOUT] {sim_str} (±{blackout_min} dk kuralı gereği işlem BLOKE EDİLDİ)",
            source=Source.SIMULATED,
            metrics={"simulated": True, "event": sim_str, "offset_min": offset_min},
        )
    return PillarResult(
        name="Makro Takvim (SİMÜLASYON)",
        status=Status.PASS,
        reason=f"[SIMULATED EVENT] {sim_str} ({offset_min} dk > {blackout_min} dk blackout sınırı)",
        source=Source.SIMULATED,
        metrics={"simulated": True, "event": sim_str, "offset_min": offset_min},
    )


def _normalize_events(live_list: list[dict[str, Any]], manual_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tüm etkinlikleri tek bir UTC zaman damgalı listeye dönüştürür."""
    out: list[dict[str, Any]] = []

    for item in live_list:
        raw_date = item.get("date")
        if raw_date:
            try:
                ev_time = ms_to_dt(raw_date)
                out.append({
                    "event": item.get("event", "Bilinmeyen Olay"),
                    "region": item.get("region", "Global"),
                    "time_utc": ev_time,
                })
            except Exception:
                continue

    for item in manual_list:
        iso_str = item.get("time_utc")
        if iso_str:
            try:
                ev_time = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                out.append({
                    "event": item.get("event", "Manuel Olay"),
                    "region": item.get("region", "Custom"),
                    "time_utc": ev_time,
                })
            except Exception:
                continue

    return out
