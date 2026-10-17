# NEXA-TRADER: Agentic Workspace Kuralları ve Geliştirici Talimatları

Bu proje, 17 Ekim Agentic Hackathon Ankara için geliştirilen, OKX Agent Trade Kit (ATK) tabanlı, 4 sinyal ayaklı ve deterministik risk korumalı bir otonom Day Trading ajanıdır.

## 1. Mimari Prensipler
- **4 Sinyal Ayağı + 1 Deterministik Koruma:**
  1. *Teknik Analiz:* OKX ATK (1H EMA 20/50 + Hacim ortalaması, 15m Price Action / Dönüş Mumları).
  2. *On-Chain:* CryptoQuant rezervleri, MVRV, balina birikimi.
  3. *Haber Akışı:* AVAX/BTC duyarlılık analizi (Google Gemini API ile JSON formatında -1.0 ile +1.0 arası).
  4. *Makro Takvim:* ABD/Almanya 3 yıldızlı veriler (±30 dakika işlem blackout penceresi).
  5. *Deterministik Risk Koruması (Guardrail):* Executor öncesi geçilmesi zorunlu matematiksel kural motoru.

- **Dürüst Veri ve Fallback Kuralı:**
  Canlı veri kaynakları (CryptoQuant, Investing.com) arızalandığında veya kotaya takıldığında sessizce sahte veri üretilmez. Sistem `mock_data.json` verisine geçer ve terminale/loglara açıkça `[FALLBACK: MOCK DATA]` yazar.

- **Sıfır Sermaye Kaybı Riski:**
  Tüm borsa işlemleri varsayılan olarak `--demo` bayrağı ile çalıştırılır. Canlı emir göndermek için açık onay gerekir.

## 2. Modüler Dizin Mimarisi
Kod tabanında her modül tek bir sorumluluğa sahiptir:
- `data/`: OKX CLI wrapper, onchain, haber ve makro veri toplayıcıları.
- `strategy/`: Pandas/Numpy ile EMA, hacim ve mum formasyonları (Engulfing, Hammer, Morning Star) ile 4 ayak sinyal motoru.
- `risk/`: Bakiye x %5, dinamik 1:2 R/R seviyeleri ve kill-switch/blackout guardrail'i.
- `execution/`: OKX ATK üzerinden yerleşik atomik attached TP/SL ile emir yürütme.
- `main.py`: Rich konsol arayüzü, `--once`, `--loop`, `--simulate-event` ve 3 senaryolu `--demo-script` yöneticisi.

## 3. Çalıştırma Komutları
- Canlı Döngü: `python main.py --loop 30`
- Tek Seferlik Analiz: `python main.py --once`
- Makro Simülasyonu: `python main.py --simulate-event "US CPI in 10m"`
- Jüri Altın Demo Senaryosu: `python main.py --demo-script`
