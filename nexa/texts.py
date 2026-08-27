START_TEXT = """Merhaba {name}, ben <b>NEXA</b>.

BIST ve kripto piyasalarını ücretsiz veri kaynaklarıyla takip etmenize yardımcı olurum. Fiyatlar bazı kaynaklarda gecikmeli olabilir; NEXA yatırım tavsiyesi vermez ve emir iletmez.

Başlamak için görsel menüyü kullanın veya /yardim komutunu yazın."""

HELP_TEXT = """<b>NEXA komutları</b>

<b>Piyasa</b>
/hisse THYAO — BIST hisse kartı
/kripto BTC — kripto varlık kartı
/endeks XU100 — BIST 30/100, döviz veya altın kartı
/ozet — endeks, kur ve altın özeti
/piyasa — kripto piyasa kartı
/fng — Fear &amp; Greed kartı
/teknik hisse THYAO — teknik analiz kartı
/grafik kripto BTC — NEXA fiyat grafiği
/temel THYAO — temel oran kartı
/tara kripto — yükselen/düşen kartı
/tara hisse — tanımlı BIST evreni taraması
/kap — public KAP sayfa gözlemi

<b>Kişisel araçlar</b>
/portfoy — sanal portföy kartı
/alarm — fiyat/değişim alarm kartı
/izleme — izleme listesi kartı

<b>Genel</b>
/start — NEXA başlangıç kartı
/yardim — bu komut kartı

Örnekler:
<code>/alarm ekle hisse THYAO ust 350</code>
<code>/alarm ekle kripto BTC degisim 5</code>
<code>/izleme ekle hisse THYAO</code>
<code>/portfoy al hisse THYAO 10 300</code>

BIST verisi yfinance/Yahoo Finance üzerinden gecikmeli veya geçici olarak erişilemez olabilir. Kripto fiyatı Binance public API’den alınır."""

MENU_LABELS = {
    "stock": "BIST Hisse",
    "crypto": "Kripto",
    "portfolio": "Portföy",
    "alerts": "Alarmlar",
    "watchlist": "İzleme Listesi",
    "help": "Yardım",
}
