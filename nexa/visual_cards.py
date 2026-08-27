from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .formatting import date_text, number, signed_pct
from .providers import FearGreed, Quote
from .technical_analysis import TechnicalSnapshot

# The cards are deliberately portrait-oriented and high-resolution so Telegram can
# scale them to a phone screen without making the small labels unreadable.
WIDTH = 1080
DEFAULT_HEIGHT = 1320
BG = "#07111D"
PANEL = "#0D1D2B"
PANEL_ALT = "#102636"
BORDER = "#1D3B4C"
TEXT = "#F4F7FA"
MUTED = "#9BAFBB"
GREEN = "#57E389"
GREEN_DARK = "#123B32"
RED = "#FF747D"
RED_DARK = "#42242A"
CYAN = "#5BD7F4"
GOLD = "#F3C76B"
ORANGE = "#F7A34D"
WHITE = "#FFFFFF"

_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD if bold else _FONT_REGULAR
    return ImageFont.truetype(path, size=size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        # Keep very long URLs/identifiers visible instead of allowing them to
        # overflow the card.
        if _text_width(draw, word, font) > max_width:
            fragment = ""
            for character in word:
                if _text_width(draw, fragment + character, font) <= max_width:
                    fragment += character
                else:
                    if fragment:
                        lines.append(fragment)
                    fragment = character
            current = fragment
        else:
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    lines = _wrap_text(draw, text, font, max_width)
    line_height = font.size + line_gap
    draw.multiline_text((x, y), "\n".join(lines), font=font, fill=fill, spacing=line_gap)
    return y + line_height * len(lines)


def _panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str = PANEL,
    outline: str = BORDER,
    radius: int = 26,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    fill: str,
    text_fill: str = BG,
    font_size: int = 22,
) -> int:
    font = _font(font_size, bold=True)
    width = _text_width(draw, text, font) + 32
    height = font_size + 24
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=fill)
    draw.text((x + 16, y + 10), text, font=font, fill=text_fill)
    return width


def _trend_color(value: float | None) -> str:
    return GREEN if value is not None and value >= 0 else RED


