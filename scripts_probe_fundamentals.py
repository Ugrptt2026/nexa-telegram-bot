"""yfinance temel oran smoke test'i."""

import yfinance as yf

from nexa.providers import YahooBistClient


def main() -> None:
    try:
        ticker = yf.Ticker("THYAO.IS")
        info = ticker.info
        print({key: info.get(key) for key in ("trailingPE", "priceToBook", "dividendYield", "dividendRate", "trailingAnnualDividendYield", "marketCap")})
        print(YahooBistClient().get_fundamentals("THYAO"))
    except Exception as exc:
        print(f"FAIL {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
