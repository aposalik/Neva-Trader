# NEXA-TRADER (SENTINEL): MVP MİMARİSİ VE GELİŞİM PLANI

**Etkinlik:** 17 Ekim Agentic Hackathon Ankara (OKX TR × Avalanche)  
**Proje Adı:** Nexa-Trader (Sentinel)  
**Tarih:** 17 Ekim 2026  
**Durum:** Çalışan Otonom MVP (Canlı OKX Demo Entegrasyonlu)  

---

## 1. Bugüne Kadar Yapılanların Özeti (Mevcut Durum)

Proje, 12 saatlik hackathon teslim disiplinine uygun olarak uçtan uca çalışan bir MVP seviyesine getirilmiştir:

1. **4 Ayaklı Karar Motoru (`strategy/signal_engine.py`):**
   - Teknik Analiz, On-Chain, Haber/Duyarlılık ve Makro Takvim ayaklarını tek bir deterministik yapıda birleştiren ve oybirliği (`UNANIMOUS`) arayan karar motoru inşa edildi.
2. **OKX Agent Trade Kit (ATK) CLI v1.4.8 Entegrasyonu (`data/okx_client.py`):**
   - Positional instrument ID (`AVAX-USDT`) desteği.
   - 1H ve 15m OHLCV mumlarının çekilmesi.
   - Canlı cüzdan bakiyesinin sorgulanması (Mevcut test bakiyesi: ~$4,750 USDT).
   - **Atomik Attached TP/SL:** Piyasa alım emri verildiği mikrosaniyede borsa motoruna bağlı Kâr Al ve Zarar Durdur seviyelerinin iletilmesi (`okx spot place --tpTriggerPx ... --slTriggerPx ...`).
3. **Deterministik Risk ve Guardrail Katmanı (`risk/`):**
   - Açık pozisyon kilidi, günlük maksimum zarar kilidi (%3), maksimum işlem sayısı (4), spread filtresi (%0.15) ve makro blackout (±30 dk) korumaları kodlandı ve doğrulandı.
4. **Otomatik Raporlama ve Tablo Sistemi (`reports/`):**
   - Ajanın her döngüsünde `decisions.log` ham verisini otomatik olarak **Markdown**, **Excel Uyumlu CSV** ve **Görsel HTML Dashboard** formatlarına dönüştüren sistem entegre edildi.
5. **Jüri Altın Senaryoları (`--demo-script`):**
   - Piyasa yatay seyretse dahi jüri önünde 3 dakikalık sunumu garantiye alan 3 deterministik senaryo hazırlandı (1. Başarılı Alım, 2. Negatif Haber Vetosu, 3. Makro Blackout Vetosu).
6. **Birim Testleri:** 11 adet hedefli birim testi yazıldı ve hepsi geçti (`pytest -v` 11/11 PASSED).

---

## 2. Kural ve Risk Yapılandırması (Kullanıcı Tarafından Özelleştirilebilir)

