"""Kullanıcıya gösterilen Türkçe metinler."""

START_TEXT = """Merhaba {name}, ben <b>Nexa</b>.

BIST ve kripto piyasalarını ücretsiz veri kaynaklarıyla takip etmenize yardımcı olurum. Fiyatlar bazı kaynaklarda gecikmeli olabilir; Nexa yatırım tavsiyesi vermez ve emir iletmez.

Başlamak için aşağıdaki menüyü kullanın veya /yardim komutunu yazın."""

HELP_TEXT = """<b>Nexa komutları</b>

<b>Piyasa</b>
/hisse THYAO — BIST hisse sorgusu
/kripto BTC — kripto varlık sorgusu
/endeks XU100 — BIST 30/100, döviz veya altın
/ozet — endeks, kur ve altın açılış/kapanış özeti
/piyasa — kripto piyasa değeri, hacim ve dominans
/fng — Crypto Fear &amp; Greed Index
/teknik hisse THYAO — RSI, MACD, MA, destek/direnç
/grafik kripto BTC — fiyat grafiği
/temel THYAO — F/K, PD/DD, temettü verimi
/tara kripto — en çok yükselen/düşenler
/tara hisse — tanımlı BIST evreni taraması
/kap — public KAP sayfa gözlemi

<b>Kişisel araçlar</b>
/portfoy — sanal portföy
/alarm — fiyat/değişim alarmı
/izleme — izleme listeniz

<b>Genel</b>
/start — başlangıç menüsü
/yardim — bu yardım metni

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
