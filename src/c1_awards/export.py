from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .capital_one import analyze_award
from .models import AwardResult


SHEET_COLUMNS = [
    "Found At","Program","Operating Airline","Flight","Origin","Destination","Depart","Arrive",
    "Cabin","Stops","Partner Award Miles","Taxes/Fees USD","Cash Price USD","Cash Price Source",
    "Cash Price URL","Partner units / 1 C1","Transfer Bonus %","Effective units / 1 C1",
    "C1 Miles Needed","Effective CPP","Value vs 1¢/mi USD","Seats","Capital One Transfer",
    "Award Booking","How to Redeem","Scraper Source","Award Source URL","Scraper Status","Notes",
]


def export_csv(
    awards: Iterable[AwardResult],
    path: Path,
    *,
    cash_price_usd: float | None = None,
    cash_price_source: str = "",
    cash_price_url: str = "",
    transfer_bonus: float = 0.0,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for award in awards:
            analyzed = analyze_award(
                award,
                cash_price_usd=cash_price_usd,
                cash_price_source=cash_price_source,
                cash_price_url=cash_price_url,
                transfer_bonus=transfer_bonus,
            )
            row = {
                "Found At": award.found_at.isoformat(),
                "Program": award.program,
                "Operating Airline": award.operating_airline,
                "Flight": award.flight,
                "Origin": award.origin,
                "Destination": award.destination,
                "Depart": award.depart.isoformat() if award.depart else "",
                "Arrive": award.arrive.isoformat() if award.arrive else "",
                "Cabin": award.cabin.value,
                "Stops": "" if award.stops is None else award.stops,
                "Partner Award Miles": award.partner_award_miles,
                "Taxes/Fees USD": f"{award.taxes_fees_usd:.2f}",
                "Cash Price USD": "" if cash_price_usd is None else f"{cash_price_usd:.2f}",
                "Cash Price Source": cash_price_source,
                "Cash Price URL": cash_price_url,
                "Partner units / 1 C1": analyzed.partner_units_per_c1,
                "Transfer Bonus %": analyzed.transfer_bonus,
                "Effective units / 1 C1": analyzed.effective_partner_units_per_c1,
                "C1 Miles Needed": analyzed.c1_miles_needed,
                "Effective CPP": "" if analyzed.effective_cpp is None else f"{analyzed.effective_cpp:.3f}",
                "Value vs 1¢/mi USD": "" if analyzed.value_vs_one_cent_usd is None else f"{analyzed.value_vs_one_cent_usd:.2f}",
                "Seats": "" if award.seats is None else award.seats,
                "Capital One Transfer": analyzed.capital_one_transfer_url,
                "Award Booking": analyzed.award_booking_url,
                "How to Redeem": (
                    f"Verify availability → transfer {analyzed.c1_miles_needed:,} Capital One miles "
                    f"to {award.program} → book {award.partner_award_miles:,} partner miles "
                    f"+ ${award.taxes_fees_usd:,.2f} fees."
                ),
                "Scraper Source": award.scraper_source,
                "Award Source URL": award.award_source_url,
                "Scraper Status": "Live",
                "Notes": "",
            }
            writer.writerow(row)
