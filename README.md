# NEXA-TRADER (SENTINEL): Çok Kaynaklı Otonom Day Trading Ajanı

Bu proje, **Agentic Hackathon Ankara 2026** (OKX TR × Team1 Türkiye) için geliştirilmiştir.
OKX Agent Trade Kit (`@okx_ai/okx-trade-cli` v1.4.8+, `--demo` modu) üzerinde `AVAX/USDT` paritesinde çalışan; 4 sinyal ayağını (Teknik, On-Chain, Haber, Makro) birleştiren ve deterministik risk korumasına (Guardrail) sahip otonom bir AI alım-satım ajanıdır.

---

## 1. Mimari: 4 Sinyal Ayağı + 1 Koruma Katmanı

```
                              +---------------------------------------+
                              |         SENTINEL DECISION ENGINE      |
                              +-------------------+-------------------+
                                                  |
         +--------------------+-------------------+-------------------+--------------------+
         | (1. Ayak)          | (2. Ayak)         | (3. Ayak)         | (4. Ayak)          |
         v                    v                   v                   v                    v
+------------------+ +------------------+ +------------------+ +------------------+ +------------------+
|   OKX ATK API    | |   CryptoQuant    | |   Haber Analizi  | | OKX + TradingView | | DETERMINİSTİK  |
|  1H Trend (EMA)  | | On-Chain Verisi  | | Google Gemini    | | Ekonomik Takvim  | | RISK GUARDRAIL   |
| 15m Price Action | | Borsa Rezervi    | | Duyarlılık (-1..)| | 3 Yıldızlı Haber | | (Executor Öncesi |
| (Hacim + Mumlar) | | (MVRV, Balina)   | | (AVAX / BTC)     | | (±30 dk Blackout)| |   Zorunlu Kapı)  |
+------------------+ +------------------+ +------------------+ +------------------+ +------------------+
```

1. **1. Ayak — Teknik Analiz (OKX ATK):**
   - 1H Grafikte `EMA 20 > EMA 50`, `Fiyat > EMA 20` ve hacim teyidi (`vol > 5h_avg`).
   - 15m Grafikte geri çekilme (pullback) sonrası dönüş mumları: **Bullish Engulfing**, **Hammer** veya **Morning Star**.
2. **2. Ayak — On-Chain Sağlık (CryptoQuant):**
   - Borsa rezervlerinde azalış (`exchange_reserve < 0`), sağlıklı MVRV oranı (`1.0 - 2.5`), artan balina birikimi.
3. **3. Ayak — Haber Akışı & Duyarlılık:**
   - AVAX ve BTC haber başlıklarının Google Gemini API ile duyarlılık analizi (-1.0 .. +1.0). Skor < 0 ise alım veto edilir.
4. **4. Ayak — Makro Takvim & Blackout (OKX + TradingView):**
   - OKX ekonomik takvimine ek olarak `takvim_verileri.json` içindeki TradingView verileri ve `events.json` manuel olayları kontrol edilir. ABD, Almanya ve Euro Bölgesi kritik verilerinden **±30 dakika** önce/sonra yeni işlem açılması kilitlenir.
5. **+1 Koruma Katmanı — Deterministik Risk Guardrail:**
   - Her işlemde portföyün sabit **%5.0**'i riske edilir.
   - **1:2 R/R Oranı:** Stop-Loss %1.2, Take-Profit %2.4.
   - **Atomik Attached TP/SL:** OKX borsasına tek komutta (`--tpTriggerPx` ve `--slTriggerPx`) iletilir; pozisyon açıldığı mikrosaniyede korumaya alınır.
   - Kill-Switch: Günlük zarar %3'ü aşarsa sistem kendini kilitler.

---

## 2. Juri Icin Adim Adim Hizli Calistirma Rehberi (Quick Start)

Juri uyelerinin projeyi kendi bilgisayarlarinda 2 dakika icinde ayaga kaldirabilmesi icin gereken adimlar:

### Adim 1: Depoyu Klonlayin ve Feat Dalina Gecin
```bash
git clone https://github.com/aposalik/Neva-Trader.git
cd Neva-Trader
git checkout feat/cchain-rpc-rules-and-mvp-plan
```

### Adim 2: Bagimliliklari Yukleyin
```bash
pip install -r requirements.txt
npm install -g @okx_ai/okx-trade-cli
```

