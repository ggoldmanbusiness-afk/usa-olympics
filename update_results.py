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

    # Reverse lookup: country name -> IOC code
    _name_to_code = {}
    for code, name in COUNTRY_NAMES.items():
        _name_to_code[name.lower()] = code
    # Wikipedia variants that differ from COUNTRY_NAMES
    _name_to_code["czech republic"] = "CZE"
    _name_to_code["republic of korea"] = "KOR"
    _name_to_code["people's republic of china"] = "CHN"
    _name_to_code["great britain"] = "GBR"
    _name_to_code["roc"] = "ROC"

    medals = []

    # Find the first wikitable (may or may not have "sortable")
    table_match = re.search(
        r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
        html, re.DOTALL
    )
    if not table_match:
        print("  ⚠️  Could not find medal table on Wikipedia")
        return None

    table_html = table_match.group(1)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)

    for row in rows:
        # Skip header rows and total/footer rows
        if 'Totals' in row or 'Total' in row:
            continue

        # Extract all cells (both <th> and <td>)
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
        if len(cells) < 5:
            continue

        # Find the country name — look in the cell that contains a link
        # to "X_at_the_2026_Winter_Olympics"
        country_name = None
        code = None
        for cell in cells:
            link_match = re.search(
                r'at_the_2026_Winter_Olympics[^"]*"[^>]*>([^<]+)', cell
            )
            if link_match:
                country_name = link_match.group(1).strip().rstrip('*')
                break

        if not country_name:
            # Fallback: strip HTML from each cell, find one that looks like a name
            for cell in cells:
                clean = html_mod.unescape(re.sub(r'<[^>]+>', '', cell)).strip().rstrip('*')
                if clean and not clean.isdigit() and len(clean) > 2:
                    country_name = clean
                    break

        if not country_name:
            continue

        # Resolve country name to IOC code
        code = _name_to_code.get(country_name.lower())
        if not code:
            # Try partial match
            for name_key, name_code in _name_to_code.items():
                if name_key in country_name.lower() or country_name.lower() in name_key:
                    code = name_code
                    break
        if not code:
            print(f"  ⚠️  Unknown country: {country_name}")
            continue

        # Extract medal numbers — last 4 digits in the row
        numbers = []
        for cell in cells:
            clean = re.sub(r'<[^>]+>', '', cell).strip()
            if clean.isdigit():
                numbers.append(int(clean))

        if len(numbers) < 4:
            continue

        gold, silver, bronze, total = numbers[-4], numbers[-3], numbers[-2], numbers[-1]

        medals.append({
            "country": COUNTRY_NAMES.get(code, country_name),
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
    """
    Extract number of completed events from Wikipedia medal table.
    Uses total gold medals awarded as proxy (1 gold per event, with rare ties).
    """
    if not html:
        return None

    # Find the wikitable
    table_match = re.search(
        r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
        html, re.DOTALL
    )
    if not table_match:
        return None

    # Find the Totals row
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_match.group(1), re.DOTALL)
    for row in rows:
        if 'Totals' not in row and 'Total' not in row:
            continue
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, re.DOTALL)
        numbers = [int(re.sub(r'<[^>]+>', '', c).strip())
                   for c in cells if re.sub(r'<[^>]+>', '', c).strip().isdigit()]
        if numbers:
            # First number is total golds = approximate events completed
            return numbers[0]

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
    "sb-w-bigair": "Snowboarding_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_big_air",
    "sb-w-hp-final": "Snowboarding_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_halfpipe",
    "sb-m-hp": "Snowboarding_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_halfpipe",
    "ss-m-1000": "Speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_1000_metres",
    "ss-m-500": "Speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_500_metres",
    "ss-w-500": "Speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_500_metres",
    "luge-w-final": "Luge_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_singles",
    "luge-relay": "Luge_at_the_2026_Winter_Olympics_%E2%80%93_Team_relay",
    "fs-m-free": "Figure_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_singles",
    "fs-id-free": "Figure_skating_at_the_2026_Winter_Olympics_%E2%80%93_Ice_dance",
    "fs-w-free": "Figure_skating_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_singles",
    "bob-mono-final": "Bobsleigh_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_monobob",
    "st-mixed-relay": "Short-track_speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_2000_metre_relay",
    # Snowboard cross
    "sbx-m": "Snowboarding_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_snowboard_cross",
    "sbx-w": "Snowboarding_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_snowboard_cross",
    "sbx-mixed": "Snowboarding_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_team_snowboard_cross",
    # Short track (individual/relay)
    "st-500-1000": "Short-track_speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_500_metres",
    "st-m-1500": "Short-track_speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_1500_metres",
    "st-w-1000": "Short-track_speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_1000_metres",
    "st-relay-500": "Short-track_speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_3000_metre_relay",
    "st-m-5000relay": "Short-track_speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_5000_metre_relay",
    # Freestyle (new events)
    "frs-w-dualmog": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_dual_moguls",
    "frs-m-dualmog": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_dual_moguls",
    "frs-m-skicross": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_ski_cross",
    "frs-mixed-aerials": "Freestyle_skiing_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_team_aerials",
    # Biathlon
    "bia-w-pursuit": "Biathlon_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_pursuit",
    "bia-m-mass": "Biathlon_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_mass_start",
    "bia-w-mass": "Biathlon_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_mass_start",
    # Skeleton
    "skel-mixed": "Skeleton_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_team",
    # Bobsled
    "bob-2man": "Bobsleigh_at_the_2026_Winter_Olympics_%E2%80%93_Two-man",
    # Speed skating
    "ss-mass": "Speed_skating_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_mass_start",
}

