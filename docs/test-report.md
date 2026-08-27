# Nexa test raporu

**Test tarihi:** 2026-08-27 (çalışma ortamı UTC)

## Otomatik kontroller

| Kontrol | Sonuç |
|---|---:|
| Python `compileall` | Başarılı |
| `pytest -q` | **16 başarılı** |
| Binance BTC public ticker | Başarılı |
| Alternative.me Fear & Greed | Başarılı |
| CoinGecko global endpoint | Başarılı |
| Yahoo/yfinance THYAO quote | Başarılı |
| Yahoo/yfinance XU030, XU100, USDTRY, EURTRY, GC=F | Başarılı |
| Yahoo/yfinance THYAO temel alanları | Başarılı; alanlar eksik olabilir |
| KAP public ana sayfa gözlemcisi | Erişim başarılı; mevcut HTML’de 0 okunabilir bildirim satırı |
| Gerçek THYAO verisiyle PNG grafik | Başarılı; `artifacts/nexa_price_chart.png` |

## Kapsanan davranışlar

Testler SQLite şema başlatma, kullanıcı ve izleme listesi kaydı, alarm koşullarının üst/alt/mutlak yüzde değişimi, basit ortalama maliyetli portföy pozisyonları, sembol normalizasyonu, Binance ticker ayrıştırması, teknik gösterge pencereleri, KAP fingerprint deduplikasyonu, kripto mover sıralaması ve PNG dosyası üretimini kapsar.

## Canlı smoke test yorumları

Canlı çağrılar sağlayıcının o andaki erişilebilirliğini gösterir; ücretsiz planların sürekliliğini garanti etmez. CoinGecko resmi dokümanında Demo planı 100 çağrı/dakika olarak belirtilir ve 4xx/5xx istekler de limite sayılır [1]. Binance public REST tarafında uygulama yalnızca piyasa verisi uç noktalarını kullanır; resmi doküman limitlerin `exchangeInfo` içindeki `rateLimits` alanından izlenmesini söyler [2]. Alternative.me ticker dokümanda 5 dakikada güncellenir [3]. yfinance dokümanı aracın Yahoo tarafından bağlı veya onaylı olmadığını, herkese açık API’leri araştırma/eğitim amacıyla kullandığını ve Yahoo kullanım şartlarına bakılması gerektiğini belirtir [4].

KAP’ın resmi REST Veri Yayın Servisi duyurusu, eş anlı iletimin abone kuruluşlara verildiğini; sözleşme, yetkili IP ve API anahtarı süreci bulunduğunu belirtir [5]. Bu nedenle KAP REST API ücretsiz/public kabul edilmemiş, MVP’ye yalnızca düşük sıklıklı public sayfa gözlemcisi eklenmiştir.

## Bilinen sınırlamalar

Render Free web service 15 dakika inbound trafik olmadan uyur; yeniden başlatma yaklaşık bir dakika sürebilir ve yerel SQLite dosyası redeploy/restart/sleep ile kaybolabilir [6]. Bu nedenle `docs/deployment.md`, Render webhook + GitHub Actions cron yolunu demo/MVP olarak belgeler ve uzun süreli veri için kalıcı bir PostgreSQL adaptörünü sonraki iş olarak bırakır. Railway’in resmi fiyat sayfasında ücretsiz başlangıcın 30 günlük $5 kredi denemesi olduğu, sonrasında ayda $1 ücret yazdığı için Railway “tamamen ücretsiz” seçenek olarak kullanılmamıştır [7].

## References

1. [CoinGecko — Errors & Rate Limits](https://docs.coingecko.com/docs/errors-and-rate-limits)
2. [Binance — Spot REST API](https://developers.binance.com/en/docs/products/spot/rest-api)
3. [Alternative.me — Crypto API Documentation](https://alternative.me/crypto/api/)
4. [yfinance Documentation](https://ranaroussi.github.io/yfinance/)
5. [KAP — Veri Yayın Servisi REST API Entegrasyonu](https://kap.org.tr/tr/api/about/content-file/8a019492945fbe080194b26d8bed4873)
6. [Render — Deploy for Free](https://render.com/docs/free)
7. [Railway — Pricing](https://railway.com/pricing)
