# NEXA — Borsa & Kripto Telegram Botu

NEXA, BIST ve kripto piyasalarını ücretsiz veya anahtarsız public veri kaynaklarıyla izlemek üzere geliştirilen bir Python Telegram botudur. Bot bilgi ve uyarı sağlar; yatırım tavsiyesi vermez ve emir iletmez.

## Durum

Bu repo çalışan bir MVP içerir: `/start`, `/yardim`, `/menu`, inline keyboard menüsü, kullanıcı kaydı, `/hisse`, `/kripto`, `/teknik`, `/grafik`, `/temel`, `/endeks`, `/piyasa`, `/fng`, `/tara`, `/kap`, `/alarm`, `/izleme` ve `/portfoy` komutları; SQLite repository; yerel alarm scheduler’ı; Render webhook ve dış cron endpoint’i hazırdır.

## Görsel ve mobil yanıt sistemi

Komutların başarılı yanıtları artık uzun düz metin blokları yerine **NEXA markalı PNG kartları** olarak gönderilir. Kartlar 1080 piksel genişlikte, portre yönelimli ve telefon ekranında okunabilir yüksek kontrastlı bir düzen kullanır. Koyu lacivert zemin, yeşil marka vurgusu, büyük ana fiyat, ayrı metrik satırları, mini grafikler ve veri gecikmesi/kaynak uyarıları tüm ana kartlarda ortak standarda sahiptir.

Başlangıç ve yardım ekranları da görsel karttır. `/hisse THYAO` ve `/kripto BTC` fiyat/değişim/hacim kartı, `/teknik hisse THYAO` teknik gösterge kartı, `/temel THYAO` temel oran kartı, `/piyasa`, `/fng`, `/tara`, `/ozet`, `/endeks`, `/kap`, `/alarm`, `/izleme` ve `/portfoy` ilgili mobil kartları üretir. `/grafik` ise NEXA koyu temalı fiyat grafiği gönderir.

## Veri kaynakları

BIST verisi yfinance/Yahoo Finance üzerinden gecikmeli ve garantisiz fallback’tir. Kripto fiyatı Binance public API’den, coin piyasa özeti CoinGecko’dan, Fear & Greed Alternative.me’den alınır. KAP tarafında sözleşmeli REST API kullanılmaz; yalnızca düşük frekanslı public sayfa gözlemcisi vardır. Ücretsiz kaynakların kapsamı, limitleri ve uyarıları `docs/free-data-sources.md` içinde tutulur.

## Yerel kurulum

Python 3.11 veya daha yeni bir sürüm kullanın. Sanal ortam oluşturup bağımlılıkları kurun:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cp .env.example .env
```

`.env` içindeki `TELEGRAM_BOT_TOKEN` değerini Telegram’da `@BotFather` ile oluşturduğunuz bot tokenı ile doldurun. Ardından botu başlatın:

```bash
python main.py
```

Botta `/start`, `/yardim` ve `/menu` komutlarını deneyin. Örnek görsel kartlar `docs/previews/` klasöründe bulunur.

## Test

```bash
pytest -q
```

## Render dağıtımı

Render Web Service için doğrudan kaynak düzeni kullanılır:

```text
Build Command: pip install .
Start Command: uvicorn nexa.web:app --host 0.0.0.0 --port $PORT
```

`APP_BASE_URL`, webhook adresinin temelidir; beklenen Telegram webhook yolu `/telegram/webhook` şeklindedir. GitHub Actions workflow’u her beş dakikada bir `POST /internal/cron` çağrısı yapar. `NEXA_URL` ve `NEXA_CRON_SECRET` GitHub Actions secret olarak, Telegram ve Render secret’ları ise yalnız Render Environment içinde tutulmalıdır. Ayrıntılı akış `docs/deployment.md` dosyasındadır.

## Ücretsiz kaynak politikası

Sağlayıcıların güncel kullanım şartları ve ücretsiz plan limitleri zaman içinde değişebilir. Yahoo/yfinance gerçek zamanlı veya sözleşmeli profesyonel veri kaynağı olarak sunulmaz; Binance yalnızca public spot piyasa verisi için kullanılır ve emir endpoint’i kullanılmaz. CoinGecko çağrıları cache/rate disipliniyle sınırlı tutulmalıdır.

## Lisans ve kullanım

Bu yazılım örnek/prototip niteliğindedir. Piyasa verileri gecikmeli veya eksik olabilir. Render Free hareketsizlikte uykuya geçebilir; `/tmp` üzerindeki SQLite verisi yeniden başlatma veya yeniden deploy sonrasında kalıcı olmayabilir. Kritik 7/24 finansal alarm garantisi verilmez. Üretimde kullanmadan önce veri sağlayıcılarının güncel şartlarını ve ücretsiz plan limitlerini kontrol edin.
