"""KAP public sayfa gözlemcisi smoke test'i."""

from nexa.kap import KAPPublicClient


def main() -> None:
    try:
        items = KAPPublicClient().fetch_recent_disclosures(5)
        print(f"OK: {len(items)} okunabilir satır")
        for item in items:
            print(item)
    except Exception as exc:
        print(f"FAIL {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
