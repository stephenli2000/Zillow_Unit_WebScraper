from bs4 import BeautifulSoup
from collections import Counter
import re

def analyze_html():
    print("📂 Opening zillow_debug.html...")
    try:
        with open('zillow_debug.html', 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        print("❌ zillow_debug.html not found.")
        return

    soup = BeautifulSoup(html, 'html.parser')

    print("\n📊 Most common data-testid attributes (This gives us the new layout names):")
    testids = [el.get('data-testid') for el in soup.find_all(attrs={'data-testid': True})]
    for tid, count in Counter(testids).most_common(15):
        if tid:  # ignore empty ones
            print(f"  {tid}: {count}")

    print("\n🏗️ Looking for actual unit rows...")
    # Search for small containers that have a price AND either "sqft" or an availability date
    for el in soup.find_all(['li', 'div', 'tr', 'button']):
        text = el.get_text(separator=' | ', strip=True)
        has_price = re.search(r'\$\d[,\d]*', text)
        has_sqft_or_avail = re.search(r'sqft|sq ft|available|now', text, re.IGNORECASE)
        
        # We want a small row, not the whole page wrapper
        if has_price and has_sqft_or_avail and 10 < len(text) < 200:
            print("\n🎯 Potential Unit Row Found:")
            print(f"Text: '{text}'")
            class_str = ' '.join(el.get('class', []))
            print(f"Element: <{el.name} class='{class_str}' testid='{el.get('data-testid', '')}'>")
            
            parent = el.parent
            for i in range(4):
                if parent and parent.name != '[document]':
                    pclass_str = ' '.join(parent.get('class', []))
                    print(f"  Parent +{i+1}: <{parent.name} class='{pclass_str}' testid='{parent.get('data-testid', '')}'>")
                    parent = parent.parent
            break

if __name__ == "__main__":
    analyze_html()