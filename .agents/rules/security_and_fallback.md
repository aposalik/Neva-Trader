# Güvenlik, Kimlik Doğrulama ve Fallback Standartları

Bu belge, Nexa-Trader projesinde güvenlik zafiyetlerini, API sızıntılarını ve dış servis arızalarını önlemek için zorunlu kılınan kuralları içerir.

## 1. Kimlik Bilgileri ve Gizlilik
- **Kodda Sıfır Secret Kuralı:** Kod tabanında, git geçmişinde veya yapılandırma dosyalarında hiçbir zaman açık API anahtarı, gizli anahtar (secret key) veya parola tutulamaz.
- **Çevre Değişkenleri:** Gemini API veya harici servis anahtarları yalnızca `.env` dosyasından okunur; `.env.example` şablon olarak repoda tutulur.
- **OKX Yerel Kimlik Koruması:** OKX CLI kimlik doğrulaması (`okx auth login`) yerel cihazdaki `~/.okx/` dizininde saklanır. Scriptler bu kimlikleri harici ağlara sızdıramaz.

## 2. Dürüst Veri ve Fallback Protokolü
- **Açık Etiketleme Zorunluluğu:** CryptoQuant veya Investing.com canlı API/scraping çağrıları başarısız olduğunda sistem sessizce kurgusal değer üretemez.
- **Fallback Bayrağı:** Çevrimdışı veriye düşüldüğünde terminalde ve kararlarda mutlaka şu etiket gösterilmelidir:
  `[FALLBACK: MOCK DATA (mock_data.json)]`
- **Jüri Şeffaflığı:** Jüriye hangi verilerin canlı OKX borsa motorundan geldiği, hangi dış verilerin hackathon ortamı nedeniyle mock fallback ile beslendiği açıkça beyan edilir.

## 3. Hata Yönetimi ve Dayanıklılık (Fault Tolerance)
- **Güvenli Varsayılan (Fail-Safe Default):** Ağ kopması, API zaman aşımı, bozuk JSON yanıtı veya beklenmeyen veri şemalarında program çökmemeli; güvenli tarafta kalarak `NO TRADE` kararı üretmelidir.
- **Audit Trail (Denetim İzi):** Alınan her karar, hesaplanan metrikler ve yürütülen emirler anlık zaman damgasıyla `decisions.log` dosyasına JSON formatında kaydedilir.
