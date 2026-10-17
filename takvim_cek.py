import json
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

TV_URL = "https://economic-calendar.tradingview.com/events"
ROOT = Path(__file__).resolve().parent

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "Content-Type": "application/json"
}

now = datetime.now(timezone.utc)
start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
end = start + timedelta(days=7)
params = {
    "from": start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    "to": end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
}

payload = {
    "countries": ["US", "DE", "EU"],
    "minImportance": "1"
}

ALLOWED_COUNTRIES = {"US", "DE", "EU"}

print("TradingView'dan veriler çekilip filtreleniyor...\n")

try:
    response = requests.post(TV_URL, headers=headers, params=params, json=payload, timeout=12)

    if response.status_code == 200:
        result_data = response.json()
        events = result_data.get("result", [])

        parsed_events = []
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

                actual_str = str(actual) if actual is not None else "-"
                forecast_str = str(forecast) if forecast is not None else "-"
                previous_str = str(previous) if previous is not None else "-"

                event_dict = {
                    "tarih_tsi": tr_time,
                    "tarih_utc": date_str,
                    "ulke": country,
                    "onem": 3,
                    "baslik": item.get("title"),
                    "aciklanan": actual,
                    "beklenti": forecast,
                    "onceki": previous
                }
                parsed_events.append(event_dict)

                print(f"{tr_time:<16} | {country:<4} | {actual_str:<10} | {forecast_str:<10} | {previous_str:<10} | {item.get('title')}")

        with (ROOT / "takvim_verileri.json").open("w", encoding="utf-8") as f:
            json.dump({"yuksek_etkili_haberler": parsed_events}, f, ensure_ascii=False, indent=2)

        print(f"\n✅Toplam {len(parsed_events)} adet US/DE/EU verisi 'takvim_verileri.json' dosyasına kaydedildi.")

    else:
        print(f"Hata Kodu: {response.status_code}")

except Exception as err:
    print(f"Hata: {str(err)}")
