"""
Royal Melbourne Hospital (RMH) research events scraper.
Events at: https://www.thermh.org.au/news/events
Filters for research seminars (excludes clinical training courses).
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Royal Melbourne Hospital"
COLOR = "#0066CC"
BASE_URL = "https://www.thermh.org.au"
EVENTS_URL = f"{BASE_URL}/news/events"

# Keywords that indicate research content
RESEARCH_KEYWORDS = [
    "research", "seminar", "lecture", "symposium", "grand round",
    "conference", "webinar", "workshop", "science", "clinical trial",
    "innovation", "discovery", "study", "findings", "data",
]

# Keywords indicating clinical training (to de-prioritise)
TRAINING_KEYWORDS = [
    "als1", "als2", "star course", "crash course", "life support",
    "certification", "recertification", "graduate nurse", "nursing program",
    "work experience",
]


def scrape() -> list[dict]:
    seminars = []
    soup = fetch(EVENTS_URL)
    if not soup:
        logger.error("RMH: could not fetch events page")
        return seminars

    # Collect event links from the page
    event_links = []
    seen = set()

    for item in soup.select("li, article, .event-card, .listing__item"):
        a = item.find("a")
        if not a:
            continue
        href = a.get("href", "")
        if href in seen:
            continue
        seen.add(href)

        title = clean_text(a.get_text()) or clean_text(
            item.find(["h2", "h3", "h4"]).get_text() if item.find(["h2", "h3", "h4"]) else ""
        )
        title_lower = title.lower()

        # Skip obvious clinical training
        if any(kw in title_lower for kw in TRAINING_KEYWORDS):
            continue

        # Prioritise research events
        is_research = any(kw in title_lower for kw in RESEARCH_KEYWORDS)
        event_links.append((href, title, is_research))

    # Sort: research events first
    event_links.sort(key=lambda x: (0 if x[2] else 1))

    logger.info(f"RMH: found {len(event_links)} event links ({sum(1 for _, _, r in event_links if r)} research)")

    for href, fallback_title, _ in event_links[:15]:
        url = href if href.startswith("http") else BASE_URL + href
        event = _scrape_event(url, fallback_title)
        if event:
            seminars.append(event)

    return seminars


def _scrape_event(url: str, fallback_title: str = "") -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    title_el = soup.find("h1")
    title = clean_text(title_el.get_text()) if title_el else fallback_title
    if not title:
        return None

    page_text = soup.get_text()
    date_str, time_str = None, None

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

    content = soup.select_one(".entry-content, .page-content, .field-body, main article")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if len(clean_text(p.get_text())) > 40]
        abstract = " ".join(paras[:2]) if paras else None

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "webinar"])
    location = "Online" if online else None
    m = re.search(r"[Ll]ocation[:\s]+([^\n]+)", page_text)
    if m:
        location = clean_text(m.group(1))

    return build_seminar(
        institution=INSTITUTION,
        institution_color=COLOR,
        title=title,
        date=date_str,
        time=time_str,
        speaker=None,
        affiliation=None,
        location=location,
        abstract=abstract,
        url=url,
        online=online,
    )
