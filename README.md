# Zillow Unit WebScraper

This tool is designed to help apartment property owners or managers conduct market research around a particular area and speed up analysis so they can answer key questions with very little effort:

* Is the property value of a particular area going up or down?
* How much should I set my rental property price?

The workflow keeps a human in the loop. For people who are looking for continuously scraping massive amounts of market data, this is **NOT** the right tool.

## Purpose & Scope

- **Who:** Property owners/managers, analysts.
- **What:** You provide Zillow complex URLs; the tool scrapes unit info, and helps analyze the data.
- **Why:** Understand (1) market trends around your property and (2) rent pricing.
- **Not:** This software is not intended for scraping massive data automatically with no human involved.

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install # Only once if needed
```

## Input (Apartment Property list)
Create a text file with one Zillow apartment URL per line, followed by a comma and the property's total unit count. Leave the total unit count empty if it is not available.

Example san_jose_properties.txt:

```bash
https://www.zillow.com/apartments/san-jose-ca/ascent/65ZDfy/, 405
https://www.zillow.com/apartments/san-jose-ca/orchard-park-apartments/5hJ233/,
https://www.zillow.com/apartments/san-jose-ca/vio/65fDwQ/, 115
```

## Scrape Zillow Website
This command will automatically launch and connect to a dedicated Chrome browser instance to collect the data.
```bash
python scrape_zillow_units.py --input san_jose_properties.txt
```
The script will open a special Chrome window. The first time you run it, you may need to log in to Zillow. The script will remember your login for all future runs. When the scrape is done, the script will exit, but the Chrome window will remain open. You can close it or leave it for your next run.

Parameters:
- --input: TXT file, one URL per line.
- --headless: "true" to run without a visible Chrome window (this is for scraper's view, not the main Chrome window which will always be visible).

### Scraper Output
The script generates a single JSON file named after your input file with a timestamp.

Example: san_jose_properties_20251014_123000.json

Common fields: property_url, total_property_units, unit_number, layout, sqft, availability, rent, image.

## Analyze Scraper Output
This script helps you analyze the exported JSON file by creating a detailed text report.

Basic usage:

```bash
python analyze_zillow_data.py path/to/your_output_file.json
```
This will generate a .txt file with the same name, containing a full report.

Example with filters:
```bash
# Analyze only 2-bedroom units available "Now"
python analyze_zillow_data.py your_output.json --bed "=2" --date "Now"
```

## Runs the scraper automatically at a specified time each day

```bash
# 1. Install dependencies
pip install schedule --break-system-packages
sudo apt-get install screen  # if on Linux

# 2. Start in screen
screen -S zillow_unit_webscraper
python3 scheduler.py --input san_jose_properties.txt --time "22:30"

# 3. Re-attach to screen
screen -ls
screen -r zillow_unit_webscraper
# Ctrl+A, D to detach

# 3. Auto-restart on boot (optional)
crontab -e
# Add: @reboot sleep 60 && screen -dmS zillow_scraper bash -c "cd /home/stephen/workspace/zillow/Zillow_Unit_WebScraper && /home/stephen/workspace/zillow/Zillow_Unit_WebScraper/venv/bin/python3 scheduler.py --input san_jose_properties.txt --time '22:30'"
```

## Troubleshooting

- “Failed to connect to or launch Chrome”: Ensure google-chrome is installed and in your system's PATH.
- “No unit table detected”: The Chrome window launched by the script may be waiting for you to log in to Zillow or solve a CAPTCHA. Interact with the Chrome window to proceed.

## Developer's Notes
- This tool was developed and tested on Ubuntu 24.04 and python 3.12.3
- This tool was built almost entirely through conversational coding ("vibe coding") in close collaboration with Google's Gemini 2.5 Pro.
- The author uses a diff tool like kdiff3 to compare the generated .txt reports over time. This is an effective way to track rent changes and market trends.
- How to find out the total units of a property in San Jose? Use apartments.com, or the San Jose Permit Portal and search for the property permit: https://portal.sanjoseca.gov/deployed/sfjsp

## License
This tool is provided for free for individual, personal use. Please do not redistribute or use for commercial purposes without permission from the author.

