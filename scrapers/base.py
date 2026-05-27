"""
Base scraper utilities shared across all institution scrapers.
"""
import re
import hashlib
import logging
from datetime import datetime, date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

# Browser-like headers to avoid 403s
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # Exclude 'br' — needs brotli library to decode
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url: str, timeout: int = 15) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def fetch_text(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch raw text from a URL."""
    try:
        resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def parse_date(date_str: str) -> Optional[str]:
    """
    Parse a messy date string into ISO format YYYY-MM-DD.
    Returns None if unparseable.
    """
    if not date_str:
        return None
    # Clean up whitespace
    date_str = re.sub(r"\s+", " ", date_str.strip())
    # Remove ordinal suffixes (1st, 2nd, 3rd, 4th...)
    date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)
    try:
        dt = dateparser.parse(date_str, dayfirst=True)
        if dt:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def parse_time(time_str: str) -> Optional[str]:
    """Parse a time string into HH:MM 24h format."""
    if not time_str:
        return None
    time_str = time_str.strip()
    try:
        dt = dateparser.parse(f"2000-01-01 {time_str}", dayfirst=True)
        if dt:
            return dt.strftime("%H:%M")
    except Exception:
        pass
    return None


def make_id(institution: str, title: str, date_str: str) -> str:
    """Generate a stable unique ID for a seminar."""
    raw = f"{institution}-{title}-{date_str}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def clean_text(text: Optional[str]) -> str:
    """Strip and normalize whitespace from text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def build_seminar(
    institution: str,
    institution_color: str,
    title: str,
    date: Optional[str],
    time: Optional[str],
    speaker: Optional[str],
    affiliation: Optional[str],
    location: Optional[str],
    abstract: Optional[str],
    url: Optional[str],
    online: bool = False,
) -> dict:
    """Build a standardised seminar dict."""
    return {
        "id": make_id(institution, title, date or ""),
        "institution": institution,
        "institution_color": institution_color,
        "title": clean_text(title),
        "date": date,
        "time": time,
        "speaker": clean_text(speaker) if speaker else None,
        "affiliation": clean_text(affiliation) if affiliation else None,
        "location": clean_text(location) if location else None,
        "abstract": clean_text(abstract) if abstract else None,
        "url": url,
        "online": online,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }
