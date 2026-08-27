# NEXA Piyasa Derinliği Kaynak Araştırması

## Sonuç

Kripto tarafında gerçek emir defteri derinliği tamamen ücretsiz public Binance Spot REST API ile alınabilir. Resmi `GET /api/v3/depth` endpointi `symbol` ve `limit` parametrelerini kabul eder; yanıt `bids` ve `asks` dizilerinde fiyat ve miktar çiftlerini döndürür. Kart için düşük istek ağırlıklı `limit=10` kullanılacaktır. Kaynak: [Binance Spot Market Data](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints#order-book).

BIST tarafında gerçek Level 2 emir kademeleri Borsa İstanbul’un resmi veri ürünleri içinde yer alır; resmi ürün sayfası Level 2’nin en iyi 10 alış ve satış seviyesinin miktar bilgisini içerdiğini, Level 2+’ın ise en iyi 25 seviyeye çıktığını belirtir. Borsa İstanbul ayrıca TIP protokolünü piyasa-fiyat bazında emir defteri derinliğini veri dağıtımcılarına aktaran doğrudan veri feed ürünü olarak tanımlar. Bu ürünler ücretsiz/public, anahtarsız bir REST endpoint olarak sunulmadığından NEXA’nın mevcut ücretsiz veri politikasında BIST için gerçek emir kademesi uydurulmayacaktır.

BIST kartında gerçek ücretsiz kaynaklardan gelen mevcut fiyat, hacim, gün içi yüksek/düşük, önceki kapanış ve işlem göstergeleri kullanılabilir; ancak bunlar emir defteri kademesi gibi gösterilmeyecektir. BIST gerçek Level 2 desteği istenirse Borsa İstanbul veri ürünü veya yetkili bir veri dağıtımcısı üzerinden ayrı sözleşme/erişim gerekir. Kaynaklar: [Borsa İstanbul Market Data Products](http://www.borsaistanbul.com/en/data/data-dissemination/market-data-products) ve [Borsa İstanbul TIP Protocol](http://www.borsaistanbul.com/en/bistech-technology/protocols/tip-protocol).

## Uygulama kararı

| Bölüm | Ücretsiz/public veri | NEXA kartı |
|---|---|---|
| KRİPTO | Binance Spot `/api/v3/depth`, 10 alış + 10 satış kademesi | Gerçek emir defteri; alış/satış renkleri, toplam miktar, spread ve dengesizlik |
| BIST | Yahoo/yfinance fiyat, OHLC ve son bar hacimleri; resmi Level 2 endpointi yok | `/derinlik` içinde Son İşlem Hacmi Dağılımı: gerçek bar hacmi, mum yönü ve yaklaşık fiyat bölgeleri; sahte kademe yok |

Bu ayrım, fiyat özeti ile gerçek emir defteri verisinin karıştırılmasını önler. BIST’te emir kademesi verisi elde edilemediği için `/derinlik THYAO` kartı artık son OHLCV barlarının hacim dağılımını gösterir. Yükselen/düşen mum hacimleri gerçek bar hacmidir; yaklaşık fiyat bölgeleri tipik fiyat `(High + Low + Close) / 3` ile bar hacmini gruplayan bir proxy’dir. Kartta “OHLCV hacim analizi; gerçek emir defteri değildir” notu açıkça gösterilir.
