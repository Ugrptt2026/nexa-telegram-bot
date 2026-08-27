from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .formatting import date_text, number, signed_pct
from .providers import DepthSnapshot, FearGreed, Quote
from .market_profile import VolumeProfile
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
GREEN_TINT = "#102E29"
RED = "#FF747D"
RED_DARK = "#42242A"
RED_TINT = "#321F27"
CYAN = "#5BD7F4"
GOLD = "#F3C76B"
ORANGE = "#F7A34D"
WHITE = "#FFFFFF"

LOGGER = logging.getLogger(__name__)

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
    gradient_draw = ImageDraw.Draw(image)
    for row in range(height):
        ratio = row / max(1, height - 1)
        color = _mix(BG, "#14152B", ratio * 0.60)
        if ratio > 0.70:
            color = _mix(color, "#0C2927", (ratio - 0.70) / 0.30 * 0.22)
        gradient_draw.line((0, row, WIDTH, row), fill=color, width=1)
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

    draw.text((56, 178), title, font=_font(38, bold=True), fill=GREEN)
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
    fill: str = PANEL,
    label_fill: str = MUTED,
) -> None:
    _panel(draw, box, fill=fill, outline=BORDER, radius=22)
    x, y, _, _ = box
    draw.text((x + 24, y + 20), label.upper(), font=_font(18, bold=True), fill=label_fill)
    value_font = _font(value_size, bold=True)
    draw.text((x + 24, y + 55), value, font=value_font, fill=accent)


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _mix(first: str, second: str, amount: float) -> str:
    a = _hex_rgb(first)
    b = _hex_rgb(second)
    amount = max(0.0, min(1.0, amount))
    rgb = tuple(round(x + (y - x) * amount) for x, y in zip(a, b))
    return "#%02X%02X%02X" % rgb


