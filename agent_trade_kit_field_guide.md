# NEXA-TRADER (SENTINEL): OKX Agent Trade Kit — Saha Kılavuzu & Üretim Mimarisi

**Etkinlik:** 17 Ekim Agentic Hackathon Ankara  
**Mimarî:** 4 Sinyal Ayağı + 1 Deterministik Koruma Katmanı (Multi-Source Day Trading)  
**Parite:** `AVAX/USDT` (Spot)  
**Yürütme Motoru:** OKX Agent Trade Kit (`@okx_ai/okx-trade-cli` v1.4.8+, `--demo` modu)  

---

## 1. 2. Mühendis İncelemesi: Güçlü Yönler, Düzeltmeler ve Hata Tespitleri

Claude tarafından yapılan kıdemli mühendis incelemesi mimarimizi olgunlaştırmıştır. Yapılan değerlendirme ve canlı terminal doğrulamaları şunlardır:

### 1.1 Doğrulanan ve Sisteme Katılan Kritik Noktalar
1. **Modüler Dizin Yapısı:** Kod `data/`, `strategy/`, `risk/`, `execution/` klasörlerine ayrılmıştır. Tek dosya monoliti elenmiştir.
2. **Dürüst Veri Ayrımı (LIVE vs. MOCK):** Dış kaynaklar (CryptoQuant, Investing.com) için canlı scraper/API denenir; hata veya kısıt durumunda `mock_data.json` devreye girer ve terminale açıkça `[FALLBACK: MOCK DATA]` basılır. Sahte veri canlı gibi yansıtılmaz.
3. **Formül Netliği:** `take_profit_pct = stop_loss_pct * risk_reward_ratio` formülüyle çelişkili config parametreleri tekilleştirilmiştir.
4. **Jüri Garantisi (`--demo-script`):** Canlı piyasa 3 dakikalık sunum esnasında nötr kalsa bile, 3 altın senaryoyu (1: Tüm ayaklar onaylı alım, 2: Negatif haber vetosu, 3: Makro blackout engeli) deterministik oynatan simülasyon modu eklenmiştir.
5. **Terminal UI:** `rich` kütüphanesiyle 4 panelli durum tablosu ve final karar kutusu kurgulanmıştır.

### 1.2 Claude'un Yanıldığı / Canlı Terminalde Düzeltilen Hususlar
- **OKX CLI Sözdizimi:** Claude `okx trade order` ve `trade algo-order` gibi varsayımsal komutlar önermiştir. Terminalde `okx --help` ve `okx spot --help` ile teyit edildiği üzere modül adı **`okx spot place`**'tir.
- **İki Aşamalı Fill Kontrolü:** Claude'un önerdiği "önce alım yap, fill bekle, sonra ayrı algo order ile TP/SL bağla" yöntemi canlı demoda ağ gecikmesi ve race condition yaratır. OKX CLI v1.4.8 yerleşik olarak **attached TP/SL** desteklemektedir:
  `okx spot place --instId AVAX-USDT --side buy --ordType market --sz <n> --tdMode cash --tpTriggerPx <px> --slTriggerPx <px> --demo`  
  Bu yöntem borsa motoru seviyesinde atomiktir; pozisyon açıldığı mikrosaniyede TP ve SL borsaya kilitlenir.

---

## 2. 5 Maddelik MVP Uygulama Planı

```
+-------------------------------------------------------------------------------------------------+
|                                 5 ADIMLI ÜRETİM YOL HARİTASI                                    |
+------------------------------------+------------------------------------------------------------+
| 1. Proje İskeleti & Ortam          | Dizin yapısı, requirements.txt, .env.example, config.json, |
|                                    | mock_data.json ve events.json takvimi.                     |
+------------------------------------+------------------------------------------------------------+
| 2. Veri Sağlayıcılar (Data Layer)  | data/okx_client.py (doğrulanmış CLI çağrıları),            |
|                                    | data/news.py (Gemini API + RSS), data/macro.py, onchain.py |
+------------------------------------+------------------------------------------------------------+
| 3. Teknik Analiz & Sinyal Motoru   | strategy/technical.py (Pandas ile EMA 20/50, Hacim,        |
|                                    | Engulfing/Hammer formasyonları), strategy/signal_engine.py |
+------------------------------------+------------------------------------------------------------+
| 4. Deterministik Risk Koruyucu     | risk/position_sizer.py (bakiye %5, dinamik 1:2 R/R),       |
|                                    | risk/guardrail.py (kill-switch, blackout, tek pozisyon)    |
+------------------------------------+------------------------------------------------------------+
| 5. Yürütme & Canlı Demo Dashboard  | execution/executor.py, main.py (Rich UI, --once, --loop,   |
|                                    | --simulate-event, --demo-script senaryoları).              |
+------------------------------------+------------------------------------------------------------+
```

