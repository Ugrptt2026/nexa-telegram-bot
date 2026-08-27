"""KAP public sayfa gözlemcisi.

KAP REST Veri Yayın Servisi abonelik/sözleşme gerektirdiğinden burada resmi
REST API taklidi yapılmaz. Bu adaptör yalnızca kamuya açık ana sayfanın HTML
cevabında tablo satırları varsa onları okur; site dinamik veya boş dönerse
boş liste döndürür.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True, slots=True)
class Disclosure:
    date: str
    code: str
    company: str
    subject: str
    url: str | None = None
    source: str = "KAP public website"

    @property
    def fingerprint(self) -> str:
        raw = "|".join((self.date, self.code, self.company, self.subject, self.url or ""))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class KAPPublicClient:
    def __init__(self, base_url: str = "https://kap.org.tr/tr") -> None:
        self.base_url = base_url

    def fetch_recent_disclosures(self, limit: int = 20) -> list[Disclosure]:
        response = httpx.get(
            self.base_url,
            timeout=15,
            headers={"User-Agent": "Nexa/0.1 (low-frequency public-page observer)"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        disclosures: list[Disclosure] = []
        tables = soup.select("table")
        if not tables:
            return disclosures
        # Ana sayfadaki ilk tablo şirket bildirimleri sekmesidir. Diğer
        # tablolar footer/özet bileşenleri olup bildirim şeması taşımaz.
        for row in tables[0].select("tbody tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(cells) < 4:
                continue
            joined = " ".join(cells).strip().lower()
            if not joined or joined == "0 0 0 0" or "bildirim bulunamadı" in joined:
                continue
            link = row.select_one("a[href]")
            url = link.get("href") if link else None
            if url and url.startswith("/"):
                url = "https://kap.org.tr" + url
            disclosures.append(
                Disclosure(
                    date=cells[0],
                    code=cells[1],
                    company=cells[2],
                    subject=cells[3],
                    url=url,
                )
            )
            if len(disclosures) >= limit:
                break
        return disclosures


def format_disclosures(items: list[Disclosure]) -> str:
    if not items:
        return (
            "<b>KAP bildirimleri</b>\n\n"
            "Public sayfa cevabında okunabilir bildirim satırı bulunamadı. "
            "KAP’ın sözleşmeli REST servisi ücretsiz/public değildir."
        )
    lines = ["<b>Son KAP bildirimleri</b>"]
    for item in items:
        lines.append(f"{item.date} — <b>{item.company}</b> — {item.subject}")
    return "\n".join(lines)
