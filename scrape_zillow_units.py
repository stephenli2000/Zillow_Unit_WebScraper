import asyncio
import json
import time
import random
import re
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from pathlib import Path
import os
from datetime import datetime
import argparse
import subprocess # NEW: Import subprocess to launch Chrome

# ----------------------------
# Utility: smart, human-like delay
# ----------------------------
async def human_delay(min_sec=3, max_sec=8):
    delay = random.uniform(min_sec, max_sec)
    print(f"⏳ Waiting {delay:.1f}s before next action...")
    await asyncio.sleep(delay)


# ----------------------------
# Page scraping
# ----------------------------
async def scrape_complex(page, url):
    print(f"\n🏢 Scraping units for: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Step 1: initial human-like scroll to load the table
        print("🖱️ Performing initial human scroll...")
        for i in range(5):
            await page.mouse.wheel(0, random.randint(800, 1600))
            await asyncio.sleep(random.uniform(1.0, 2.0))
            if await page.locator("tbody[data-testid='unit-table-body']").count() > 0:
                break

        # Step 2: ensure table is visible
        if await page.locator("tbody[data-testid='unit-table-body']").count() == 0:
            print("⚠️ No unit table detected after scroll.")
            return None
        print("✅ Unit table detected.")

        # Step 3: iterative expansion for "Show more units" or "Load more"
        expanded = 0
        while True:
            show_more_btn = page.locator(
                "tbody[data-testid='unit-table-body'] tr:has-text('Show') >> text=more units"
            )
            load_more_btn = page.locator("button:has-text('Load more')")
            if await show_more_btn.count() == 0 and await load_more_btn.count() == 0:
                break

            try:
                if await show_more_btn.count() > 0:
                    print("🧩 Clicking 'Show more units'...")
                    await show_more_btn.first.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    await show_more_btn.first.click(timeout=5000)
                elif await load_more_btn.count() > 0:
                    print("🧩 Clicking 'Load more'...")
                    await load_more_btn.first.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    await load_more_btn.first.click(timeout=5000)

                expanded += 1
                # Wait for DOM update after each click
                await asyncio.sleep(random.uniform(3.0, 5.0))
            except Exception as e:
                print(f"⚠️ Failed to click expand button: {e}")
                break

        if expanded > 0:
            print(f"✅ Expanded {expanded} 'Show more' section(s).")

        # Step 4: deep scroll to bottom (lazy load safety)
        print("🔽 Scrolling to bottom for lazy-load content...")
        last_height = await page.evaluate("document.body.scrollHeight")
        while True:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(1.5, 2.5))
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Step 5: ensure table fully populated before scraping
        await asyncio.sleep(2)
        html = await page.content()
        print("📄 Page HTML captured successfully.")
        return html

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return None


