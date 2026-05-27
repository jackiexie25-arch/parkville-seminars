"""
Murdoch Children's Research Institute (MCRI) event scraper.
Events at: https://www.mcri.edu.au/news/events
Site returns 403 — uses browser headers + Playwright fallback.
"""
from __future__ import annotations
import logging
import re
import time
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "MCRI"
COLOR = "#009FDA"
BASE_URL = "https://www.mcri.edu.au"
EVENTS_URL = f"{BASE_URL}/news/events"


def scrape() -> list[dict]:
    seminars = []

    soup = fetch(EVENTS_URL)
    if not soup:
        logger.info("MCRI: requests failed, trying Playwright")
        return _scrape_playwright()

    return _parse_events_page(soup)


def _scrape_playwright() -> list[dict]:
    """Playwright fallback for JS-rendered or bot-protected pages."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("MCRI: Playwright not installed, skipping")
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
            browser.close()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        seminars = _parse_events_page(soup)
    except Exception as e:
        logger.error(f"MCRI: Playwright failed: {e}")

    return seminars


def _parse_events_page(soup) -> list[dict]:
    seminars = []

    # Try various selectors for event cards
    event_cards = (
        soup.select(".views-row, .event-item, article.node--type-event, .event-card")
        or soup.select("article")
    )

    if not event_cards:
        # Fallback: find all links matching event URL patterns
        links = set()
        for a in soup.select("a[href*='/event'], a[href*='/news/events/']"):
            href = a.get("href", "")
            if href and href != EVENTS_URL and "events" in href:
                links.add(href)
        for href in list(links)[:15]:
            url = href if href.startswith("http") else BASE_URL + href
            event = _scrape_event_detail(url)
            if event:
                seminars.append(event)
        return seminars

    for card in event_cards:
        a = card.find("a")
        if not a:
            continue
        href = a.get("href", "")
        if not href:
            continue

        # Try to get date from card
        date_str = None
        card_text = clean_text(card.get_text())
        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}", card_text)
        if m:
            date_str = parse_date(m.group(0))

        title = clean_text(a.get_text()) or clean_text(card.find(["h2", "h3", "h4"]).get_text() if card.find(["h2", "h3", "h4"]) else "")
        if not title:
            continue

        url = href if href.startswith("http") else BASE_URL + href
        time.sleep(0.3)
        event = _scrape_event_detail(url)
        if event:
            seminars.append(event)

    return seminars


def _scrape_event_detail(url: str) -> dict | None:
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
        dt = time_el.get("datetime", "")
        if dt:
            date_str = dt[:10]
            if "T" in dt:
                time_str = dt[11:16]

    if not date_str:
        m = re.search(r"\d{1,2}\s+\w+\s+\d{4}", page_text)
        if m:
            date_str = parse_date(m.group(0))

    content = soup.select_one(".field--type-text-with-summary, .body-text, main article, .entry-content")
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
