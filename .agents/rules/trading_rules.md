# Quant İşlem ve Deterministik Risk Kuralları

Bu kurallar `Nexa-Trader` motoru tarafından her karar ve emir yürütme döngüsünde istisnasız uygulanmalıdır.

## 1. Giriş ve Sinyal Onay Kuralları
- **4 Ayak Oybirliği Kuralı:** Emir verilebilmesi için 4 sinyal ayağının (Teknik, On-Chain, Haber, Makro) tamamının `PASS` (Onay) vermesi şarttır. Herhangi bir ayak `FAIL` veya `NEUTRAL` dönerse karar kesinlikle `NO TRADE` olmalıdır.
- **Teknik Filtre:**
  - 1H grafikte: `EMA 20 > EMA 50` ve `Son Fiyat > EMA 20`.
  - 1H hacim: Son 1 saatlik hacim, önceki 5 saatin ortalama hacminden büyük olmalıdır.
  - 15m grafikte: Geri çekilme sonrası Bullish Engulfing, Hammer veya Morning Star mum formasyonlarından biri teyit edilmelidir. Kapanmamış (confirm=0) mumlar analize dahil edilemez.

## 2. Sermaye ve R/R Yönetimi
- **Maksimum Pozisyon Riski:** Her bir işlemde kullanılacak sermaye, mevcut USDT bakiyesinin tam **%5.0**'i ile sınırlandırılmıştır (`position_size_pct = 5.0`).
- **Dinamik R/R Oranı:** `take_profit_pct = stop_loss_pct * risk_reward_ratio` formülü esastır.
  - Stop-Loss: %1.2
  - Risk / Ödül (R/R): 1 : 2
  - Otomatik Hesaplanan Take-Profit: %2.4
- **Atomik Attached TP/SL:** OKX borsasına gönderilen emir tek bir komutta (`--tpTriggerPx` ve `--slTriggerPx`) attached olarak verilmelidir. Açık pozisyonun korumasız kalmasına asla izin verilemez.

## 3. Guardrail ve Acil Durum Kilitleri
- **Açık Pozisyon Kilidi:** Halihazırda açık bir pozisyon varsa yeni alım emri açılamaz (`[BLOCKED: Open position exists]`).
- **Maksimum Günlük İşlem Limiti:** Günde en fazla 4 işlem açılabilir (`[BLOCKED: Max daily trades reached]`).
- **Günlük Max Zarar (Kill-Switch):** Günlük gerçekleşen zarar %3'ü aşarsa sistem kendini gün sonuna kadar kilitler (`[BLOCKED: Daily loss limit exceeded]`).
- **Makro Blackout:** 3 yıldızlı kritik ekonomik verilerden 30 dakika önce ve 30 dakika sonra işlem açılması engellenir (`[BLOCKED: Macro blackout window]`).
