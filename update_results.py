#!/usr/bin/env python3
"""
Update Olympics results from Wikipedia (primary) with Claude API fallback.
Fetches medal table and marks completed events.
"""

import json
import re
import sys
import os
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from html.parser import HTMLParser


DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
WIKI_MEDAL_URL = "https://en.wikipedia.org/wiki/2026_Winter_Olympics_medal_table"
WIKI_RESULTS_URL = "https://en.wikipedia.org/wiki/2026_Winter_Olympics"

# Country code to flag emoji mapping
FLAG_MAP = {
    "NOR": "🇳🇴", "USA": "🇺🇸", "ITA": "🇮🇹", "JPN": "🇯🇵", "AUT": "🇦🇹",
    "GER": "🇩🇪", "CZE": "🇨🇿", "FRA": "🇫🇷", "SWE": "🇸🇪", "SUI": "🇨🇭",
    "CHE": "🇨🇭", "KOR": "🇰🇷", "SLO": "🇸🇮", "BUL": "🇧🇬", "CAN": "🇨🇦",
    "CHN": "🇨🇳", "NED": "🇳🇱", "FIN": "🇫🇮", "GBR": "🇬🇧", "AUS": "🇦🇺",
    "NZL": "🇳🇿", "ESP": "🇪🇸", "POL": "🇵🇱", "BEL": "🇧🇪", "ROU": "🇷🇴",
    "HUN": "🇭🇺", "CRO": "🇭🇷", "SVK": "🇸🇰", "UKR": "🇺🇦", "BLR": "🇧🇾",
    "KAZ": "🇰🇿", "LAT": "🇱🇻", "EST": "🇪🇪", "LTU": "🇱🇹", "DEN": "🇩🇰",
}

# Full country names for codes
COUNTRY_NAMES = {
    "NOR": "Norway", "USA": "United States", "ITA": "Italy", "JPN": "Japan",
    "AUT": "Austria", "GER": "Germany", "CZE": "Czechia", "FRA": "France",
    "SWE": "Sweden", "SUI": "Switzerland", "CHE": "Switzerland", "KOR": "South Korea",
    "SLO": "Slovenia", "BUL": "Bulgaria", "CAN": "Canada", "CHN": "China",
    "NED": "Netherlands", "FIN": "Finland", "GBR": "Great Britain", "AUS": "Australia",
    "NZL": "New Zealand", "ESP": "Spain", "POL": "Poland", "BEL": "Belgium",
    "ROU": "Romania", "HUN": "Hungary", "CRO": "Croatia", "SVK": "Slovakia",
    "UKR": "Ukraine", "KAZ": "Kazakhstan", "LAT": "Latvia", "EST": "Estonia",
    "LTU": "Lithuania", "DEN": "Denmark",
}


def fetch_url(url):
    """Fetch URL content with a browser-like user agent."""
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; OlympicsTracker/1.0)"
    })
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"  ⚠️  Failed to fetch {url}: {e}")
        return None


def parse_wiki_medal_table(html):
    """
    Parse the Wikipedia medal table page.
    Returns list of dicts with country medal counts.
    """
    if not html:
        return None

    medals = []
    # Find the medal table - look for wikitable with G S B Total columns
    # Wikipedia tables have NOC, Gold, Silver, Bronze, Total
    # We'll use regex to extract table rows

    # Find the main medal table (first wikitable sortable after "Medal table")
    table_match = re.search(
        r'<table[^>]*class="[^"]*wikitable[^"]*sortable[^"]*"[^>]*>(.*?)</table>',
        html, re.DOTALL
    )
    if not table_match:
        print("  ⚠️  Could not find medal table on Wikipedia")
        return None

    table_html = table_match.group(1)

    # Extract rows
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)

    for row in rows:
        # Skip header rows and total row
        if '<th' in row and 'Gold' in row:
            continue
        if 'Totals' in row or 'Total' in row:
            continue

        # Extract cells
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
        if len(cells) < 5:
            continue

        # Try to find country code/name
        # Wikipedia uses format like: <span ...>Norway</span> (NOR) or similar
        country_cell = cells[0] if cells else ""
        # Try to extract 3-letter code
        code_match = re.search(r'\(([A-Z]{3})\)', country_cell)
        if not code_match:
            # Try href-based detection
            code_match = re.search(r'at_the_2026_Winter_Olympics"[^>]*>([A-Z]{3})', country_cell)
        if not code_match:
            # Try just finding a 3-letter code in a link
            code_match = re.search(r'>([A-Z]{3})<', country_cell)

        if not code_match:
            continue

        code = code_match.group(1)

        # Extract numbers - take last 4 numeric cells
        numbers = []
        for cell in cells:
            clean = re.sub(r'<[^>]+>', '', cell).strip()
            if clean.isdigit():
                numbers.append(int(clean))

        if len(numbers) < 4:
            continue

        # Last 4 numbers should be: rank/gold/silver/bronze/total or gold/silver/bronze/total
        gold, silver, bronze, total = numbers[-4], numbers[-3], numbers[-2], numbers[-1]

        medals.append({
            "country": COUNTRY_NAMES.get(code, code),
            "code": code,
            "flag": FLAG_MAP.get(code, "🏳️"),
            "gold": gold,
            "silver": silver,
            "bronze": bronze,
            "total": total,
        })

    if not medals:
        print("  ⚠️  Parsed 0 medal entries from Wikipedia")
        return None

    # Sort by gold, then silver, then bronze
    medals.sort(key=lambda x: (-x["gold"], -x["silver"], -x["bronze"]))

    # Add ranks
    for i, m in enumerate(medals):
        m["rank"] = i + 1

    return medals


