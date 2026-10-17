# NEXA-TRADER (SENTINEL): Çok Kaynaklı Otonom Day Trading Ajanı

Bu proje, **Agentic Hackathon Ankara 2026** (OKX TR × Team1 Türkiye) için geliştirilmiştir.
OKX Agent Trade Kit (`@okx_ai/okx-trade-cli` v1.4.8+, `--demo` modu) üzerinde `AVAX/USDT` paritesinde çalışan; 4 sinyal ayağını (Teknik, On-Chain, Haber, Makro) birleştiren ve deterministik risk korumasına (Guardrail) sahip otonom bir AI alım-satım ajanıdır.

---

## 1. Sistem Mimarisi (Architecture)

Nexa-Trader (Sentinel), BlackRock ve Team1 Türkiye'nin *Güvenilir Agent* standartlarına (Kimlik, Araçlar, Sınırlar, İzlenebilirlik) tam uyumlu, 4 katmanlı bir boru hattı mimarisiyle çalışır:

```
+--------------------------------------------------------------------------------------------------+
|                            1. VERI TOPLAMA VE ENTEGRASYON KATMANI                                |
|  - OKX ATK CLI (v1.4.8)    : 1H & 15m Mumlar, Ticker, Cüzdan Bakiyesi, Spot & Attached TP/SL     |
|  - Avalanche C-Chain RPC   : Anlık Blok Yüksekliği, nAVAX Gaz Maliyeti, Canlı Ağ Durumu          |
|  - Cointelegraph/TV RSS    : Canlı Haber Akışı, Google Gemini 3.8 Flash Kurumsal NLP Analizi     |
|  - Ekonomik Takvim         : OKX Calendar + takvim_verileri.json (TradingView) + events.json      |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  v
+--------------------------------------------------------------------------------------------------+
|                            2. 4 AYAKLI SINYAL VE STRATEJI MOTORU                                 |
|  [Teknik Analiz]    : 1H Trend (EMA20 > EMA50, Kapanış > EMA20, Hacim) + 15m Pullback Onayı      |
|  [On-Chain Sağlık]  : C-Chain Blok/Gaz Akışı, Rezerv Azalışı (<0), MVRV (1.0-2.5), Balina Trendi  |
|  [Haber & NLP]      : Gemini 3.8 Flash Wall Street Duyarlılık Skoru (>0.0, negatifse VETO)       |
|  [Makro Blackout]   : ABD / Almanya / EUR 3 Yıldızlı Olaylardan ±30 dk Önce/Sonra İşlem Yasağı   |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | [Kural: UNANIMOUS (4 Ayak da PASS Olmalı)]
                                                  v
+--------------------------------------------------------------------------------------------------+
|                            3. DETERMINİSTİK RISK VE GUARDRAIL KATMANI                            |
|  - Sermaye Boyutu   : Cüzdan bakiyesinin sabit maksimum %5.0'i ile pozisyon açılışı            |
|  - Risk/Kazanç (R/R): %1.0 Stop-Loss (Zarar Durdur) / %2.0 Take-Profit (Kâr Al) [1:2 Oran]       |
|  - İşlem Limitleri  : Günde maksimum 4 işlem, aynı anda tek aktif pozisyon kuralı                |
|  - Acil Kilitleme   : Günlük toplam zarar %3.0'e ulaştığında sistemi 24 saat donduran Kill-Switch|
|  - Likidite Koruma  : Alış-satış makası (Spread) %0.15'i aşarsa piyasa alımını engelleme        |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | [Guardrail Onayı Verildi]
                                                  v
+--------------------------------------------------------------------------------------------------+
|                            4. BORSA VE BLOKZİNCİRİ YÜRÜTME (EXECUTION)                           |
|  - OKX TR Demo Motoru   : okx spot place --instId AVAX-USDT --tdMode cash --side buy             |
|  - Atomik Attached TP/SL: --tpTriggerPx ve --slTriggerPx borsa motorunda milisaniyede kilitlenir  |
|  - Avalanche Fuji Noter : `AgentNotary.sol` (Chain ID 43113) ile karar hash'i zincire mühürlenir  |
|                           (Snowtrace Explorer üzerinden doğrulanabilir audit trail)              |
+--------------------------------------------------------------------------------------------------+
`