def _compact(value: float | int | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    absolute = abs(numeric)
    if absolute >= 1_000_000_000_000:
        rendered = f"{numeric / 1_000_000_000_000:.2f} Tn"
    elif absolute >= 1_000_000_000:
        rendered = f"{numeric / 1_000_000_000:.2f} Mr"
    elif absolute >= 1_000_000:
        rendered = f"{numeric / 1_000_000:.2f} Mn"
    elif absolute >= 1_000:
        rendered = f"{numeric / 1_000:.2f} B"
    else:
        rendered = number(numeric, 2)
    return rendered.replace(".", ",") + suffix


def _base(title: str, subtitle: str = "", height: int = DEFAULT_HEIGHT) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    # Thin brand rail and soft header blocks keep the visual language consistent.
    draw.rectangle((0, 0, WIDTH, 12), fill=GREEN)
    draw.ellipse((56, 48, 132, 124), fill=GREEN_DARK, outline=GREEN, width=2)
    draw.text((78, 62), "N", font=_font(38, bold=True), fill=GREEN)
    draw.text((160, 48), "NEXA", font=_font(44, bold=True), fill=TEXT)
    draw.text((160, 101), "BORSA & KRİPTO", font=_font(20, bold=True), fill=GREEN)
    pill_text = "%100 ÜCRETSİZ"
    pill_font = _font(20, bold=True)
    pill_width = _text_width(draw, pill_text, pill_font) + 34
    draw.rounded_rectangle((WIDTH - pill_width - 56, 58, WIDTH - 56, 104), radius=23, fill=GREEN_DARK, outline=GREEN, width=2)
    draw.text((WIDTH - pill_width - 39, 69), pill_text, font=pill_font, fill=GREEN)

    draw.text((56, 178), title, font=_font(38, bold=True), fill=TEXT)
    if subtitle:
        _draw_wrapped(draw, (56, 228), subtitle, _font(23), MUTED, WIDTH - 112, line_gap=5)
        content_y = 286
    else:
        content_y = 238
    draw.line((56, content_y - 20, WIDTH - 56, content_y - 20), fill=BORDER, width=2)
    return image, draw, content_y


def _footer(
    draw: ImageDraw.ImageDraw,
    height: int,
    source: str | None = None,
    note: str = "Yatırım tavsiyesi değildir.",
) -> None:
    y = height - 92
    draw.line((56, y - 18, WIDTH - 56, y - 18), fill=BORDER, width=2)
    draw.text((56, y), note, font=_font(20, bold=True), fill=MUTED)
    if source:
        source_text = source if len(source) <= 54 else source[:51] + "..."
        font = _font(18)
        width = _text_width(draw, source_text, font)
        draw.text((WIDTH - 56 - width, y + 2), source_text, font=font, fill=MUTED)


def _metric(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    accent: str = CYAN,
    value_size: int = 34,
) -> None:
    _panel(draw, box, fill=PANEL, outline=BORDER, radius=22)
    x, y, _, _ = box
    draw.text((x + 24, y + 20), label.upper(), font=_font(18, bold=True), fill=MUTED)
    value_font = _font(value_size, bold=True)
    draw.text((x + 24, y + 55), value, font=value_font, fill=accent)


def _draw_sparkline(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    values: Iterable[float],
    color: str = GREEN,
) -> None:
    points = [float(value) for value in values if value is not None]
    if len(points) < 2:
        draw.text((box[0], box[1]), "Mini grafik için yeterli veri yok", font=_font(20), fill=MUTED)
        return
    left, top, right, bottom = box
    minimum = min(points)
    maximum = max(points)
    span = maximum - minimum or 1.0
    mapped: list[tuple[int, int]] = []
    for index, value in enumerate(points):
        x = int(left + (right - left) * index / (len(points) - 1))
        y = int(bottom - (bottom - top) * (value - minimum) / span)
        mapped.append((x, y))
    fill_points = [(mapped[0][0], bottom), *mapped, (mapped[-1][0], bottom)]
    draw.polygon(fill_points, fill="#12342F")
    draw.line(mapped, fill=color, width=5, joint="curve")
    draw.ellipse((mapped[-1][0] - 7, mapped[-1][1] - 7, mapped[-1][0] + 7, mapped[-1][1] + 7), fill=color)


def _path(output_dir: Path, slug: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{slug}.png"


def _save(image: Image.Image, output_dir: Path, slug: str) -> Path:
    path = _path(output_dir, slug)
    image.save(path, format="PNG", optimize=True)
    return path


def save_start_card(name: str, output_dir: Path) -> Path:
    image, draw, y = _base("NEXA'YA HOŞ GELDİN", "BIST ve kripto piyasalarını ücretsiz veri kaynaklarıyla takip edin.", height=990)
    _panel(draw, (56, y, WIDTH - 56, y + 174), fill=PANEL_ALT)
    draw.text((86, y + 28), f"Merhaba {name}.", font=_font(34, bold=True), fill=TEXT)
    _draw_wrapped(
        draw,
        (86, y + 84),
        "Fiyat, analiz, grafik, alarm ve piyasa özetleri tek yerde.",
        _font(25),
        MUTED,
        WIDTH - 172,
        line_gap=5,
    )
    y += 220
    draw.text((56, y), "HIZLI BAŞLANGIÇ", font=_font(25, bold=True), fill=GREEN)
    commands = [("/hisse THYAO", "BIST hisse kartı"), ("/kripto BTC", "Kripto fiyat kartı"), ("/teknik hisse THYAO", "Teknik göstergeler"), ("/yardim", "Tüm komutlar")]
    for index, (command, description) in enumerate(commands):
        row_y = y + 48 + index * 76
        draw.rounded_rectangle((56, row_y, WIDTH - 56, row_y + 58), radius=18, fill=PANEL, outline=BORDER, width=2)
        draw.text((82, row_y + 14), command, font=_font(23, bold=True), fill=TEXT)
        desc_font = _font(20)
        desc_width = _text_width(draw, description, desc_font)
        draw.text((WIDTH - 82 - desc_width, row_y + 16), description, font=desc_font, fill=MUTED)
    _footer(draw, 990, "NEXA ücretsiz veri katmanı")
    return _save(image, output_dir, "start_card")


def save_help_card(output_dir: Path) -> Path:
    image, draw, y = _base("NEXA KOMUTLARI", "Mobil odaklı hızlı kullanım rehberi.", height=1550)
    sections = [
        ("PİYASA", [
            ("/hisse THYAO", "BIST fiyat kartı"),
            ("/kripto BTC", "Kripto fiyat kartı"),
            ("/endeks XU100", "Endeks, döviz, altın"),
            ("/ozet", "Günlük piyasa özeti"),
            ("/piyasa", "Kripto piyasa görünümü"),
            ("/fng", "Fear & Greed"),
        ]),
        ("ANALİZ", [
            ("/teknik hisse THYAO", "RSI, MACD, MA, seviye"),
            ("/grafik kripto BTC", "Fiyat grafiği"),
            ("/temel THYAO", "F/K, PD/DD, temettü"),
            ("/tara kripto", "Yükselen / düşenler"),
            ("/kap", "Public KAP gözlemi"),
        ]),
        ("KİŞİSEL ARAÇLAR", [
            ("/portfoy", "Sanal portföy"),
            ("/alarm", "Fiyat / değişim alarmı"),
            ("/izleme", "İzleme listesi"),
        ]),
    ]
    for section, commands in sections:
        draw.text((56, y), section, font=_font(23, bold=True), fill=GREEN)
        y += 42
        for command, description in commands:
            draw.rounded_rectangle((56, y, WIDTH - 56, y + 58), radius=18, fill=PANEL, outline=BORDER, width=2)
            draw.text((82, y + 14), command, font=_font(22, bold=True), fill=TEXT)
            desc_font = _font(19)
            desc_width = _text_width(draw, description, desc_font)
            draw.text((WIDTH - 82 - desc_width, y + 17), description, font=desc_font, fill=MUTED)
            y += 70
        y += 16
    _footer(draw, 1550, "NEXA | BIST + KRİPTO")
    return _save(image, output_dir, "help_card")


def save_quote_card(
    quote: Quote,
    output_dir: Path,
    snapshot: dict[str, Any] | None = None,
    ohlcv: pd.DataFrame | None = None,
) -> Path:
    height = 1330
    image, draw, y = _base("PİYASA KARTI", f"{quote.symbol}  ·  {quote.name}", height=height)
    trend = _trend_color(quote.change_pct)
    _panel(draw, (56, y, WIDTH - 56, y + 226), fill=PANEL_ALT, outline=BORDER, radius=28)
    draw.text((86, y + 30), quote.symbol, font=_font(28, bold=True), fill=GREEN)
    draw.text((86, y + 76), number(quote.price), font=_font(64, bold=True), fill=TEXT)
    draw.text((86, y + 154), quote.currency, font=_font(24, bold=True), fill=MUTED)
    change_text = signed_pct(quote.change_pct)
    pill_x = WIDTH - 86 - _text_width(draw, change_text, _font(28, bold=True)) - 36
    _pill(draw, pill_x, y + 54, change_text, GREEN_DARK if trend == GREEN else RED_DARK, trend, 28)
    label = "GECİKMELİ / HARİCİ" if quote.delayed else "ANLIK PUBLIC VERİ"
    label_width = _text_width(draw, label, _font(18, bold=True)) + 28
    draw.rounded_rectangle((WIDTH - 86 - label_width, y + 145, WIDTH - 86, y + 181), radius=18, fill=BG, outline=BORDER, width=1)
    draw.text((WIDTH - 72 - label_width, y + 154), label, font=_font(18, bold=True), fill=MUTED)
    y += 258
    _metric(draw, (56, y, 526, y + 122), "24S DEĞİŞİM", signed_pct(quote.change_pct), trend, 31)
    _metric(draw, (554, y, WIDTH - 56, y + 122), "HACİM", _compact(quote.volume), CYAN, 31)
    y += 148
    _panel(draw, (56, y, WIDTH - 56, y + 235), fill=PANEL)
    draw.text((86, y + 24), "FİYAT AKIŞI", font=_font(21, bold=True), fill=GREEN)
    if ohlcv is not None and "close" in ohlcv:
        _draw_sparkline(draw, (86, y + 74, WIDTH - 86, y + 192), ohlcv["close"].tail(45), trend)
    else:
        draw.text((86, y + 96), "Mini grafik için ek OHLCV verisi bulunamadı.", font=_font(23), fill=MUTED)
    y += 264
    if snapshot:
        draw.text((56, y), "KRİPTO PİYASA BİLGİSİ", font=_font(23, bold=True), fill=ORANGE)
        y += 42
        _metric(draw, (56, y, 374, y + 120), "PİYASA DEĞERİ", _compact(snapshot.get("market_cap_usd"), " USD"), ORANGE, 27)
        _metric(draw, (390, y, 708, y + 120), "24S HACİM", _compact(snapshot.get("volume_24h_usd"), " USD"), CYAN, 27)
        _metric(draw, (724, y, WIDTH - 56, y + 120), "COINGECKO 24S", signed_pct(snapshot.get("change_24h_pct")), _trend_color(snapshot.get("change_24h_pct")), 27)
        y += 142
    source = quote.source
    if quote.note:
        _draw_wrapped(draw, (56, height - 165), quote.note, _font(18), MUTED, WIDTH - 112, line_gap=4)
    _footer(draw, height, source)
    return _save(image, output_dir, f"quote_{quote.symbol.lower()}")


def save_technical_card(
    symbol: str,
    snapshot: TechnicalSnapshot,
    output_dir: Path,
    last_price: float | None = None,
    source: str | None = None,
) -> Path:
    height = 1250
    image, draw, y = _base("TEKNİK ANALİZ", f"{symbol}  ·  Göstergeler eğitim amaçlıdır", height=height)
    if last_price is not None:
        draw.text((56, y), "SON FİYAT", font=_font(20, bold=True), fill=MUTED)
        draw.text((56, y + 28), number(last_price), font=_font(52, bold=True), fill=TEXT)
        y += 108
    rows = [
        ("RSI (14)", number(snapshot.rsi14), CYAN),
        ("MACD", number(snapshot.macd), GREEN),
        ("MACD SİNYAL", number(snapshot.macd_signal), GOLD),
        ("MA20", number(snapshot.ma20), CYAN),
        ("MA50", number(snapshot.ma50), CYAN),
        ("DESTEK (20)", number(snapshot.support20), GREEN),
        ("DİRENÇ (20)", number(snapshot.resistance20), RED),
    ]
    for index, (label, value, accent) in enumerate(rows):
        row_y = y + index * 78
        draw.rounded_rectangle((56, row_y, WIDTH - 56, row_y + 58), radius=18, fill=PANEL, outline=BORDER, width=2)
        draw.text((84, row_y + 14), label, font=_font(22, bold=True), fill=MUTED)
        value_font = _font(25, bold=True)
        value_width = _text_width(draw, value, value_font)
        draw.text((WIDTH - 84 - value_width, row_y + 13), value, font=value_font, fill=accent)
    _footer(draw, height, source, "Teknik göstergeler tek başına al/sat sinyali değildir.")
    return _save(image, output_dir, f"technical_{symbol.lower()}")


def save_fundamentals_card(data: dict[str, Any], output_dir: Path) -> Path:
    symbol = str(data.get("symbol", "—"))
    name = str(data.get("name", "—"))
    height = 1050
    image, draw, y = _base("TEMEL ORANLAR", f"{symbol}  ·  {name}", height=height)
    metrics = [
        ("F/K", number(data.get("pe")), CYAN),
        ("PD/DD", number(data.get("pb")), GOLD),
        ("TEMETTÜ VERİMİ", signed_pct(data.get("dividend_yield_pct")), GREEN),
        ("PİYASA DEĞERİ", _compact(data.get("market_cap"), ""), ORANGE),
    ]
    for index, (label, value, accent) in enumerate(metrics):
        col = index % 2
        row = index // 2
        x = 56 + col * 498
        y_pos = y + row * 150
        _metric(draw, (x, y_pos, x + 468, y_pos + 122), label, value, accent, 30 if len(value) < 16 else 25)
    note = str(data.get("note", "Oranlar eksik olabilir."))
    _draw_wrapped(draw, (56, y + 340), note, _font(21), MUTED, WIDTH - 112, line_gap=6)
    _footer(draw, height, str(data.get("source", "Yahoo Finance via yfinance")))
    return _save(image, output_dir, f"fundamentals_{symbol.lower()}")


def save_global_market_card(data: dict[str, Any], output_dir: Path) -> Path:
    height = 950
    image, draw, y = _base("KRİPTO PİYASA ÖZETİ", "Toplam piyasa görünümü ve BTC dominansı", height=height)
    metrics = [
        ("TOPLAM PİYASA DEĞERİ", _compact(data.get("total_market_cap_usd"), " USD"), ORANGE),
        ("24S HACİM", _compact(data.get("total_volume_24h_usd"), " USD"), CYAN),
        ("BTC DOMİNASI", signed_pct(data.get("btc_dominance_pct")), GREEN),
        ("AKTİF KRİPTO", number(data.get("active_cryptocurrencies"), 0), GOLD),
    ]
    for index, (label, value, accent) in enumerate(metrics):
        col = index % 2
        row = index // 2
        x = 56 + col * 498
        y_pos = y + row * 150
        _metric(draw, (x, y_pos, x + 468, y_pos + 122), label, value, accent, 27 if len(value) > 15 else 31)
    _footer(draw, height, str(data.get("source", "CoinGecko Demo/keyless API")))
    return _save(image, output_dir, "global_market_card")


def save_fear_greed_card(index: FearGreed, output_dir: Path) -> Path:
    height = 900
    image, draw, y = _base("FEAR & GREED", "Kripto piyasası duyarlılık göstergesi", height=height)
    _panel(draw, (56, y, WIDTH - 56, y + 280), fill=PANEL_ALT)
    value_font = _font(92, bold=True)
    value_text = f"{index.value}"
    value_width = _text_width(draw, value_text, value_font)
    draw.text(((WIDTH - value_width) // 2, y + 24), value_text, font=value_font, fill=GREEN if index.value >= 50 else RED)
    class_font = _font(30, bold=True)
    class_text = index.classification.upper()
    class_width = _text_width(draw, class_text, class_font)
    draw.text(((WIDTH - class_width) // 2, y + 142), class_text, font=class_font, fill=TEXT)
    bar_x, bar_y, bar_w, bar_h = 106, y + 214, WIDTH - 212, 18
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=9, fill=RED_DARK)
    draw.rounded_rectangle((bar_x + bar_w * 0.25, bar_y, bar_x + bar_w * 0.75, bar_y + bar_h), radius=9, fill=GOLD)
    draw.rounded_rectangle((bar_x + bar_w * 0.5, bar_y, bar_x + bar_w, bar_y + bar_h), radius=9, fill=GREEN_DARK)
    marker_x = int(bar_x + bar_w * max(0, min(100, index.value)) / 100)
    draw.ellipse((marker_x - 13, bar_y - 7, marker_x + 13, bar_y + bar_h + 7), fill=WHITE, outline=BG, width=3)
    _draw_wrapped(draw, (56, y + 320), "Bu gösterge tek başına yatırım kararı için kullanılmamalıdır.", _font(23), MUTED, WIDTH - 112, line_gap=6)
    _footer(draw, height, index.source)
    return _save(image, output_dir, "fear_greed_card")


def save_daily_summary_card(items: list[dict[str, Any]], output_dir: Path) -> Path:
    height = 1110
    image, draw, y = _base("GÜNLÜK PİYASA ÖZETİ", "BIST endeksleri, döviz ve altın", height=height)
    for index, item in enumerate(items[:5]):
        row_y = y + index * 126
        _panel(draw, (56, row_y, WIDTH - 56, row_y + 100), fill=PANEL)
        draw.text((84, row_y + 17), str(item.get("name", "—")), font=_font(25, bold=True), fill=TEXT)
        date = str(item.get("date", "—"))
        draw.text((84, row_y + 56), date, font=_font(18), fill=MUTED)
        close_text = number(item.get("close"))
        close_font = _font(31, bold=True)
        close_width = _text_width(draw, close_text, close_font)
        draw.text((WIDTH - 84 - close_width, row_y + 18), close_text, font=close_font, fill=GREEN)
        range_text = f"Y {number(item.get('high'))}  ·  D {number(item.get('low'))}"
        range_font = _font(18)
        range_width = _text_width(draw, range_text, range_font)
        draw.text((WIDTH - 84 - range_width, row_y + 61), range_text, font=range_font, fill=MUTED)
    _footer(draw, height, "Yahoo Finance via yfinance", "Gecikmeli/harici veri; yatırım tavsiyesi değildir.")
    return _save(image, output_dir, "daily_summary_card")


def save_movers_card(result: dict[str, list[Any]], output_dir: Path, asset_label: str = "KRİPTO") -> Path:
    height = 1260
    image, draw, y = _base("TARAMA", f"{asset_label} · En çok hareket edenler", height=height)
    for group_index, (title, key, accent) in enumerate((("EN ÇOK YÜKSELENLER", "gainers", GREEN), ("EN ÇOK DÜŞENLER", "losers", RED))):
        top = y + group_index * 430
        draw.text((56, top), title, font=_font(23, bold=True), fill=accent)
        top += 46
        rows = result.get(key, [])[:5]
        for row_index, item in enumerate(rows):
            row_y = top + row_index * 66
            draw.rounded_rectangle((56, row_y, WIDTH - 56, row_y + 52), radius=16, fill=PANEL, outline=BORDER, width=1)
            draw.text((82, row_y + 13), str(getattr(item, "symbol", "—")), font=_font(23, bold=True), fill=TEXT)
            price = number(getattr(item, "price", None))
            draw.text((300, row_y + 14), price, font=_font(21), fill=MUTED)
            change = signed_pct(getattr(item, "change_pct", None))
            change_font = _font(22, bold=True)
            change_width = _text_width(draw, change, change_font)
            draw.text((WIDTH - 82 - change_width, row_y + 13), change, font=change_font, fill=accent)
    _footer(draw, height, "Binance/Yahoo ücretsiz veri katmanı")
    return _save(image, output_dir, f"movers_{asset_label.lower()}")


def save_watchlist_card(items: list[dict[str, Any]], output_dir: Path) -> Path:
    height = 850
    image, draw, y = _base("İZLEME LİSTESİ", "Takip etmek istediğiniz BIST ve kripto varlıkları", height=height)
    if not items:
        _panel(draw, (56, y, WIDTH - 56, y + 160), fill=PANEL_ALT)
        draw.text((88, y + 32), "Listeniz şu anda boş.", font=_font(30, bold=True), fill=TEXT)
        _draw_wrapped(draw, (88, y + 88), "/izleme ekle hisse THYAO", _font(22), MUTED, WIDTH - 176)
    else:
        for index, item in enumerate(items[:8]):
            row_y = y + index * 72
            kind = "BIST" if item.get("asset_type") == "stock" else "KRİPTO"
            draw.rounded_rectangle((56, row_y, WIDTH - 56, row_y + 56), radius=17, fill=PANEL, outline=BORDER, width=1)
            draw.text((84, row_y + 14), kind, font=_font(19, bold=True), fill=GREEN)
            draw.text((250, row_y + 13), str(item.get("symbol", "—")), font=_font(23, bold=True), fill=TEXT)
            draw.text((WIDTH - 84 - _text_width(draw, "TAKİPTE", _font(18, bold=True)), row_y + 16), "TAKİPTE", font=_font(18, bold=True), fill=MUTED)
    _footer(draw, height, "NEXA kişisel izleme listesi")
    return _save(image, output_dir, "watchlist_card")


def save_alarms_card(items: list[dict[str, Any]], output_dir: Path) -> Path:
    height = 900
    image, draw, y = _base("AKTİF ALARMLAR", "Fiyat ve yüzde değişim takipleri", height=height)
    if not items:
        _panel(draw, (56, y, WIDTH - 56, y + 160), fill=PANEL_ALT)
        draw.text((88, y + 32), "Aktif alarmınız yok.", font=_font(30, bold=True), fill=TEXT)
        _draw_wrapped(draw, (88, y + 88), "/alarm ekle hisse THYAO ust 350", _font(21), MUTED, WIDTH - 176)
    else:
        labels = {"above": "ÜSTÜ", "below": "ALTI", "change_pct": "DEĞİŞİM"}
        for index, item in enumerate(items[:7]):
            row_y = y + index * 72
            kind = "BIST" if item.get("asset_type") == "stock" else "KRİPTO"
            condition = labels.get(item.get("condition"), str(item.get("condition", "—")))
            suffix = "%" if item.get("condition") == "change_pct" else ""
            draw.rounded_rectangle((56, row_y, WIDTH - 56, row_y + 56), radius=17, fill=PANEL, outline=BORDER, width=1)
            draw.text((82, row_y + 15), f"#{item.get('id', '—')}", font=_font(21, bold=True), fill=GOLD)
            draw.text((180, row_y + 14), f"{kind} {item.get('symbol', '—')}", font=_font(22, bold=True), fill=TEXT)
            value = f"{condition} {number(item.get('target'))}{suffix}"
            value_font = _font(20, bold=True)
            value_width = _text_width(draw, value, value_font)
            draw.text((WIDTH - 82 - value_width, row_y + 16), value, font=value_font, fill=GREEN)
    _footer(draw, height, "NEXA alarm motoru")
    return _save(image, output_dir, "alarms_card")


def save_portfolio_card(
    positions: list[dict[str, Any]],
    current_quotes: dict[tuple[str, str], Any] | None,
    output_dir: Path,
) -> Path:
    height = 1120
    image, draw, y = _base("SANAL PORTFÖY", "Basit ortalama maliyet yöntemiyle takip", height=height)
    current_quotes = current_quotes or {}
    if not positions:
        _panel(draw, (56, y, WIDTH - 56, y + 170), fill=PANEL_ALT)
        draw.text((88, y + 34), "Henüz pozisyon yok.", font=_font(30, bold=True), fill=TEXT)
        _draw_wrapped(draw, (88, y + 94), "/portfoy al hisse THYAO 10 300", _font(22), MUTED, WIDTH - 176)
    else:
        total_cost = 0.0
        total_value = 0.0
        rows: list[tuple[dict[str, Any], float | None, float | None]] = []
        for position in positions[:7]:
            cost = float(position.get("cost", 0) or 0)
            quantity = float(position.get("quantity", 0) or 0)
            quote = current_quotes.get((position.get("asset_type"), position.get("symbol")))
            market_value = float(quote.price) * quantity if quote else None
            total_cost += cost
            if market_value is not None:
                total_value += market_value
            rows.append((position, market_value, cost))
        pnl = total_value - total_cost if total_value else None
        _metric(draw, (56, y, 526, y + 122), "TOPLAM MALİYET", _compact(total_cost), CYAN, 30)
        _metric(draw, (554, y, WIDTH - 56, y + 122), "TOPLAM K/Z", signed_pct((pnl / total_cost) * 100 if pnl is not None and total_cost else None), _trend_color(pnl), 30)
        y += 148
        for index, (position, market_value, cost) in enumerate(rows):
            row_y = y + index * 82
            draw.rounded_rectangle((56, row_y, WIDTH - 56, row_y + 66), radius=18, fill=PANEL, outline=BORDER, width=1)
            draw.text((82, row_y + 11), str(position.get("symbol", "—")), font=_font(23, bold=True), fill=TEXT)
            quantity = number(position.get("quantity"), 4)
            draw.text((82, row_y + 40), f"Miktar {quantity}", font=_font(18), fill=MUTED)
            value_text = _compact(market_value) if market_value is not None else "Fiyat yok"
            value_font = _font(23, bold=True)
            value_width = _text_width(draw, value_text, value_font)
            draw.text((WIDTH - 82 - value_width, row_y + 13), value_text, font=value_font, fill=GREEN if market_value is not None else MUTED)
            cost_text = f"Maliyet {_compact(cost)}"
            cost_width = _text_width(draw, cost_text, _font(18))
            draw.text((WIDTH - 82 - cost_width, row_y + 43), cost_text, font=_font(18), fill=MUTED)
    _footer(draw, height, "NEXA sanal portföy")
    return _save(image, output_dir, "portfolio_card")


def save_kap_card(items: list[Any], output_dir: Path) -> Path:
    height = 1080
    image, draw, y = _base("KAP BİLDİRİMLERİ", "Herkese açık sayfa gözlemi · düşük frekans", height=height)
    if not items:
        _panel(draw, (56, y, WIDTH - 56, y + 190), fill=PANEL_ALT)
        draw.text((88, y + 34), "Okunabilir bildirim satırı bulunamadı.", font=_font(27, bold=True), fill=TEXT)
        _draw_wrapped(draw, (88, y + 96), "KAP public sayfası dinamik veya boş dönebilir.", _font(21), MUTED, WIDTH - 176)
    else:
        for index, item in enumerate(items[:6]):
            row_y = y + index * 122
            _panel(draw, (56, row_y, WIDTH - 56, row_y + 100), fill=PANEL)
            date = str(getattr(item, "date", "—"))
            company = str(getattr(item, "company", "—"))
            subject = str(getattr(item, "subject", "—"))
            draw.text((84, row_y + 15), f"{date}  ·  {company}", font=_font(20, bold=True), fill=RED)
            _draw_wrapped(draw, (84, row_y + 50), subject, _font(21), TEXT, WIDTH - 168, line_gap=4)
    _footer(draw, height, "KAP public website", "KAP public gözlemi; yatırım tavsiyesi değildir.")
    return _save(image, output_dir, "kap_card")


def save_notice_card(title: str, message: str, output_dir: Path, slug: str = "notice_card", accent: str = GREEN) -> Path:
    image, draw, y = _base(title, "NEXA bilgi kartı", height=720)
    _panel(draw, (56, y, WIDTH - 56, y + 220), fill=PANEL_ALT)
    draw.rectangle((56, y, 70, y + 220), fill=accent)
    _draw_wrapped(draw, (102, y + 38), message, _font(28, bold=True), TEXT, WIDTH - 168, line_gap=10)
    _footer(draw, 720, "NEXA")
    return _save(image, output_dir, slug)
