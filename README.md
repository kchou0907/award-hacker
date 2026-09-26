# Capital One Award Hacker — scraper MVP

This is the scraper-side companion to the **Capital One Award Hacker — MVP** Google Sheet.

## What is implemented

- A normalized award-result schema.
- Capital One transfer ratios and effective Capital One-mile cost.
- Bonus-aware effective CPP:
  `CPP = (comparable cash fare - award taxes/fees) / Capital One miles needed * 100`.
- A Playwright browser/session layer with persistent browser state.
- A generic JSON/XHR capture harness that saves structured responses for later reverse-engineering.
- An **experimental Air Canada Aeroplan scraper** adapted from public OSS selector patterns.
- CSV export whose columns line up with the Google Sheet's `Award Results` raw-input columns.

## What is intentionally not claimed

The Aeroplan adapter is **not validated against a live logged-in session in this build environment**.
Airline award sites change frequently, may require login, and may use bot defenses. The scraper therefore:

1. uses a normal visible browser by default;
2. keeps a persistent profile so you can log in normally;
3. saves JSON/XHR responses, HTML, and a screenshot when parsing fails;
4. does not attempt to bypass CAPTCHAs or authentication controls.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

## First Aeroplan run

Use a visible browser so you can sign in if Air Canada asks you to.

```bash
c1-awards aeroplan \
  --origin SFO \
  --destination TPE \
  --date 2027-01-01 \
  --cabin business \
  --profile-dir .browser-profile \
  --raw-dir .raw \
  --out aeroplan.csv
```

If you want CPP immediately, supply a **comparable** cash fare:

```bash
c1-awards aeroplan \
  --origin SFO \
  --destination TPE \
  --date 2027-01-01 \
  --cabin business \
  --cash-price 2500 \
  --cash-source "Google Flights" \
  --cash-url "https://www.google.com/travel/flights" \
  --out aeroplan.csv
```

Do not use an unrelated cash fare just to get a high CPP. The cash itinerary should match date,
route, cabin and roughly the same routing/conditions.

## Transfer bonus

Pass a current Capital One transfer bonus as a decimal. Example: 20%:

```bash
c1-awards aeroplan ... --transfer-bonus 0.20
```

The code uses the program's base transfer ratio and the bonus to calculate Capital One miles needed.

## Debugging a broken scraper

On every Aeroplan search, JSON/XHR responses are captured under `--raw-dir`.
If selectors stop working, inspect those files before changing the DOM parser.

A failed parse also saves:

- `aeroplan-failure.html`
- `aeroplan-failure.png`

The preferred evolution is **structured-response parser first, DOM parser second**.

## Next adapters

The most sensible next programs based on existing OSS reference implementations are:

1. British Airways Club
2. Cathay Pacific Asia Miles
3. Singapore Airlines KrisFlyer

EVA Air is strategically useful for Taiwan, but the inspected references did not already contain a ready adapter,
so it likely needs a fresh network-flow reverse-engineering pass.

## Data contract

Scrapers should emit at least:

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

The cash-fare component should separately emit:

- comparable cash price
- cash source
- cash URL

Capital One transfer cost and CPP belong in the normalization/analysis layer, not inside each airline scraper.
