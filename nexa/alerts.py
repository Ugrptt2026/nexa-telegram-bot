"""Alarm iş mantığı."""

from __future__ import annotations

from dataclasses import dataclass

from .providers import Quote


@dataclass(frozen=True, slots=True)
class AlarmMatch:
    alarm_id: int
    reason: str


def alarm_matches(alarm: dict, quote: Quote) -> AlarmMatch | None:
    """Alarm koşulu sağlanıyorsa eşleşme, aksi halde None döndürür."""
    condition = alarm["condition"]
    target = float(alarm["target"])
    if condition == "above" and quote.price >= target:
        return AlarmMatch(int(alarm["id"]), f"fiyat {target:g} seviyesinin üstüne çıktı")
    if condition == "below" and quote.price <= target:
        return AlarmMatch(int(alarm["id"]), f"fiyat {target:g} seviyesinin altına indi")
    if condition == "change_pct" and quote.change_pct is not None and abs(quote.change_pct) >= target:
        return AlarmMatch(int(alarm["id"]), f"24 saatlik mutlak değişim %{target:g} eşiğini geçti")
    return None


def parse_alarm_condition(raw: str) -> str:
    values = {
        "ust": "above",
        "üst": "above",
        "above": "above",
        "alt": "below",
        "below": "below",
        "degisim": "change_pct",
        "değişim": "change_pct",
        "change": "change_pct",
    }
    normalized = raw.strip().lower()
    if normalized not in values:
        raise ValueError("Koşul ust, alt veya degisim olmalı")
    return values[normalized]


def parse_asset_type(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized in {"hisse", "stock", "bist"}:
        return "stock"
    if normalized in {"kripto", "crypto", "coin"}:
        return "crypto"
    raise ValueError("Varlık türü hisse veya kripto olmalı")
