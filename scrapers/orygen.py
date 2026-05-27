"""
Orygen (National Centre for Excellence in Youth Mental Health) event scraper.
Events at: https://www.orygen.org.au/About/News-And-Events
Page is dynamically rendered — uses Playwright with requests fallback.
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Orygen"
COLOR = "#E4022D"
BASE_URL = "https://www.orygen.org.au"
EVENTS_URL = f"{BASE_URL}/About/News-And-Events"
EVENTS_URL2 = f"{BASE_URL}/training-education/conferences-workshops"


def scrape() -> list[dict]:
    # Try Playwright first for dynamic content
    seminars = _scrape_playwright()
    if seminars:
        return seminars

    # Fallback: requests
    for url in [EVENTS_URL, EVENTS_URL2]:
        soup = fetch(url)
        if soup:
            found = _parse_page(soup, url)
            if found:
                seminars.extend(found)

    return seminars


def _scrape_playwright() -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.info("Orygen: Playwright not available, using requests")
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
            html = page.content()

            # Also try training/education page
            page.goto(EVENTS_URL2, wait_until="networkidle", timeout=30000)
            html2 = page.content()
            browser.close()

        from bs4 import BeautifulSoup
        for html in [html, html2]:
            soup = BeautifulSoup(html, "html.parser")
            found = _parse_page(soup, EVENTS_URL)
            seminars.extend(found)
    except Exception as e:
        logger.error(f"Orygen: Playwright failed: {e}")

    return seminars


def _parse_page(soup, source_url: str) -> list[dict]:
    seminars = []
    seen = set()

    # Look for event cards / article blocks
    cards = soup.select(
        "article, .event-listing, .news-item, .card, "
        ".views-row, li.event, .lf-event-list__item"
    )

    links_to_follow = []

    if cards:
        for card in cards:
            a = card.find("a")
            if not a:
                continue
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            title_el = card.find(["h2", "h3", "h4"]) or a
            title = clean_text(title_el.get_text())
            if not title or len(title) < 5:
                continue
            links_to_follow.append((href, title))
    else:
        # Harvest event links
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            title = clean_text(a.get_text())
            if href in seen or not title or len(title) < 10:
                continue
            if not any(kw in href.lower() or kw in title.lower()
                       for kw in ["event", "seminar", "workshop", "webinar", "conference", "lecture"]):
                continue
            seen.add(href)
            links_to_follow.append((href, title))

    for href, fallback_title in links_to_follow[:20]:
        url = href if href.startswith("http") else BASE_URL + href
        event = _scrape_detail(url, fallback_title)
        if event:
            seminars.append(event)

    return seminars


def _scrape_detail(url: str, fallback_title: str = "") -> dict | None:
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

    content = soup.select_one(".entry-content, .post-content, .body, main")
    abstract = None
    if content:
        paras = [clean_text(p.get_text()) for p in content.find_all("p") if len(clean_text(p.get_text())) > 40]
        abstract = " ".join(paras[:2]) if paras else None

    online = any(w in page_text.lower() for w in ["zoom", "online", "teams", "webinar"])
    location = "Online" if online else None

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
