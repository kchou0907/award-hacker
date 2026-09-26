from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path

from .api_discovery import discover_aeroplan_api
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


async def run_discover_aeroplan(args) -> None:
    result = await discover_aeroplan_api(
        args.origin,
        args.destination,
        date.fromisoformat(args.date),
        passengers=args.passengers,
        profile_dir=Path(args.profile_dir),
        capture_dir=Path(args.capture_dir),
        browser=args.browser,
        headless=args.headless,
        wait_seconds=args.wait_seconds,
        attempt_replay=not args.no_replay,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="c1-awards")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser(
        "discover-aeroplan",
        help="Capture Aeroplan fetch/XHR traffic, identify polldapi, and test direct replay",
    )
    d.add_argument("--origin", required=True)
    d.add_argument("--destination", required=True)
    d.add_argument("--date", required=True, help="YYYY-MM-DD")
    d.add_argument("--passengers", type=int, default=1)
    d.add_argument("--profile-dir", default=".browser-profile")
    d.add_argument("--capture-dir", default=".captures")
    d.add_argument("--browser", choices=["auto", "chrome", "chromium"], default="auto")
    d.add_argument("--headless", action="store_true")
    d.add_argument("--wait-seconds", type=int, default=180)
    d.add_argument("--no-replay", action="store_true")

    a = sub.add_parser(
        "aeroplan",
        help="Legacy experimental Aeroplan DOM scraper; prefer discover-aeroplan first",
    )
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
    if args.command == "discover-aeroplan":
        asyncio.run(run_discover_aeroplan(args))
    elif args.command == "aeroplan":
        asyncio.run(run_aeroplan(args))


if __name__ == "__main__":
    main()