def _draw_sparkline(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    values: Iterable[float],
    color: str = GREEN,
    last_label: str | None = None,
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

    # Gradient dolgu: çizginin altını yön rengine doğru neonlaştırır.
    fill_points = [(mapped[0][0], bottom), *mapped, (mapped[-1][0], bottom)]
    mask = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.polygon(fill_points, fill=255)
    gradient = Image.new("RGB", image.size, BG)
    gradient_draw = ImageDraw.Draw(gradient)
    for y in range(top, bottom + 1):
        ratio = (y - top) / max(1, bottom - top)
        gradient_draw.line((left, y, right, y), fill=_mix(BG, color, 0.16 + ratio * 0.34), width=1)
    image.paste(gradient, (0, 0), mask)

    # İnce kılavuz çizgileri alanı daha dolu ve okunur gösterir.
    for ratio in (0.25, 0.5, 0.75):
        guide_y = int(top + (bottom - top) * ratio)
        draw.line((left, guide_y, right, guide_y), fill="#183343", width=1)
    draw.line(mapped, fill=color, width=5, joint="curve")
    last_x, last_y = mapped[-1]
    draw.ellipse((last_x - 11, last_y - 11, last_x + 11, last_y + 11), fill=BG, outline=color, width=4)
    draw.ellipse((last_x - 5, last_y - 5, last_x + 5, last_y + 5), fill=color)
    if last_label:
        bubble_font = _font(18, bold=True)
        bubble_width = _text_width(draw, last_label, bubble_font) + 26
        bubble_x = max(left + 8, min(last_x - bubble_width - 14, right - bubble_width))
        bubble_y = max(top + 4, last_y - 48)
        draw.rounded_rectangle((bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + 34), radius=17, fill=color)
        draw.text((bubble_x + 13, bubble_y + 7), last_label, font=bubble_font, fill=BG)


def _draw_time_tabs(draw: ImageDraw.ImageDraw, x: int, y: int, selected: str = "1A") -> None:
    tab_font = _font(16, bold=True)
    interval_font = _font(11, bold=True)
    tabs = (("1G", "15DK"), ("1H", "1SA"), ("1A", "1G"), ("1Y", "1HF"))
    for tab, interval in tabs:
        width = 58
        active = tab == selected
        draw.rounded_rectangle(
            (x, y, x + width, y + 42),
            radius=18,
            fill=GREEN_DARK if active else PANEL_ALT,
            outline=GREEN if active else BORDER,
            width=2 if active else 1,
        )
        draw.text((x + 13, y + 4), tab, font=tab_font, fill=GREEN if active else MUTED)
        draw.text((x + 13, y + 25), interval, font=interval_font, fill=GREEN if active else MUTED)
        x += width + 9


def _draw_candlesticks(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    ohlcv: pd.DataFrame | None,
    last_label: str | None = None,
) -> None:
    """OHLC verisini mobil kart için yoğunluğu sınırlı mum grafiğine dönüştürür."""
    required = ("open", "high", "low", "close")
    if ohlcv is None or ohlcv.empty or any(column not in ohlcv for column in required):
        raise ValueError("Candlestick için OHLC verisi eksik veya boş")
    frame = ohlcv.loc[:, list(required)].apply(pd.to_numeric, errors="coerce").dropna().tail(48)
    if frame.empty:
        raise ValueError("Candlestick için geçerli OHLC satırı yok")
    left, top, right, bottom = box
    high = float(frame["high"].max())
    low = float(frame["low"].min())
    span = high - low or 1.0
    pad = span * 0.08
    high += pad
    low -= pad
    span = high - low
    chart_left = left + 8
    chart_right = right - 8
    chart_top = top + 8
    chart_bottom = bottom - 8
    draw.rectangle((chart_left, chart_top, chart_right, chart_bottom), fill="#0A1D2A")
    for ratio in (0.25, 0.5, 0.75):
        guide_y = int(chart_top + (chart_bottom - chart_top) * ratio)
        draw.line((chart_left, guide_y, chart_right, guide_y), fill="#1A3544", width=1)

    step = (chart_right - chart_left) / max(1, len(frame) - 1)
    candle_width = max(6, min(18, int(step * 0.60)))

    def map_y(value: float) -> int:
        return int(chart_bottom - (value - low) / span * (chart_bottom - chart_top))

    last_position: tuple[int, int] | None = None
    for index, (_, row) in enumerate(frame.iterrows()):
        center_x = int(chart_left + step * index)
        open_value = float(row["open"])
        high_value = float(row["high"])
        low_value = float(row["low"])
        close_value = float(row["close"])
        rising = close_value >= open_value
        color = GREEN if rising else RED
        wick_x = center_x
        draw.line((wick_x, map_y(high_value), wick_x, map_y(low_value)), fill=color, width=2)
        body_top = map_y(max(open_value, close_value))
        body_bottom = map_y(min(open_value, close_value))
        body_bottom = max(body_bottom, body_top + 4)
        draw.rectangle((center_x - candle_width // 2, body_top, center_x + candle_width // 2, body_bottom), fill=color, outline=color)
        if index == len(frame) - 1:
            last_position = (center_x, map_y(close_value))

    if last_position and last_label:
        last_x, last_y = last_position
        bubble_font = _font(18, bold=True)
        bubble_width = _text_width(draw, last_label, bubble_font) + 26
        bubble_x = max(chart_left + 6, min(last_x - bubble_width - 14, chart_right - bubble_width))
        bubble_y = max(chart_top + 4, last_y - 42)
        draw.rounded_rectangle((bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + 32), radius=16, fill=GREEN if frame["close"].iloc[-1] >= frame["open"].iloc[-1] else RED)
        draw.text((bubble_x + 13, bubble_y + 6), last_label, font=bubble_font, fill=BG)
        draw.ellipse((last_x - 9, last_y - 9, last_x + 9, last_y + 9), fill=BG, outline=color, width=3)


def _draw_trend_icon(draw: ImageDraw.ImageDraw, x: int, y: int, trend_label: str, color: str) -> None:
    """SVG viewBox karşılığı küçük vektör ok; raster kartta piksellenmeden çizilir."""
    draw.ellipse((x, y, x + 44, y + 44), fill=BG, outline=color, width=2)
    if "YÜKSELİŞ" in trend_label:
        draw.line((x + 12, y + 29, x + 22, y + 18, x + 32, y + 25), fill=color, width=4, joint="curve")
        draw.polygon(((x + 29, y + 14), (x + 36, y + 15), (x + 33, y + 22)), fill=color)
    elif "DÜŞÜŞ" in trend_label:
        draw.line((x + 12, y + 15, x + 22, y + 26, x + 32, y + 19), fill=color, width=4, joint="curve")
        draw.polygon(((x + 29, y + 30), (x + 36, y + 29), (x + 33, y + 22)), fill=color)
    else:
        draw.line((x + 11, y + 22, x + 33, y + 22), fill=color, width=4)
        draw.polygon(((x + 10, y + 22), (x + 16, y + 16), (x + 16, y + 28)), fill=color)
        draw.polygon(((x + 34, y + 22), (x + 28, y + 16), (x + 28, y + 28)), fill=color)


def _draw_asset_icon(draw: ImageDraw.ImageDraw, x: int, y: int, symbol: str, is_crypto: bool) -> None:
    accent = ORANGE if is_crypto else GREEN
    draw.ellipse((x, y, x + 78, y + 78), fill=BG, outline=accent, width=3)
    draw.ellipse((x + 10, y + 10, x + 68, y + 68), fill=GREEN_DARK if not is_crypto else "#4A3020")
    # DejaVu Sans bazı ortamlarda ₿ glifini kutu gösterebildiği için güvenli B işareti kullanılır.
    mark = "B" if is_crypto and symbol.upper() == "BTC" else symbol[:1].upper()
    mark_font = _font(34, bold=True)
    mark_width = _text_width(draw, mark, mark_font)
    draw.text((x + (78 - mark_width) // 2, y + 18), mark, font=mark_font, fill=accent)


def _market_status(is_crypto: bool) -> tuple[str, str]:
    if is_crypto:
        return "7/24 AKTİF", GREEN
    now = datetime.now(ZoneInfo("Europe/Istanbul"))
    open_now = now.weekday() < 5 and 10 <= (now.hour * 60 + now.minute) < (18 * 60 + 10)
    return ("BIST · AÇIK" if open_now else "BIST · KAPALI"), (GREEN if open_now else MUTED)


def _trend_label(change_pct: float | None) -> tuple[str, str]:
    if change_pct is None or abs(change_pct) < 0.10:
        return "YATAY ↔", GOLD
    if change_pct > 0:
        return "YÜKSELİŞ ↑", GREEN
    return "DÜŞÜŞ ↓", RED


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


def _pair_metric(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    first: str,
    second: str,
    accent: str,
) -> None:
    _panel(draw, box, fill=PANEL, outline=BORDER, radius=22)
    x, y, _, _ = box
    draw.text((x + 20, y + 16), label.upper(), font=_font(16, bold=True), fill=MUTED)
    draw.text((x + 20, y + 49), first, font=_font(24, bold=True), fill=accent)
    draw.text((x + 20, y + 80), second, font=_font(18), fill=MUTED)


def _frame_number(frame: pd.DataFrame | None, column: str, reducer: str) -> float | None:
    if frame is None or column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return None
    if reducer == "first":
        return float(values.iloc[0])
    if reducer == "last":
        return float(values.iloc[-1])
    if reducer == "max":
        return float(values.max())
    if reducer == "min":
        return float(values.min())
    return None


def _price_or_dash(value: float | None) -> str:
    return number(value) if value is not None else "—"


def save_quote_card(
    quote: Quote,
    output_dir: Path,
    snapshot: dict[str, Any] | None = None,
    ohlcv: pd.DataFrame | None = None,
    time_range: str = "1A",
) -> Path:
    """Hisse ve kripto için premium, mobil odaklı ortak piyasa kartı."""
    snapshot = snapshot or {}
    is_crypto = quote.currency.upper() == "USDT"
    full_name = str(snapshot.get("name") or quote.name or quote.symbol)
    subtitle = f"{quote.symbol}  –  {full_name}"
    height = 1450
    image, draw, y = _base("PİYASA KARTI", subtitle, height=height)
    trend = _trend_color(quote.change_pct)
    trend_label, trend_accent = _trend_label(quote.change_pct)
    metadata = quote.metadata or {}
    open_value = metadata.get("open")
    day_high = metadata.get("high")
    day_low = metadata.get("low")
    previous_close = metadata.get("previous_close")
    long_frame = ohlcv.tail(365) if ohlcv is not None else None
    range_high = _frame_number(long_frame, "high", "max")
    range_low = _frame_number(long_frame, "low", "min")
    if is_crypto:
        range_label = "24S YÜKSEK / DÜŞÜK"
        range_high = day_high
        range_low = day_low
        market_cap = snapshot.get("market_cap_usd")
        market_cap_text = _compact(market_cap, " USD")
    else:
        range_label = "52H YÜKSEK / DÜŞÜK"
        market_cap = snapshot.get("market_cap")
        market_cap_text = _compact(market_cap)

    # Varlık özeti: ikonu, tam adı ve piyasa durumunu tek bir hero panelinde toplar.
    _panel(draw, (56, y, WIDTH - 56, y + 214), fill=PANEL_ALT, outline=BORDER, radius=28)
    _draw_asset_icon(draw, 84, y + 36, quote.symbol, is_crypto)
    draw.text((184, y + 36), quote.symbol, font=_font(29, bold=True), fill=GREEN if not is_crypto else ORANGE)
    name_font = _font(22, bold=True)
    name_text = full_name if len(full_name) <= 27 else full_name[:24] + "..."
    draw.text((184, y + 78), name_text, font=name_font, fill=MUTED)
    price_fill = "#E8FFF2" if trend == GREEN else ("#FFF0F1" if trend == RED else TEXT)
    draw.text((184, y + 121), number(quote.price), font=_font(53, bold=True), fill=price_fill)
    draw.text((184, y + 178), quote.currency, font=_font(19, bold=True), fill=MUTED)
    status_text, status_color = _market_status(is_crypto)
    status_font = _font(18, bold=True)
    status_width = _text_width(draw, status_text, status_font) + 30
    draw.rounded_rectangle((WIDTH - 86 - status_width, y + 32, WIDTH - 86, y + 70), radius=19, fill=GREEN_DARK if status_color == GREEN else PANEL, outline=status_color, width=2)
    draw.text((WIDTH - 71 - status_width, y + 42), status_text, font=status_font, fill=status_color)
    change_text = signed_pct(quote.change_pct)
    change_font = _font(29, bold=True)
    change_width = _text_width(draw, change_text, change_font) + 36
    draw.rounded_rectangle((WIDTH - 86 - change_width, y + 102, WIDTH - 86, y + 154), radius=25, fill=GREEN_DARK if trend == GREEN else RED_DARK)
    draw.text((WIDTH - 68 - change_width, y + 113), change_text, font=change_font, fill=trend)
    source_label = "GECİKMELİ / HARİCİ" if quote.delayed else "ANLIK PUBLIC VERİ"
    source_font = _font(15, bold=True)
    source_width = _text_width(draw, source_label, source_font) + 24
    draw.rounded_rectangle((WIDTH - 86 - source_width, y + 171, WIDTH - 86, y + 198), radius=14, fill=BG, outline=BORDER, width=1)
    draw.text((WIDTH - 74 - source_width, y + 177), source_label, font=source_font, fill=MUTED)
    y += 238

    # 2x3 veri grid'i: yüksek bilgi yoğunluğu, kısa etiket ve iki satırlı range kutusu.
    cell_width = 310
    cell_height = 112
    gap = 18
    x_positions = [56, 56 + cell_width + gap, 56 + 2 * (cell_width + gap)]
    grid = [
        ("AÇILIŞ", _price_or_dash(open_value), CYAN),
        ("GÜN İÇİ YÜKSEK", _price_or_dash(day_high), GREEN),
        ("GÜN İÇİ DÜŞÜK", _price_or_dash(day_low), RED),
        ("ÖNCEKİ KAPANIŞ", _price_or_dash(previous_close), GOLD),
    ]
    for index, (label, value, accent) in enumerate(grid[:3]):
        cell_fill = GREEN_TINT if label == "GÜN İÇİ YÜKSEK" else (RED_TINT if label == "GÜN İÇİ DÜŞÜK" else PANEL)
        label_color = GREEN if label == "GÜN İÇİ YÜKSEK" else (RED if label == "GÜN İÇİ DÜŞÜK" else MUTED)
        _metric(draw, (x_positions[index], y, x_positions[index] + cell_width, y + cell_height), label, value, accent, 26, fill=cell_fill, label_fill=label_color)
    second_y = y + cell_height + 18
    for index, (label, value, accent) in enumerate(grid[3:]):
        _metric(draw, (x_positions[index], second_y, x_positions[index] + cell_width, second_y + cell_height), label, value, accent, 25)
    _pair_metric(draw, (x_positions[1], second_y, x_positions[1] + cell_width, second_y + cell_height), range_label, _price_or_dash(range_high), _price_or_dash(range_low), ORANGE)
    market_label = "PİYASA DEĞERİ" if not is_crypto else "PİYASA DEĞERİ"
    _metric(draw, (x_positions[2], second_y, x_positions[2] + cell_width, second_y + cell_height), market_label, market_cap_text, ORANGE, 22 if len(market_cap_text) > 13 else 26)
    y = second_y + cell_height + 22

    # Grafik paneli: zaman sekmeleri, neon gradient dolgu ve son veri balonu.
    graph_height = 342
    _panel(draw, (56, y, WIDTH - 56, y + graph_height), fill=PANEL, outline=BORDER, radius=24)
    draw.text((84, y + 20), "FİYAT AKIŞI", font=_font(21, bold=True), fill=GREEN)
    _draw_time_tabs(draw, 757, y + 15, selected=time_range)
    try:
        _draw_candlesticks(image, draw, (86, y + 82, WIDTH - 86, y + 282), ohlcv, number(quote.price))
    except ValueError as exc:
        LOGGER.error("Piyasa kartı OHLC/candlestick verisi kullanılamadı: %s", exc)
        draw.text((86, y + 130), "Grafik verisi geçici olarak kullanılamadı.", font=_font(23, bold=True), fill=RED)
    y += graph_height + 22

    # Basit sinyal/trend özeti, karar önerisi vermeden yönü görselleştirir.
    _panel(draw, (56, y, WIDTH - 56, y + 82), fill=GREEN_DARK if trend_accent == GREEN else (RED_DARK if trend_accent == RED else PANEL_ALT), outline=trend_accent, radius=22)
    _draw_trend_icon(draw, 78, y + 19, trend_label, trend_accent)
    draw.text((138, y + 25), "TREND", font=_font(18, bold=True), fill=GREEN)
    trend_width = _text_width(draw, trend_label, _font(27, bold=True))
    draw.text((WIDTH - 86 - trend_width, y + 20), trend_label, font=_font(27, bold=True), fill=trend_accent)

    if quote.note:
        _draw_wrapped(draw, (56, height - 168), quote.note, _font(17), MUTED, WIDTH - 112, line_gap=4)
    _footer(draw, height, quote.source)
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


def save_depth_card(
    symbol: str,
    asset_type: str,
    output_dir: Path,
    depth: DepthSnapshot | None = None,
    quote: Quote | None = None,
) -> Path:
    """Kripto için gerçek emir defteri, BIST için dürüst erişim durumu kartı."""
    is_crypto = asset_type == "crypto"
    title = "KRİPTO DERİNLİĞİ" if is_crypto else "BIST DERİNLİĞİ"
    subtitle = "Gerçek alış / satış kademeleri" if depth and depth.available else "Level 2 veri erişim durumu"
    available = bool(depth and depth.available and depth.bids and depth.asks)
    height = 1640 if available else 1250
    image, draw, y = _base(title, f"{symbol.upper()}  ·  {subtitle}", height=height)

    hero_height = 138 if available else 172
    _panel(draw, (56, y, WIDTH - 56, y + hero_height), fill=PANEL_ALT, outline=BORDER, radius=24)
    status = "GERÇEK PUBLIC" if available else "KULLANILAMIYOR"
    status_color = GREEN if available else GOLD
    draw.ellipse((84, y + 31, 146, y + 93), fill=GREEN_DARK if available else RED_TINT, outline=status_color, width=2)
    # Use an ASCII-safe glyph so every Telegram client renders the icon consistently.
    draw.text((103, y + 42), "B", font=_font(28, bold=True), fill=status_color)
    draw.text((176, y + 27), symbol.upper(), font=_font(30, bold=True), fill=ORANGE if is_crypto else GREEN)
    draw.text((176, y + 70), "Binance Spot order book" if available else "Borsa İstanbul Level 2", font=_font(19), fill=MUTED)
    status_font = _font(17, bold=True)
    status_width = _text_width(draw, status, status_font) + 28
    draw.rounded_rectangle((WIDTH - 86 - status_width, y + 42, WIDTH - 86, y + 78), radius=18, fill=GREEN_DARK if available else RED_TINT, outline=status_color, width=2)
    draw.text((WIDTH - 72 - status_width, y + 51), status, font=status_font, fill=status_color)
    y += hero_height + 20

    if not available:
        _panel(draw, (56, y, WIDTH - 56, y + 270), fill=PANEL_ALT, outline=GOLD, radius=24)
        draw.rectangle((56, y, 70, y + 270), fill=GOLD)
        message = (
            "Bu ücretsiz veri katmanında BIST’in gerçek Level 2 emir kademesi bulunmuyor. "
            "NEXA sahte alış/satış satırı üretmez. Gerçek derinlik için Borsa İstanbul veya yetkili veri dağıtıcısı erişimi gerekir."
        )
        _draw_wrapped(draw, (102, y + 32), message, _font(25, bold=True), TEXT, WIDTH - 168, line_gap=9)
        y += 300
        if quote:
            draw.text((56, y), "MEVCUT FİYAT ÖZETİ", font=_font(22, bold=True), fill=GREEN)
            y += 42
            _metric(draw, (56, y, 298, y + 112), "SON FİYAT", number(quote.price), CYAN, 27)
            _metric(draw, (316, y, 558, y + 112), "DEĞİŞİM", signed_pct(quote.change_pct), GREEN if (quote.change_pct or 0) >= 0 else RED, 25)
            _metric(draw, (576, y, 820, y + 112), "HACİM", _compact(quote.volume), ORANGE, 24)
        _footer(draw, height, "BIST public fiyat katmanı", "Gerçek Level 2 kademesi gösterilmemektedir.")
        return _save(image, output_dir, f"depth_{asset_type}_{symbol.lower()}")

    bid_qty_total = sum(level.quantity for level in depth.bids)
    ask_qty_total = sum(level.quantity for level in depth.asks)
    best_bid = depth.bids[0].price
    best_ask = depth.asks[0].price
    spread = best_ask - best_bid
    imbalance = ((bid_qty_total - ask_qty_total) / (bid_qty_total + ask_qty_total) * 100) if bid_qty_total + ask_qty_total else 0.0
    _metric(draw, (56, y, 298, y + 112), "EN İYİ ALIŞ", number(best_bid), GREEN, 26, fill=GREEN_TINT, label_fill=GREEN)
    _metric(draw, (316, y, 558, y + 112), "EN İYİ SATIŞ", number(best_ask), RED, 26, fill=RED_TINT, label_fill=RED)
    _metric(draw, (576, y, 802, y + 112), "SPREAD", number(spread), GOLD, 25, fill=PANEL)
    _metric(draw, (820, y, 1024, y + 112), "DENGE", signed_pct(imbalance), CYAN, 23, fill=PANEL)
    y += 138

    draw.text((56, y), "EMİR DEFTERİ · İLK 10 KADEME", font=_font(24, bold=True), fill=GREEN)
    y += 43
    col_gap = 20
    col_width = (WIDTH - 112 - col_gap) // 2
    left_x = 56
    right_x = left_x + col_width + col_gap
    header_height = 42
    for x, heading, color in ((left_x, "ALIŞLAR  ·  BID", GREEN), (right_x, "SATIŞLAR  ·  ASK", RED)):
        _panel(draw, (x, y, x + col_width, y + header_height), fill=PANEL_ALT, outline=color, radius=15)
        draw.text((x + 20, y + 11), heading, font=_font(18, bold=True), fill=color)
    y += header_height + 10

    def draw_side(x: int, levels: tuple, color: str, tint: str, label: str) -> None:
        max_qty = max((level.quantity for level in levels), default=1.0)
        row_height = 72
        for index in range(10):
            level = levels[index] if index < len(levels) else None
            row_y = y + index * (row_height + 8)
            _panel(draw, (x, row_y, x + col_width, row_y + row_height), fill=tint, outline=BORDER, radius=15)
            draw.text((x + 18, row_y + 12), f"{index + 1:02d}", font=_font(17, bold=True), fill=MUTED)
            if level is None:
                draw.text((x + 70, row_y + 22), "—", font=_font(22, bold=True), fill=MUTED)
                continue
            bar_width = int((col_width - 104) * min(1.0, level.quantity / max_qty))
            draw.rounded_rectangle((x + 68, row_y + 53, x + 68 + bar_width, row_y + 62), radius=4, fill=color)
            price_text = number(level.price)
            qty_text = number(level.quantity)
            draw.text((x + 70, row_y + 10), price_text, font=_font(21, bold=True), fill=color)
            qty_width = _text_width(draw, qty_text, _font(18, bold=True))
            draw.text((x + col_width - 18 - qty_width, row_y + 13), qty_text, font=_font(18, bold=True), fill=TEXT)
            draw.text((x + col_width - 18 - _text_width(draw, label, _font(13)), row_y + 42), label, font=_font(13), fill=MUTED)

    draw_side(left_x, depth.bids, GREEN, GREEN_TINT, "MİKTAR")
    draw_side(right_x, depth.asks, RED, RED_TINT, "MİKTAR")
    _footer(draw, height, depth.source, depth.note or "Public emir defteri; yatırım tavsiyesi değildir.")
    return _save(image, output_dir, f"depth_{asset_type}_{symbol.lower()}")


def save_volume_profile_card(symbol: str, quote: Quote, profile: VolumeProfile, output_dir: Path) -> Path:
    """BIST için kripto derinlik kartıyla aynı yoğunlukta OHLCV analiz kartı."""
    # Keep the exact portrait rhythm of the crypto depth card while replacing
    # bid/ask rows with actual OHLCV candle-volume rows.
    height = 1640
    image, draw, y = _base("BIST HACİM DAĞILIMI", f"{symbol.upper()}  ·  OHLCV hacim dağılımı", height=height)

    hero_height = 138
    _panel(draw, (56, y, WIDTH - 56, y + hero_height), fill=PANEL_ALT, outline=BORDER, radius=24)
    draw.ellipse((84, y + 31, 146, y + 93), fill=GREEN_TINT, outline=GREEN, width=2)
    draw.text((104, y + 43), "V", font=_font(27, bold=True), fill=GREEN)
    draw.text((176, y + 27), symbol.upper(), font=_font(30, bold=True), fill=GREEN)
    draw.text((176, y + 70), "Yahoo Finance OHLCV", font=_font(19), fill=MUTED)
    badge = "OHLCV VERİSİ"
    badge_font = _font(17, bold=True)
    badge_width = _text_width(draw, badge, badge_font) + 28
    draw.rounded_rectangle((WIDTH - 86 - badge_width, y + 42, WIDTH - 86, y + 78), radius=18, fill=GREEN_DARK, outline=GREEN, width=2)
    draw.text((WIDTH - 72 - badge_width, y + 51), badge, font=badge_font, fill=GREEN)
    y += hero_height + 20

    # Same four-tile summary row as the crypto depth card.
    metric_gap = 18
    metric_width = (WIDTH - 112 - metric_gap * 3) // 4
    metric_x = [56 + index * (metric_width + metric_gap) for index in range(4)]
    _metric(draw, (metric_x[0], y, metric_x[0] + metric_width, y + 112), "SON FİYAT", number(quote.price), CYAN, 24, fill=PANEL)
    _metric(draw, (metric_x[1], y, metric_x[1] + metric_width, y + 112), "DEĞİŞİM", signed_pct(quote.change_pct), _trend_color(quote.change_pct), 23, fill=GREEN_TINT if (quote.change_pct or 0) >= 0 else RED_TINT, label_fill=_trend_color(quote.change_pct))
    _metric(draw, (metric_x[2], y, metric_x[2] + metric_width, y + 112), "TOPLAM HACİM", _compact(profile.total_volume), GREEN, 21, fill=GREEN_TINT, label_fill=GREEN)
    _metric(draw, (metric_x[3], y, WIDTH - 56, y + 112), "ORT. BAR", _compact(profile.average_volume), CYAN, 22, fill=PANEL)
    y += 138

    up_pct = profile.up_volume / profile.total_volume * 100 if profile.total_volume else 0.0
    down_pct = profile.down_volume / profile.total_volume * 100 if profile.total_volume else 0.0
    draw.text((56, y), "HACİM DAĞILIMI · SON 10 BAR", font=_font(24, bold=True), fill=GREEN)
    y += 43
    col_gap = 20
    col_width = (WIDTH - 112 - col_gap) // 2
    left_x = 56
    right_x = left_x + col_width + col_gap
    header_height = 42
    left_heading = f"YÜKSELEN · UP  %{up_pct:.1f}".replace(".", ",")
    right_heading = f"DÜŞEN · DOWN  %{down_pct:.1f}".replace(".", ",")
    for x, heading, color in ((left_x, left_heading, GREEN), (right_x, right_heading, RED)):
        _panel(draw, (x, y, x + col_width, y + header_height), fill=PANEL_ALT, outline=color, radius=15)
        draw.text((x + 20, y + 11), heading, font=_font(18, bold=True), fill=color)
    y += header_height + 10

    up_bars = tuple(reversed([bar for bar in profile.recent_bars if bar.direction == "up"][-10:]))
    down_bars = tuple(reversed([bar for bar in profile.recent_bars if bar.direction == "down"][-10:]))

    def draw_side(x: int, levels: tuple[Any, ...], color: str, tint: str) -> None:
        max_volume = max((bar.volume for bar in levels), default=1.0)
        row_height = 72
        for index in range(10):
            bar = levels[index] if index < len(levels) else None
            row_y = y + index * (row_height + 8)
            _panel(draw, (x, row_y, x + col_width, row_y + row_height), fill=tint, outline=BORDER, radius=15)
            draw.text((x + 18, row_y + 12), f"{index + 1:02d}", font=_font(17, bold=True), fill=MUTED)
            if bar is None:
                draw.text((x + 70, row_y + 22), "—", font=_font(22, bold=True), fill=MUTED)
                continue
            bar_width = int((col_width - 104) * min(1.0, bar.volume / max_volume))
            draw.rounded_rectangle((x + 68, row_y + 53, x + 68 + bar_width, row_y + 62), radius=4, fill=color)
            close_text = number(bar.close)
            volume_text = _compact(bar.volume)
            draw.text((x + 70, row_y + 10), close_text, font=_font(21, bold=True), fill=color)
            volume_width = _text_width(draw, volume_text, _font(18, bold=True))
            draw.text((x + col_width - 18 - volume_width, row_y + 13), volume_text, font=_font(18, bold=True), fill=TEXT)
            draw.text((x + 70, row_y + 42), bar.label, font=_font(13), fill=MUTED)
            volume_label = "HACİM"
            label_width = _text_width(draw, volume_label, _font(13))
            draw.text((x + col_width - 18 - label_width, row_y + 42), volume_label, font=_font(13), fill=MUTED)

    draw_side(left_x, up_bars, GREEN, GREEN_TINT)
    draw_side(right_x, down_bars, RED, RED_TINT)
    _footer(draw, height, "Yahoo Finance via yfinance", "OHLCV ANALİZ VERİSİ")
    return _save(image, output_dir, f"volume_profile_{symbol.lower()}")


def save_notice_card(
    title: str,
    message: str,
    output_dir: Path,
    slug: str = "notice_card",
    accent: str = GREEN,
    commands: list[tuple[str, str]] | None = None,
) -> Path:
    """Bölüm yönlendirmesi ve örnek komutları birlikte gösteren mobil bilgi kartı."""
    command_rows = commands or []
    height = 720 + min(len(command_rows), 6) * 78
    image, draw, y = _base(title, "NEXA bilgi kartı", height=height)
    message_height = 196 if command_rows else 220
    _panel(draw, (56, y, WIDTH - 56, y + message_height), fill=PANEL_ALT)
    draw.rectangle((56, y, 70, y + message_height), fill=accent)
    _draw_wrapped(draw, (102, y + 32), message, _font(26, bold=True), TEXT, WIDTH - 168, line_gap=9)
    y += message_height + 28
    if command_rows:
        draw.text((56, y), "NE YAPABİLİRSİNİZ?", font=_font(23, bold=True), fill=GREEN)
        y += 44
        for command, description in command_rows[:6]:
            row_height = 62
            draw.rounded_rectangle((56, y, WIDTH - 56, y + row_height), radius=17, fill=PANEL, outline=BORDER, width=2)
            draw.text((82, y + 9), command, font=_font(22, bold=True), fill=TEXT)
            desc_font = _font(17)
            desc_width = _text_width(draw, description, desc_font)
            draw.text((WIDTH - 82 - desc_width, y + 22), description, font=desc_font, fill=MUTED)
            y += row_height + 16
    _footer(draw, height, "NEXA")
    return _save(image, output_dir, slug)
