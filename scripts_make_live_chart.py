"""Gerçek Yahoo BIST verisiyle Nexa grafik smoke test'i."""

from pathlib import Path

from nexa.charts import save_price_chart
from nexa.providers import YahooBistClient


def main() -> None:
    client = YahooBistClient()
    frame = client.get_ohlcv("THYAO", period="6mo", interval="1d")
    output = save_price_chart(frame, "Nexa — THYAO fiyat grafiği", Path("/home/ubuntu/nexa/artifacts"))
    print(output)


if __name__ == "__main__":
    main()
