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
def parse_units(html, url):
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

        # Skip non-data rows (e.g., the "Show X more units" row)
        if len(tds) == 1:
            only = norm(tds[0].get_text(" ", strip=True)).lower()
            if "show" in only and "more units" in only:
                continue

        if len(tds) < 4:
            # Not a standard data row
            continue

        # --- Column mapping by position ---
        unit_cell = norm(tds[0].get_text(" ", strip=True))
        sqft_cell = norm(tds[1].get_text(" ", strip=True))
        avail_cell = norm(tds[2].get_text(" ", strip=True))
        rent_cell = norm(tds[3].get_text(" ", strip=True))

        # --- Extract layout from the unit cell, then remove it to reveal unit number ---
        # handles "2 bd, 1 ba", "Studio, 1 ba", "2 bd", "1.5 ba"
        layout_pat = r"(?i)(studio(?:,\s*\d+\.?\d*\s*ba)?|[0-9]+\s*bd\s*,\s*[0-9]+\.?\d*\s*ba|[0-9]+\s*bd|[0-9]+\.?\d*\s*ba)"
        layout_m = re.search(layout_pat, unit_cell)
        layout = norm(layout_m.group(0)) if layout_m else None

        unit_text_wo_layout = unit_cell
        if layout_m:
            # remove only the first occurrence of the matched layout chunk
            start, end = layout_m.span()
            unit_text_wo_layout = (unit_cell[:start] + " " + unit_cell[end:]).strip()

        # strip known tag words left in the unit cell
        unit_text_wo_layout = re.sub(r"(?i)\b(Floor plan|3D tour|Special offer|\d+\s*photos?)\b", " ", unit_text_wo_layout)
        unit_text_wo_layout = norm(unit_text_wo_layout)

        # --- Extract unit number (prefer prefixed IDs like A-244, then pure numbers, then "Plan X") ---
        unit_number = None
        m = re.search(r"\b[A-Z]-?\d{1,4}\b", unit_text_wo_layout)  # A-244, B505, etc.
        if m:
            unit_number = m.group(0)
        else:
            m = re.search(r"(?i)\bPlan\s+[A-Za-z0-9]+\b", unit_text_wo_layout)
            if m:
                unit_number = m.group(0).title()
            else:
                m = re.search(r"\b\d{1,4}\b", unit_text_wo_layout)  # 3, 22, 182, etc.
                if m:
                    unit_number = m.group(0)

        # --- Sqft: prefer the numeric portion from the sqft cell; ignore if it's actually layout text ---
        sqft = None
        if sqft_cell and not re.search(r"(?i)\bbd\b|\bba\b|studio", sqft_cell):
            num = re.search(r"\d[\d,]*", sqft_cell)
            sqft = num.group(0) if num else sqft_cell  # keep raw if no pure number
        else:
            # fallback: try to find a pure number anywhere in the row AFTER we've already taken layout
            # but avoid picking up dates (Nov 1) by requiring 3+ digits
            num = re.search(r"\b\d{3,4}\b", unit_cell)
            sqft = num.group(0) if num else None

        # --- Availability: should look like "Now", "Dec 1", "Nov 12" etc. ---
        availability = avail_cell or None
        # If availability is actually a number (e.g., 788), try to detect a date-like token from unit_cell/rent cell
        if availability and re.fullmatch(r"\d{3,4}", availability):
            # Look for month + day in the row text
            all_text = " ".join([unit_cell, sqft_cell, avail_cell, rent_cell])
            date_m = re.search(r"(?i)\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.? \d{1,2}\b|\bNow\b", all_text)
            if date_m:
                availability = date_m.group(0).replace(".", "")
            else:
                availability = None  # leave unknown rather than wrong

        # --- Rent (keep full string like "$3,509+") ---
        rent = rent_cell or None

        # --- Image (best-effort) ---
        img_el = tds[0].select_one("img") or row.select_one("img")
        image = img_el["src"] if img_el and img_el.has_attr("src") else None

        units.append({
            "property_url": url,
            "unit_number": unit_number,
            "layout": layout,
            "sqft": sqft,
            "availability": availability,
            "rent": rent,
            "image": image,
        })

    return units

# ----------------------------
# Main function
# ----------------------------
async def main(input_file, out_file, headless=True):
    # MODIFIED: Read a text file, extracting only the URL from each line
    urls = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                # Take the first part of the line, delimited by comma or space
                url = line.split(",")[0].split()[0]
                urls.append(url)

    all_units = []

    async with async_playwright() as p:
        user_data_dir = str(Path.home() / "user_data_chrome")
        print(f"Using existing Chrome profile: {user_data_dir}")

        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("✅ Connected to existing Chrome session")

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        for i, url in enumerate(urls):
            html = await scrape_complex(page, url)
            if html:
                units = parse_units(html, url)
                all_units.extend(units)

            if i < len(urls) - 1:
                await human_delay(5, 12)

        print("Closing Playwright session...")
        await context.close()
        await browser.close()

    # Save both JSON and CSV
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_units, f, indent=2, ensure_ascii=False)
    pd.DataFrame(all_units).to_csv(out_file.replace(".json", ".csv"), index=False)

    print(f"\n✅ Scraping completed. {len(all_units)} units saved to {out_file}")


# ----------------------------
# CLI entry point
# ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Text file with one Zillow URL per line")
    parser.add_argument("--headless", type=str, default="true", help="Set 'false' to keep Chrome visible")
    args = parser.parse_args()

    # Generate output file name from input file name
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(args.input)[0]  # Get basename from input
    json_out = f"{base_name}_{ts}.json"

    headless = args.headless.lower() == "true"
    asyncio.run(main(args.input, json_out, headless))
