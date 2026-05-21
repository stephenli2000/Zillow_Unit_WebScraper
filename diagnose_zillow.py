import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import subprocess
from pathlib import Path

async def main():
    async with async_playwright() as p:
        print("🔄 Checking for running Chrome instance...")
        browser = None
        for i in range(10): # Try for 10 seconds
            try:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                print("✅ Successfully connected to existing Chrome instance.")
                break
            except Exception:
                if i == 0:
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
            print("❌ Failed to connect to or launch Chrome. Aborting.")
            return

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        
        url = "https://www.zillow.com/apartments/san-jose-ca/the-lex/CkBcqn/"
        print(f"🏢 Visiting {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        print("⏳ Waiting 15 seconds. If Chrome asks you to solve a CAPTCHA (Press & Hold), please do it now!")
        await asyncio.sleep(15)
        
        # Scroll slightly to trigger lazy loading
        print("🖱️ Scrolling to load dynamic content...")
        for _ in range(3):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1.5)
        
        html = await page.content()
        with open("zillow_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("📄 Saved raw HTML to 'zillow_debug.html'")

        soup = BeautifulSoup(html, "html.parser")
        
        print("\n--- Analyzing DOM Structure ---")
        
        # Find any elements containing a dollar sign followed by a number (rent price)
        price_elements = soup.find_all(string=re.compile(r'\$\d[,\d]*'))
        
        if not price_elements:
            print("❌ Could not find any price text. You might be blocked by a CAPTCHA or the page didn't load.")
        else:
            print(f"✅ Found {len(price_elements)} price elements. Analyzing structure of the first match:")
            for idx, el in enumerate(price_elements[:1]):
                print(f"\n--- Match {idx + 1}: '{el.strip()}' ---")
                parent = el.parent
                for i in range(8):
                    if parent and parent.name:
                        class_attr = parent.get('class', [])
                        class_str = ' '.join(class_attr) if isinstance(class_attr, list) else class_attr
                        testid = parent.get('data-testid', parent.get('data-test', ''))
                        
                        print(f"Level +{i+1}: <{parent.name} class='{class_str}' testid='{testid}'>")
                        parent = parent.parent
        
        print("\n=======================================================")
        print("Please reply with the output above so I can fix the scraper!")
        print("=======================================================")
        
        # Leave browser open for you

if __name__ == "__main__":
    asyncio.run(main())