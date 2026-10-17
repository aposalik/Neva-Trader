# NEXA-TRADER: DIŞ ENTEGRASYON, API ANAHTARLARI VE HESAP REHBERİ

Bu rehber, **Adım 3, 4, 5 ve 6**'da yer alan dış servislerin nasıl temin edileceğini, hangi siteden hangi adımlarla ücretsiz anahtar/hesap açılacağını ve sisteme nasıl entegre edileceğini adım adım açıklar.

---

## 1. Genel Durum Özeti ve Gereksinim Matrisi

| Adım | Servis / Özellik | Gerekli Bilgi / Anahtar | Ücret | Durum |
|:---|:---|:---|:---:|:---|
| **Adım 1-2** | OKX ATK & Risk Motoru | OKX CLI OAuth | Ücretsiz | **TAMAMLANDI** |
| **Haber** | Google Gemini LLM | `GEMINI_API_KEY` | Ücretsiz | **TAMAMLANDI (Canlı devrede)** |
| **Adım 3** | Avalanche & CryptoQuant | Avalanche RPC (Ücretsiz) / CryptoQuant Key | İsteğe Bağlı | **RPC Canlıda / CQ API Opsiyonel** |
| **Adım 4** | Makro Ekonomik Takvim | OKX Calendar / ForexFactory RSS | Ücretsiz | **OKX Canlıda / Harici feed eklenecek** |
| **Adım 5** | TradingView / Kripto Haber | Cointelegraph RSS / CryptoPanic API | Ücretsiz | **RSS Canlıda / CryptoPanic Opsiyonel** |
| **Adım 6** | Avalanche Fuji Testnet (Bonus) | Testnet Cüzdanı (Private Key) + Faucet AVAX | %100 Ücretsiz | **Sıradaki Kritik Adım (Jüri Bonusu)** |

---

## 2. Adım Adım Hesap ve Anahtar Alma Kılavuzu

### 🟡 ADIM 3: On-Chain (CryptoQuant & Avalanche)
Şu anda Avalanche C-Chain genel RPC'si (`https://api.avax.network/ext/bc/C/rpc`) üzerinden canlı blok yüksekliği, tx sayısı ve gaz verilerini **sıfır anahtarla** çekmekteyiz.

Eğer CryptoQuant'ın profesyonel zincir verilerini de bağlamak isterseniz:
1. **Site:** [cryptoquant.com](https://cryptoquant.com)
2. **Kayıt:** Ücretsiz hesap açın.
3. **API Sayfası:** Profil -> *API Management* sekmesine gidin.
4. **Key:** *Generate API Key* butonuna basın.
5. **.env Eklemesi:**
   ```env
   CRYPTOQUANT_API_KEY=cq_xxxxxxxxxxxxxxxx
   ```
*(Not: Hackathon için Avalanche C-Chain RPC verimiz tamamen canlı ve jüri için fazlasıyla yeterlidir).*

---

### 🟡 ADIM 4: Makro Takvim (Investing.com & ForexFactory)
Investing.com'un katı Cloudflare bot koruması nedeniyle scraper yerine açık formatta takvim sunan **ForexFactory / OKX Calendar** hibrit yapısını kullanıyoruz.
- **Herhangi bir API anahtarı veya şifre GEREKMEZ.**
- Sistem `data/macro.py` içerisinde açık XML/JSON endpoint'lerinden otomatik çeker.

---

### 🟡 ADIM 5: Haber ve Piyasa Duyarlılığı (CryptoPanic & TradingView)
Şu anda Cointelegraph/TradingView canlı RSS akışı ve **Gemini 3.8 Flash** yapay zekası sisteme bağlıdır.  
İlave olarak profesyonel kripto haber filtreleme API'si (CryptoPanic) eklemek isterseniz:
1. **Site:** [cryptopanic.com/developers/api/](https://cryptopanic.com/developers/api/)
2. **Kayıt:** Ücretsiz geliştirici hesabı açın.
3. **Auth Token:** *Auth Token* alanındaki anahtarı kopyalayın.
4. **.env Eklemesi:**
   ```env
   CRYPTOPANIC_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

### 🔴 ADIM 6: Avalanche Fuji Testnet İşlem Mühürleme (Jüri Bonus Puanı)
Hackathon değerlendirme kriterlerinde yer alan *"Avalanche ekosistemiyle etkileşim ve akıllı sözleşme kullanımı"* bonus puanını almak için ajanımızın verdiği her alım-satım kararının özet hash'ini **Avalanche Fuji Testnet** üzerindeki `AgentNotary` sözleşmesine yazdıracağız.

Bunun için gerekenler (**Sıfır Gerçek Para / Tamamen Test Ağı**):

#### 1. Testnet Cüzdanı Oluşturma (Core Wallet veya MetaMask)
- Tarayıcınızda MetaMask veya Core Wallet eklentisini açın.
- Ağ olarak **Avalanche Fuji Testnet**'i seçin (Chain ID: `43113`).
- Sadece bu hackathon için yeni, boş bir test hesabı açın.
- Hesap detaylarından **Private Key (Özel Anahtar)**'ı kopyalayın.
  > ⚠️ **Güvenlik Uyarısı:** Bu anahtar sadece test ağı (Fuji) içindir, içinde gerçek para olan ana cüzdanınızı ASLA kullanmayın!

#### 2. Ücretsiz Testnet AVAX Alma (Faucet)
1. **Site:** [core.app/tools/testnet-faucet/?subnet=c&token=c](https://core.app/tools/testnet-faucet/?subnet=c&token=c)
2. Testnet cüzdan adresinizi (`0x...`) yapıştırın.
3. **"Request 2 AVAX"** butonuna tıklayın.
4. 10 saniye içinde test hesabınıza ücretsiz 2 Fuji AVAX gelecektir (Gaz ücretleri için kullanılır).

#### 3. `.env` Dosyasına Tanımlama
```env
AVALANCHE_FUJI_RPC=https://api.avax-test.network/ext/bc/C/rpc
AVALANCHE_PRIVATE_KEY=0x_sizin_testnet_private_keyiniz
```

---

## 3. Güvenlik Protokolü
1. `.env` dosyası yerel makinenizde kalır ve `.gitignore` içinde yer alır.
2. `git push` komutlarında hiçbir anahtar GitHub'a gönderilmez.
3. Testnet private key haricinde borsa çekim yetkisi olan hiçbir anahtar sisteme girilmez.
