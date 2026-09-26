# Capital One Award Hacker — API-first MVP

The goal is to search airline award inventory, normalize it, then calculate the effective Capital One cost and CPP.

The project is now **API-discovery first**. Browser automation is used only to observe a normal airline search and bootstrap session state when necessary. The preferred end state for each airline is a direct HTTP API client, not DOM scraping.

## Current status

Implemented:

- Normalized award-result schema.
- Capital One transfer ratios and effective Capital One-mile cost.
- Bonus-aware effective CPP:
  `CPP = (comparable cash fare - award taxes/fees) / Capital One miles needed * 100`.
- Aeroplan API-discovery harness.
- XHR/fetch capture with raw and sanitized reports.
- Candidate-endpoint scoring.
- Direct `httpx` replay using ordinary session/auth state while deliberately excluding known bot-defense-specific state.
- Legacy experimental Aeroplan DOM scraper kept only as a fallback/reference.
- CSV export aligned with the original Google Sheet MVP.

Current Aeroplan lead:

- A recent open-source implementation reports that Aeroplan award inventory arrives in a JSON response whose URL contains `polldapi`.
- That response can contain structured fields such as `airBoundGroups`, `airBounds`, `availabilityDetails`, `quota`, `prices`, and `convertedMiles`.
- Our discovery command verifies the request on your own session instead of assuming that implementation is still current.

## Install

```fish
git clone https://github.com/kchou0907/award-hacker.git
cd award-hacker

python -m venv .venv
source .venv/bin/activate.fish
pip install -e .
playwright install chromium
```

If Google Chrome is installed, the discovery command prefers it automatically. Otherwise it falls back to Playwright Chromium.

## Reverse-engineer Aeroplan first

Run:

```fish
c1-awards discover-aeroplan \
  --origin SFO \
  --destination TPE \
  --date 2027-01-01
```

What happens:

1. A normal Air Canada/Aeroplan search page opens.
2. If login is required, log in normally in that browser window.
3. The tool records JSON XHR/fetch responses only.
4. It waits for a request/response whose URL contains `polldapi`.
5. It saves the raw exchange locally under `.captures/aeroplan/`.
6. It also writes a sanitized `summary.public.json`.
7. It attempts to replay the candidate request directly with `httpx`.
8. Bot-defense-specific headers/cookies are intentionally not reused. If the direct call requires them, the tool reports that instead of trying to bypass the protection.

Useful options:

```fish
# Force installed Google Chrome
c1-awards discover-aeroplan ... --browser chrome

# Force bundled Playwright Chromium
c1-awards discover-aeroplan ... --browser chromium

# Capture only; do not attempt the HTTP replay
c1-awards discover-aeroplan ... --no-replay

# Give yourself more time to finish a manual login
c1-awards discover-aeroplan ... --wait-seconds 300
```

## What to inspect after a run

```text
.captures/aeroplan/
├── exchange-001.raw.json
├── exchange-001.public.json
├── ...
├── summary.public.json
└── replay.public.json
```

The files ending in `.raw.json` can contain authenticated request headers or other session material. They are intentionally ignored by Git.

The sanitized summary is the useful artifact to inspect or share.

A successful direct replay is the key milestone. If `replay.public.json` shows a 2xx response with the same award JSON, we can replace the Aeroplan browser scraper with a direct API adapter.

## Security / session handling

Do **not** put airline passwords in this repo or send them in chat.

Use the persistent local browser profile:

```text
.browser-profile/
```

Log in normally in the browser window. The following are gitignored:

```text
.browser-profile/
.raw/
.captures/
*.har
cookies.json
session.json
storage-state.json
```

## API-first target architecture

```text
normal browser login/search, only when needed
                 │
                 ▼
       capture XHR/fetch contract
                 │
                 ▼
       direct airline API client
            (httpx)
                 │
                 ▼
       normalized AwardResult
                 │
                 ▼
 Capital One transfer ratio / bonus
                 │
                 ▼
           effective CPP
```

For each airline, the preferred progression is:

1. identify its structured search endpoint;
2. determine request method, parameters/body, headers, cookies and prerequisite calls;
3. replay it outside the browser;
4. minimize the required session state;
5. build a stable JSON parser;
6. keep browser automation only if session/bootstrap remains necessary.

## Legacy Aeroplan DOM scraper

The old command still exists:

```fish
c1-awards aeroplan \
  --origin SFO \
  --destination TPE \
  --date 2027-01-01 \
  --cabin business \
  --out aeroplan.csv
```

It should now be considered a fallback. Do API discovery first.

## Comparable cash fare / CPP

Once award inventory is normalized, CPP is:

```text
(cash fare - award taxes/fees)
----------------------------- × 100
     Capital One miles
```

The cash comparison should match the award itinerary's date, route, cabin and roughly the same routing/conditions.

## Next programs

After Aeroplan's request contract is understood, use the same discovery/replay framework for:

1. EVA Air Infinity MileageLands
2. Cathay Pacific Asia Miles
3. Singapore Airlines KrisFlyer
4. British Airways Club
5. Flying Blue

For Taiwan searches, EVA and Cathay are intentionally prioritized.

## Data contract

Airline adapters should emit at least:

- program
- operating airline / flight
- origin / destination
- depart / arrive
- cabin / stops
- partner award miles
- taxes/fees
- seats
- award source URL
- found-at timestamp

Capital One transfer cost and CPP belong in the normalization/analysis layer, not inside individual airline clients.
