# 🔬 Parkville Biomedical Seminars

A live, auto-updating page that aggregates research seminars from all major institutions in **Melbourne's Parkville Biomedical Precinct** — in one place.

**Institutions covered:**
WEHI · Doherty Institute · Peter MacCallum · MCRI · Bio21 Institute · Florey Institute · Orygen · Melbourne Bioinformatics · Melbourne Brain Centre · Royal Melbourne Hospital · CERA · Bionics Institute

---

## How It Works

```
GitHub Actions (daily cron, 7:00 AM Melbourne time)
    ↓
Python scrapers visit each institution's events page
    ↓
seminars.json is updated and committed to the repo
    ↓
GitHub Pages serves index.html, which reads seminars.json
    ↓
Your browser shows a filtered, searchable live page
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium --with-deps
```

### 2. Run scrapers locally
```bash
# Run all scrapers
python run_scrapers.py

# Run specific institutions only
python run_scrapers.py --institutions wehi,doherty,peter_mac

# Preview output without writing file
python run_scrapers.py --dry-run

# Include past events
python run_scrapers.py --keep-past
```

### 3. View the page locally
```bash
# Python's built-in HTTP server (required — file:// won't work for fetch())
python -m http.server 8000
# Then open http://localhost:8000
```

---

## Deploy to GitHub Pages

1. **Push this repo to GitHub**
2. Go to **Settings → Pages → Source** → select `main` branch, root folder
3. GitHub Pages URL: `https://YOUR_USERNAME.github.io/parkville-seminars/`
4. The GitHub Actions workflow runs daily and pushes updated `seminars.json`

---

## Project Structure

```
parkville-seminars/
├── scrapers/
│   ├── base.py                    # Shared utilities (fetch, parse_date, etc.)
│   ├── wehi.py                    # WEHI scraper
│   ├── doherty.py                 # Doherty Institute
│   ├── peter_mac.py               # Peter MacCallum Cancer Centre
│   ├── mcri.py                    # MCRI (+ Playwright fallback)
│   ├── florey.py                  # Florey Institute
│   ├── bio21.py                   # Bio21 Institute
│   ├── orygen.py                  # Orygen (+ Playwright)
│   ├── melbourne_bioinformatics.py
│   ├── melbourne_brain_centre.py
│   ├── rmh.py                     # Royal Melbourne Hospital
│   ├── cera.py                    # CERA (+ Playwright)
│   └── bionics.py                 # Bionics Institute
├── run_scrapers.py                # Aggregator — runs all scrapers
├── requirements.txt
├── seminars.json                  # ← Generated output (auto-updated daily)
├── scraper_status.json            # ← Scraper health (auto-updated)
├── index.html                     # Live page
├── app.js                         # Frontend logic
├── styles.css                     # Dark theme styles
└── .github/workflows/
    └── scrape.yml                 # Daily cron + manual trigger
```

---

## Scraper Data Format

Each seminar in `seminars.json`:
```json
{
  "id": "abc123def456",
  "institution": "WEHI",
  "institution_color": "#003087",
  "title": "AnneMarie Welch – Blood Cells and Blood Cancer division",
  "date": "2026-05-27",
  "time": "13:00",
  "speaker": "AnneMarie Welch",
  "affiliation": "Davidson Laboratory, Blood Cells and Blood Cancer division",
  "location": "Davis Auditorium",
  "abstract": "The presentation focuses on...",
  "url": "https://www.wehi.edu.au/event/...",
  "online": false,
  "scraped_at": "2026-05-27T21:00:00Z"
}
```

---

## Manual Trigger (from phone)

You can trigger a fresh scrape at any time without a computer:
1. Go to your GitHub repo → **Actions** tab → **Scrape Parkville Seminars**
2. Click **Run workflow**
3. Optionally specify which institutions to scrape

Or, if you set up Claude Code Remote Control, use the routine created by Claude Code to trigger it from your phone.

---

## Maintaining Scrapers

Scrapers may need updating if an institution redesigns their website. Signs:
- `scraper_status.json` shows `"status": "empty"` or `"error"` for an institution
- The sidebar shows `0` for a specific institution

To fix: visit the institution's events page, inspect the new HTML structure, update the relevant `scrapers/*.py` file.

---

## Adding a New Institution

1. Create `scrapers/new_institution.py` modelled on an existing scraper
2. Add it to `SCRAPERS` list in `run_scrapers.py`
3. Add institution metadata (color, short name) to `INSTITUTIONS` in `app.js`

---

*Data scraped from public institution websites. All seminar details are owned by the respective institutions.*