---

## 3. Sistem Mimarisi: 4 Sinyal Ayağı + 1 Koruma Katmanı

```
                              +---------------------------------------+
                              |         SENTINEL DECISION ENGINE      |
                              +-------------------+-------------------+
                                                  |
         +--------------------+-------------------+-------------------+--------------------+
         | (1. Ayak)          | (2. Ayak)         | (3. Ayak)         | (4. Ayak)          |
         v                    v                   v                   v                    v
+------------------+ +------------------+ +------------------+ +------------------+ +------------------+
|   OKX ATK API    | |   CryptoQuant    | |   Haber Analizi  | |  Investing.com   | | DETERMINISTIK    |
|  1H Trend (EMA)  | | On-Chain Verisi  | | Google Gemini    | | Ekonomik Takvim  | | RISK GUARDRAIL   |
| 15m Price Action | | Borsa Rezervi    | | Duyarlılık (-1..)| | 3 Yıldızlı Haber | | (Executor Öncesi |
| (Hacim + Mumlar) | | (MVRV, Balina)   | | (AVAX / BTC)     | | (±30 dk Blackout)| |   Zorunlu Kapı)  |
+------------------+ +------------------+ +------------------+ +------------------+ +------------------+
         |                    |                   |                   |                    |
         +--------------------+-------------------+-------------------+                    |
                                                  |                                        |
                                         [ TÜMÜ PASS MI? ]                                 |
                                         /               \                                 |
                                    (EVET)              (HAYIR)                            |
                                      |                   |                                |
                                      v                   v                                |
                            +-------------------+    [ NO TRADE ]                          |
                            | Risk Guardrail    |                                          |
                            | Kontrolü          |                                          |
                            +---------+---------+                                          |
                                      | (ONAY)                                             |
                                      v                                                    |
                            +-------------------------------------------+                  |
                            | OKX ATK Executor (Atomik Attached TP/SL)  |<-----------------+
                            | `okx spot place --tpTriggerPx --slTrigger`|
                            +-------------------------------------------+
```

---

## 4. Modüler Dizin Şeması (`Nexa-Trader/`)

```
Nexa-Trader/
├── data/
│   ├── __init__.py
│   ├── okx_client.py       # Doğrulanmış okx CLI wrapper (ticker, candles, balance)
│   ├── onchain.py          # CryptoQuant / On-chain metrikleri (Canlı / Fallback)
│   ├── news.py             # RSS / CryptoPanic + Gemini API duyarlılık puanlaması
│   └── macro.py            # Ekonomik takvim ve blackout kontrolcüsü
├── strategy/
│   ├── __init__.py
│   ├── technical.py        # EMA 20/50, Hacim ortalaması, Mum formasyonları (Pandas)
│   └── signal_engine.py    # 4 ayağı birleştiren karar matrisi (PASS / FAIL / NEUTRAL)
├── risk/
│   ├── __init__.py
│   ├── position_sizer.py   # Bakiye x %5, Stop-Loss ve 1:2 R/R seviye hesaplayıcı
│   └── guardrail.py        # Kill-switch, blackout, tek pozisyon kilidi, spread filtresi
├── execution/
│   ├── __init__.py
│   └── executor.py         # okx spot place çağrısı ve fill/audit logging
├── tests/
│   ├── test_technical.py   # Mum formasyonları ve EMA testleri
│   └── test_guardrail.py   # Risk sınırları ve blackout testleri
├── mock_data.json          # Harici API arızalarında devreye giren şeffaf mock veriler
├── events.json             # Günün 3 yıldızlı ekonomik verileri (saat dilimi: Europe/Istanbul)
├── config.json             # Kullanıcı risk ve strateji parametreleri
├── .env.example            # GEMINI_API_KEY ve opsiyonel API token şablonu
├── requirements.txt        # python bağımlılıkları (rich, pandas, requests, google-genai)
├── decisions.log           # Her döngünün JSON denetim izi (Audit trail)
├── main.py                 # CLI argümanları, Rich Dashboard ve döngü yöneticisi
└── README.md               # Jüri kurulum ve demo çalıştırma rehberi
```