def parse_events_completed(html):
    """Try to extract number of completed events from Wikipedia."""
    if not html:
        return None
    match = re.search(r'(\d+)\s*of\s*116\s*events?\s*completed', html, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # Try alternate pattern
    match = re.search(r'Completed events\D*(\d+)', html, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def update_via_claude_api(data):
    """
    Fallback: Use Claude API with web search to get latest results.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ⚠️  No ANTHROPIC_API_KEY set, skipping Claude fallback")
        return None

    print("  🤖 Using Claude API fallback...")

    import json as json_mod
    from urllib.request import urlopen, Request

    prompt = """Search for the current 2026 Winter Olympics medal table and any results from today.

Return ONLY valid JSON with this exact structure (no markdown, no explanation):
{
  "events_completed": <number>,
  "medal_table": [
    {"country": "Norway", "code": "NOR", "gold": 0, "silver": 0, "bronze": 0, "total": 0},
    ...
  ],
  "new_results": [
    {"event_id_hint": "brief description like alpine-womens-slalom", "result": "short result like 🥇 SHIFFRIN GOLD"}
  ]
}

Include ALL countries that have won at least one medal. Sort by gold medals descending."""

    request_body = json_mod.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = Request("https://api.anthropic.com/v1/messages", data=request_body, headers={
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    })

    try:
        with urlopen(req, timeout=30) as resp:
            response = json_mod.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  ⚠️  Claude API request failed: {e}")
        return None

    # Extract text from response content blocks
    text_parts = []
    for block in response.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block["text"])

    full_text = "\n".join(text_parts)

    # Try to extract JSON from the response
    # Strip markdown fences if present
    clean = re.sub(r'```json\s*', '', full_text)
    clean = re.sub(r'```\s*', '', clean)
    clean = clean.strip()

    try:
        result = json_mod.loads(clean)
    except json_mod.JSONDecodeError:
        # Try to find JSON object in the text
        json_match = re.search(r'\{[\s\S]*\}', clean)
        if json_match:
            try:
                result = json_mod.loads(json_match.group())
            except json_mod.JSONDecodeError:
                print("  ⚠️  Could not parse Claude's response as JSON")
                return None
        else:
            print("  ⚠️  No JSON found in Claude's response")
            return None

    # Validate and add flags/ranks
    medal_table = result.get("medal_table", [])
    if medal_table:
        for i, entry in enumerate(medal_table):
            code = entry.get("code", "")
            entry["flag"] = FLAG_MAP.get(code, "🏳️")
            entry["rank"] = i + 1
            if "country" not in entry:
                entry["country"] = COUNTRY_NAMES.get(code, code)

    return result


def mark_past_events_done(data):
    """
    Mark events as done if their date+time is in the past.
    Conservative: only auto-marks if event was >3 hours ago.
    """
    et = timezone(timedelta(hours=-5))  # Eastern Time
    now = datetime.now(et)

    for event in data["schedule"]:
        if event["done"]:
            continue

        date_str = event["date"]
        time_str = event["time"]

        if time_str == "TBD":
            continue

        try:
            # Parse "2026-02-12" and "5:30 AM"
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
            dt = dt.replace(tzinfo=et)

            # Mark as done if event started 3+ hours ago (buffer for long events)
            if now - dt > timedelta(hours=3):
                event["done"] = True
                print(f"  ✅ Auto-marked done: {event['title']}")
        except ValueError:
            continue


def main():
    print("🏅 Olympics Tracker Update")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    # Load current data
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    updated = False

    # --- Step 1: Try Wikipedia scrape ---
    print("📡 Fetching Wikipedia medal table...")
    html = fetch_url(WIKI_MEDAL_URL)
    medals = parse_wiki_medal_table(html)
    events_done = parse_events_completed(html)

    if medals:
        print(f"  ✅ Got {len(medals)} countries from Wikipedia")
        data["medal_table"] = medals
        updated = True

        # Log USA status
        usa = next((m for m in medals if m["code"] == "USA"), None)
        if usa:
            print(f"  🇺🇸 USA: {usa['gold']}G {usa['silver']}S {usa['bronze']}B = {usa['total']} total")
    else:
        print("  ❌ Wikipedia scrape failed. No fallback configured.")
        print("  💡 To add Claude API fallback, set ANTHROPIC_API_KEY env var.")

    if events_done and events_done != data.get("events_completed"):
        data["events_completed"] = events_done
        print(f"  📊 Events completed: {events_done}/116")
        updated = True

    # --- Step 2: Auto-mark past events as done ---
    print("\n⏰ Checking event times...")
    mark_past_events_done(data)

    # --- Step 3: Update timestamp ---
    if updated:
        data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Data saved to {DATA_FILE}")
    else:
        print("\n🔄 No changes detected")

    print("✅ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
