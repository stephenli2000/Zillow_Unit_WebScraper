# Zillow Unit WebScraper

This is vibe scraping: simple logs, human-like scrolling/delays, and a workflow that keeps a human in the loop.

## Purpose & Scope

- **Who:** Property owners/analysts.
- **What:** You provide Zillow complex URLs and open Chrome to review them; the tool automatically scrapes unit info and helps analyze the exported JSON/CSV.
- **Why:** Understand (1) market trends around your property and (2) rent pricing.
- **Not:** This software is not intended for scraping massive data automatically with no human involved.

How to find out how many units offered by a property in San Jose?

https://portal.sanjoseca.gov/deployed/sfjsp then search for property permit

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install pandas bs4 playwright
# Only once if needed:
playwright install
```

## Start Chrome (human-in-the-loop)

Keep this Chrome open while scraping (your normal cookies/session apply):

```bash
mkdir -p ~/user_data_chrome
google-chrome --remote-debugging-port=9222 \
  --user-data-dir="$HOME/user_data_chrome" \
  --no-first-run --no-default-browser-check
```

## Input (URLs list)

Create a text file with one Zillow complex URL per line:

https://www.zillow.com/apartments/san-jose-ca/ascent/65ZDfy/, <total number of units>
https://www.zillow.com/apartments/san-jose-ca/vio/65fDwQ/, <total number of units>

## Scrape (record units)
python scrape_zillow_units.py --input san_jose_properties.txt --headless true


--input: TXT file, one URL per line.
--out: Base name; timestamp is appended.
--headless: "true" to run without visible browser; "false" if you want to see Playwright’s window. (Chrome with :9222 must be running.)

## Output

Two files are written with the same base + timestamp:

…YYYYMMDD_HHMMSS.json
…YYYYMMDD_HHMMSS.csv

Common fields: property_url, unit_number, layout, sqft, availability, rent, image.

## Post-processing (parse_json_results.py)

The tool helps to analyze the exported JSON/CSV. Use parse_json_results.py for quick filtering, summaries, and basic price metrics.

Basic usage
```bash
python parse_json_results.py path/to/units_output_YYYYMMDD_HHMMSS.json
```

Typical filters (examples)

```bash
# Show help to see available flags in your version
python parse_json_results.py -h

# Example: filter by beds/baths and show a summary
python parse_json_results.py units.json --beds ">=2" --baths ">=1.5"

# Example: filter by availability text
python parse_json_results.py units.json --date "Now"

# Example: compute simple $/sqft metrics (if supported by your script)
python parse_json_results.py units.json --metrics rent,median,per_sqft
```

If your parse_json_results.py exposes different flags, run -h to view the exact interface. It typically prints filtered tables and basic stats (count, min/median/mean/max, $/sqft if sqft & rent are present).

## Troubleshooting

“No unit table detected”: Ensure the page is visible in your Chrome window and you can access Zillow normally (login if needed).

Keep Chrome with --remote-debugging-port=9222 open while running the scraper.
