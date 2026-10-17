"""TradingView Ekonomik Takvim Entegratörü.

TradingView resmi takvim API'sinden US, DE ve EU için yüksek etkili (onem=3)
ekonomik olayları çeker ve takvim_verileri.json içine kaydeder.
Hem bağımsız CLI aracı hem de data/macro.py tarafından doğrudan çağrılabilen bir kütüphanedir.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger("nexa.tradingview_calendar")

TV_URL = "https://economic-calendar.tradingview.com/events"
ROOT = Path(__file__).resolve().parent
DEFAULT_CALENDAR_PATH = ROOT / "takvim_verileri.json"
ALLOWED_COUNTRIES = {"US", "DE", "EU"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "Content-Type": "application/json",
}


def fetch_tradingview_events(
    days_ahead: int = 7,
    save_path: Path | None = DEFAULT_CALENDAR_PATH,
    timeout: int = 12,
    print_table: bool = False,
) -> list[dict[str, Any]]:
    """TradingView'dan yüksek etkili ekonomik takvim verilerini çeker ve opsiyonel olarak kaydeder."""
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    end = start + timedelta(days=days_ahead)

    params = {
        "from": start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "to": end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }

    payload = {
        "countries": list(ALLOWED_COUNTRIES),
        "minImportance": "1",
    }

    parsed_events: list[dict[str, Any]] = []

    try:
        response = requests.post(TV_URL, headers=HEADERS, params=params, json=payload, timeout=timeout)
        if response.status_code != 200:
            log.warning("TradingView takvim API hatası: HTTP %s", response.status_code)
            return []

        result_data = response.json()
        events = result_data.get("result", [])

        if print_table:
            print(f"{'TARİH (TSİ)':<16} | {'ÜLKE':<4} | {'AÇIKLANAN':<10} | {'BEKLENTİ':<10} | {'ÖNCEKİ':<10} | {'OLAY'}")
            print("-" * 95)

        for item in events:
            country = str(item.get("country", "")).upper()
            importance = str(item.get("importance", ""))

            if country in ALLOWED_COUNTRIES and importance in ["1", "high"]:
                date_str = item.get("date", "")
                tr_time = ""
                if date_str:
                    try:
                        utc_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        tr_dt = utc_dt + timedelta(hours=3)
                        tr_time = tr_dt.strftime("%d.%m %H:%M")
                    except (TypeError, ValueError):
                        tr_time = date_str

                actual = item.get("actual")
                forecast = item.get("forecast")
                previous = item.get("previous")

                event_dict = {
                    "tarih_tsi": tr_time,
                    "tarih_utc": date_str,
                    "ulke": country,
                    "onem": 3,
                    "baslik": item.get("title"),
                    "aciklanan": actual,
                    "beklenti": forecast,
                    "onceki": previous,
                }
                parsed_events.append(event_dict)

                if print_table:
                    actual_str = str(actual) if actual is not None else "-"
                    forecast_str = str(forecast) if forecast is not None else "-"
                    previous_str = str(previous) if previous is not None else "-"
                    print(f"{tr_time:<16} | {country:<4} | {actual_str:<10} | {forecast_str:<10} | {previous_str:<10} | {item.get('title')}")

        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with save_path.open("w", encoding="utf-8") as f:
                json.dump({"yuksek_etkili_haberler": parsed_events}, f, ensure_ascii=False, indent=2)

    except Exception as err:
        log.warning("TradingView takvim çekme hatası: %s", err)
        if print_table:
            print(f"Hata: {str(err)}")

    return parsed_events


if __name__ == "__main__":
    print("TradingView'dan veriler çekilip filtreleniyor...\n")
    events = fetch_tradingview_events(print_table=True)
    print(f"\n✅ Toplam {len(events)} adet US/DE/EU verisi 'takvim_verileri.json' dosyasına kaydedildi.")
