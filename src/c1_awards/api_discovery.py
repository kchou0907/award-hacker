from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Request, Response, async_playwright


SENSITIVE_HEADER_MARKERS = (
    "authorization",
    "cookie",
    "csrf",
    "token",
    "api-key",
    "apikey",
    "session",
)

BOT_MARKERS = (
    "kpsdk",
    "kasada",
    "akamai",
    "datadome",
    "cf-ray",
    "cf_clearance",
    "bm_sz",
    "ak_bmsc",
    "_abck",
)

REPLAY_HEADER_ALLOWLIST = {
    "accept",
    "accept-language",
    "authorization",
    "content-type",
    "origin",
    "referer",
    "user-agent",
    "x-csrf-token",
    "x-requested-with",
}

CANDIDATE_URL_TERMS = (
    "polldapi",
    "dapi",
    "availability",
    "award",
    "redeem",
    "search",
    "flight",
)


@dataclass(slots=True)
class CapturedExchange:
    sequence: int
    observed_at: str
    method: str
    url: str
    resource_type: str
    request_headers: dict[str, str]
    post_data: str | None
    status: int
    response_headers: dict[str, str]
    response_json: Any
    score: int
    reasons: list[str]


@dataclass(slots=True)
class ReplayResult:
    attempted: bool
    status: int | None
    content_type: str
    response_json: Any | None
    response_text_preview: str
    error: str
    bot_protection_observed: bool


def _contains_marker(value: str, markers: tuple[str, ...]) -> bool:
    lower = value.lower()
    return any(marker in lower for marker in markers)


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for name, value in headers.items():
        if _contains_marker(name, SENSITIVE_HEADER_MARKERS) or name.lower() == "set-cookie":
            redacted[name] = "<redacted>"
        else:
            redacted[name] = value
    return redacted


def has_bot_marker(headers: dict[str, str]) -> bool:
    for name, value in headers.items():
        if _contains_marker(name, BOT_MARKERS) or _contains_marker(value, BOT_MARKERS):
            return True
    return False


def _json_key_hits(value: Any, wanted: set[str], depth: int = 0) -> set[str]:
    if depth > 6:
        return set()
    hits: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in wanted:
                hits.add(key)
            hits |= _json_key_hits(child, wanted, depth + 1)
    elif isinstance(value, list):
        for child in value[:30]:
            hits |= _json_key_hits(child, wanted, depth + 1)
    return hits


def score_candidate(url: str, resource_type: str, response_json: Any) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    lower = url.lower()

    if resource_type in {"fetch", "xhr"}:
        score += 3
        reasons.append(f"resource_type={resource_type}")

    for term in CANDIDATE_URL_TERMS:
        if term in lower:
            score += 2 if term != "polldapi" else 8
            reasons.append(f"url contains {term}")

    if isinstance(response_json, (dict, list)):
        score += 2
        reasons.append("JSON response")

    wanted = {
        "airBoundGroups",
        "airBounds",
        "availabilityDetails",
        "convertedMiles",
        "prices",
        "quota",
    }
    hits = _json_key_hits(response_json, wanted)
    if hits:
        score += 3 * len(hits)
        reasons.append("award keys: " + ", ".join(sorted(hits)))

    return score, reasons


def _public_exchange(exchange: CapturedExchange) -> dict[str, Any]:
    data = asdict(exchange)
    data["request_headers"] = redact_headers(exchange.request_headers)
    data["response_headers"] = redact_headers(exchange.response_headers)
    if exchange.post_data:
        # Bodies sometimes contain auth/session material. Keep the raw body only in the
        # local raw capture; the public report only records whether a body existed.
        data["post_data"] = "<present; see local raw capture>"
    return data