### Proje Modüler Yapısı
- `data/` : OKX CLI, Avalanche C-Chain RPC, TradingView RSS ve ekonomik takvim veri köprüleri.
- `strategy/` : 4 ayağı tek potada eriten karar motoru (`signal_engine.py`) ve teknik hesaplamalar (`indicators.py`).
- `risk/` : Sermaye koruması, bakiye hesaplama ve guardrail güvenlik kilitleri (`guardrail.py`).
- `execution/` : OKX borsa emir yürütücüsü (`executor.py`) ve Avalanche Fuji Web3 noter mühürleyicisi (`notary.py`).
- `contracts/` : Avalanche üzerinde çalışan `AgentNotary.sol` akıllı sözleşmesi.
- `reports/` : Her analiz döngüsünde otomatik güncellenen HTML Dashboard, CSV ve Markdown denetim kayıtları.

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

# Son 30 günlük karar geçmişini analiz edip öneriler üret
python main.py --review-history

# Son 7 günü analiz et
python main.py --review-history --history-days 7
```

TradingView takvim verilerini yenilemek için proje klasöründe `python takvim_cek.py` çalıştırın. Toplayıcı bugünden itibaren 7 günlük dönemdeki yüksek etkili ABD/Almanya/Euro Bölgesi olaylarını `takvim_verileri.json` dosyasına kaydeder; ajan her analiz döngüsünde bu dosyayı blackout kontrolüne dahil eder.

### 3.3 Kullanıcı Kural Motoru ve Risk Belirleme (CMD Üzerinden Özelleştirme)
Ajanın işlem başına bakiyenin yüzde kaçını kullanacağı (`--capital-pct`), Stop-Loss (`--sl-pct`) ve Take-Profit (`--tp-pct`) oranları kullanıcı tarafından komut satırından dinamik olarak belirlenebilir:

#### A. Komut Satırından Doğrudan Parametre ile Çalıştırma
```bash
# Örnek 1: Bakiyenin %10'u ile pozisyon aç, %1.5 SL / %3.0 TP uygula
python main.py --capital-pct 10.0 --sl-pct 1.5 --tp-pct 3.0

# Örnek 2: 30 saniyelik otonom döngüde özel risk kuralları ile çalıştır
python main.py --loop 30 --capital-pct 7.5 --sl-pct 1.2 --tp-pct 2.4

# Örnek 3: Günlük zarar tavanını (Kill-Switch) ve işlem limitini de belirle
python main.py --capital-pct 5.0 --sl-pct 1.0 --tp-pct 2.0 --max-daily-trades 3 --max-daily-loss-pct 2.5
```

#### B. Terminalden İnteraktif Kural Belirleme (`--set-rules`)
Ajan başlamadan önce terminal üzerinden adım adım parametreleri girmenizi sağlar (Enter'a basarak mevcut varsayılan değerleri kabul edebilirsiniz):
```bash
python main.py --set-rules

