"""
Florey Institute of Neuroscience and Mental Health scraper.
The Florey doesn't maintain a dedicated upcoming-events listing page.
We scrape their news feed and filter for seminar/lecture/symposium content.
News at: https://florey.edu.au/news/
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Florey Institute"
COLOR = "#FF6B00"
BASE_URL = "https://florey.edu.au"
NEWS_URL = f"{BASE_URL}/news/"

# Keywords that indicate a research event (not just a press release)
EVENT_KEYWORDS = [
    "seminar", "lecture", "symposium", "workshop", "conference",
    "webinar", "forum", "presentation", "talk", "colloquium"
]


def scrape() -> list[dict]:
    seminars = []

    # Try dedicated event URLs first
    for url in [
        f"{BASE_URL}/events/",
        f"{BASE_URL}/news-events/events/",
        f"{BASE_URL}/events-seminars/",
    ]:
        soup = fetch(url)
        if soup and soup.find("h1"):
            page_text = soup.get_text().lower()
            if any(k in page_text for k in EVENT_KEYWORDS):
                logger.info(f"Florey: found events at {url}")
                seminars = _parse_events_generic(soup, url)
                if seminars:
                    return seminars

    # Fallback: scrape news page and filter for event content
    soup = fetch(NEWS_URL)
    if not soup:
        logger.error("Florey: could not fetch news page")
        return seminars

    # Find article links
    articles = soup.select("article a, .news-item a, h2 a, h3 a")
    seen = set()
    for a in articles:
        href = a.get("href", "")
        if href in seen:
            continue
        seen.add(href)
        title = clean_text(a.get_text())
        if not any(kw in title.lower() for kw in EVENT_KEYWORDS):
            continue
        url = href if href.startswith("http") else BASE_URL + href
        event = _scrape_article(url)
        if event:
            seminars.append(event)

    logger.info(f"Florey: found {len(seminars)} events from news feed")
    return seminars


def _parse_events_generic(soup, source_url: str) -> list[dict]:
    """Generic event list parser."""
    seminars = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        title = clean_text(a.get_text())
        if not title or len(title) < 10:
            continue
        if not any(kw in title.lower() for kw in EVENT_KEYWORDS + ["lecture", "seminar"]):
            continue
        url = href if href.startswith("http") else BASE_URL + href
        event = _scrape_article(url)
        if event:
            seminars.append(event)
    return seminars


def _scrape_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    title_el = soup.find("h1")
    title = clean_text(title_el.get_text()) if title_el else None
    if not title:
        return None

    # Must contain event-like content
    page_text = soup.get_text()
    if not any(kw in page_text.lower() for kw in EVENT_KEYWORDS):
        return None

    date_str = None
    time_str = None
    time_el = soup.find("time")
    if time_el:
        dt = time_el.get("datetime", "")
        if dt:
            date_str = dt[:10]
            if "T" in dt:
                time_str = dt[11:16]

    if not date_str:
        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}", page_text)
        if m:
            date_str = parse_date(m.group(0))

    if not time_str:
        m = re.search(r"\d{1,2}[:.]\d{2}\s*(?:am|pm)", page_text, re.I)
        if m:
            time_str = parse_time(m.group(0))

    content = soup.select_one(".entry-content, .post-content, article, main")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if len(clean_text(p.get_text())) > 40]
        abstract = " ".join(paras[:2]) if paras else None

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "webinar"])
    location = "Online" if online else None

    speaker = None
    m = re.search(r"[Ss]peaker[:\s]+([A-Z][^\n,]+)", page_text)
    if m:
        speaker = clean_text(m.group(1))

    return build_seminar(
        institution=INSTITUTION,
        institution_color=COLOR,
        title=title,
        date=date_str,
        time=time_str,
        speaker=speaker,
        affiliation=None,
        location=location,
        abstract=abstract,
        url=url,
        online=online,
    )
