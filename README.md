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
|   OKX ATK API    | |   CryptoQuant    | |   Haber Analizi  | |  Investing.com   | | DETERMINİSTİK    |
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
4. **4. Ayak — Makro Takvim & Blackout (Investing.com):**
   - ABD, Almanya ve Euro Bölgesi 3 yıldızlı kritik ekonomik verilerden **±30 dakika** önce/sonra yeni işlem açılması kilitlenir.
5. **+1 Koruma Katmanı — Deterministik Risk Guardrail:**
   - Her işlemde portföyün sabit **%5.0**'i riske edilir.
   - **1:2 R/R Oranı:** Stop-Loss %1.2, Take-Profit %2.4.
   - **Atomik Attached TP/SL:** OKX borsasına tek komutta (`--tpTriggerPx` ve `--slTriggerPx`) iletilir; pozisyon açıldığı mikrosaniyede korumaya alınır.
   - Kill-Switch: Günlük zarar %3'ü aşarsa sistem kendini kilitler.

---

## 2. Hızlı Kurulum

### 2.1 Bağımlılıklar
Node.js (v18+) ve Python 3.10+ gereklidir:

```bash
# 1. OKX CLI Kurulumu ve Demo Girişi
npm install -g @okx_ai/okx-trade-cli
okx auth login   # Tarayıcıda doğrulama koduyla tek tıkla bağlanın

# 2. Python Kütüphanelerini Yükleyin
pip install -r requirements.txt

# 3. Ortam Değişkenleri (Opsiyonel Gemini API)
cp .env.example .env
# .env dosyasına GEMINI_API_KEY değerinizi ekleyin (yoksa ATK yerleşik duyarlılık kullanılır)
```

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

### 3.3 Testleri Çalıştırma
```bash
pytest -v
```

---

## 4. Dürüst Veri ve Jüri Şeffaflığı (Bilinen Sınırlamalar)

- **Doğrulanmış Canlı Bileşenler:** OKX CLI üzerinden bakiye sorgulama, mum verisi (1H, 15m), ticker, spot alım ve attached TP/SL emirleri gerçek OKX demo motorunda canlı test edilmiş ve doğrulanmıştır.
- **Fallback Protokolü:** CryptoQuant veya dış haber scraping servisleri kotaya takıldığında sistem sessizce sahte veri üretmez; `mock_data.json` verisine geçer ve terminalde açıkça `[FALLBACK: MOCK DATA]` etiketini gösterir.
- **Tek Yönlü İşlem (Spot):** İlk MVP'de marjin tasfiye riskinden kaçınmak için sadece Spot alım yapılır; düşüş trendinde nakitte kalınır.
