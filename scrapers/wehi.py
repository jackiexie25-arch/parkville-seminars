"""
WEHI (Walter and Eliza Hall Institute) seminar scraper.
Events at: https://www.wehi.edu.au/events/
Server-rendered WordPress site - works with plain requests.
"""
from __future__ import annotations
import logging
from .base import fetch, fetch_text, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "WEHI"
COLOR = "#003087"  # WEHI navy
BASE_URL = "https://www.wehi.edu.au"
EVENTS_URL = f"{BASE_URL}/events/"


def scrape() -> list[dict]:
    seminars = []

    soup = fetch(EVENTS_URL)
    if not soup:
        logger.error("WEHI: could not fetch events page")
        return seminars

    # Each event is a link — WEHI uses absolute URLs like https://www.wehi.edu.au/event/slug/
    event_links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        # Match both absolute (https://www.wehi.edu.au/event/...) and relative (/event/...)
        if "/event/" in href and href not in seen:
            # Skip non-event URLs (e.g. /events/ listing page)
            if href.rstrip("/").endswith("/events") or href == EVENTS_URL:
                continue
            seen.add(href)
            event_links.append(href)

    logger.info(f"WEHI: found {len(event_links)} event links")

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

    # Title in h1
    title_el = soup.find("h1")
    title = clean_text(title_el.get_text()) if title_el else None
    if not title:
        return None

    # Date/time — look for time element or text matching date pattern
    date_str = None
    time_str = None

    # Try <time> element first
    time_el = soup.find("time")
    if time_el:
        dt_attr = time_el.get("datetime", "")
        if dt_attr:
            date_str = dt_attr[:10]  # ISO format
        else:
            date_str = parse_date(clean_text(time_el.get_text()))

    # Fallback: look for date pattern in page text
    if not date_str:
        import re
        text = soup.get_text()
        m = re.search(r"\d{1,2}/\d{1,2}/\d{4}\s+\d+:\d+\s*(?:am|pm)", text, re.I)
        if m:
            parts = m.group(0).split()
            date_str = parse_date(parts[0])
            time_str = parse_time(" ".join(parts[1:]))

    # Speaker — WEHI titles are "Speaker Name – Division"
    speaker = None
    affiliation = None
    if "–" in (title or ""):
        parts = title.split("–", 1)
        speaker = clean_text(parts[0])
        affiliation = clean_text(parts[1]) if len(parts) > 1 else None

    # Abstract — WEHI uses .o-type--wysiwyg for rich text content
    abstract = None
    content_el = soup.select_one(".o-type--wysiwyg, .c-block-post-content, .col-span-8")
    if content_el:
        paras = [clean_text(p.get_text()) for p in content_el.find_all("p") if len(clean_text(p.get_text())) > 30]
        # Skip short/boilerplate paragraphs
        paras = [p for p in paras if not any(skip in p.lower() for skip in ["support us", "newsletter", "donate", "give to"])]
        abstract = " ".join(paras[:3]) if paras else None

    # Location — look in the event metadata block
    location = None
    page_text = soup.get_text()
    page_text_lower = page_text.lower()

    # Try structured location field
    import re
    loc_match = re.search(r'\bLocation\s+([A-Z][^\n]{3,60})', page_text)
    if loc_match:
        location = clean_text(loc_match.group(1))
    else:
        # Fallback patterns
        for pat in ["Davis Auditorium", "zoom", "online", "virtual"]:
            if pat.lower() in page_text_lower:
                location = pat
                break

    online = any(w in page_text_lower for w in ["zoom", "online", "webinar", "virtual", "teams"])

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
