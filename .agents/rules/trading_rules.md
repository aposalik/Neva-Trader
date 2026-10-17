# Quant İşlem ve Deterministik Risk Kuralları

Bu kurallar `Nexa-Trader (Sentinel)` otonom karar ve emir yürütme motoru tarafından istisnasız uygulanır.  
Referans Belge: [agent_trade_kit_field_guide.md](file:///c:/Users/Yusuf/Desktop/Nexa-Trader/agent_trade_kit_field_guide.md)

---

## 1. Giriş ve Sinyal Onay Kuralları (4 Ayak Oybirliği)
- **Oybirliği Prensibi:** Bir emrin açılabilmesi için 4 sinyal ayağının (Teknik, On-Chain, Haber, Makro) tamamının `PASS` (Onay) vermesi şarttır. Herhangi bir ayak `FAIL` veya `NEUTRAL` dönerse nihai karar kesinlikle `NO TRADE` olmalıdır.
- **1. Ayak: Teknik Analiz (OKX ATK):**
  - **1H Trend Filtresi:** `EMA 20 > EMA 50` ve `Son Fiyat > EMA 20`.
  - **1H Hacim Teyidi:** Son 1 saatlik işlem hacmi, önceki 5 saatin ortalama hacminden büyük olmalıdır (`volume_ratio > 1.0`).
  - **15m Giriş Teyidi:** Trend yönündeki geri çekilme (pullback) sonrası Bullish Engulfing, Hammer veya Morning Star mum formasyonlarından biri oluşmalıdır. Kapanmamış (confirm=0) mumlar analize dahil edilemez.
- **2. Ayak: On-Chain (CryptoQuant / Avalanche C-Chain):**
  - Borsa rezerv değişimi negatif/azalan olmalıdır (satış baskısı düşüklüğü).
  - MVRV oranı sağlıklı bölgede (< 2.5) bulunmalıdır.
  - Balina net akışı ve staking oranı pozitif/stabil olmalıdır.
- **3. Ayak: Haber ve Piyasa Duyarlılığı (OKX Sentiment / Gemini / TradingView):**
  - AVAX ve BTC duyarlılık skoru pozitif (`score >= 0.0`) olmalıdır. Negatif haber akışı doğrudan vetodur.
- **4. Ayak: Makro Ekonomik Takvim:**
  - 3 yıldızlı kritik ekonomik verilerden (TÜFE, Faiz, Tarım Dışı İstihdam vb.) 30 dakika önce ve 30 dakika sonra işlem açılması kesinlikle engellenir (`[BLOCKED: Macro blackout window]`).

---

## 2. Sermaye, R/R Yönetimi ve Kullanıcı Yapılandırması

### 2.1 Sermaye Koruma Sınırları (Önerilen Day Trading Parametreleri)
- **Maksimum İşlem Büyüklüğü:** Tek bir işlemde kullanılacak maksimum sermaye, mevcut USDT bakiyesinin en fazla **%5.0**'i olabilir (`position_size_pct = 5.0`).
- **Önerilen Day Trading R/R Oranı:**
  - **Zarar Durdur (Stop-Loss):** **%1.0** (`stop_loss_pct = 1.0`).
  - **Risk / Ödül (R/R):** **1 : 2** (`risk_reward_ratio = 2.0`).
  - **Kâr Al (Take-Profit):** **%2.0** (`take_profit_pct = stop_loss_pct * risk_reward_ratio`).
- **Atomik Attached TP/SL Emri:** Pozisyon OKX borsasına gönderildiği mikrosaniyede TP ve SL seviyeleri emre bağlı (`--tpTriggerPx` ve `--slTriggerPx`) olarak iletilir. Piyasada asla korumasız açık pozisyon bırakılamaz.

### 2.2 Kullanıcı Yapılandırma Özgürlüğü (Configurability)
- Kullanıcı bu oranları koda dokunmadan dilediği gibi değiştirebilir:
  - Ayar Dosyası: `config.json` -> `"risk"` nesnesi.
  - Değiştirilebilir Parametreler: `position_size_pct` (% sermaye), `stop_loss_pct` (% SL), `risk_reward_ratio` (R/R katsayısı), `max_daily_trades`, `max_daily_loss_pct`.
- Ajan her döngü başlangıcında `config.json` dosyasını yeniden okur, parametre değişiklikleri motor yeniden başlatıldığında anında devreye girer.

---

## 3. Deterministik Guardrail Kilitleri

Aşağıdaki durumlarda 4 ayak onay verse dahi emir borsa motoruna iletilmez:
1. **Açık Pozisyon Kilidi:** Halihazırda açık bir pozisyon varsa yeni alım emri açılamaz (`[BLOCKED: Open position exists]`).
2. **Maksimum Günlük İşlem Limiti:** Günlük en fazla 4 işlem açılabilir (`[BLOCKED: Max daily trades reached]`).
3. **Günlük Maksimum Zarar (Kill-Switch):** Günlük gerçekleşen zarar bakiye bazında %3'ü aşarsa sistem gün sonuna kadar kilitlenir (`[BLOCKED: Daily loss limit exceeded]`).
4. **Maksimum Spread Kilidi:** Alış-satış spread'i %0.15'i aşarsa likidite yetersizliği nedeniyle işlem engellenir.
5. **Makro Blackout:** Kritik olay öncesi ve sonrası ±30 dakika boyunca işlem vetolanır.

---

## 4. Canlı MVP Doğrulama Prensibi
- Nexa-Trader bir salt kağıt simülatörü değildir; OKX Agent Trade Kit (`okx spot place`) üzerinden OKX Demo hesabına gerçek zamanlı emir iletebilen çalışan bir MVP'dir.
- Jüri sunumunda veya canlı testte borsadaki gerçekleşmeler `https://tr.okx.com/trade-spot/avax-usdt` ekranından anlık olarak doğrulanabilir olmalıdır.