# Döngü moduyla interaktif kural belirleme:
python main.py --loop 30 --set-rules
```
*Terminal Soru Akışı:*
- `-> Bakiye Kullanım Yüzdesi (%) [Mevcut: %5.0]:`
- `-> Stop-Loss (Zarar Durdur) Yüzdesi (%) [Mevcut: %1.0]:`
- `-> Take-Profit (Kâr Al) Yüzdesi (%) [Mevcut: %2.0]:`
- `-> Günlük Maksimum İşlem Sayısı [Mevcut: 4]:`
- `-> Günlük Kill-Switch Zarar Tavanı (%) [Mevcut: %3.0]:`

*(İsteğe bağlı: Belirlediğiniz kuralları `config.json` dosyasına kalıcı olarak işlemek için komutun sonuna `--save-rules` bayrağını ekleyebilirsiniz.)*

### 3.4 Testleri Çalıştırma
```bash
pytest -v
```

Normal analiz döngüsü her karar kaydından sonra geçmiş raporunu otomatik yeniler. Özet her sinyal ayağı için PASS/FAIL/NEUTRAL sayılarını ve varsa doğrulanmış kapanış PnL'sini gösterir. `--once` ve jüri demosu sonunda; sürekli döngüde ilk karardan sonra özet ekrana basılır. Sonraki döngülerde rapor sessizce güncellenir. `--review-history` komutu analizi ayrıca çalıştırmak veya farklı bir dönem seçmek için kullanılabilir. Rapor `reports/history_analysis.md` dosyasına, izlenen pozisyon/dolum durumu `trade_history.json` dosyasına yazılır. Kapanışlar OKX'in gerçek spot dolumları ve ücretleriyle hesaplanır; dry-run işlemleri ve özellik eklenmeden önceki eski kayıtlar geriye dönük PnL üretmez. OKX CLI dolum sorgusu son 3 günle sınırlıdır; uygulamayı bu süreden uzun kapalı bırakmak eksik sonuçlara yol açabilir. Sonuçları başka bir bot veya kişi aynı paritede işlem yapıyorsa kesin strateji performansı olarak yorumlamayın; takip FIFO eşleştirmesine dayanır. Rapor risk ayarlarını otomatik değiştirmez.

---

## 4. Dürüst Veri ve Jüri Şeffaflığı (Bilinen Sınırlamalar)

- **Doğrulanmış Canlı Bileşenler:** OKX CLI üzerinden bakiye sorgulama, mum verisi (1H, 15m), ticker, spot alım ve attached TP/SL emirleri gerçek OKX demo motorunda canlı test edilmiş ve doğrulanmıştır.
- **Fallback Protokolü:** CryptoQuant veya dış haber scraping servisleri kotaya takıldığında sistem sessizce sahte veri üretmez; `mock_data.json` verisine geçer ve terminalde açıkça `[FALLBACK: MOCK DATA]` etiketini gösterir.
- **Tek Yönlü İşlem (Spot):** İlk MVP'de marjin tasfiye riskinden kaçınmak için sadece Spot alım yapılır; düşüş trendinde nakitte kalınır.

---

## 5. Kod İncelemesi ve Mimari Güçlendirmeler (Audit & Hardening)

Yapılan kapsamlı statik incelemeler ve jüri hazırlık testleri doğrultusunda sistemde uygulanan kritik iyileştirmeler:

| Bileşen | Yapılan İyileştirme | Güvenlik / Şeffaflık Etkisi |
| :--- | :--- | :--- |
| **On-Chain Şeffaflık** | `Source.HYBRID` rozeti eklendi. Avalanche RPC'den canlı blok ve nAVAX gaz maliyeti okunurken, rezerv/MVRV metriklerinin analitik modelden geldiği terminalde `[HIBRIT: RPC+MODEL]` olarak netleştirildi. | Jüriye yanıltıcı veri sunumu engellendi; canlı RPC ile analitik model ayrımı şeffaflaştırıldı. |
| **Canlı Kill-Switch Senkronizasyonu** | OKX CLI `spot_fills` sorgusu entegre edilerek gerçekleşen emirlerin kâr/zararı (`sync_realized_pnl_from_fills`) kümülatif günlük zarar takipçisine bağlandı. | Günlük %3 zarar sınırı borsa motorundaki gerçek dolumlarla anlık kilitlenebilir hale getirildi. |
| **Web3 Fuji Noter Doğrulaması** | Karar hash'leri Avalanche Fuji Testnet'e (Chain ID: 43113) Web3 imzalı işlemle gönderilir. İşlem başarısız olursa veya cüzdan anahtarı girilmemişse sessizce onaylamak yerine `notarized: false` ve `ZİNCİRE_MÜHÜRLENEMEDİ` raporlanır. | Blokzincir denetim izinde %100 dürüstlük sağlandı. |
| **Agentic Reasoning Açıklanabilirliği** | Sinyal motoruna `generate_agentic_reasoning()` zinciri eklendi. Ajanın sermayeyi neden koruduğu ve işlemi neden beklettiği terminal ve raporlara yansıtıldı. | Ajanın salt kural motoru değil, araçları ve koşulları tartan açıklanabilir bir AI karar mekanizması olduğu gösterildi. |
| **Canlı Emir Güvenliği** | `--demo-script` ve `--dry-run` bayraklarının `--live` ile aynı anda çalışması kesin kurallarla engellendi. | Sunum sırasında borsaya kazara istenmeyen emir gönderilme riski sıfırlandı. |
| **Makro Takvim Akışı** | `data/macro.py` içindeki `calendar_events` değişkeni ve TradingView UTC zaman dilimi normalizasyonu (`_as_utc`) düzeltildi (12/12 test geçildi). | Otonom döngüde yüksek etkili ekonomik veri blackout kontrolünün çökmeden çalışması garanti altına alındı. |

