---
name: onchain-macro-feeder
description: >-
  Operational guide for ingesting CryptoQuant on-chain metrics, parsing macroeconomic calendar events, calculating the ±30 min blackout window, and managing transparent mock fallbacks.
---

# On-Chain ve Makroekonomik Veri Besleme Kılavuzu

Bu yetenek, borsa dışı veri kaynaklarını (CryptoQuant on-chain dinamikleri ve Investing.com makroekonomik takvimi) güvenli, zaman dilimine duyarlı ve fallback destekli şekilde çalıştırmak için kullanılır.

## 1. On-Chain Metrikleri (2. Ayak)

CryptoQuant veya Avalanche cüzdan verilerinden şu 4 metrik analiz edilir:
1. **Exchange Reserve (Borsa Rezervi):** Borsa cüzdanlarındaki AVAX miktarı. Son 24 saatte azalıyorsa (`change_24h < 0`), yatırımcılar varlıklarını soğuk cüzdana çekiyordur; satış baskısı düşüktür -> **PASS (Onay)**. Rezerv artıyorsa -> **FAIL**.
2. **MVRV Ratio:** Piyasa değeri / Gerçekleşen değer oranı.
   - `< 1.0`: Aşırı ucuzluk / Akümülasyon (Pozitif).
   - `1.0 - 2.5`: Sağlıklı boğa piyasası (Pozitif).
   - `> 3.7`: Aşırı ısınma ve tepe riski (Negatif).
3. **Whale Accumulation (Balina Birikimi):** 10,000+ AVAX tutan UTXO / cüzdan gruplarının net akışı pozitif olmalıdır.

## 2. Makroekonomik Takvim ve Blackout Yönetimi (4. Ayak)

### 2.1 Takip Edilen Ülkeler ve Olaylar
Sadece piyasayı doğrudan sarsan **3 Yıldızlı** kritik olaylar izlenir:
- **Ülkeler:** ABD (US), Almanya (DE), Euro Bölgesi (EU).
- **Etkinlikler:** FED Faiz Kararı (FOMC), TÜFE/Enflasyon (CPI), Tarım Dışı İstihdam (NFP), ECB Faiz Kararı.

### 2.2 Saat Dilimi ve Blackout Penceresi
- Etkinlik saatleri Türkiye yerel saatine (`Europe/Istanbul`, UTC+3) göre normalize edilir.
- **Kural:** Kritik haberden **30 dakika önce ve 30 dakika sonra** (`now - 30m <= event_time <= now + 30m`) yeni işlem açılması deterministik olarak engellenir.

## 3. Şeffaf Fallback Mekanizması
- Canlı web scraping veya API kotası dolduğunda, sistem doğrudan `mock_data.json` içindeki güncel piyasa koşullarını okur.
- Çevrimdışı veriye geçildiğinde terminale açıkça şu bayrak basılır:
  `[FALLBACK: MOCK DATA (mock_data.json)]`
- Böylece jüriye dış bağımlılıkların güvenli şekilde izole edildiği gösterilir.
