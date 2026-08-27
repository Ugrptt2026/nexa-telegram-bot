# Piyasa Kartı Grafik Tanısı

Tanı betiği gerçek public kaynaklarla çalıştırıldı. Veri yokluğu hipotezi elendi:

| Varlık | Kaynak | OHLC satırı | `close` dolu | `open/high/low` dolu | Son kapanış |
|---|---|---:|---:|---:|---:|
| THYAO | Yahoo Finance / yfinance, 1y günlük | 255 | 255 | 255 / 255 / 255 | 306,00 |
| BTC | Binance public kline, 60 adet 1d | 60 | 60 | 60 / 60 / 60 | 80.424,00 |

Quote metadatası da dolu döndü. THYAO için açılış 309,50, gün içi yüksek 311,00, düşük 305,50 ve önceki kapanış 308,50; BTC için açılış 78.481,81, yüksek 80.494,16, düşük 77.632,58 ve önceki kapanış 78.481,81 elde edildi.

Sonuç: Grafik kaybı API’nin boş dönmesinden kaynaklanmıyor. Uygulama yeni sürümde veriyi sessizce atlamayacak; OHLC boş veya zorunlu kolon eksikse `MarketDataError`/ayrıntılı `LOGGER.error` kaydı üretecek. Görselleştirme, bu doğrulanmış OHLC akışı üzerinden candlestick olarak yeniden kurulacak.
