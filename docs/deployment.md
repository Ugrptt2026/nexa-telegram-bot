# Nexa ücretsiz dağıtım rehberi

Bu rehberde iki çalışma modeli verilir. İlk model yerel ve en basit doğrulamadır. İkinci model, Render Free üzerinde HTTPS webhook + GitHub Actions zamanlayıcısıdır. İkisi de bot tokenı ve veri sağlayıcı erişimini kullanıcıya ait gizli çevre değişkenlerinde tutar.

## 1. Yerel polling ile ilk çalıştırma

Telegram Bot API, güncellemeleri `getUpdates` long polling veya webhook ile alabilir; bu iki yöntem aynı anda kullanılmaz [1]. Yerel doğrulamada polling daha basittir.

```bash
git clone <REPO_URL>
cd nexa
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cp .env.example .env
```

`.env` dosyasına `TELEGRAM_BOT_TOKEN` değerini yazın. `ENABLE_INTERNAL_SCHEDULER=true` bırakın. Ardından:

```bash
python main.py
```

Botu durdurmadan Telegram’da `/start`, `/hisse THYAO`, `/kripto BTC`, `/alarm`, `/izleme` ve `/portfoy` komutlarını test edin. Yerel SQLite dosyası `./data/nexa.sqlite3` içinde tutulur.

## 2. Render Free + webhook + GitHub Actions zamanlayıcısı

Render’ın resmi dokümanına göre Python web servisleri ücretsiz çalıştırılabilir; fakat Free servisler 15 dakika inbound trafik olmazsa uyur, yeniden başlarken yaklaşık bir dakika sürebilir ve yerel dosya sistemi (SQLite dahil) redeploy/restart/sleep sonrasında kaybolur [2]. Bu nedenle aşağıdaki dağıtım **ücretsiz MVP/demo** içindir; verilerin kalıcı olacağı varsayılmamalıdır.

### Render kurulumu

Projeyi GitHub’a gönderin ve Render Dashboard’da **New → Web Service** seçin. Repository’yi bağladıktan sonra `render.yaml` Blueprint ayarlarını kullanın veya aşağıdaki değerleri manuel girin:

| Alan | Değer |
|---|---|
| Runtime | Python |
| Build command | `pip install .` |
| Start command | `uvicorn nexa.web:app --host 0.0.0.0 --port $PORT` |
| Plan | Free |
| Health check | `/health` |
| `ENABLE_INTERNAL_SCHEDULER` | `false` |
| `DATABASE_PATH` | `/tmp/nexa.sqlite3` (demo; kalıcı değildir) |

İlk deploy tamamlanınca Render servis URL’sini alın. `APP_BASE_URL` boş bırakılırsa uygulama Render’ın `RENDER_EXTERNAL_URL` değişkenini kullanır. Webhook URL’si `https://<render-url>/telegram/webhook` olur.

Aşağıdaki sırları yerel makinenizde üretip Render Environment Variables alanına ekleyin:

```bash
openssl rand -hex 32
```

| Değişken | Değer |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `@BotFather` tokenı |
| `TELEGRAM_WEBHOOK_SECRET` | 64 karakterlik rastgele sır |
| `CRON_SECRET` | farklı 64 karakterlik rastgele sır |
| `COINGECKO_DEMO_API_KEY` | Opsiyonel ücretsiz Demo anahtarı |
| `BIST_UNIVERSE` | Virgülle ayrılmış BIST sembolleri |

Deploy sonrası `https://<render-url>/health` adresi `{"status":"ok","service":"nexa"}` döndürmelidir. Servis başlarken `APP_BASE_URL` veya Render dış URL’si varsa Telegram webhook’u otomatik ayarlanır.

### GitHub Actions alarm zamanlayıcısı

`.github/workflows/alarm-cron.yml` workflow’u beş dakikada bir Render’daki `/internal/cron` endpoint’ine POST gönderir. GitHub repository **Settings → Secrets and variables → Actions** alanında şu iki repository secret’ı tanımlayın:

| Secret | Değer |
|---|---|
| `NEXA_URL` | `https://<render-url>`; sonunda `/` olmadan |
| `NEXA_CRON_SECRET` | Render’daki `CRON_SECRET` ile aynı değer |

Workflow’u önce **Actions → Nexa alarm checker → Run workflow** ile manuel çalıştırın. Başarılı cevap `{"checked":true}` olmalıdır. GitHub zamanlamaları yoğunluk nedeniyle gecikebileceğinden beş dakikalık kesinlik garantisi verilmez.

Bu modelde Render üzerindeki uygulama içi scheduler kapalıdır; böylece GitHub Actions ve in-process job aynı alarmı iki kez kontrol etmez. Gelen Telegram webhook’ları ve beş dakikalık cron istekleri Render servisini uyandırır; Free planın uyku ve yeniden başlatma davranışı yine geçerlidir.

## 3. Kalıcı veri konusunda açık sınır

Render Free’ın yerel SQLite dosyası kalıcı değildir. Render dokümanı ücretsiz Postgres veritabanlarının 1 GB ile sınırlı ve 30 gün sonra sona erdiğini, ücretsiz servislerin production için önerilmediğini belirtir [2]. Bu nedenle bu repo varsayılan olarak SQLite kullanır ve deploy rehberi bunu demo sınırı olarak açıkça işaretler.

Uzun süreli kullanımda ücretsiz bir harici PostgreSQL sağlayıcısına geçmek mümkündür; ancak sağlayıcının güncel ücretsiz planı, uyku ve saklama koşulları ayrıca doğrulanmalı ve repository’nin SQLite repository’si PostgreSQL adaptörüyle değiştirilmelidir. Bu değişiklik yapılmadan Render Free üzerinde kullanıcı alarmları ve portföy kayıtları kalıcı kabul edilmemelidir.

## 4. Üretim öncesi kontrol listesi

Bot tokenını Git’e göndermeyin; yalnızca Render/GitHub secret alanlarında tutun. Ücretsiz veri kaynaklarının rate limitlerini düşük çağrı frekansıyla koruyun. BIST verisini gecikmeli/harici veri olarak etiketleyin. KAP’ın sözleşmeli REST servisini ücretsiz/public varsaymayın. Alarm kontrolünü kişisel veri veya emir iletimi için kullanmayın. Her yeniden deploy öncesi SQLite yedeği alın; demo kaybı ihtimalini kullanıcıya bildirin.

## References

1. [Telegram Bot API — Getting updates](https://core.telegram.org/bots/api#getting-updates)
2. [Render — Deploy for Free](https://render.com/docs/free)
3. [Railway — Pricing](https://railway.com/pricing)