def _replay_headers(headers: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in headers.items():
        lower = name.lower()
        if lower not in REPLAY_HEADER_ALLOWLIST:
            continue
        if _contains_marker(name, BOT_MARKERS) or _contains_marker(value, BOT_MARKERS):
            continue
        out[lower] = value
    return out


def _safe_session_cookies(cookies: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cookie in cookies:
        name = str(cookie.get("name", ""))
        value = str(cookie.get("value", ""))
        if not name or _contains_marker(name, BOT_MARKERS):
            continue
        out[name] = value
    return out


class NetworkDiscovery:
    def __init__(self, capture_dir: Path, target_substring: str = "polldapi"):
        self.capture_dir = capture_dir
        self.target_substring = target_substring.lower()
        self.exchanges: list[CapturedExchange] = []
        self.target_event = asyncio.Event()
        self.inventory_event = asyncio.Event()
        self.capture_dir.mkdir(parents=True, exist_ok=True)

    async def capture_response(self, response: Response) -> None:
        request = response.request
        url = response.url
        resource_type = request.resource_type

        # Keep discovery focused on actual API traffic.
        if resource_type not in {"fetch", "xhr"} and self.target_substring not in url.lower():
            return

        try:
            response_headers = await response.all_headers()
        except Exception:
            response_headers = dict(response.headers)

        content_type = response_headers.get("content-type", "")
        if "json" not in content_type.lower() and self.target_substring not in url.lower():
            return

        try:
            response_json = await response.json()
        except Exception:
            response_json = None

        try:
            request_headers = await request.all_headers()
        except Exception:
            request_headers = dict(request.headers)

        score, reasons = score_candidate(url, resource_type, response_json)
        sequence = len(self.exchanges) + 1
        exchange = CapturedExchange(
            sequence=sequence,
            observed_at=datetime.now(timezone.utc).isoformat(),
            method=request.method,
            url=url,
            resource_type=resource_type,
            request_headers=request_headers,
            post_data=request.post_data,
            status=response.status,
            response_headers=response_headers,
            response_json=response_json,
            score=score,
            reasons=reasons,
        )
        self.exchanges.append(exchange)

        index = len(self.exchanges)
        raw_path = self.capture_dir / f"exchange-{index:03d}.raw.json"
        public_path = self.capture_dir / f"exchange-{index:03d}.public.json"
        raw_path.write_text(
            json.dumps(asdict(exchange), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        public_path.write_text(
            json.dumps(_public_exchange(exchange), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        if self.target_substring in url.lower():
            self.target_event.set()
        if "airBoundGroups" in _json_key_hits(response_json, {"airBoundGroups"}):
            self.inventory_event.set()

    def best_candidates(self, limit: int = 10) -> list[CapturedExchange]:
        return sorted(self.exchanges, key=lambda item: item.score, reverse=True)[:limit]

    def write_summary(self) -> Path:
        candidates = self.best_candidates()
        path = self.capture_dir / "summary.public.json"
        payload = {
            "captured_exchange_count": len(self.exchanges),
            "target_substring": self.target_substring,
            "candidates": [_public_exchange(item) for item in candidates],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path


def build_aeroplan_results_url(
    origin: str,
    destination: str,
    travel_date: date,
    passengers: int = 1,
) -> str:
    params = {
        "org0": origin.upper(),
        "dest0": destination.upper(),
        "departureDate0": travel_date.isoformat(),
        "ADT": passengers,
        "YTH": 0,
        "CHD": 0,
        "INF": 0,
        "INS": 0,
        "lang": "en-CA",
        "tripType": "O",
        "marketCode": "INT",
    }
    return "https://www.aircanada.com/aeroplan/redeem/availability/outbound?" + urlencode(params)


async def _launch_context(playwright, profile_dir: Path, headless: bool, browser: str) -> BrowserContext:
    launch_args: dict[str, Any] = {
        "user_data_dir": str(profile_dir),
        "headless": headless,
        "viewport": {"width": 1440, "height": 1000},
    }

    if browser == "chrome":
        launch_args["channel"] = "chrome"
        return await playwright.chromium.launch_persistent_context(**launch_args)

    if browser == "chromium":
        return await playwright.chromium.launch_persistent_context(**launch_args)

    # auto: prefer the user's installed Chrome, then fall back to Playwright Chromium.
    try:
        launch_args["channel"] = "chrome"
        return await playwright.chromium.launch_persistent_context(**launch_args)
    except Exception:
        launch_args.pop("channel", None)
        return await playwright.chromium.launch_persistent_context(**launch_args)


async def replay_exchange(
    exchange: CapturedExchange,
    context: BrowserContext,
) -> ReplayResult:
    url_lower = exchange.url.lower()
    if exchange.method.upper() not in {"GET", "POST"}:
        return ReplayResult(False, None, "", None, "", "Only GET/POST discovery calls are replayed.", False)

    if not any(term in url_lower for term in CANDIDATE_URL_TERMS):
        return ReplayResult(False, None, "", None, "", "Request does not look like an award/search API.", False)

    captured_bot_marker = has_bot_marker(exchange.request_headers)
    cookies = _safe_session_cookies(await context.cookies())
    headers = _replay_headers(exchange.request_headers)

    try:
        async with httpx.AsyncClient(
            headers=headers,
            cookies=cookies,
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            response = await client.request(
                exchange.method,
                exchange.url,
                content=exchange.post_data.encode("utf-8") if exchange.post_data else None,
            )

        content_type = response.headers.get("content-type", "")
        response_json: Any | None = None
        if "json" in content_type.lower():
            try:
                response_json = response.json()
            except Exception:
                response_json = None

        preview = response.text[:2000]
        bot_rejected = response.status_code in {401, 403, 429} and (
            captured_bot_marker
            or _contains_marker(preview, BOT_MARKERS)
            or "challenge" in preview.lower()
        )
        return ReplayResult(
            attempted=True,
            status=response.status_code,
            content_type=content_type,
            response_json=response_json,
            response_text_preview=preview,
            error="",
            bot_protection_observed=bot_rejected,
        )
    except Exception as exc:
        return ReplayResult(
            attempted=True,
            status=None,
            content_type="",
            response_json=None,
            response_text_preview="",
            error=str(exc),
            bot_protection_observed=captured_bot_marker,
        )


async def discover_aeroplan_api(
    origin: str,
    destination: str,
    travel_date: date,
    *,
    passengers: int,
    profile_dir: Path,
    capture_dir: Path,
    browser: str = "auto",
    headless: bool = False,
    wait_seconds: int = 180,
    attempt_replay: bool = True,
) -> dict[str, Any]:
    url = build_aeroplan_results_url(origin, destination, travel_date, passengers)
    run_dir = capture_dir / "aeroplan"
    discovery = NetworkDiscovery(run_dir, target_substring="polldapi")
    pending: set[asyncio.Task] = set()

    async with async_playwright() as playwright:
        context = await _launch_context(playwright, profile_dir, headless, browser)
        page = context.pages[0] if context.pages else await context.new_page()

        def on_response(response: Response) -> None:
            task = asyncio.create_task(discovery.capture_response(response))
            pending.add(task)
            task.add_done_callback(pending.discard)

        page.on("response", on_response)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            try:
                await asyncio.wait_for(discovery.target_event.wait(), timeout=wait_seconds)
                if not discovery.inventory_event.is_set():
                    try:
                        await asyncio.wait_for(discovery.inventory_event.wait(), timeout=15)
                    except asyncio.TimeoutError:
                        pass
            except asyncio.TimeoutError:
                pass

            if pending:
                await asyncio.gather(*list(pending), return_exceptions=True)

            summary_path = discovery.write_summary()
            target = next(
                (item for item in discovery.best_candidates() if "polldapi" in item.url.lower()),
                None,
            )

            replay: ReplayResult | None = None
            if target is not None and attempt_replay:
                replay = await replay_exchange(target, context)
                (run_dir / "replay.public.json").write_text(
                    json.dumps(asdict(replay), ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )

            return {
                "search_url": url,
                "capture_dir": str(run_dir),
                "summary_path": str(summary_path),
                "target_found": target is not None,
                "target_method": target.method if target else None,
                "target_url": target.url if target else None,
                "target_status": target.status if target else None,
                "target_score": target.score if target else None,
                "replay": asdict(replay) if replay else None,
            }
        finally:
            page.remove_listener("response", on_response)
            await context.close()
