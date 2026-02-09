#!/usr/bin/env python3
"""
Update Olympics results from Wikipedia (primary) with Claude API fallback.
Fetches medal table and marks completed events.
"""

import html as html_mod
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


# Map schedule event IDs to Wikipedia article URL fragments
EVENT_WIKI_MAP = {
    "alp-m-dh": "Alpine_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_downhill",
    "alp-w-dh": "Alpine_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_downhill",
    "alp-w-sg": "Alpine_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_super-G",
    "alp-w-gs": "Alpine_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_giant_slalom",
    "alp-w-sl": "Alpine_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_slalom",
    "frs-w-slope": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_slopestyle",
    "frs-m-slope": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_slopestyle",
    "frs-w-moguls": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_moguls",
    "frs-m-moguls": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_moguls",
    "frs-w-bigair": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_big_air",
    "frs-m-bigair": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_big_air",
    "frs-w-hp": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_halfpipe",
    "frs-w-aerials": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_aerials",
    "frs-m-aerials": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_aerials",
    "sj-m-nh": "Ski_jumping_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_normal_hill_individual",
    "sb-w-bigair": "Snowboard_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_big_air",
    "sb-w-hp-final": "Snowboard_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_halfpipe",
    "sb-m-hp": "Snowboard_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_halfpipe",
    "ss-m-1000": "Speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_1000_metres",
    "ss-m-500": "Speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_500_metres",
    "ss-w-500": "Speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_500_metres",
    "luge-w-final": "Luge_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_singles",
    "luge-relay": "Luge_at_the_2026_Winter_Olympics_%E2%80%93_Team_relay",
    "fs-m-free": "Figure_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_singles",
    "fs-id-free": "Figure_skating_at_the_2026_Winter_Olympics_%E2%80%93_Ice_dance",
    "fs-w-free": "Figure_skating_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_singles",
    "bob-mono-final": "Bobsleigh_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_monobob",
    "hoc-w-gold": "Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament",
    "hoc-m-gold": "Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament",
}

# Tournament game events — maps event ID to (wiki_slug, opponent country name)
# Used for group-stage / knockout games where we scrape a score, not a gold medalist.
TOURNAMENT_GAME_MAP = {
    "hoc-w-fin": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Finland"),
    "hoc-w-sui": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Switzerland"),
    "hoc-w-can": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Canada"),
    "hoc-m-lat": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament", "Latvia"),
    "hoc-m-den": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament", "Denmark"),
    "curl-md-ita": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "Italy"),
}

# Reverse lookup: country name fragments to 3-letter codes
NAME_TO_CODE = {}
for code, name in COUNTRY_NAMES.items():
    NAME_TO_CODE[name.lower()] = code
    # Also add partial names
    for part in name.lower().split():
        if len(part) > 3:
            NAME_TO_CODE[part] = code
# Add common Wikipedia variants
NAME_TO_CODE.update({
    "swiss": "SUI", "chinese": "CHN", "american": "USA", "japanese": "JPN",
    "norwegian": "NOR", "italian": "ITA", "german": "GER", "french": "FRA",
    "austrian": "AUT", "swedish": "SWE", "canadian": "CAN", "korean": "KOR",
    "czech": "CZE", "slovenian": "SLO", "dutch": "NED", "finnish": "FIN",
    "british": "GBR", "australian": "AUS",
})


