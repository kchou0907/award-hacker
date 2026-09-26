from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Optional

from .models import AwardResult, AnalyzedAward


CAPITAL_ONE_REWARDS_URL = "https://www.capitalone.com/credit-cards/rewards/"
MIN_TRANSFER_MILES = 1_000


@dataclass(frozen=True, slots=True)
class TransferPartner:
    program: str
    partner_units_per_c1: float
    redemption_url: str


PARTNERS: dict[str, TransferPartner] = {
    "Aeromexico Rewards": TransferPartner("Aeromexico Rewards", 1.0, "https://www.aeromexicorewards.com/"),
    "Air Canada Aeroplan": TransferPartner("Air Canada Aeroplan", 1.0, "https://www.aircanada.com/aeroplan/redeem/availability/outbound"),
    "Avianca LifeMiles": TransferPartner("Avianca LifeMiles", 1.0, "https://www.lifemiles.com/"),
    "British Airways Club": TransferPartner("British Airways Club", 1.0, "https://www.britishairways.com/content/executive-club"),
    "Cathay Pacific Asia Miles": TransferPartner("Cathay Pacific Asia Miles", 1.0, "https://www.cathaypacific.com/cx/en_US/book-a-trip/redeem-flights/redeem-flight-awards.html"),
    "Etihad Guest": TransferPartner("Etihad Guest", 1.0, "https://www.etihad.com/en/book/book-with-miles"),
    "Finnair Plus": TransferPartner("Finnair Plus", 1.0, "https://www.finnair.com/us-en/finnair-plus/use-avios"),
    "Flying Blue": TransferPartner("Flying Blue", 1.0, "https://www.flyingblue.com/en/spend/flights/rewards"),
    "Qantas Frequent Flyer": TransferPartner("Qantas Frequent Flyer", 1.0, "https://www.qantas.com/us/en/frequent-flyer/use-points/classic-flight-rewards.html"),
    "Qatar Airways Privilege Club": TransferPartner("Qatar Airways Privilege Club", 1.0, "https://www.qatarairways.com/en-us/Privilege-Club.html"),
    "Singapore Airlines KrisFlyer": TransferPartner("Singapore Airlines KrisFlyer", 1.0, "https://www.singaporeair.com/en_UK/us/ppsclub-krisflyer/use-miles/redeem-miles/"),
    "TAP Miles&Go": TransferPartner("TAP Miles&Go", 1.0, "https://www.flytap.com/en-us/miles-and-go/spend-miles"),
    "Turkish Airlines Miles&Smiles": TransferPartner("Turkish Airlines Miles&Smiles", 1.0, "https://www.turkishairlines.com/en-us/miles-and-smiles/awards/"),
    "Virgin Red": TransferPartner("Virgin Red", 1.0, "https://www.virgin.com/virgin-red"),
    "Emirates Skywards": TransferPartner("Emirates Skywards", 0.75, "https://www.emirates.com/us/english/skywards/spend-miles/"),
    "EVA Air Infinity MileageLands": TransferPartner("EVA Air Infinity MileageLands", 0.75, "https://www.evaair.com/en-us/infinity-mileagelands/mileage-award-program/ticket-awards/"),
    "Japan Airlines Mileage Bank": TransferPartner("Japan Airlines Mileage Bank", 0.75, "https://www.jal.co.jp/jp/en/jalmile/use/jal/"),
    "JetBlue TrueBlue": TransferPartner("JetBlue TrueBlue", 0.60, "https://www.jetblue.com/trueblue/using-points"),
    "Choice Privileges": TransferPartner("Choice Privileges", 1.0, "https://www.choicehotels.com/choice-privileges/redeem-points"),
    "Wyndham Rewards": TransferPartner("Wyndham Rewards", 1.0, "https://www.wyndhamhotels.com/wyndham-rewards/redeem"),
    "I Prefer Hotel Rewards": TransferPartner("I Prefer Hotel Rewards", 2.0, "https://preferredhotels.com/i-prefer"),
    "ALL - Accor Live Limitless": TransferPartner("ALL - Accor Live Limitless", 0.5, "https://all.accor.com/loyalty-program/reasonstojoin/index.en.shtml"),
}


def capital_one_miles_needed(
    partner_award_miles: int,
    partner_units_per_c1: float,
    transfer_bonus: float = 0.0,
) -> int:
    if partner_award_miles <= 0:
        raise ValueError("partner_award_miles must be > 0")
    if partner_units_per_c1 <= 0:
        raise ValueError("partner_units_per_c1 must be > 0")
    if transfer_bonus < 0:
        raise ValueError("transfer_bonus cannot be negative")

    effective = partner_units_per_c1 * (1.0 + transfer_bonus)
    exact = ceil(partner_award_miles / effective)
    return max(MIN_TRANSFER_MILES, exact)


def effective_cpp(
    cash_price_usd: float,
    taxes_fees_usd: float,
    c1_miles_needed: int,
) -> float:
    if c1_miles_needed <= 0:
        raise ValueError("c1_miles_needed must be > 0")
    return max(0.0, cash_price_usd - taxes_fees_usd) / c1_miles_needed * 100.0


def analyze_award(
    award: AwardResult,
    *,
    cash_price_usd: Optional[float] = None,
    cash_price_source: str = "",
    cash_price_url: str = "",
    transfer_bonus: float = 0.0,
) -> AnalyzedAward:
    partner = PARTNERS[award.program]
    effective_units = partner.partner_units_per_c1 * (1.0 + transfer_bonus)
    needed = capital_one_miles_needed(
        award.partner_award_miles,
        partner.partner_units_per_c1,
        transfer_bonus,
    )

    cpp = None
    value_vs_one_cent = None
    if cash_price_usd is not None:
        net_cash = max(0.0, cash_price_usd - award.taxes_fees_usd)
        cpp = effective_cpp(cash_price_usd, award.taxes_fees_usd, needed)
        value_vs_one_cent = max(0.0, net_cash - needed * 0.01)

    return AnalyzedAward(
        award=award,
        cash_price_usd=cash_price_usd,
        cash_price_source=cash_price_source,
        cash_price_url=cash_price_url,
        partner_units_per_c1=partner.partner_units_per_c1,
        transfer_bonus=transfer_bonus,
        effective_partner_units_per_c1=effective_units,
        c1_miles_needed=needed,
        effective_cpp=cpp,
        value_vs_one_cent_usd=value_vs_one_cent,
        capital_one_transfer_url=CAPITAL_ONE_REWARDS_URL,
        award_booking_url=partner.redemption_url,
    )
