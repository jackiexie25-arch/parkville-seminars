"""
Bionics Institute seminar scraper.
Seminars at: https://www.bionicsinstitute.org/news-and-events/our-seminars/
All seminars listed on a single page. Structure:
  <h2>18 October: Dr Hamish MacDougall</h2>
  <h3>Neurological Assessment using Virtual Reality</h3>
  ... date/time/location text ...
  <h4>About the Seminar</h4>
  ... abstract paragraphs ...
"""
from __future__ import annotations
import logging
import re
from .base import fetch, parse_date, parse_time, build_seminar, clean_text

logger = logging.getLogger(__name__)

INSTITUTION = "Bionics Institute"
COLOR = "#E31B23"
BASE_URL = "https://www.bionicsinstitute.org"
SEMINARS_URL = f"{BASE_URL}/news-and-events/our-seminars/"


def scrape() -> list[dict]:
    seminars = []
    soup = fetch(SEMINARS_URL)
    if not soup:
        logger.error("Bionics: could not fetch seminars page")
        return seminars

    # Find the main content area
    content = soup.select_one("main, .entry-content, article, #content, .page-content")
    if not content:
        content = soup

    # Each seminar starts with an h2 like "18 October: Dr Hamish MacDougall"
    # followed by h3 (title), then plain text + About sections
    h2_tags = content.find_all("h2")

    # Filter to seminar-like h2s (contain date patterns or "Speaker:" type content)
    date_pattern = re.compile(
        r'\b(\d{1,2}\s+\w+|\w+\s+\d{1,2}|\d{1,2}/\d{1,2})',
        re.I
    )

    for h2 in h2_tags:
        h2_text = clean_text(h2.get_text())
        if not h2_text or len(h2_text) < 5:
            continue

        # Determine if this is a seminar heading (has date or ":" separator)
        if ":" not in h2_text and not date_pattern.search(h2_text):
            continue

        seminar = _parse_seminar_block(h2, h2_text)
        if seminar:
            seminars.append(seminar)

    logger.info(f"Bionics: found {len(seminars)} seminars from main listing page")
    return seminars


def _parse_seminar_block(h2_tag, h2_text: str) -> dict | None:
    """
    Parse a seminar starting from its h2 heading.
    Collects following siblings until the next h2.
    """
    # Extract date and speaker from h2 text
    # Format: "18 October: Dr Hamish MacDougall" or "Speaker Name"
    date_str = None
    speaker = None

    if ":" in h2_text:
        parts = h2_text.split(":", 1)
        date_part = parts[0].strip()
        speaker = clean_text(parts[1]) if len(parts) > 1 else None
        date_str = parse_date(date_part)
    else:
        # Try to find a date in the text
        date_str = parse_date(h2_text)
        speaker = h2_text if not date_str else None

    # Collect sibling nodes until next h2
    siblings = []
    for sib in h2_tag.find_next_siblings():
        if sib.name == "h2":
            break
        siblings.append(sib)

    if not siblings:
        return None

    # Title is in first h3 after h2
    title = None
    for sib in siblings:
        if sib.name == "h3":
            title = clean_text(sib.get_text())
            break

    if not title and speaker:
        title = speaker  # Fall back to using speaker name as title

    if not title:
        return None

    # Collect all text from siblings for date/time/location parsing
    all_text = " ".join(clean_text(s.get_text()) for s in siblings)

    # Try to get date from body text if not found in h2
    if not date_str:
        m = re.search(r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\s*\d{1,2}\s+\w+\s+\d{4}', all_text, re.I)
        if m:
            date_str = parse_date(m.group(0))

    # Time: "4.00-5.00pm" or "4:00 pm"
    time_str = None
    m = re.search(r'\d{1,2}[:.]\d{2}\s*(?:am|pm)?', all_text, re.I)
    if m:
        time_str = parse_time(m.group(0))

    # Location — look for "in person" / "online" / "Teams" explicitly
    location = None
    online = False
    text_lower = all_text.lower()
    if any(w in text_lower for w in ["zoom", "teams", "webinar", "virtual"]):
        online = True
        if "in person" in text_lower:
            location = "In person & Online"
        else:
            location = "Online"
    elif "in person" in text_lower:
        location = "In person"
    # Keep location short — don't include contact/email text
    if location and len(location) > 60:
        location = location[:60].rsplit(" ", 1)[0]

    # Abstract: content under "About the Seminar" heading
    abstract = None
    in_about_seminar = False
    for sib in siblings:
        sib_text = clean_text(sib.get_text())
        if sib.name in ["h3", "h4"] and "about the seminar" in sib_text.lower():
            in_about_seminar = True
            continue
        if sib.name in ["h3", "h4"] and "about" in sib_text.lower() and in_about_seminar:
            break  # Stop at "About [Speaker Name]"
        if in_about_seminar and sib.name == "p" and len(sib_text) > 20:
            abstract = (abstract or "") + " " + sib_text

    if abstract:
        abstract = clean_text(abstract)
    else:
        # Fallback: first meaningful paragraph
        for sib in siblings:
            if sib.name == "p":
                t = clean_text(sib.get_text())
                if len(t) > 40:
                    abstract = t
                    break

    # Ensure speaker is clean (max 60 chars, no emails)
    if speaker and (len(speaker) > 80 or "@" in speaker):
        speaker = None

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
        url=SEMINARS_URL,
        online=online,
    )
