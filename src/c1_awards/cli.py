from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path

from .export import export_csv
from .models import Cabin
from .scrapers import AeroplanScraper


CABIN_BY_ARG = {
    "economy": Cabin.ECONOMY,
    "premium-economy": Cabin.PREMIUM_ECONOMY,
    "business": Cabin.BUSINESS,
    "first": Cabin.FIRST,
}


async def run_aeroplan(args) -> None:
    scraper = AeroplanScraper(
        profile_dir=Path(args.profile_dir),
        raw_dir=Path(args.raw_dir),
        headless=args.headless,
    )
    awards = await scraper.search(
        args.origin,
        args.destination,
        date.fromisoformat(args.date),
        CABIN_BY_ARG[args.cabin],
    )
    export_csv(
        awards,
        Path(args.out),
        cash_price_usd=args.cash_price,
        cash_price_source=args.cash_source,
        cash_price_url=args.cash_url,
        transfer_bonus=args.transfer_bonus,
    )
    print(f"Wrote {len(awards)} award rows to {args.out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="c1-awards")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("aeroplan", help="Experimental Aeroplan award search")
    a.add_argument("--origin", required=True)
    a.add_argument("--destination", required=True)
    a.add_argument("--date", required=True, help="YYYY-MM-DD")
    a.add_argument("--cabin", choices=list(CABIN_BY_ARG), default="economy")
    a.add_argument("--profile-dir", default=".browser-profile")
    a.add_argument("--raw-dir", default=".raw")
    a.add_argument("--out", default="awards.csv")
    a.add_argument("--headless", action="store_true")
    a.add_argument("--cash-price", type=float, default=None)
    a.add_argument("--cash-source", default="")
    a.add_argument("--cash-url", default="")
    a.add_argument("--transfer-bonus", type=float, default=0.0)

    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "aeroplan":
        asyncio.run(run_aeroplan(args))


if __name__ == "__main__":
    main()
