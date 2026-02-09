#!/usr/bin/env python3
"""
Build the Olympics schedule HTML from data.json.
Reads structured data, outputs a single self-contained HTML file.
"""

import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "data.json")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "index.html")
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "template.html")


def build():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # Get USA medals
    usa = next((m for m in data["medal_table"] if m["code"] == "USA"), {
        "gold": 0, "silver": 0, "bronze": 0, "total": 0
    })

    proj = data["usa_projection"]
    events_done = data.get("events_completed", 13)
    events_total = data.get("events_total", 116)
    last_updated = data.get("last_updated", "unknown")

    # Format last_updated for display
    try:
        dt = datetime.fromisoformat(last_updated)
        updated_display = dt.strftime("%b %d, %I:%M %p %Z")
    except:
        updated_display = last_updated

    # --- Build schedule JSON for JS ---
    schedule_js = json.dumps(data["schedule"], ensure_ascii=False)
    athletes_js = json.dumps(data["athletes"], ensure_ascii=False)
    medal_table_rows = ""

    for m in data["medal_table"]:
        is_usa = ' class="usa-row"' if m["code"] == "USA" else ""
        medal_table_rows += f"""<tr{is_usa}><td class="rank">{m['rank']}</td><td><span class="flag">{m['flag']}</span><span class="country">{m['country']}</span></td><td class="num gold-num">{m['gold']}</td><td class="num silver-num">{m['silver']}</td><td class="num bronze-num">{m['bronze']}</td><td class="num total-cell">{m['total']}</td></tr>\n"""

    total_medals = sum(m["total"] for m in data["medal_table"])
    countries_count = len(data["medal_table"])

    # Read template and do replacements
    with open(TEMPLATE_FILE, "r") as f:
        html = f.read()

    replacements = {
        "{{USA_GOLD}}": str(usa.get("gold", 0)),
        "{{USA_SILVER}}": str(usa.get("silver", 0)),
        "{{USA_BRONZE}}": str(usa.get("bronze", 0)),
        "{{USA_TOTAL}}": str(usa.get("total", 0)),
        "{{PROJ_GOLD_MID}}": str(proj["projected_gold_mid"]),
        "{{PROJ_TOTAL_MID}}": str(proj["projected_total_mid"]),
        "{{PROJ_GOLD_LOW}}": str(proj["projected_gold_low"]),
        "{{PROJ_GOLD_HIGH}}": str(proj["projected_gold_high"]),
        "{{PROJ_TOTAL_LOW}}": str(proj["projected_total_low"]),
        "{{PROJ_TOTAL_HIGH}}": str(proj["projected_total_high"]),
        "{{EVENTS_DONE}}": str(events_done),
        "{{EVENTS_TOTAL}}": str(events_total),
        "{{MEDAL_TABLE_ROWS}}": medal_table_rows,
        "{{TOTAL_MEDALS}}": str(total_medals),
        "{{COUNTRIES_COUNT}}": str(countries_count),
        "{{SCHEDULE_JSON}}": schedule_js,
        "{{ATHLETES_JSON}}": athletes_js,
        "{{LAST_UPDATED}}": updated_display,
    }

    for key, val in replacements.items():
        html = html.replace(key, val)

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"✅ Built {OUTPUT_FILE}")
    print(f"   USA: {usa.get('gold',0)}G {usa.get('silver',0)}S {usa.get('bronze',0)}B")
    print(f"   Medal table: {countries_count} countries, {total_medals} total medals")
    print(f"   Events: {events_done}/{events_total}")


if __name__ == "__main__":
    build()