---

## 5. Doğrulanmış ATK CLI Komutları Referansı

Bu komutlar terminalde canlı test edilmiş ve doğrulanmıştır:

| Görev | Doğrulanmış CLI Komutu |
| :--- | :--- |
| **Bakiye Sorgulama** | `okx account balance --demo --json` |
| **Anlık Fiyat** | `okx market ticker AVAX-USDT --demo --json` |
| **1H Mumlar (Trend)** | `okx market candles AVAX-USDT --bar 1H --limit 50 --demo --json` |
| **15m Mumlar (Giriş)** | `okx market candles AVAX-USDT --bar 15m --limit 20 --demo --json` |
| **Haber & Trend** | `okx news list --demo --json` |
| **Atomik Alım + TP/SL** | `okx spot place --instId AVAX-USDT --side buy --ordType market --sz <size> --tdMode cash --tpTriggerPx <tp> --slTriggerPx <sl> --demo --json` |

---

## 6. Canlı Demo & Senaryo Oynatıcı (`--demo-script`)

Jüri sunumunda internet gecikmesi veya yatay piyasa riskine karşı 3 senaryo tek komutla çalıştırılabilir:

```bash
# 1. Normal Canlı Döngü (Her 30 saniyede bir analiz)
python main.py --loop 30

# 2. Tek Seferlik Analiz
python main.py --once

# 3. Kasıtlı Olay Tetikleme (Guardrail testi)
python main.py --simulate-event "US CPI in 10m"

# 4. Jüri Altın Demo Senaryosu (3 Senaryoyu Sırayla Oynatır)
python main.py --demo-script
```

### `--demo-script` Akışı (2 Dakika 30 Saniye):
1. **Senaryo 1 (Mükemmel Koşul - BUY):**  
   1H EMA trendi yukarı, 15m Yutan Boğa mumu var, On-Chain rezervler düşüyor, Gemini haber skoru +0.72, makro blackout yok.  
   -> **Sonuç:** `[DECISION: BUY]` -> OKX Demo'da $250'lık AVAX alımı yapılır, TP ve SL seviyeleri terminale yazılır.
2. **Senaryo 2 (Haber Vetosu - NO TRADE):**  
   Teknik göstergeler pozitif ancak Gemini AVAX için regülasyon haberi nedeniyle -0.45 skor veriyor.  
   -> **Sonuç:** `[DECISION: NO TRADE]` -> `Gerekçe: Haber duyarlılığı negatif (-0.45 < 0)`.
3. **Senaryo 3 (Guardrail / Makro Blackout - BLOCKED):**  
   Teknik ve haber pozitif ancak ABD TÜFE verisine 8 dakika kalmış.  
   -> **Sonuç:** `[BLOCKED: Macro Blackout Window (US CPI in 8m)]` -> Emir motoru kilitlenir, sermaye korunur.

---

## 7. Bilinen Sınırlamalar & Jüri Şeffaflığı

- **Spot Sadece Long:** İlk MVP'de marjin/tasfiye riskinden kaçınmak için sadece Spot alım yapılır; düşüş trendinde "Nakitte Kal (Cash)" kararı verilir.
- **On-Chain & Makro Fallback:** Dış API'ler kotaya takıldığında sistem şeffaf bir şekilde `[FALLBACK: MOCK DATA]` bayrağını yakar; sahte veri asla canlı gibi sunulmaz.
- **Slippage ve Komisyon:** %1.2 SL ve %2.4 TP seviyeleri likit AVAX piyasasında minimum slippage varsayımıyla çalışır; volatil haber anlarında blackout devrededir.
