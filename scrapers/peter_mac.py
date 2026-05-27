"""
Peter MacCallum Cancer Centre event scraper.
Events at: https://www.petermac.org/about-us/news-and-events/events
Returns 403 to bots — uses browser-like headers + retries.
"""
from __future__ import annotations
import logging
import re
import time
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Peter MacCallum Cancer Centre"
COLOR = "#6D2077"
BASE_URL = "https://www.petermac.org"
EVENTS_URL = f"{BASE_URL}/about-us/news-and-events/events"


def scrape() -> list[dict]:
    seminars = []

    soup = fetch(EVENTS_URL)
    if not soup:
        # Try without trailing path variation
        soup = fetch(f"{BASE_URL}/events")
    if not soup:
        logger.warning("Peter Mac: could not fetch events page (likely bot protection). Returning empty.")
        return seminars

    # Find event links
    event_links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if re.search(r"/event[s]?/", href) and href not in event_links:
            event_links.append(href)

    # Also try article cards
    for card in soup.select("article, .event-card, .listing-item, li.event"):
        a = card.find("a")
        if a:
            href = a.get("href", "")
            if href and href not in event_links:
                event_links.append(href)

    logger.info(f"Peter Mac: found {len(event_links)} event links")

    for href in event_links[:20]:  # cap at 20 to avoid hammering
        time.sleep(0.5)
        url = href if href.startswith("http") else BASE_URL + href
        event = _scrape_event(url)
        if event:
            seminars.append(event)

    return seminars


def _scrape_event(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    title_el = soup.find("h1")
    title = clean_text(title_el.get_text()) if title_el else None
    if not title:
        return None

    page_text = soup.get_text()
    date_str = None
    time_str = None

    time_el = soup.find("time")
    if time_el:
        dt_attr = time_el.get("datetime", "")
        if dt_attr:
            date_str = dt_attr[:10]
            if "T" in dt_attr:
                time_str = dt_attr[11:16]

    if not date_str:
        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}", page_text)
        if m:
            date_str = parse_date(m.group(0))

    if not time_str:
        m = re.search(r"\d{1,2}[:.]\d{2}\s*(?:am|pm)", page_text, re.I)
        if m:
            time_str = parse_time(m.group(0))

    content = soup.select_one(".entry-content, .field-body, main article, .page-content")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if len(clean_text(p.get_text())) > 40]
        abstract = " ".join(paras[:2]) if paras else None

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "webinar", "virtual"])
    location = "Online" if online else None
    m = re.search(r"[Ll]ocation[:\s]+([^\n]+)", page_text)
    if m:
        location = clean_text(m.group(1))

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