# ----------------------------
# Parsing the units
# ----------------------------
def parse_units(html, url, total_units):
    from bs4 import BeautifulSoup
    import re

    def norm(s: str) -> str:
        s = re.sub(r"\s+", " ", s or "").strip()
        return s

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select('tbody[data-testid="unit-table-body"] tr')
    units = []

    for row in rows:
        tds = row.find_all("td", recursive=False)

        if len(tds) < 4:
            continue

        unit_cell = norm(tds[0].get_text(" ", strip=True))
        sqft_cell = norm(tds[1].get_text(" ", strip=True))
        avail_cell = norm(tds[2].get_text(" ", strip=True))
        rent_cell = norm(tds[3].get_text(" ", strip=True))
        layout_pat = r"(?i)(studio(?:,\s*\d+\.?\d*\s*ba)?|[0-9]+\s*bd\s*,\s*[0-9]+\.?\d*\s*ba|[0-9]+\s*bd|[0-9]+\.?\d*\s*ba)"
        layout_m = re.search(layout_pat, unit_cell)
        layout = norm(layout_m.group(0)) if layout_m else None
        unit_text_wo_layout = unit_cell
        if layout_m:
            start, end = layout_m.span()
            unit_text_wo_layout = (unit_cell[:start] + " " + unit_cell[end:]).strip()
        unit_text_wo_layout = re.sub(r"(?i)\b(Floor plan|3D tour|Special offer|\d+\s*photos?)\b", " ", unit_text_wo_layout)
        unit_text_wo_layout = norm(unit_text_wo_layout)
        unit_number = None
        patterns_to_try = [
            (re.compile(r"\b[A-Z]-?\d+\b", re.IGNORECASE), lambda m: m.group(0).upper()),
            (re.compile(r"\b\d+-\d+\b"), lambda m: m.group(0)),
            (re.compile(r"(?i)\b(?:Plan|Unit|Apt|#|Model)\s*[A-Za-z0-9\s\-]+"), lambda m: m.group(0).strip()),
            (re.compile(r"\b(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z0-9]{2,8}\b"), lambda m: m.group(0).upper()),
            (re.compile(r"\b\d{2,8}\b"), lambda m: m.group(0)),
        ]
        for pattern, extractor in patterns_to_try:
            match = pattern.search(unit_text_wo_layout)
            if match:
                unit_number = extractor(match)
                break
        if not unit_number and unit_text_wo_layout:
            unit_number = unit_text_wo_layout
        sqft = None
        if sqft_cell and not re.search(r"(?i)\bbd\b|\bba\b|studio", sqft_cell):
            num = re.search(r"\d[\d,]*", sqft_cell)
            sqft = num.group(0) if num else sqft_cell
        else:
            num = re.search(r"\b\d{3,4}\b", unit_cell)
            sqft = num.group(0) if num else None
        availability = avail_cell or None
        if availability and re.fullmatch(r"\d{3,4}", availability):
            all_text = " ".join([unit_cell, sqft_cell, avail_cell, rent_cell])
            date_m = re.search(r"(?i)\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.? \d{1,2}\b|\bNow\b", all_text)
            availability = date_m.group(0).replace(".", "") if date_m else None
        rent = rent_cell or None
        img_el = tds[0].select_one("img") or row.select_one("img")
        image = img_el["src"] if img_el and img_el.has_attr("src") else None
        units.append({
            "property_url": url, "total_property_units": total_units,
            "unit_number": unit_number, "layout": layout, "sqft": sqft,
            "availability": availability, "rent": rent, "image": image,
        })
    return units

# ----------------------------
# Main function
# ----------------------------
async def main(input_file, out_file, headless=True):
    properties_to_scrape = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = [p.strip() for p in line.split(',')]
            url = parts[0]
            total_units = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            properties_to_scrape.append({'url': url, 'total_units': total_units})

    all_units = []

    async with async_playwright() as p:
        browser = None
        # NEW: Robustly connect to or launch Chrome
        print("🔄 Checking for running Chrome instance...")
        for i in range(10): # Try for 10 seconds
            try:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                print("✅ Successfully connected to existing Chrome instance.")
                break
            except Exception:
                if i == 0: # Only try to launch on the first attempt
                    print("⚠️ No running instance found. Launching Chrome...")
                    data_dir = Path.home() / "zillow_data_chrome"
                    command = [
                        'google-chrome',
                        '--remote-debugging-port=9222',
                        f'--user-data-dir={data_dir}',
                        '--no-first-run',
                        '--no-default-browser-check'
                    ]
                    subprocess.Popen(command)
                await asyncio.sleep(1)
        
        if not browser:
            print("❌ Failed to connect to or launch Chrome after 10 seconds. Aborting.")
            return

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        for i, prop_data in enumerate(properties_to_scrape):
            html = await scrape_complex(page, prop_data['url'])
            if html:
                units = parse_units(html, prop_data['url'], prop_data['total_units'])
                all_units.extend(units)
            if i < len(properties_to_scrape) - 1:
                await human_delay(5, 12)

        # We don't close the browser, just the context if we created a new one
        # This leaves the browser window open for the user
        if not browser.contexts:
            await context.close()
        
        # We also don't close the connection
        # await browser.close() 

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_units, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Scraping completed. {len(all_units)} units saved to {out_file}")


# ----------------------------
# CLI entry point
# ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Text file with one Zillow URL per line")
    parser.add_argument("--headless", type=str, default="true", help="Set 'false' to keep Playwright visible")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(args.input)[0]
    json_out = f"{base_name}_{ts}.json"

    headless = args.headless.lower() == "true"
    asyncio.run(main(args.input, json_out, headless))