# Tournament game events — maps event ID to (wiki_slug, opponent country name)
# Used for group-stage / knockout games where we scrape a score, not a gold medalist.
TOURNAMENT_GAME_MAP = {
    # Women's hockey - group stage
    "hoc-w-fin": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Finland"),
    "hoc-w-sui": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Switzerland"),
    "hoc-w-can": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Canada"),
    "hoc-w-cze": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Czechia"),
    # Men's hockey - group stage
    "hoc-m-lat": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament", "Latvia"),
    "hoc-m-den": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament", "Denmark"),
    "hoc-m-fin": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament", "Finland"),
    "hoc-m-swe": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament", "Sweden"),
    # Curling - mixed doubles
    "curl-md-ita": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "Italy"),
    "curl-md-nor": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "Norway"),
    "curl-md-swe": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "Sweden"),
    "curl-md-can": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "Canada"),
    "curl-md-chn": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "China"),
    "curl-md-kor": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "South Korea"),
    "curl-md-gbr": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "Great Britain"),
    "curl-md-gold": ("Curling_at_the_2026_Winter_Olympics_%E2%80%93_Mixed_doubles_tournament", "Sweden"),
    # Hockey gold medal games — opponents TBD until semifinals
    "hoc-w-gold": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Women%27s_tournament", "Canada"),
    "hoc-m-gold": ("Ice_hockey_at_the_2026_Winter_Olympics_%E2%80%93_Men%27s_tournament", "Canada"),
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
    "the united states": "USA", "united states": "USA",
    "switzerland": "SUI",
})


def _extract_recap(page_html, winner_name=None, country_code=None):
    """
    Extract a short recap from the Wikipedia article's lead paragraph.
    Returns a concise 1-line description or None.
    """
    if not page_html:
        return None

    # Strip style/script tags, then find <p> tags
    clean = re.sub(r'<style[^>]*>.*?</style>', '', page_html, flags=re.DOTALL)
    clean = re.sub(r'<script[^>]*>.*?</script>', '', clean, flags=re.DOTALL)
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', clean, re.DOTALL)

    for p_html in paragraphs[:5]:
        text = html_mod.unescape(re.sub(r'<[^>]+>', '', p_html)).strip()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\[\d+\]', '', text)  # remove citation refs like [1]
        if len(text) < 40:
            continue

        # Look for a sentence with a result keyword
        sentences = re.split(r'(?<=\.)\s+', text)
        for s in sentences:
            s_lower = s.lower()
            if any(kw in s_lower for kw in ['won', 'claimed', 'took', 'earned',
                                              'captured', 'defeated', 'clinched']):
                # Trim to first clause about the winner — cut at first comma
                # after the main subject to avoid listing all medalists
                comma_idx = s.find(',')
                if comma_idx > 20 and comma_idx < 70:
                    s = s[:comma_idx] + '.'
                elif len(s) > 70:
                    s = s[:67].rsplit(' ', 1)[0] + '...'
                return s

    return None


