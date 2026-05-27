"""
Melbourne Brain Centre / Melbourne Neuroscience Institute seminar scraper.
Events via: https://neuroscience.unimelb.edu.au/events
and University of Melbourne events platform.
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Melbourne Brain Centre"
COLOR = "#9B2335"
BASE_URL = "https://neuroscience.unimelb.edu.au"

CANDIDATE_URLS = [
    f"{BASE_URL}/events",
    "https://events.unimelb.edu.au/neuroscience/",
    "https://psychologicalsciences.unimelb.edu.au/cognitive-neuroscience-hub/events",
    "https://medicine.unimelb.edu.au/school-structure/medicine/research/mbciu/events",
    "https://events.unimelb.edu.au/Melbourne_Brain_Centre/",
]


def scrape() -> list[dict]:
    seminars = []

    for url in CANDIDATE_URLS:
        soup = fetch(url)
        if not soup:
            continue
        page_text = soup.get_text().lower()
        if "event" in page_text or "seminar" in page_text:
            logger.info(f"Melbourne Brain Centre: using {url}")
            found = _parse_page(soup, url)
            if found:
                seminars.extend(found)

    # Deduplicate
    seen = set()
    unique = []
    for s in seminars:
        key = (s["title"], s["date"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    logger.info(f"Melbourne Brain Centre: {len(unique)} events total")
    return unique


def _parse_page(soup, source_url: str) -> list[dict]:
    seminars = []
    seen = set()

    cards = soup.select(
        "article, .lf-event-list__item, a.lf-event-list__item, "
        ".event-card, .views-row, li[class*='event']"
    )

    links_to_follow = []

    if cards:
        for card in cards:
            a = card if card.name == "a" else card.find("a")
            if not a:
                continue
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            title_el = card.find(["h2", "h3", "h4"]) if card.name != "a" else card
            title = clean_text(title_el.get_text()) if title_el else clean_text(a.get_text())
            if title and len(title) > 5:
                links_to_follow.append((href, title))
    else:
        for a in soup.select("h2 a, h3 a, a[href*='/event/'], a[href*='/seminar']"):
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            title = clean_text(a.get_text())
            if title and len(title) > 5:
                links_to_follow.append((href, title))

    for href, fallback_title in links_to_follow[:20]:
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            # Determine base domain
            from urllib.parse import urlparse
            parsed = urlparse(source_url)
            url = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            url = source_url.rstrip("/") + "/" + href

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
    location = None
    abstract = None
    speaker = None
    affiliation = None

    # Melbourne Brain Centre / CNH pages use structured <p> tags:
    # <p>Date and Time: Thursday 28 May 2026, 12:00pm-1:00pm</p>
    # <p>Talk Location: 1201, Level 12 Tea Room...</p>
    # <p>Talk Title: ...</p>  <p>Talk Abstract: ...</p>  <p>Speaker Bio: ...</p>

    all_paras = [clean_text(p.get_text()) for p in soup.find_all("p") if clean_text(p.get_text())]

    for para in all_paras:
        pl = para.lower()

        # Date and time
        if not date_str and ("date and time:" in pl or "date:" in pl):
            m = re.search(r"\d{1,2}\s+\w+\s+\d{4}", para)
            if m:
                date_str = parse_date(m.group(0))
            m2 = re.search(r"(\d{1,2}[:.]\d{2}\s*(?:am|pm))", para, re.I)
            if m2:
                time_str = parse_time(m2.group(1))

        # Location
        if not location and ("talk location:" in pl or "location:" in pl or "venue:" in pl):
            loc_val = re.sub(r"(?i)(?:talk\s+)?(?:location|venue)\s*:\s*", "", para, count=1)
            # Only take up to "Talk Title:" or "Lunch" if they appear
            loc_val = re.split(r"(?:Talk Title:|Lunch|Contact)", loc_val, maxsplit=1)[0]
            location = clean_text(loc_val)

        # Talk title (override page h1 if more specific)
        if "talk title:" in pl and len(para) > 15:
            talk_title = re.sub(r"(?i)talk\s+title\s*:\s*", "", para, count=1).strip()
            if talk_title and talk_title.lower() not in ["tbd", ""]:
                title = clean_text(talk_title)

        # Abstract
        if not abstract and "talk abstract:" in pl:
            abstract_val = re.sub(r"(?i)talk\s+abstract\s*:\s*", "", para, count=1).strip()
            # Remove speaker bio if it's in the same para
            abstract_val = re.split(r"[Ss]peaker [Bb]io\s*:", abstract_val, maxsplit=1)[0]
            if abstract_val and abstract_val.lower() not in ["tbd", ""]:
                abstract = clean_text(abstract_val)

        # Speaker bio (extract speaker name from bio start)
        if not speaker and "speaker bio:" in pl:
            bio_val = re.sub(r"(?i)speaker\s+bio\s*:\s*", "", para, count=1).strip()
            if bio_val and bio_val.lower() not in ["tbd", ""]:
                # Speaker name is usually the first sentence before a period or comma
                name_m = re.match(r"(?:Dr\.?\s+|Prof(?:essor)?\.?\s+|A/Prof\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", bio_val)
                if name_m:
                    speaker = clean_text(name_m.group(0))

    # Fallback: try <time> element
    if not date_str:
        time_el = soup.find("time")
        if time_el:
            dt = time_el.get("datetime", "")
            if dt:
                date_str = dt[:10]
                if "T" in dt:
                    time_str = dt[11:16]

    # Fallback: date from page text
    if not date_str:
        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}", page_text)
        if m:
            date_str = parse_date(m.group(0))

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "webinar"])
    if online and not location:
        location = "Online"

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