def scrape_event_result(event_id):
    """
    Try to scrape the gold medalist from a Wikipedia event page.
    Returns a result string like '🥇 GREMAUD (SUI)' or None.
    
    Uses multiple strategies with strict validation to avoid garbage results.
    """
    wiki_slug = EVENT_WIKI_MAP.get(event_id)
    if not wiki_slug:
        return None

    url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
    html = fetch_url(url)
    if not html:
        return None

    # First check: does the page indicate the event is COMPLETED?
    # If the page says "will be held" but NOT "was held/was won", skip it
    text_only = re.sub(r'<[^>]+>', ' ', html)
    text_only = html_mod.unescape(text_only)
    text_lower = text_only.lower()
    
    # Strong signals the event has NOT happened yet
    future_signals = [
        "will be held",
        "will be started",
        "the event will",
        "will take place",
    ]
    past_signals = [
        "was held",
        "was won",
        "won the competition",
        "won the gold",
        "won the event",
        "claimed gold",
        "took gold",
        "finished first",
        "became the champion",
        "became the olympic champion",
        "won the olympic",
    ]
    
    has_future = any(sig in text_lower for sig in future_signals)
    has_past = any(sig in text_lower for sig in past_signals)
    
    # If page only has future tense and no past tense, event hasn't happened
    if has_future and not has_past:
        print(f"     ⏳ Event not completed yet (future tense detected)")
        return None

    # Strategy 1: Look for medalist infobox pattern
    # Wikipedia uses: {{MedalGold}} or class="gold" or similar
    # The most reliable pattern is the medalists section with gold/silver/bronze rows
    
    winner_name = None
    country_code = None
    
    # Pattern A: "X won the competition" or "X claimed gold"  
    won_patterns = [
        r'([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)+)\s+(?:of\s+)?(\w+)\s+won\s+the\s+competition',
        r'([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)+)\s+(?:of\s+)?(\w+)\s+claimed?\s+(?:the\s+)?(?:olympic\s+)?gold',
        r'([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)+)\s+(?:of\s+)?(\w+)\s+won\s+(?:the\s+)?(?:olympic\s+)?gold',
    ]
    
    for pattern in won_patterns:
        m = re.search(pattern, text_only)
        if m:
            winner_name = m.group(1).strip()
            country_word = m.group(2).strip().lower()
            country_code = NAME_TO_CODE.get(country_word)
            if winner_name and country_code:
                break
    
    # Pattern B: Look for medalist template in HTML
    # Wikipedia often has: <th>Gold</th>...<td>...<a>Name</a>...<a>Country</a>
    if not winner_name:
        # Look for gold medalist in infobox - must have both gold AND silver nearby
        # This prevents matching random "gold" mentions
        gold_section = re.search(
            r'(?:1st\s*place|Gold|gold_medalist|🥇).*?<a[^>]*title="([^"]+)"[^>]*>([^<]+)</a>',
            html, re.DOTALL | re.IGNORECASE
        )
        silver_section = re.search(
            r'(?:2nd\s*place|Silver|silver_medalist|🥈)',
            html, re.IGNORECASE
        )
        
        # Only trust gold match if silver is also present (confirms it's a results section)
        if gold_section and silver_section:
            candidate = gold_section.group(2).strip()
            # Validate: name should be 2+ words, not a country/sport name
            words = candidate.split()
            if len(words) >= 2 and len(candidate) > 4:
                # Check it looks like a person's name (capitalized words)
                if all(w[0].isupper() for w in words if w):
                    winner_name = candidate
                    # Find country code nearby
                    context = html[gold_section.start():gold_section.end()+500]
                    code_match = re.search(r'\(([A-Z]{3})\)', context)
                    if code_match:
                        country_code = code_match.group(1)
    
    # Pattern C: Look for results table with rank column
    if not winner_name:
        # Find a table row with rank "1" and extract the athlete name
        rank1_match = re.search(
            r'<t[dh][^>]*>\s*1\s*</t[dh]>.*?<a[^>]*title="([^"]+)"[^>]*>([^<]+)</a>',
            html, re.DOTALL
        )
        if rank1_match:
            candidate = rank1_match.group(2).strip()
            words = candidate.split()
            if len(words) >= 2 and len(candidate) > 4:
                if all(w[0].isupper() for w in words if w):
                    winner_name = candidate
                    context = html[rank1_match.start():rank1_match.end()+500]
                    code_match = re.search(r'\(([A-Z]{3})\)', context)
                    if code_match:
                        country_code = code_match.group(1)

    if not winner_name:
        return None
    
    # Final validation: result must look like a real name
    # Reject single words, numbers, or very short strings
    surname = winner_name.split()[-1].upper()
    if len(surname) < 2 or surname.isdigit():
        return None
    
    # Reject known garbage patterns
    garbage = ['ROUND', 'FINAL', 'QUALIFICATION', 'TRAINING', 'OFFICIAL', 'SESSION', 
               'MEDAL', 'EVENT', 'COMPETITION', 'OLYMPIC', 'WINTER', 'GAMES']
    if surname in garbage or winner_name.upper() in garbage:
        return None

    if country_code:
        return f"🥇 {surname} ({country_code})"
    else:
        return f"🥇 {surname}"


