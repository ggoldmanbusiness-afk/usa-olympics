#!/usr/bin/env python3
"""
Debug script: fetch Wikipedia hockey tournament page with Playwright
and show the text around score entries to diagnose regex patterns.

Usage:
  pip install playwright && playwright install chromium
  python debug_wiki_format.py
"""

import re
import html as html_mod
from playwright.sync_api import sync_playwright

URL = "https://en.wikipedia.org/wiki/Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament"
OPPONENTS = ["Finland", "Switzerland", "Canada"]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        raw_html = page.content()
        browser.close()

    # Same processing as update_results.py
    text = re.sub(r'<[^>]+>', ' ', raw_html)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text)

    print(f"Page length: {len(text)} chars\n")

    # Show all text around "United States" + score-like patterns
    for keyword in ["United States"] + OPPONENTS:
        print(f"=== Occurrences of '{keyword}' ===")
        idx = text.find(keyword)
        count = 0
        while idx != -1 and count < 10:
            snippet = text[max(0, idx - 60):idx + len(keyword) + 60]
            print(f"  [{idx}] ...{snippet}...")
            idx = text.find(keyword, idx + 1)
            count += 1
        print()

    # Try to find any digit-separator-digit pattern near "United States"
    print("=== Score-like patterns near 'United States' ===")
    for m in re.finditer(r'United States', text):
        context = text[max(0, m.start() - 80):m.end() + 80]
        scores = re.findall(r'(\d+)\s*[–\-—:]\s*(\d+)', context)
        if scores:
            print(f"  Context: ...{context}...")
            print(f"  Scores found: {scores}")
            print()

if __name__ == "__main__":
    main()
