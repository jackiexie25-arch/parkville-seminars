"""
Bio21 Institute (University of Melbourne) seminar scraper.
Events via University of Melbourne events platform and Bio21 website.
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Bio21 Institute"
COLOR = "#0F4C81"
BASE_URL = "https://www.bio21.unimelb.edu.au"
UNIMELB_EVENTS = "https://events.unimelb.edu.au/bio21/"

CANDIDATE_URLS = [
    UNIMELB_EVENTS,
    f"{BASE_URL}/events",
    f"{BASE_URL}/news-and-events",
    f"{BASE_URL}/seminars",
    "https://science.unimelb.edu.au/bio21/events",
]


def scrape() -> list[dict]:
    seminars = []

    for url in CANDIDATE_URLS:
        soup = fetch(url)
        if not soup:
            continue
        page_text = soup.get_text().lower()
        if "event" in page_text or "seminar" in page_text:
            logger.info(f"Bio21: using {url}")
            found = _parse_page(soup, url)
            if found:
                seminars.extend(found)
                break

    if not seminars:
        logger.warning("Bio21: no events found from known URLs")

    return seminars


def _parse_page(soup, source_url: str) -> list[dict]:
    seminars = []
    seen_urls = set()

    # Try event card selectors
    cards = soup.select(
        ".event-card, article, .views-row, .lf-event-list__item, "
        ".search-result-item, li.event, .whats-on-list__item"
    )

    if cards:
        for card in cards:
            a = card.find("a")
            if not a:
                continue
            href = a.get("href", "")
            if href in seen_urls:
                continue
            seen_urls.add(href)
            title_el = card.find(["h2", "h3", "h4"]) or a
            title = clean_text(title_el.get_text())
            if not title or len(title) < 5:
                continue
            url = href if href.startswith("http") else "https://events.unimelb.edu.au" + href
            event = _scrape_event_detail(url, title)
            if event:
                seminars.append(event)
    else:
        # Generic link harvest
        for a in soup.select("a[href*='/event'], a[href*='/seminar']"):
            href = a.get("href", "")
            if href in seen_urls or not href:
                continue
            seen_urls.add(href)
            url = href if href.startswith("http") else BASE_URL + href
            title = clean_text(a.get_text())
            if len(title) < 5:
                continue
            event = _scrape_event_detail(url, title)
            if event:
                seminars.append(event)

    return seminars


def _scrape_event_detail(url: str, fallback_title: str = "") -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    title_el = soup.find("h1")
    title = clean_text(title_el.get_text()) if title_el else fallback_title
    if not title:
        return None

    page_text = soup.get_text()
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

    content = soup.select_one(".description, .event-description, .entry-content, main")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if len(clean_text(p.get_text())) > 40]
        abstract = " ".join(paras[:2]) if paras else None

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "webinar"])
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
