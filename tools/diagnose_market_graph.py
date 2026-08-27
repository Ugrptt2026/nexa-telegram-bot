from __future__ import annotations

import json
from pathlib import Path

from nexa.providers import BinanceClient, MarketDataError, YahooBistClient


CASES = (
    ("stock", "THYAO", YahooBistClient(), lambda client, symbol: client.get_ohlcv(symbol, "1y", "1d")),
    ("crypto", "BTC", BinanceClient(), lambda client, symbol: client.get_ohlcv(symbol, "1d", 60)),
)


def main() -> None:
    results: list[dict[str, object]] = []
    for asset_type, symbol, client, getter in CASES:
        row: dict[str, object] = {"asset_type": asset_type, "symbol": symbol}
        try:
            quote = client.get_quote(symbol)
            frame = getter(client, symbol)
            row.update(
                {
                    "quote_price": quote.price,
                    "quote_metadata": quote.metadata,
                    "ohlcv_empty": frame.empty,
                    "ohlcv_rows": int(len(frame)),
                    "ohlcv_columns": list(frame.columns),
                    "close_non_null": int(frame["close"].notna().sum()) if "close" in frame else 0,
                    "open_non_null": int(frame["open"].notna().sum()) if "open" in frame else 0,
                    "high_non_null": int(frame["high"].notna().sum()) if "high" in frame else 0,
                    "low_non_null": int(frame["low"].notna().sum()) if "low" in frame else 0,
                    "last_close": float(frame["close"].dropna().iloc[-1]) if "close" in frame and not frame["close"].dropna().empty else None,
                }
            )
        except (MarketDataError, ValueError) as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        results.append(row)

    output = Path("docs/graph-diagnosis.json")
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
