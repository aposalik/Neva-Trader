---
name: okx-atk-operations
description: >-
  Operational runbook and syntax guard for interacting with OKX Agent Trade Kit CLI v1.4.8+, enforcing demo mode, attached TP/SL syntax, and handling JSON outputs and error codes.
---

# OKX ATK Operasyonları ve Sözdizimi Kılavuzu

Bu yetenek (skill), OKX Agent Trade Kit (`@okx_ai/okx-trade-cli`) ile Python ve terminal üzerinden doğru, hatasız ve güvenli iletişim kurmak için kullanılır.

## 1. Doğrulanmış CLI Komutları Referansı

Komutlar CLI v1.4.8 üzerinde canlı olarak doğrulanmıştır:

### 1.1 Bakiye Sorgulama
```bash
okx account balance --demo --json
```
- Dönen JSON'da `currency == "USDT"` nesnesi aranır ve `available` veya `equity` alanı float olarak okunur.

### 1.2 Ticker / Anlık Fiyat
```bash
okx market ticker AVAX-USDT --demo --json
```
- `instId` argümanı pozisyoneldir (tireli bayrak kullanılmaz).
- Dönen JSON'da `last` alanı anlık fiyatı belirtir.

### 1.3 Mum Verisi (Candles)
```bash
# 1 Saatlik Mumlar (Makro Trend & EMA)
okx market candles AVAX-USDT --bar 1H --limit 50 --demo --json

# 15 Dakikalık Mumlar (Mikro Formasyonlar)
okx market candles AVAX-USDT --bar 15m --limit 20 --demo --json
```
- **Önemli Kural:** OKX mumları en yeni mumdan en eski muma doğru sıralar (`index 0 = en yeni mum`).
- **Kapanmamış Mum Kuralı:** Listenin başındaki mum kapanmamış olabilir (`confirm == "0"`). Teknik sinyal üretirken yalnızca kapanmış mumlar (`confirm == "1"`) kullanılmalıdır.

### 1.4 Atomik Alım ve Attached TP/SL (Spot)
```bash
okx spot place \
  --instId AVAX-USDT \
  --side buy \
  --ordType market \
  --sz <size> \
  --tdMode cash \
  --tpTriggerPx <tp_price> \
  --slTriggerPx <sl_price> \
  --demo \
  --json
```
- `--tdMode cash`: Spot nakit işlem modu.
- `--tpTriggerPx`: Kâr alma tetikleyici fiyatı.
- `--slTriggerPx`: Zarar kes tetikleyici fiyatı.
- `--sz`: Alınacak AVAX miktarı (2 ondalık basamağa yuvarlanmalıdır: `round(sz, 2)`).

## 2. Hata Yönetimi ve `sCode` Denetimi
OKX CLI `--json` çıktısında `code` veya `sCode` alanları döner:
- `code == "0"` veya `sCode == "0"`: İşlem başarılıdır.
- `code != "0"`: Hata durumudur. `sMsg` veya `msg` alanı okunarak terminale hata gerekçesi basılmalıdır.
- CLI çağrısı subprocess hatası verirse, işlem fail-safe olarak durdurulmalı ve `None` dönülmelidir.
