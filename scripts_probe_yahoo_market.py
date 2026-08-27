"""Yahoo sembol eşleşmelerinin tek seferlik geliştirme smoke test'i."""

import yfinance as yf


SYMBOLS = ["XU030.IS", "XU100.IS", "USDTRY=X", "EURTRY=X", "GC=F"]


def main() -> None:
    for symbol in SYMBOLS:
        try:
            frame = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False, actions=False)
            if frame.empty:
                print(f"FAIL {symbol}: boş veri")
            else:
                print(f"OK   {symbol}: {frame.index[-1]} close={frame['Close'].iloc[-1]}")
        except Exception as exc:
            print(f"FAIL {symbol}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
