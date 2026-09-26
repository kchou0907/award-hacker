from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .base import BaseScraper, ScraperError
from .capture import JsonResponseCapture
from ..models import AwardResult, Cabin


class AeroplanScraper(BaseScraper):
    """
    Experimental Aeroplan scraper.

    DOM selectors are intentionally treated as fallback logic. Every run also records
    JSON responses so the preferred future parser can consume structured responses.
    """

    program_name = "Air Canada Aeroplan"
    base_url = "https://www.aircanada.com"

    cabin_map = {
        Cabin.ECONOMY: "economy",
        Cabin.PREMIUM_ECONOMY: "premium-economy",
        Cabin.BUSINESS: "business",
        Cabin.FIRST: "first",
    }

    def _search_url(self, origin: str, destination: str, travel_date: date, cabin: Cabin) -> str:
        params = {
            "org0": origin.upper(),
            "dest0": destination.upper(),
            "departureDate0": travel_date.isoformat(),
            "ADT": "1",
            "YTH": "0",
            "CHD": "0",
            "INF": "0",
            "INS": "0",
            "tripType": "O",
            "marketCode": "INT",
            "cabinClass": self.cabin_map[cabin],
        }
        return f"{self.base_url}/aeroplan/redeem/availability/outbound?{urlencode(params)}"

    async def search(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        cabin: Cabin,
    ) -> list[AwardResult]:
        url = self._search_url(origin, destination, travel_date, cabin)
        capture = JsonResponseCapture(
            self.raw_dir,
            f"aeroplan-{origin.upper()}-{destination.upper()}-{travel_date.isoformat()}",
        )

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                viewport={"width": 1440, "height": 1000},
            )
            page = context.pages[0] if context.pages else await context.new_page()
            page.on("response", lambda response: asyncio.create_task(capture.capture(response)))

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                # Give a headful user time to complete a normal login prompt if one appears.
                try:
                    await page.wait_for_load_state("networkidle", timeout=20_000)
                except PlaywrightTimeoutError:
                    pass

                try:
                    await page.wait_for_selector(
                        ".flight-row, [data-testid='flight-row'], .no-results-message, .no-flights",
                        timeout=35_000,
                    )
                except PlaywrightTimeoutError:
                    await page.screenshot(path=str(self.raw_dir / "aeroplan-failure.png"), full_page=True)
                    (self.raw_dir / "aeroplan-failure.html").write_text(
                        await page.content(), encoding="utf-8"
                    )
                    raise ScraperError(
                        "Aeroplan result selectors were not found. "
                        "If the site requested login, rerun headful and sign in normally. "
                        f"Diagnostic files were saved in {self.raw_dir}."
                    )

                if await page.query_selector(".no-results-message, .no-flights"):
                    return []

                rows = await page.query_selector_all(".flight-row, [data-testid='flight-row']")
                awards: list[AwardResult] = []
                for row in rows:
                    parsed = await self._parse_row(
                        row, origin.upper(), destination.upper(), travel_date, cabin, url
                    )
                    if parsed is not None:
                        awards.append(parsed)
                return awards
            finally:
                await context.close()

    async def _text(self, row, selector: str, default: str = "") -> str:
        elem = await row.query_selector(selector)
        return (await elem.inner_text()).strip() if elem else default

    async def _parse_row(
        self,
        row,
        origin: str,
        destination: str,
        travel_date: date,
        cabin: Cabin,
        source_url: str,
    ) -> Optional[AwardResult]:
        try:
            flight = await self._text(row, ".flight-number", "AC???")
            dep_text = await self._text(row, ".departure-time", "")
            arr_text = await self._text(row, ".arrival-time", "")
            points_text = await self._text(
                row, ".points-value, .aeroplan-points, [data-testid='points']", "0"
            )
            fees_text = await self._text(row, ".taxes-fees, .cash-portion", "$0")
            operating_text = await self._text(row, ".operated-by, .carrier-name", "Air Canada")

            miles = self._parse_int(points_text)
            if miles <= 0:
                return None

            airline = self._normalize_carrier(operating_text)
            depart = self._parse_datetime(travel_date, dep_text)
            arrive = self._parse_datetime(travel_date, arr_text)
            if depart and arrive and arrive < depart:
                # Handles simple overnight arrivals. Multi-day itineraries need a structured-response parser.
                from datetime import timedelta
                arrive += timedelta(days=1)

            return AwardResult(
                found_at=datetime.now(timezone.utc),
                program=self.program_name,
                operating_airline=airline,
                flight=flight,
                origin=origin,
                destination=destination,
                depart=depart,
                arrive=arrive,
                cabin=cabin,
                stops=None,
                partner_award_miles=miles,
                taxes_fees_usd=self._parse_price(fees_text),
                seats=None,
                award_source_url=source_url,
                scraper_source="aeroplan-playwright-dom-experimental",
            )
        except Exception:
            return None

    @staticmethod
    def _parse_int(text: str) -> int:
        cleaned = re.sub(r"[^\d]", "", text)
        return int(cleaned) if cleaned else 0

    @staticmethod
    def _parse_price(text: str) -> float:
        match = re.search(r"(?:US|CA)?\$?\s*([\d,]+(?:\.\d{1,2})?)", text)
        return float(match.group(1).replace(",", "")) if match else 0.0

    @staticmethod
    def _parse_datetime(travel_date: date, text_value: str) -> Optional[datetime]:
        value = text_value.strip().upper()
        if not value:
            return None
        for fmt in ("%I:%M %p", "%H:%M"):
            try:
                parsed = datetime.strptime(value, fmt).time()
                return datetime.combine(travel_date, parsed)
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_carrier(text: str) -> str:
        carriers = {
            "Lufthansa": "Lufthansa",
            "United": "United Airlines",
            "ANA": "ANA",
            "Swiss": "Swiss",
            "Singapore": "Singapore Airlines",
            "Thai": "Thai Airways",
            "EVA": "EVA Air",
            "Turkish": "Turkish Airlines",
            "Air Canada": "Air Canada",
        }
        for needle, canonical in carriers.items():
            if needle.lower() in text.lower():
                return canonical
        return text.strip() or "Unknown"