def scrape_tournament_game_result(event_id):
    """
    Scrape a tournament game result (hockey/curling) from Wikipedia.
    Returns a result string like 'USA wins 5-0' or 'Lost 2-3' or None.
    """
    info = TOURNAMENT_GAME_MAP.get(event_id)
    if not info:
        return None

    wiki_slug, opponent = info
    url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
    html = fetch_url(url)
    if not html:
        return None

    # Strip HTML tags, decode entities (&nbsp; &ndash; etc.), collapse whitespace
    text = re.sub(r'<[^>]+>', ' ', html)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text)

    # Look for score patterns like "United States 5–1 (1–0, 3–1, 1–0) Finland"
    # Wikipedia format: scores are tight around en-dash, followed by optional
    # period breakdown in parentheses before the opponent name.
    score_sep = r'[–\-—]'
    period_scores = r'(?:\s*\([^)]*\))?'
    patterns = [
        # USA listed first: "United States 5–0 (1–0, 3–0, 1–0) Finland"
        (rf'United States\s+(\d+){score_sep}(\d+){period_scores}\s+{opponent}', False),
        # Opponent listed first: "Switzerland 0–5 (0–1, 0–1, 0–3) United States"
        (rf'{opponent}\s+(\d+){score_sep}(\d+){period_scores}\s+United States', True),
    ]

    for pattern, opponent_first in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if opponent_first:
                opp_score = int(match.group(1))
                usa_score = int(match.group(2))
            else:
                usa_score = int(match.group(1))
                opp_score = int(match.group(2))

            if usa_score > opp_score:
                return f"USA wins {usa_score}-{opp_score}"
            elif usa_score < opp_score:
                return f"Lost {usa_score}-{opp_score}"
            else:
                return f"Draw {usa_score}-{opp_score}"

    return None


def update_event_results(data):
    """
    For events marked done but without results, try to scrape Wikipedia.
    Checks medal events (🏅 in title) and tournament games (hockey/curling).
    """
    print("\n🔍 Checking for event results on Wikipedia...")
    for event in data["schedule"]:
        if not event["done"]:
            continue
        if event.get("result"):
            continue

        eid = event["id"]

        # Medal events — scrape for gold medalist
        if "🏅" in event.get("title", "") and eid in EVENT_WIKI_MAP:
            print(f"  📄 Checking {event['title'][:40]}...")
            result = scrape_event_result(eid)
            if result:
                event["result"] = result
                print(f"     → {result}")
            else:
                print(f"     → No result found yet")
            continue

        # Tournament games — scrape for score
        if eid in TOURNAMENT_GAME_MAP:
            print(f"  📄 Checking {event['title'][:40]}...")
            result = scrape_tournament_game_result(eid)
            if result:
                event["result"] = result
                print(f"     → {result}")
            else:
                print(f"     → No result found yet")


def _event_duration_minutes(event):
    """Return expected duration in minutes based on event tags."""
    # Longer-form events need a bigger threshold before being marked done
    LONG_EVENTS = {
        "hockey": 180,    # ~3 hours with intermissions/OT
        "curling": 180,   # ~3 hours per match
        "ceremony": 210,  # opening/closing ceremonies
    }
    for tag in event.get("tags", []):
        if tag in LONG_EVENTS:
            return LONG_EVENTS[tag]
    return 90  # default for most events


def mark_past_events_done(data):
    """
    Mark events as done if their date+time is in the past.
    Uses per-event duration estimates so long events (hockey, curling)
    aren't marked done prematurely.
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

            # Mark as done if enough time has passed for this event type
            duration = _event_duration_minutes(event)
            if now - dt > timedelta(minutes=duration):
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

    # --- Step 2b: Try to fill in results for done medal events ---
    update_event_results(data)

    # --- Step 3: Always update timestamp and save ---
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Data saved to {DATA_FILE}")

    print("✅ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
