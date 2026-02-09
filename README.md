# 🇺🇸 Team USA Olympics Tracker — Milano Cortina 2026

Auto-updating Winter Olympics viewing guide with medal table, schedule, and Team USA projections.

## How It Works

1. **Every 4 hours**, a GitHub Actions cron job runs `update_results.py`
2. It scrapes the [Wikipedia medal table](https://en.wikipedia.org/wiki/2026_Winter_Olympics_medal_table) for current standings
3. If Wikipedia fails, it falls back to the **Claude API** (Haiku) with web search
4. Past events are auto-marked as completed based on time
5. `build.py` regenerates `index.html` from `data.json` + `template.html`
6. The updated page deploys to **GitHub Pages**

## Setup

### 1. Create the repo

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/olympics-2026.git
git push -u origin main
```

### 2. Add your Anthropic API key (for fallback)

Go to **Settings → Secrets → Actions** and add:
- `ANTHROPIC_API_KEY` — your API key from [console.anthropic.com](https://console.anthropic.com)

This is only used if the Wikipedia scrape fails. Cost is ~$0.03 per fallback call.

### 3. Enable GitHub Pages

Go to **Settings → Pages** and set:
- Source: **Deploy from a branch**
- Branch: **gh-pages** / **(root)**

### 4. Your site is live!

Visit `https://YOUR_USERNAME.github.io/olympics-2026/`

## Manual Updates

You can also manually update results:

```bash
# Edit data.json directly (add results, mark events done)
python build.py  # Rebuild HTML
```

Or trigger the workflow manually from the **Actions** tab.

## File Structure

```
├── data.json            # All structured data (events, medals, athletes)
├── template.html        # HTML template with {{TOKENS}}
├── build.py             # Generates index.html from data + template
├── update_results.py    # Wikipedia scraper + Claude API fallback
├── index.html           # Generated output (don't edit directly)
└── .github/workflows/
    └── update.yml       # Cron job: update → build → deploy
```

## Cost

- **Hosting**: Free (GitHub Pages)
- **Updates**: Free (GitHub Actions — ~100 runs over 16 days)
- **Data**: Free (Wikipedia scrape) / ~$2-3 total (Claude API fallback if needed)

## Disabling After the Olympics

After Feb 22, you can disable the cron by commenting out the schedule in `.github/workflows/update.yml` or deleting the workflow.
