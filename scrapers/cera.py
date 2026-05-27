"""
Centre for Eye Research Australia (CERA) event scraper.
Events at: https://www.cera.org.au/events/
Uses The Events Calendar (WordPress plugin) — may be dynamically loaded.
Tries Playwright first, falls back to requests.
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "CERA"
COLOR = "#00A9CE"
BASE_URL = "https://www.cera.org.au"
EVENTS_URL = f"{BASE_URL}/events/"


def scrape() -> list[dict]:
    seminars = _scrape_playwright()
    if not seminars:
        seminars = _scrape_requests()
    return seminars


def _scrape_playwright() -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    seminars = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            )
            page = context.new_page()
            page.goto(EVENTS_URL, wait_until="networkidle", timeout=30000)
            # Wait for The Events Calendar to load
            try:
                page.wait_for_selector(".tribe-events-calendar, .tribe-event, article.type-tribe_events", timeout=5000)
            except Exception:
                pass
            html = page.content()
            browser.close()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        seminars = _parse_cera_page(soup)
        logger.info(f"CERA: Playwright found {len(seminars)} events")
    except Exception as e:
        logger.error(f"CERA: Playwright failed: {e}")

    return seminars


def _scrape_requests() -> list[dict]:
    soup = fetch(EVENTS_URL)
    if not soup:
        logger.error("CERA: could not fetch events page")
        return []
    return _parse_cera_page(soup)


def _parse_cera_page(soup) -> list[dict]:
    seminars = []
    seen = set()

    # The Events Calendar (WordPress) uses these selectors
    event_articles = soup.select(
        "article.type-tribe_events, "
        ".tribe-event, "
        ".tribe-events-calendar__month-grid-cell--has-events article, "
        ".tribe-common-g-row article"
    )

    if not event_articles:
        # Generic fallback
        event_articles = soup.select("article")

    if not event_articles:
        # Link harvest
        for a in soup.select("a[href*='/event/'], a[href*='/tribe_events/']"):
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            url = href if href.startswith("http") else BASE_URL + href
            event = _scrape_event_detail(url, clean_text(a.get_text()))
            if event:
                seminars.append(event)
        return seminars

    for article in event_articles:
        a = article.find("a")
        if not a:
            continue
        href = a.get("href", "")
        if href in seen:
            continue
        seen.add(href)

        url = href if href.startswith("http") else BASE_URL + href
        title_el = article.find(["h2", "h3", "h4", ".tribe-event-url"])
        title = clean_text(title_el.get_text()) if title_el else clean_text(a.get_text())

        # Try to get date from card
        date_str = None
        time_el = article.find("time")
        if time_el:
            dt = time_el.get("datetime", "")
            if dt:
                date_str = dt[:10]
        if not date_str:
            date_el = article.select_one(".tribe-event-date-start, .tribe-event__datetime")
            if date_el:
                date_str = parse_date(clean_text(date_el.get_text()))

        event = _scrape_event_detail(url, title, date_str)
        if event:
            seminars.append(event)

    return seminars


def _scrape_event_detail(url: str, fallback_title: str = "", fallback_date: str = None) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    title_el = soup.find("h1")
    title = clean_text(title_el.get_text()) if title_el else fallback_title
    if not title:
        return None

    page_text = soup.get_text()
    date_str = fallback_date
    time_str = None

    if not date_str:
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

    content = soup.select_one(".tribe-event-description, .entry-content, main")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if len(clean_text(p.get_text())) > 40]
        abstract = " ".join(paras[:2]) if paras else None

    location = None
    loc_el = soup.select_one(".tribe-venue, .tribe-events-abbr")
    if loc_el:
        location = clean_text(loc_el.get_text())
    else:
        m = re.search(r"[Ll]ocation[:\s]+([^\n]+)", page_text)
        if m:
            location = clean_text(m.group(1))

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "webinar"])
    if online and not location:
        location = "Online"

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