def scrape_event_result(event_id):
    """
    Try to scrape the gold medalist from a Wikipedia event page.
    Returns (result, recap) tuple. Result like '🥇 GREMAUD (SUI)', recap is a short description.
    Either or both may be None.
    """
    wiki_slug = EVENT_WIKI_MAP.get(event_id)
    if not wiki_slug:
        return None, None

    url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
    html = fetch_url(url)
    if not html:
        return None, None

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
        return None, None

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
        return None, _extract_recap(html)

    # Final validation: result must look like a real name
    # Reject single words, numbers, or very short strings
    surname = winner_name.split()[-1].upper()
    if len(surname) < 2 or surname.isdigit():
        return None, None

    # Reject known garbage patterns
    garbage = ['ROUND', 'FINAL', 'QUALIFICATION', 'TRAINING', 'OFFICIAL', 'SESSION',
               'MEDAL', 'EVENT', 'COMPETITION', 'OLYMPIC', 'WINTER', 'GAMES']
    if surname in garbage or winner_name.upper() in garbage:
        return None, None

    recap = _extract_recap(html, winner_name, country_code)

    # Fallback: if no country code yet, look for "Name of Country" in lead paragraph
    if not country_code:
        text_clean = re.sub(r'\s+', ' ', text_only)
        # Pattern: "Surname of [the] Country" — try known country names
        of_match = re.search(
            rf'{re.escape(surname)}\s+of\s+(the\s+)?(\w+(?:\s+\w+)?(?:\s+\w+)?)',
            text_clean, re.IGNORECASE
        )
        if of_match:
            raw = ((of_match.group(1) or '') + of_match.group(2)).strip().lower()
            # Try progressively shorter fragments
            words = raw.split()
            for n in range(len(words), 0, -1):
                candidate = ' '.join(words[:n])
                country_code = NAME_TO_CODE.get(candidate)
                if country_code:
                    break
        # Also try: "Country, with Name" (team events)
        if not country_code:
            team_match = re.search(
                rf'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+with\s+.*?{re.escape(surname)}',
                text_clean, re.IGNORECASE
            )
            if team_match:
                country_word = team_match.group(1).strip().lower()
                country_code = NAME_TO_CODE.get(country_word) or NAME_TO_CODE.get(country_word.split()[0])

    if country_code:
        return f"🥇 {surname} ({country_code})", recap
    else:
        return f"🥇 {surname}", recap


