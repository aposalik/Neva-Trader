# NEXA-TRADER (SENTINEL) — ÇALIŞTIRMA VE OPERASYON REHBERİ

Bu kılavuz, OKX TR & Avalanche Agentic Hackathon Ankara projesi olan **Nexa-Trader**'ın sıfırdan ayağa kaldırılması, test edilmesi, jüri sunumu ve OKX Demo arayüzünden doğrulanması için gereken tüm adımları içerir.

---

## 1. Sistem Gereksinimleri ve Ön Hazırlık

- **İşletim Sistemi:** Windows (PowerShell veya CMD)
- **Python Sürümü:** Python 3.10+ (Python 3.14 ile doğrulanmıştır)
- **OKX CLI:** `@okx_ai/okx-trade-cli` v1.4.8+ kurulu ve OAuth yetkilendirmesi tamamlanmış olmalıdır.

Terminalde oturum ve bakiye kontrolü:
```powershell
okx account balance --demo
```
*(Gereken çıktı: Yaklaşık 5,000 USDT demo bakiyesi).*

---

## 2. Kurulum ve Ortam Hazırlığı

Terminali proje dizininde açın:
```powershell
cd C:\Users\Yusuf\Desktop\Nexa-Trader
```

### 2.1 Kütüphanelerin Yüklenmesi
```powershell
pip install -r requirements.txt
```
*(Yüklenen paketler: `pandas`, `numpy`, `rich`, `requests`, `python-dotenv`, `pytest`)*

### 2.2 Çevre Değişkenleri (.env)
Canlı Gemini haber analizi için `.env` dosyasını kontrol edin:
```powershell
copy .env.example .env
```
*(Eğer API anahtarınız yoksa sistem otomatik olarak güvenli `[FALLBACK: MOCK DATA]` moduna geçer).*

### 2.3 Birim Testlerin Doğrulanması
Teknik analiz formasyonları, 1:2 R/R hesaplamaları ve guardrail kilitleri test edilir:
```powershell
pytest -v
```
**Beklenen Sonuç:** `11 passed in 0.4x s`

---

## 3. Ajanı Çalıştırma Senaryoları

### Senaryo A: Jüri Sunumu ve Altın Demo (ÖNERİLEN)
3 altın senaryoyu (1. Tüm ayaklar onaylı alım emri, 2. Negatif haber vetosu, 3. Makro blackout engeli) sırayla konsolda oynatır ve **OKX Demo hesabına gerçek alım emri gönderir**:
```powershell
python main.py --demo-script
```

> **Not (Borsaya Emir Göndermeden Simüle Etmek İçin):**  
> `python main.py --demo-script --dry-run`

---

### Senaryo B: Canlı Piyasa Analizi (Tek Seferlik)
OKX'ten anlık AVAX-USDT 1 saatlik ve 15 dakikalık mumlarını, emir defteri spread'ini ve haber duyarlılığını çeker:
```powershell
python main.py --once
```

---

### Senaryo C: Otonom Döngü Modu (Sürekli Çalışma)
Her 30 saniyede bir piyasayı tarayarak sinyal oluştuğunda emir tetikler:
```powershell
python main.py --loop 30
```

---

### Senaryo D: Makro Blackout Olay Simülasyonu
Takvime kritik bir veri (örn: 8 dakika sonra ABD TÜFE) enjekte ederek ajan korumasını test eder:
```powershell
python main.py --simulate-event "US CPI in 8m" --once
```

### TradingView Takvimini Yenileme
TradingView'dan bugünden itibaren 7 günlük dönemdeki yüksek etkili ABD/Almanya/Euro Bölgesi olaylarını almak için proje klasöründe:
```powershell
python takvim_cek.py
```
Veriler `takvim_verileri.json` dosyasına yazılır ve ajan tarafından otomatik olarak makro blackout kontrolünde kullanılır. İnternet veya TradingView erişimi yoksa mevcut JSON dosyası korunur.

### OKX Akışını Kontrol Etme
`python test_flow.py` bakiye ve fiyat bilgilerini salt okunur biçimde kontrol eder. Demo alım emri ve attached TP/SL denemek için açıkça `python test_flow.py --submit-demo-order` çalıştırın.

### Geçmiş Kayıtları Analiz Etme
Son 30 günlük kararları ve kullanıcıya yönelik iyileştirme önerilerini incelemek için:
```powershell
python main.py --review-history
```
Dönemi değiştirmek için `python main.py --review-history --history-days 7` gibi gün sayısı verin. Özet her sinyal ayağı için PASS/FAIL/NEUTRAL adetlerini gösterir. Rapor `reports/history_analysis.md` dosyasına kaydedilir; izlenen giriş ve kapanış dolumları `trade_history.json` içinde tutulur. Kapanış PnL'si OKX'in gerçek spot dolum fiyatları ve ücretleri üzerinden hesaplanır; dry-run işlemleri ve özellik eklenmeden önceki kayıtlar hesaba katılmaz.
Normal `--once`, `--loop` ve `--demo-script` çalıştırmalarında karar günlüğü ve rapor otomatik güncellenir. Tek seferlik analiz ve demo sonunda, sürekli modda ilk analizden sonra özet konsolda gösterilir. OKX CLI spot dolum geçmişi sorgusu son 3 günle sınırlı olduğundan uygulamayı 3 günden uzun süre kapalı bırakmak eksik kapanış verisi oluşturabilir. Ayrıca aynı paritede uygulama dışında işlem yapılıyorsa FIFO eşleştirmesi kâr/zararın hangi işleme ait olduğunu kesin ayıramaz. Rapor eksik ya da eşleştirilemeyen PnL için kazanma oranı uydurmaz.
---

## 4. OKX Arayüzünde Emri Görüntüleme Adımları

Ajan Senaryo 1'de alım yaptığında borsada emri izlemek için:

1. **Doğru Sayfaya Gidin:**  
   Tarayıcınızda şu adresi açın:  
   👉 **`https://tr.okx.com/trade-spot/avax-usdt`**  
   *(Hesabınızın sağ üstte **Demo Trading / Simülasyon İşlemleri** modunda olduğundan emin olun).*

2. **Emir Geçmişi (Order History):**  
   Grafiğin altındaki panelden **"Emir Geçmişi"** sekmesine tıklayın.  
   Ajanın attığı Piyasa Alış (Market Buy) emrinin **"Filled / Gerçekleşti"** durumunu göreceksiniz.

3. **Kâr Al / Zarar Durdur (Attached TP/SL):**  
   Alttaki panelden **"Açık Emirler" -> "Tetikleme Emri (KA/ZD)"** sekmesini açın.  
   Ajanın alım anında borsa motoruna kilitlediği **%2.4 Kâr Al (TP)** ve **%1.2 Zarar Durdur (SL)** emirlerinin hazır beklediğini göreceksiniz.

4. **Terminalden Doğrulama (Alternatif):**
   ```powershell
   okx spot orders --instId AVAX-USDT --demo
   okx spot orders-algo --instId AVAX-USDT --demo
   ```

---

## 5. Raporlama ve Denetim İzi (Audit Log)

Ajanın verdiği tüm kararlar, veto gerekçeleri ve emir ayrıntıları 3 farklı formatta tablo olarak tutulur:

- **Markdown Raporu:** `reports/decisions_table.md`
- **Excel Uyumlu CSV:** `reports/decisions_table.csv`
- **Web Panosu:** `reports/decisions_dashboard.html`

Tabloları manuel güncellemek için:
```powershell
python export_reports.py
```