Proje kuralları [trading_rules.md](file:///c:/Users/Yusuf/Desktop/Nexa-Trader/.agents/rules/trading_rules.md) dosyasında resmileştirilmiş olup `config.json` üzerinden koda dokunmadan değiştirilebilir:

| Parametre | Önerilen / Varsayılan Değer | Açıklama |
|:---|:---:|:---|
| **Maksimum İşlem Sermayesi** | **%5.0** | Tek bir işlemde cüzdanın en fazla %5'i riske edilir. |
| **Zarar Durdur (Stop-Loss)** | **%1.0** | Giriş fiyatının %1.0 altına yerleştirilen acil çıkış emri. |
| **Risk / Ödül (R/R) Oranı** | **1 : 2** | Day trading disiplinine uygun getiri/risk katsayısı. |
| **Kâr Al (Take-Profit)** | **%2.0** | Dinamik hesaplanan hedef: `%1.0 SL * 2.0 = %2.0 TP`. |
| **Makro Blackout Penceresi** | **±30 Dakika** | 3 yıldızlı kritik veri öncesi ve sonrası işlem yasağı. |
| **Özelleştirilebilirlik** | `config.json` | Parametreler JSON üzerinden anında güncellenir. |
| **Çalışan Canlı MVP İlkesi** | OKX Demo Entegrasyonu | Sadece ekranda simülasyon değil, OKX Demo arayüzünde görülebilen gerçek borsa emri üretir. |

---

## 3. 4 Sinyal Ayağının Detaylı Mimarisi ve Soruların Yanıtları

### 3.1. Ayak 1: Teknik Analiz (OKX ATK)
- **Kullanıcının Sorusu:** *"20/50 EMA'yı zaten OKX'ten çekiyoruz, ekstra bir API almaya gerek var mı?"*
- **Teknik Yanıt:** **HAYIR, KESİNLİKLE GEREK YOK.**
  - **Gerekçe:** OKX Agent Trade Kit (`okx market candles AVAX-USDT --bar 1H/15m`) doğrudan OKX borsa sunucularından anlık OHLCV (Açılış, Yüksek, Düşük, Kapanış, Hacim) verilerini çeker. Bu veri sıfır gecikmeli, limitsiz ve tamamen ücretsizdir.
  - Projemiz bu veriyi alır, yerel bellekte `pandas` kütüphanesini kullanarak EMA 20 ve EMA 50 ortalamalarını milisaniyeler içinde hesaplar.
  - Ekstra bir üçüncü taraf API (TradingView/CoinMarketCap API vb.) eklemek sisteme maliyet, rate-limit (istek kotası) ve harici ağ bağımlılığı getireceğinden teknik olarak gereksizdir.

---

### 3.2. Ayak 2: On-Chain Analizi (CryptoQuant & Avalanche C-Chain)
Avalanche (AVAX) için day trading kararlarında en kritik on-chain metrikler şunlardır:

1. **Borsa Net Akışı ve Rezervi (Exchange Inflow/Outflow):**
   - *Anlamı:* Merkezi borsalara (OKX, Binance vb.) giren ve çıkan AVAX miktarı.
   - *Sinyal:* Rezerv düşüyorsa AVAX'lar soğuk cüzdanlara veya staking'e çekiliyordur -> Satış baskısı az, **BOĞA (PASS)**. Rezerv hızla artıyorsa borsaya satış için transfer yapılıyordur -> **AYI (VETO)**.
2. **MVRV Oranı (Market Value to Realized Value):**
   - *Anlamı:* AVAX piyasa değerinin cüzdanlardaki gerçekleşen maliyet değerine oranı.
   - *Sinyal:* `< 1.0` aşırı ucuz (dip bölgesi), `1.0 - 2.5` sağlıklı trend bölgesi (**PASS**), `> 3.7` aşırı ısınmış tepe bölgesi (**VETO**).
3. **Büyük Cüzdan (Balina) Birikimi (Whale Accumulation):**
   - *Anlamı:* 10.000+ ve 100.000+ AVAX tutan balina adreslerinin son 24 saatteki hareketleri.
4. **Avalanche C-Chain Aktif İşlem Sayısı ve Gaz Tüketimi:**
   - *Anlamı:* Avalanche C-Chain üzerindeki gerçek kullanım yoğunluğu.
5. **Staking Oranı ve Doğrulayıcı (Validator) Sağlığı:**
   - *Anlamı:* Avalanche P-Chain üzerinde kilitli duran AVAX arzı (Arz kilitliyse piyasada satılabilir miktar düşüktür).

*Uygulama Modeli:*
- CryptoQuant REST API anahtarı girildiğinde canlı veri çekilir.
- API anahtarı girilmediğinde sistem şeffaf bir şekilde `[MOCK DATA]` etiketiyle önceden kalibre edilmiş güvenli değerleri kullanarak çalışmayı sürdürür.

---

### 3.3. Ayak 3: Makro Ekonomik Takvim (Investing.com vs OKX Calendar)
- **Investing.com'dan Veri Çekme Durumu:**
  - Investing.com resmi, ücretsiz ve açık bir REST API sunmaz.
  - Web scraping (HTML kazıma) veya `investpy` gibi Python kütüphaneleri Investing.com'un sıkı **Cloudflare Bot Koruması**na takılmakta ve canlı demo esnasında IP engeli (HTTP 403 Forbidden) riski taşımaktadır.
- **Daha Güvenilir Çözüm:**
  - **OKX News Economic Calendar (`okx news economic-calendar`):** Halihazırda projemizde çalışan ve OKX'in sağladığı küresel 3 yıldızlı takvim verisidir. JSON formatında, sıfır bot engeliyle doğrudan gelir.
  - Eğer Investing.com verisi istenirse: Harici bir RSS feed köprüsü veya önbelleğe alınmış takvim JSON servisi entegre edilebilir.

---

### 3.4. Ayak 4: Haber ve Piyasa Duyarlılığı (TradingView & OKX & Gemini)
TradingView'den ve diğer kaynaklardan haber çekme yöntemleri:

1. **TradingView Yöntemi:**
   - TradingView resmi bir haber REST API'si sağlamaz; ancak TradingView Crypto News RSS akışı (`https://www.tradingview.com/news/category/crypto/`) veya TradingView genel kripto piyasa duyarlılık göstergesi çekilebilir.
2. **Mevcut OKX ATK Sentiment (Halihazırda Çalışan):**
   - `okx news coin-sentiment` komutu doğrudan OKX'in profesyonel duyarlılık motorunu kullanır. Şu anda ajanımızın canlı çıktısında gördüğünüz üzere AVAX için: `Boğa: %67, Ayı: %20 -> Skor: +0.41` şeklinde anlık çalışmaktadır.
3. **Google Gemini LLM Entegrasyonu:**
   - Çekilen son 5 haber başlığı Gemini API'ye gönderilerek -1.0 ile +1.0 arasında bağımsız bir Yapay Zekâ Güven Skoru üretilir.

---

## 4. Yapılacaklar Yol Haritası (Uygulanan ve Tamamlanan Adımlar)

- [x] **Adım 1: Risk ve Sermaye Kurallarının Güncellenmesi**
  - Cüzdanın maksimum %5'i ile sınırlandırıldı. %1.0 Stop-Loss, %2.0 Take-Profit (1:2 R/R) şablonu yerleştirildi.
- [x] **Adım 2: Kural Belgelerinin ve Parametrelerin Senkronizasyonu**
  - `trading_rules.md` ve `config.json` tam senkronize edildi. Koda dokunmadan JSON üzerinden özelleştirilebilir yapı sağlandı.
- [x] **Adım 3: Canlı Avalanche C-Chain RPC & On-Chain Veri Besleyici**
  - `https://api.avax.network/ext/bc/C/rpc` üzerinden canlı blok yüksekliği, gaz fiyatı ve tx metrikleri doğrudan sisteme bağlandı.
- [x] **Adım 4: Harici Makro Takvim Feed Köprüsü (ForexFactory / Investing Alternatifi)**
  - Açık küresel JSON takvim akışı (`ff_calendar_thisweek.json`) OKX Calendar'a çift yönlü yedek olarak entegre edildi.
- [x] **Adım 5: TradingView Partner RSS & Canlı Gemini 3.8 Flash Duyarlılık Motoru**
  - Cointelegraph/TradingView RSS akışı ve Google Gemini 3.8 Flash LLM NLP analizi canlı haber akışına bağlandı.
- [x] **Adım 6: Avalanche Fuji Testnet `AgentNotary` Akıllı Sözleşmesi (Jüri Bonus Puanı)**
  - `contracts/AgentNotary.sol` ve `execution/notary.py` ile alınan her işlem kararının ve TP/SL planının SHA-256 hash özeti Avalanche Fuji C-Chain üzerine mühürlendi.