def scrape_tournament_game_result(event_id):
    """
    Scrape a tournament game result (hockey/curling) from Wikipedia.
    Returns (result, recap) tuple. Result like 'USA wins 5-0'.
    """
    info = TOURNAMENT_GAME_MAP.get(event_id)
    if not info:
        return None, None

    wiki_slug, opponent = info
    url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
    html = fetch_url(url)
    if not html:
        return None, None

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
                result = f"USA wins {usa_score}-{opp_score}"
                recap = f"USA dominated {opponent} {usa_score}-{opp_score}."
            elif usa_score < opp_score:
                result = f"Lost {usa_score}-{opp_score}"
                recap = f"Fell to {opponent} {usa_score}-{opp_score}."
            else:
                result = f"Draw {usa_score}-{opp_score}"
                recap = f"Drew {opponent} {usa_score}-{opp_score}."
            return result, recap

    # Fallback: curling table format — end-by-end scores then final total
    # Scope to gold/final section to avoid matching earlier round-robin games
    gold_section = text
    for marker in ['Gold medal game', 'Gold_medal_game', 'Final ']:
        idx = text.lower().rfind(marker.lower())
        if idx != -1:
            gold_section = text[idx:]
            break

    table_patterns = [
        # Opponent row then USA row — grab last number before "United States"
        (rf'{opponent}\s*\([^)]*\)(?:\s+\d+)*\s+(\d+)\s+United States\s*\([^)]*\)(?:\s+\d+)*\s+(\d+)', True),
        # USA row then opponent row
        (rf'United States\s*\([^)]*\)(?:\s+\d+)*\s+(\d+)\s+{opponent}\s*\([^)]*\)(?:\s+\d+)*\s+(\d+)', False),
    ]

    for pattern, opponent_first in table_patterns:
        match = re.search(pattern, gold_section, re.IGNORECASE)
        if match:
            if opponent_first:
                opp_score = int(match.group(1))
                usa_score = int(match.group(2))
            else:
                usa_score = int(match.group(1))
                opp_score = int(match.group(2))

            if usa_score > opp_score:
                result = f"USA wins {usa_score}-{opp_score}"
                recap = f"USA beat {opponent} {usa_score}-{opp_score}."
            elif usa_score < opp_score:
                result = f"Lost {usa_score}-{opp_score}"
                recap = f"Fell to {opponent} {usa_score}-{opp_score}."
            else:
                result = f"Draw {usa_score}-{opp_score}"
                recap = f"Drew {opponent} {usa_score}-{opp_score}."
            return result, recap

    return None, None


