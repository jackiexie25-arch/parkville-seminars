"""
Doherty Institute seminar scraper.
Events at: https://www.doherty.edu.au/news-impact/events/
Server-rendered — works with plain requests.
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Doherty Institute"
COLOR = "#00539B"
BASE_URL = "https://www.doherty.edu.au"
EVENTS_URL = f"{BASE_URL}/news-impact/events/"


def scrape() -> list[dict]:
    seminars = []
    soup = fetch(EVENTS_URL)
    if not soup:
        logger.error("Doherty: could not fetch events page")
        return seminars

    # Events are h3 > a[href*="/event/"]
    event_links = []
    for a in soup.select("h3 a[href*='/event/'], h2 a[href*='/event/'], a[href*='/event/']"):
        href = a.get("href", "")
        if href and href not in event_links:
            event_links.append(href)

    logger.info(f"Doherty: found {len(event_links)} event links")

    for href in event_links:
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

    # Date / time
    date_str = None
    time_str = None
    time_el = soup.find("time")
    if time_el:
        dt_attr = time_el.get("datetime", "")
        if dt_attr:
            date_str = dt_attr[:10]
            if "T" in dt_attr:
                time_str = dt_attr[11:16]
        else:
            raw = clean_text(time_el.get_text())
            date_str = parse_date(raw)

    # Fallback: scan for date patterns
    if not date_str:
        text = soup.get_text()
        m = re.search(r"\d{1,2}\s+\w+[,.]?\s+\d{4}", text)
        if m:
            date_str = parse_date(m.group(0))

    # Look for time like "8.30 - 9.30am" or "12:00 pm"
    if not time_str:
        text = soup.get_text()
        m = re.search(r"\d{1,2}[:.]\d{2}\s*(?:am|pm|[-–]\s*\d{1,2}[:.]\d{2}\s*(?:am|pm)?)?", text, re.I)
        if m:
            time_str = parse_time(m.group(0).split("–")[0].split("-")[0].strip())

    # Speaker / affiliation — Doherty often doesn't expose speaker on listing
    speaker = None
    affiliation = None
    page_text = soup.get_text()

    # Check for "Speaker: Name" pattern
    m = re.search(r"[Ss]peaker[:\s]+([A-Z][^\n,]+)", page_text)
    if m:
        speaker = clean_text(m.group(1))

    # Abstract: first meaningful paragraph after h1
    content = soup.select_one(".entry-content, .post-content, article main, .field--type-text-with-summary")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if clean_text(p.get_text())]
        if paras:
            abstract = " ".join(paras[:3])

    # Location
    location = None
    online = False
    loc_text = page_text.lower()
    if "zoom" in loc_text or "webinar" in loc_text or "online" in loc_text or "teams" in loc_text:
        online = True
        location = "Online"
    else:
        m = re.search(r"[Ll]ocation[:\s]+([^\n]+)", page_text)
        if m:
            location = clean_text(m.group(1))

    return build_seminar(
        institution=INSTITUTION,
        institution_color=COLOR,
        title=title,
        date=date_str,
        time=time_str,
        speaker=speaker,
        affiliation=affiliation,
        location=location,
        abstract=abstract,
        url=url,
        online=online,
    )
