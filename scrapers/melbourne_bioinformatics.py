"""
Melbourne Bioinformatics event scraper.
Workshops + meetups via the University of Melbourne events platform.
Primary: https://events.unimelb.edu.au/Melbourne_Bioinformatics/
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Melbourne Bioinformatics"
COLOR = "#005A8E"
BASE_URL = "https://events.unimelb.edu.au"
EVENTS_URL = f"{BASE_URL}/Melbourne_Bioinformatics/"
MEETUPS_URL = "https://mdhs.unimelb.edu.au/melbournebioinformatics/training-and-support/workshops-and-events/bioinformatics-meetups"
WORKSHOPS_URL = "https://mdhs.unimelb.edu.au/melbournebioinformatics/training-and-support/workshops-and-events/workshops"


def scrape() -> list[dict]:
    seminars = []

    # Primary: University of Melbourne events platform
    soup = fetch(EVENTS_URL)
    if soup:
        found = _parse_unimelb_events(soup)
        seminars.extend(found)
        logger.info(f"Melbourne Bioinformatics: {len(found)} events from events.unimelb.edu.au")

    # Meetups page
    soup2 = fetch(MEETUPS_URL)
    if soup2:
        found2 = _parse_meetups(soup2)
        seminars.extend(found2)
        logger.info(f"Melbourne Bioinformatics: {len(found2)} meetups")

    return _dedupe(seminars)


def _parse_unimelb_events(soup) -> list[dict]:
    seminars = []
    seen = set()

    cards = soup.select(
        "a.lf-event-list__item, .event-card, article.event, "
        ".search-result-item, li[class*='event']"
    )

    if not cards:
        cards = soup.select("h2 a, h3 a, a[href*='/event/']")

    for card_or_a in cards:
        if card_or_a.name == "a":
            a = card_or_a
        else:
            a = card_or_a.find("a")
        if not a:
            continue
        href = a.get("href", "")
        if href in seen:
            continue
        seen.add(href)

        title = clean_text(a.get_text())
        if not title or len(title) < 5:
            # Try parent element
            parent = a.find_parent()
            if parent:
                heading = parent.find(["h2", "h3", "h4"])
                title = clean_text(heading.get_text()) if heading else title

        url = href if href.startswith("http") else BASE_URL + href
        event = _scrape_unimelb_event(url, title)
        if event:
            seminars.append(event)

    return seminars


def _scrape_unimelb_event(url: str, fallback_title: str = "") -> dict | None:
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

    content = soup.select_one(".event-description, .description, .entry-content, main")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if len(clean_text(p.get_text())) > 30]
        abstract = " ".join(paras[:2]) if paras else None

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "virtual"])
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


def _parse_meetups(soup) -> list[dict]:
    """Parse the bioinformatics meetups page — table with Date/Speaker/Topic."""
    seminars = []
    table = soup.find("table")
    if not table:
        return seminars

    rows = table.find_all("tr")
    for row in rows[1:]:  # Skip header
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        date_cell = clean_text(cells[0].get_text())
        speaker_cell = clean_text(cells[1].get_text()) if len(cells) > 1 else ""
        topic_cell = clean_text(cells[2].get_text()) if len(cells) > 2 else ""

        if not date_cell or date_cell.lower() in ["tbd", "date", ""]:
            continue

        date_str = parse_date(date_cell)
        if not date_str:
            continue

        title = topic_cell or f"Bioinformatics Meetup – {date_cell}"
        speaker = speaker_cell if speaker_cell.lower() not in ["tbd", "speaker", ""] else None

        # Link to "More information" if present
        url = MEETUPS_URL
        if len(cells) > 3:
            a = cells[3].find("a")
            if a:
                href = a.get("href", "")
                url = href if href.startswith("http") else "https://mdhs.unimelb.edu.au" + href

        seminars.append(build_seminar(
            institution=INSTITUTION,
            institution_color=COLOR,
            title=title,
            date=date_str,
            time="10:00",  # Meetups are at 10am
            speaker=speaker,
            affiliation=None,
            location="Online (Zoom)",
            abstract=None,
            url=url,
            online=True,
        ))

    return seminars


def _dedupe(seminars: list) -> list:
    seen = set()
    out = []
    for s in seminars:
        key = (s["institution"], s["title"], s["date"])
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out