def update_event_results(data):
    """
    For events marked done but without results, try to scrape Wikipedia.
    Checks medal events (🏅 in title) and tournament games (hockey/curling).
    Also updates the event description with a short recap when available.
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
            result, recap = scrape_event_result(eid)
            if result:
                event["result"] = result
                print(f"     → {result}")
                if recap:
                    event["desc"] = recap
                    print(f"     📝 {recap}")
            else:
                print(f"     → No result found yet")
            continue

        # Tournament games — scrape for score
        if eid in TOURNAMENT_GAME_MAP:
            print(f"  📄 Checking {event['title'][:40]}...")
            result, recap = scrape_tournament_game_result(eid)
            if result:
                event["result"] = result
                print(f"     → {result}")
                if recap:
                    event["desc"] = recap
                    print(f"     📝 {recap}")
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


YAHOO_SCHEDULE_URL = "https://sports.yahoo.com/olympics/article/2026-winter-olympics-milan-cortina-daily-schedule-streaming-tv-times-193334165.html"

# Map our event ID prefixes to Yahoo sport header keywords
SPORT_KEYWORDS = {
    "alp": ["alpine skiing"],
    "frs": ["freestyle skiing"],
    "fs": ["figure skating"],
    "hoc": ["hockey"],
    "ss": ["speed skating"],
    "st": ["short track"],
    "sb": ["snowboarding"],
    "sj": ["ski jumping"],
    "luge": ["luge"],
    "bob": ["bobsled"],
    "skel": ["skeleton"],
    "biat": ["biathlon"],
    "xc": ["cross-country"],
    "nc": ["nordic combined"],
    "curl": ["curling"],
    "skimo": ["ski mountaineering"],
    "open": ["opening ceremony"],
    "close": ["closing ceremony"],
}

# Map our event ID fragments to Yahoo event text keywords for matching
EVENT_KEYWORDS = {
    "m-dh": ["men's downhill"],
    "w-dh": ["women's downhill"],
    "w-sg": ["women's super-g"],
    "w-gs": ["women's giant slalom"],
    "w-sl": ["women's slalom"],
    "m-moguls": ["men's moguls"],
    "w-moguls": ["women's moguls"],
    "w-slope": ["women's slopestyle"],
    "m-slope": ["men's slopestyle"],
    "w-bigair": ["women's big air"],
    "m-bigair": ["men's big air"],
    "w-hp": ["women's halfpipe"],
    "m-hp": ["men's halfpipe"],
    "w-aerials": ["women's aerials"],
    "m-aerials": ["men's aerials"],
    "m-nh": ["normal hill", "men's"],
    "mixed-relay": ["mixed relay", "mixed team"],
    "relay": ["relay"],
    "m-1000": ["1000", "men's"],
    "m-500": ["500", "men's"],
    "w-500": ["500", "women's"],
    "w-final": ["women's final"],
    "m-free": ["men's free"],
    "w-free": ["women's free"],
    "id-free": ["ice dance"],
    "mono": ["monobob"],
    "gold": ["gold-medal", "gold medal"],
}

# Subsection keywords extracted from event IDs for disambiguation within a sport
# Maps event ID fragments to Yahoo subsection headers (e.g., "Halfpipe", "Aerials")
SUBSECTION_KEYWORDS = {
    "hp": ["halfpipe"],
    "aerials": ["aerials"],
    "moguls": ["moguls"],
    "slope": ["slopestyle"],
    "bigair": ["big air"],
    "dh": ["downhill"],
    "sg": ["super-g"],
    "gs": ["giant slalom"],
    "sl": ["slalom"],
}


def scrape_schedule_times(data):
    """
    Scrape Yahoo Sports schedule page to sync event times.
    Only updates future (not done) events where a match is found.
    """
    print("\n📅 Checking schedule times from Yahoo Sports...")
    html = fetch_url(YAHOO_SCHEDULE_URL)
    if not html:
        print("  ⚠️  Could not fetch Yahoo schedule")
        return

    # Parse into text lines
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'</(p|h[1-6]|div|li)>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html_mod.unescape(text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Build a structured schedule: {date_str: [(time, sport, description), ...]}
    MONTH_MAP = {"Feb.": "02", "February": "02", "Mar.": "03"}
    yahoo_schedule = {}
    current_date = None
    current_sport = None
    current_subsection = None

    for line in lines:
        # Day header: "Tuesday, Feb. 10, 2026 (Day 4)"
        day_match = re.match(
            r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
            r'(Feb\.?|February|Mar\.?)\s+(\d+),?\s+2026',
            line
        )
        if day_match:
            month = MONTH_MAP.get(day_match.group(1), "02")
            day = day_match.group(2).zfill(2)
            current_date = f"2026-{month}-{day}"
            current_sport = None
            current_subsection = None
            continue

        if not current_date:
            continue

        # Sport header: a line that's just a sport name (no time)
        if not re.search(r'\d{1,2}:\d{2}', line) and len(line) < 40:
            sport_lower = line.lower().strip()
            if any(kw in sport_lower for kws in SPORT_KEYWORDS.values() for kw in kws):
                current_sport = sport_lower
                current_subsection = None
                continue
            # Subsection header within a sport (e.g., "Halfpipe", "Aerials", "Giant slalom")
            if current_sport:
                for sub_kws in SUBSECTION_KEYWORDS.values():
                    if any(kw in sport_lower for kw in sub_kws):
                        current_subsection = sport_lower
                        break
                continue

        # Skip delayed rebroadcast lines: "airs at 4:30 p.m. on USA"
        if re.search(r'airs at \d', line, re.IGNORECASE):
            continue

        # Time line: "4:30 a.m.: Women's qualifying..."
        time_match = re.match(r'(\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.))\s*:?\s*(.*)', line)
        if time_match and current_sport:
            raw_time = time_match.group(1)
            desc = time_match.group(2).strip()
            # Normalize time: "4:30 a.m." → "4:30 AM"
            norm_time = raw_time.replace('a.m.', 'AM').replace('p.m.', 'PM')
            norm_time = re.sub(r'\s+', ' ', norm_time).strip()

            if current_date not in yahoo_schedule:
                yahoo_schedule[current_date] = []
            yahoo_schedule[current_date].append((norm_time, current_sport, desc.lower(), current_subsection))

    if not yahoo_schedule:
        print("  ⚠️  Could not parse any schedule data")
        return

    print(f"  ✅ Parsed schedule for {len(yahoo_schedule)} days")

    # Now match our events to Yahoo entries
    changes = 0
    for event in data["schedule"]:
        if event["done"]:
            continue
        if event["time"] == "TBD":
            continue

        eid = event["id"]
        edate = event["date"]

        if edate not in yahoo_schedule:
            continue

        # Determine sport from event ID prefix
        prefix = eid.split("-")[0]
        sport_kws = SPORT_KEYWORDS.get(prefix, [])

        # Find matching Yahoo entries for this date + sport
        candidates = []
        for ytime, ysport, ydesc, ysubsection in yahoo_schedule[edate]:
            if any(kw in ysport for kw in sport_kws):
                candidates.append((ytime, ydesc, ysubsection))

        if not candidates:
            continue

        # Filter candidates by subsection if the event ID maps to one
        # e.g., frs-w-hp should only match entries under a "Halfpipe" subsection
        eid_parts = eid.split("-")
        event_subsection_kws = None
        for part in eid_parts:
            if part in SUBSECTION_KEYWORDS:
                event_subsection_kws = SUBSECTION_KEYWORDS[part]
                break

        if event_subsection_kws:
            subsection_filtered = [
                (ytime, ydesc, ysub) for ytime, ydesc, ysub in candidates
                if ysub and any(kw in ysub for kw in event_subsection_kws)
            ]
            # If we expected a specific subsection but found none, skip — don't
            # fall back to unfiltered candidates (that causes cross-subsection matches)
            if subsection_filtered:
                candidates = subsection_filtered
            else:
                continue

        # If only one candidate for this sport on this date, use it
        matched_time = None
        if len(candidates) == 1:
            matched_time = candidates[0][0]
        else:
            # Try to match by event keywords
            for suffix, kws in EVENT_KEYWORDS.items():
                if suffix in eid:
                    for ytime, ydesc, _ysub in candidates:
                        if any(kw in ydesc for kw in kws):
                            matched_time = ytime
                            break
                    if matched_time:
                        break

        if matched_time and matched_time != event["time"]:
            print(f"  ⏰ {event['title'][:40]}: {event['time']} → {matched_time}")
            event["time"] = matched_time
            changes += 1

    if changes:
        print(f"  📅 Updated {changes} event time(s)")
    else:
        print("  ✅ All times match")


def update_projections(data):
    """
    Dynamically update USA medal projections based on current pace.
    Uses medals won so far and events remaining to project final totals.
    """
    events_done = data.get("events_completed", 0)
    events_total = data.get("events_total", 116)
    if events_done < 1:
        return

    usa = next((m for m in data.get("medal_table", []) if m["code"] == "USA"), None)
    if not usa:
        return

    gold_now = usa["gold"]
    total_now = usa["total"]
    pct_done = events_done / events_total

    # Project based on current pace, with slight regression toward pre-Games
    # expectations (10G, 30T) to handle early variance
    pre_gold = 10
    pre_total = 30
    # Weight current pace more as Games progress
    pace_weight = min(pct_done * 1.5, 0.9)  # caps at 90% pace weight

    pace_gold = gold_now / pct_done if pct_done > 0 else pre_gold
    pace_total = total_now / pct_done if pct_done > 0 else pre_total

    proj_gold = round(pace_weight * pace_gold + (1 - pace_weight) * pre_gold)
    proj_total = round(pace_weight * pace_total + (1 - pace_weight) * pre_total)

    # Projections can't be less than what's already won
    proj_gold = max(proj_gold, gold_now)
    proj_total = max(proj_total, total_now)

    # Range: ±20% of mid projection, floored at current count
    gold_low = max(round(proj_gold * 0.8), gold_now)
    gold_high = round(proj_gold * 1.2)
    total_low = max(round(proj_total * 0.8), total_now)
    total_high = round(proj_total * 1.2)

    data["usa_projection"] = {
        "projected_gold_low": gold_low,
        "projected_gold_high": gold_high,
        "projected_gold_mid": proj_gold,
        "projected_total_low": total_low,
        "projected_total_high": total_high,
        "projected_total_mid": proj_total,
    }
    print(f"\n📈 Updated projections: {proj_gold}G ({gold_low}-{gold_high}), {proj_total}T ({total_low}-{total_high})")


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

    # --- Step 2c: Sync schedule times from Yahoo ---
    scrape_schedule_times(data)

    # --- Step 2d: Update projections based on pace ---
    update_projections(data)

    # --- Step 3: Always update timestamp and save ---
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Data saved to {DATA_FILE}")

    print("✅ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
