# Nexa ücretsiz veri kaynakları ve limit politikası

Bu belge Nexa’nın **ücretli veri sağlayıcısına bağımlı olmaması** için kullanılan kaynakların kapsamını ve sınırlamalarını tanımlar. Limitler sağlayıcılar tarafından değiştirilebildiği için üretime almadan önce bağlantılardaki güncel metin tekrar kontrol edilmelidir.

## Kaynak matrisi

| İhtiyaç | Kaynak | Kimlik doğrulama | Doğrulanmış ücretsiz durum | Rate limit / güncelleme | Nexa politikası |
|---|---|---|---|---|---|
| Kripto spot fiyatı ve OHLCV | [Binance Spot public REST](https://developers.binance.com/en/docs/products/spot/rest-api) | Public piyasa uç noktalarında anahtar yok | Ücretsiz public piyasa erişimi | Limitler `exchangeInfo` içindeki `rateLimits` alanından okunmalı; uygulama düşük sıklıkla çağırır | Binance sembolü `BTCUSDT` biçimine normalize edilir; emir uç noktaları kullanılmaz |
| Kripto piyasa değeri, global özet | [CoinGecko Demo/keyless API](https://www.coingecko.com/en/api/pricing) | Demo anahtarı opsiyonel; keyless IP bazlı | Demo planı $0/ay, kredi kartı gerektirmiyor; attribution gerekli | Resmi rate-limit dokümanı Demo için 100 çağrı/dakika; 4xx/5xx çağrılar da sayılır | Önbellek ve düşük çağrı bütçesi; 429 durumunda kullanıcıya kaynak geçici olarak sınırlı bilgisi |
| Fear & Greed | [Alternative.me Crypto API](https://alternative.me/crypto/api/) | Anahtarsız | Public ve ücretsiz endpoint | Ticker dokümanda 5 dakikada güncellenir; Fear & Greed için endpoint sağlanır, sabit dakika limiti ilan edilmedi | Göstergede Alternative.me attribution korunur; tek başına yatırım sinyali olarak sunulmaz |
| BIST fiyat ve OHLCV | [yfinance](https://ranaroussi.github.io/yfinance/) / Yahoo Finance public API | Anahtar yok | Açık kaynak istemci; ancak Yahoo’ya bağlı/endorsed değil ve kişisel kullanım uyarısı var | Resmi, sabit ve garanti edilmiş BIST API rate limiti doğrulanmadı; canlılık garanti edilmez | Düşük frekans, önbellek, `delayed=True`; gerçek zamanlı profesyonel veri iddiası yok |
| KAP bildirimleri | [KAP ana sitesi](https://kap.org.tr/tr) | Ana sitede kamuya açık liste | KAP sitesi kamuya açık bildirim listeleri sunuyor; resmi REST API ise abonelik/sözleşme ve API anahtarı gerektiriyor | Resmi ücretsiz RSS/REST sözleşmesi doğrulanmadı | Sadece düşük sıklıklı, şartlara uygun public sayfa gözlemcisi opsiyonel; REST API kullanılmayacak |

## Sağlayıcı kullanım kuralları

Nexa her kullanıcı mesajında yeni bir dış çağrı yapacak şekilde tasarlanmaz; mümkün olduğunda aynı sembol ve kısa zaman penceresi için önbellek kullanılmalıdır. Alarm taraması da tüm kullanıcılar için aynı varlıkları tek seferde sorgulayıp sonucu paylaşacak bir toplu kontrol mekanizmasına dönüştürülmelidir. CoinGecko çağrıları özellikle 100 çağrı/dakika resmi Demo sınırının altında tutulmalı; anahtarsız kullanımda IP paylaşımı nedeniyle daha muhafazakâr hız uygulanmalıdır.

BIST tarafında Yahoo/yfinance verisi **gecikmeli veya geçici olarak erişilemez** olabilir. Yahoo kullanım koşulları ve yfinance dokümantasyonundaki kişisel kullanım uyarısı nedeniyle Nexa, ticari veri terminali veya gerçek zamanlı alım-satım altyapısı olarak konumlandırılmaz. KAP’ın resmi API hizmeti ücretsiz/public kabul edilmez; bu yüzden ücretsiz MVP yalnızca kamuya açık sayfa takibini, düşük istek hızını ve kolay kapatılabilir bir adaptörü destekleyecektir.

## 2026-08-27 smoke test sonucu

Geliştirme ortamında birer düşük hacimli çağrı ile Binance BTC/USDT fiyatı, Alternative.me Fear & Greed, CoinGecko global özet ve Yahoo BIST THYAO erişimleri başarılı oldu. Bu sonuç yalnızca o andaki erişilebilirliği gösterir; sağlayıcıların süreklilik, gerçek zamanlılık veya ücretsiz planın gelecekte aynı kalacağı garantisi değildir.

## Kaynaklar

1. [CoinGecko — Errors & Rate Limits](https://docs.coingecko.com/docs/errors-and-rate-limits)
2. [CoinGecko — API Pricing](https://www.coingecko.com/en/api/pricing)
3. [Binance — Spot REST API](https://developers.binance.com/en/docs/products/spot/rest-api)
4. [Alternative.me — Crypto API Documentation](https://alternative.me/crypto/api/)
5. [yfinance Documentation](https://ranaroussi.github.io/yfinance/)
6. [KAP — Kamuyu Aydınlatma Platformu](https://kap.org.tr/tr)
7. [KAP — Veri Yayın Servisi REST API Entegrasyonu](https://kap.org.tr/tr/api/about/content-file/8a019492945fbe080194b26d8bed4873)