### Adim 3: OKX Demo Girisi Yapin (Tarayicidan Tek Tikla)
```bash
okx auth login
```
*(API anahtari olusturmaniza gerek yoktur; CLI tarayicida OKX TR demo onayini otomatik baglar.)*

### Adim 4: Ortam Sablonunu Kopyalayin
```bash
# Windows PowerShell:
Copy-Item .env.example .env

# Mac / Linux:
cp .env.example .env
```
*(Not: Sistem, dis anahtar girilmese dahi OKX yerlesik duyarlilik analizi ve Avalanche RPC ile %100 canli calisir.)*

---

## 3. Çalıştırma ve Canlı Jüri Demosu

### 3.1 Jüri Altın Demo Senaryosu (ÖNERİLEN)
Piyasa o an yatayda olsa bile, ajanın tüm yeteneklerini 3 altın senaryoyla arka arkaya kanıtlar:
```bash
python main.py --demo-script
```
- **Senaryo 1:** Tüm ayaklar yeşil -> OKX Demo'da $250'lık AVAX alımı yapılır, TP/SL kilitlenir.
- **Senaryo 2:** Teknik pozitif ancak haber skoru negatif -> İşlem veto edilir (`NO TRADE`).
- **Senaryo 3:** Sinyaller pozitif ancak ABD TÜFE verisine 8 dk var -> Guardrail işlemi kilitler (`BLOCKED`).

### 3.2 Diğer Çalıştırma Modları
```bash
# Tek seferlik canlı analiz
python main.py --once

# Her 30 saniyede bir otonom analiz döngüsü
python main.py --loop 30

# Sanal makro blackout testi
python main.py --simulate-event "US CPI in 8m"

# Borsaya gerçek emir iletmeden simülasyon (Dry-Run)
python main.py --dry-run
```

TradingView takvim verilerini yenilemek için proje klasöründe `python takvim_cek.py` çalıştırın. Toplayıcı bugünden itibaren 7 günlük dönemdeki yüksek etkili ABD/Almanya/Euro Bölgesi olaylarını `takvim_verileri.json` dosyasına kaydeder; ajan her analiz döngüsünde bu dosyayı blackout kontrolüne dahil eder.

### 3.3 Testleri Çalıştırma
```bash
pytest -v
```

---

## 4. Dürüst Veri ve Jüri Şeffaflığı (Bilinen Sınırlamalar)

- **Doğrulanmış Canlı Bileşenler:** OKX CLI üzerinden bakiye sorgulama, mum verisi (1H, 15m), ticker, spot alım ve attached TP/SL emirleri gerçek OKX demo motorunda canlı test edilmiş ve doğrulanmıştır.
- **Fallback Protokolü:** CryptoQuant veya dış haber scraping servisleri kotaya takıldığında sistem sessizce sahte veri üretmez; `mock_data.json` verisine geçer ve terminalde açıkça `[FALLBACK: MOCK DATA]` etiketini gösterir.
- **Tek Yönlü İşlem (Spot):** İlk MVP'de marjin tasfiye riskinden kaçınmak için sadece Spot alım yapılır; düşüş trendinde nakitte kalınır.

---

## 5. Juri 5 Temel Soru - Cevap Matrisi

| Soru | Nexa-Trader (Sentinel) Cozumu |
| :--- | :--- |
| **1. Agent canli calisiyor mu?** | Evet. @okx_ai/okx-trade-cli v1.4.8+ ile canli OKX TR Demo borsa motoruna ve resmi Avalanche C-Chain RPC endpoint\'ine baglidir. |
| **2. Hangi yetkilere ve limitlere sahip?** | Sermayenin maksimum %5\'i, gunluk en fazla 4 islem, %3 gunluk kayip limiti (Kill-Switch), 1:2 R/R orani (%1.0 SL / %2.0 TP). |
| **3. Gecmis islemler dogrulanabiliyor mu?** | Evet. Her karar ve TP/SL seviyesi SHA-256 ozetiyle Avalanche Fuji Testnet\'teki AgentNotary akilli sozlesmesine muhurlenir. |
| **4. Beklenmedik girdide ne yapar?** | Guardrail korumasi devreye girer; supheli veya kural disi durumlarda sermayeyi korumak adina varsayilan olarak nakitte kalir ([NO TRADE]). |
| **5. Cozdugu problem ve hedef kitle nedir?** | Gunluk alim-satim yapan yatirimcilarin duygusal ve kontrolsuz islemlerini onleyerek matematiksel, risk kontrollu ve blokzinciri uzerinde denetlenebilir bir otonom disiplin saglar. |

