# NEXA Piyasa Derinliği Kaynak Araştırması

## Sonuç

Kripto tarafında gerçek emir defteri derinliği tamamen ücretsiz public Binance Spot REST API ile alınabilir. Resmi `GET /api/v3/depth` endpointi `symbol` ve `limit` parametrelerini kabul eder; yanıt `bids` ve `asks` dizilerinde fiyat ve miktar çiftlerini döndürür. Kart için düşük istek ağırlıklı `limit=10` kullanılacaktır. Kaynak: [Binance Spot Market Data](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints#order-book).

BIST tarafında gerçek Level 2 emir kademeleri Borsa İstanbul’un resmi veri ürünleri içinde yer alır; resmi ürün sayfası Level 2’nin en iyi 10 alış ve satış seviyesinin miktar bilgisini içerdiğini, Level 2+’ın ise en iyi 25 seviyeye çıktığını belirtir. Borsa İstanbul ayrıca TIP protokolünü piyasa-fiyat bazında emir defteri derinliğini veri dağıtımcılarına aktaran doğrudan veri feed ürünü olarak tanımlar. Bu ürünler ücretsiz/public, anahtarsız bir REST endpoint olarak sunulmadığından NEXA’nın mevcut ücretsiz veri politikasında BIST için gerçek emir kademesi uydurulmayacaktır.

BIST kartında gerçek ücretsiz kaynaklardan gelen mevcut fiyat, hacim, gün içi yüksek/düşük, önceki kapanış ve işlem göstergeleri kullanılabilir; ancak bunlar emir defteri kademesi gibi gösterilmeyecektir. BIST gerçek Level 2 desteği istenirse Borsa İstanbul veri ürünü veya yetkili bir veri dağıtımcısı üzerinden ayrı sözleşme/erişim gerekir. Kaynaklar: [Borsa İstanbul Market Data Products](http://www.borsaistanbul.com/en/data/data-dissemination/market-data-products) ve [Borsa İstanbul TIP Protocol](http://www.borsaistanbul.com/en/bistech-technology/protocols/tip-protocol).

## Uygulama kararı

| Bölüm | Ücretsiz/public veri | NEXA kartı |
|---|---|---|
| KRİPTO | Binance Spot `/api/v3/depth`, 10 alış + 10 satış kademesi | Gerçek emir defteri; alış/satış renkleri, toplam miktar, spread ve dengesizlik |
| BIST | Borsa İstanbul public `veriler.php?veriTuru=pay-hacim-liderleri` güncel TL hacim/miktar listesi; Yahoo/yfinance tarihsel OHLCV fallback; resmi Level 2 endpointi yok | `/derinlik` içinde OHLCV Hacim Profili: 30 günlük adet hacim bölgeleri, güncel TL hacim varsa resmi Borsa kaynağı, son 10 gerçek OHLCV barı; sahte kademe yok |

Bu ayrım, fiyat özeti ile gerçek emir defteri verisinin karıştırılmasını önler. BIST’te emir kademesi verisi elde edilemediği için `/derinlik THYAO` kartı son 30 günlük OHLCV barlarının hacim profilini gösterir. Hacim bölgeleri barların gerçek adet hacmini tipik fiyat `(High + Low + Close) / 3` aralıklarına toplar; bu alıcı-satıcı akışı değildir. Güncel TL hacim değeri, sembol Borsa İstanbul’un public hacim liderleri listesinde yer alıyorsa resmi endpointten alınır; tarihsel OHLCV adet hacmi Yahoo/yfinance’tan gelir. Kartta kullanıcı isteği doğrultusunda yalnızca “OHLCV ANALİZ VERİSİ” etiketi bulunur.
