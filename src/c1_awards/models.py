from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class Cabin(str, Enum):
    ECONOMY = "Economy"
    PREMIUM_ECONOMY = "Premium Economy"
    BUSINESS = "Business"
    FIRST = "First"


@dataclass(slots=True)
class AwardResult:
    found_at: datetime
    program: str
    operating_airline: str
    flight: str
    origin: str
    destination: str
    depart: Optional[datetime]
    arrive: Optional[datetime]
    cabin: Cabin
    stops: Optional[int]
    partner_award_miles: int
    taxes_fees_usd: float
    seats: Optional[int]
    award_source_url: str
    scraper_source: str

    def as_dict(self) -> dict:
        out = asdict(self)
        out["found_at"] = self.found_at.isoformat()
        out["depart"] = self.depart.isoformat() if self.depart else ""
        out["arrive"] = self.arrive.isoformat() if self.arrive else ""
        out["cabin"] = self.cabin.value
        return out


@dataclass(slots=True)
class AnalyzedAward:
    award: AwardResult
    cash_price_usd: Optional[float]
    cash_price_source: str
    cash_price_url: str
    partner_units_per_c1: float
    transfer_bonus: float
    effective_partner_units_per_c1: float
    c1_miles_needed: int
    effective_cpp: Optional[float]
    value_vs_one_cent_usd: Optional[float]
    capital_one_transfer_url: str
    award_booking_url: str
