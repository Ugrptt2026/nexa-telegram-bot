# Nexa — Telegram Borsa & Kripto Botu

Nexa, BIST ve kripto piyasalarını ücretsiz veya anahtarsız public veri kaynaklarıyla izlemek üzere geliştirilen bir Python Telegram botudur. Bot bilgi ve uyarı sağlar; yatırım tavsiyesi vermez ve emir iletmez.

## Durum

Bu repo çalışan bir MVP içerir: `/start`, `/yardim`, `/menu`, inline keyboard menüsü, kullanıcı kaydı, `/hisse`, `/kripto`, `/teknik`, `/grafik`, `/temel`, `/endeks`, `/piyasa`, `/fng`, `/tara`, `/kap`, `/alarm`, `/izleme` ve `/portfoy` komutları; SQLite repository; yerel alarm scheduler’ı; Render webhook ve dış cron endpoint’i hazırdır.

BIST verisi yfinance/Yahoo Finance üzerinden gecikmeli ve garantisiz fallback’tir. Kripto fiyatı Binance public API’den, coin piyasa özeti CoinGecko’dan, Fear & Greed Alternative.me’den alınır. KAP tarafında sözleşmeli REST API kullanılmaz; yalnızca public sayfa gözlemcisi vardır.

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

Botta `/start`, `/yardim` ve `/menu` komutlarını deneyin.

## Test

```bash
pytest -q
```

## Ücretsiz kaynak politikası

Kripto için Binance public Spot API ve Alternative.me; genel piyasa bilgisi için CoinGecko Demo/keyless seçenekleri; BIST için yfinance/Yahoo Finance fallback olarak değerlendirilecektir. Sağlayıcıların limitleri ve kullanım şartları `docs/free-data-sources.md` içinde güncel tutulur. Yahoo/yfinance gerçek zamanlı veya sözleşmeli profesyonel veri kaynağı olarak sunulmaz.

## Lisans ve kullanım

Bu yazılım örnek/prototip niteliğindedir. Piyasa verileri gecikmeli veya eksik olabilir. Üretimde kullanmadan önce veri sağlayıcılarının güncel şartlarını ve ücretsiz plan limitlerini kontrol edin.
