# NEXA Görsel Kart İncelemesi

## İlk görsel kontrolü

`start_card.png` ve `quote_thyao.png` üretildi ve görsel olarak incelendi. Her iki kartta da NEXA üst marka bandı, koyu lacivert arka plan, yeşil vurgu, yüksek kontrastlı başlıklar ve Telegram mobil ekranına uygun portre düzeni başarılı görünüyor.

Başlangıç kartında `/hisse THYAO`, `/kripto BTC`, `/teknik hisse THYAO` ve `/yardim` komutları ayrı satırlarda okunabilir durumda. Hisse kartında fiyat ana odak, değişim ve hacim ikincil metrik olarak ayrılmış; mini grafik ve gecikmeli veri etiketi alt bilgiyle uyumlu.

Kart üreticisi deterministik Pillow düzeni kullanıyor; finansal sayıların ve Türkçe metinlerin tam kontrolü korunuyor. Kartlar 1080 piksel genişlikte PNG olarak üretiliyor ve mobil ölçekte ölçeklenebilir. İlk görsel kontrolünde kritik bir taşma veya okunabilirlik engeli gözlenmedi.

## İkinci görsel kontrolü

`technical_thyao.png` kartında son fiyat üstte, RSI/MACD/MA20/MA50/destek/direnç değerleri tek satırlık yüksek kontrastlı satırlarda ve alt uyarı metni ayrı footer alanında görünüyor. `help_card.png` kartında piyasa, analiz ve kişisel araçlar bölümleri taşmadan ayrılmış; uzun komutlar mobilde yatay satırlarda okunabilir.

İkinci kontrolde kritik bir kesilme, taşma veya düşük kontrast problemi gözlenmedi. Yardım kartının boyu 1080×1550 olarak ayarlanarak tüm komut bölümleri footer ile çakışmadan yerleştirildi.
