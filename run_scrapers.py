#!/usr/bin/env python3
"""
Parkville Biomedical Precinct — Seminar Aggregator
====================================================
Runs all 12 institution scrapers, merges results,
removes past events and duplicates, sorts by date,
and writes seminars.json.

Usage:
    python run_scrapers.py               # run all scrapers
    python run_scrapers.py --institutions wehi,doherty  # run specific scrapers
    python run_scrapers.py --dry-run     # print results, don't write file
"""
import argparse
import json
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aggregator")

# All scrapers — (key, display_name, module_path)
SCRAPERS = [
    ("wehi",                    "WEHI",                     "scrapers.wehi"),
    ("doherty",                 "Doherty Institute",        "scrapers.doherty"),
    ("peter_mac",               "Peter MacCallum",          "scrapers.peter_mac"),
    ("mcri",                    "MCRI",                     "scrapers.mcri"),
    ("florey",                  "Florey Institute",         "scrapers.florey"),
    ("bio21",                   "Bio21 Institute",          "scrapers.bio21"),
    ("orygen",                  "Orygen",                   "scrapers.orygen"),
    ("melbourne_bioinformatics","Melbourne Bioinformatics", "scrapers.melbourne_bioinformatics"),
    ("melbourne_brain_centre",  "Melbourne Brain Centre",   "scrapers.melbourne_brain_centre"),
    ("rmh",                     "Royal Melbourne Hospital", "scrapers.rmh"),
    ("cera",                    "CERA",                     "scrapers.cera"),
    ("bionics",                 "Bionics Institute",        "scrapers.bionics"),
]

OUTPUT_FILE = Path(__file__).parent / "seminars.json"
STATUS_FILE = Path(__file__).parent / "scraper_status.json"


def run_scraper(key: str, module_path: str) -> tuple[list, str, float]:
    """
    Run a single scraper, return (seminars, status, duration_seconds).
    status is 'ok', 'empty', or 'error'.
    """
    import importlib
    start = time.time()
    try:
        module = importlib.import_module(module_path)
        seminars = module.scrape()
        duration = time.time() - start
        if seminars:
            return seminars, "ok", duration
        else:
            return [], "empty", duration
    except Exception as e:
        duration = time.time() - start
        logger.error(f"  ✗ {key}: {e}")
        return [], "error", duration


def filter_and_sort(seminars: list) -> list:
    """
    - Remove seminars with no date
    - Remove seminars in the past (more than 1 day ago)
    - Sort by date ascending
    """
    today = date.today()
    filtered = []
    for s in seminars:
        d = s.get("date")
        if not d:
            continue
        try:
            event_date = date.fromisoformat(d)
        except ValueError:
            continue
        # Keep events from yesterday onwards (to catch late-night events)
        from datetime import timedelta
        if event_date >= today - timedelta(days=1):
            filtered.append(s)

    # Sort by date, then time
    filtered.sort(key=lambda x: (x.get("date") or "9999", x.get("time") or "00:00"))
    return filtered


def deduplicate(seminars: list) -> list:
    """Remove duplicates based on institution + title + date."""
    seen = set()
    unique = []
    for s in seminars:
        key = (
            s.get("institution", "").lower(),
            s.get("title", "").lower()[:60],
            s.get("date", ""),
        )
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def main():
    parser = argparse.ArgumentParser(description="Run Parkville seminar scrapers")
    parser.add_argument(
        "--institutions",
        help="Comma-separated list of institution keys to run (default: all)",
        default=None,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results but don't write seminars.json",
    )
    parser.add_argument(
        "--keep-past",
        action="store_true",
        help="Don't filter out past events",
    )
    args = parser.parse_args()

    # Determine which scrapers to run
    if args.institutions:
        keys = [k.strip().lower() for k in args.institutions.split(",")]
        to_run = [(k, n, m) for k, n, m in SCRAPERS if k in keys]
    else:
        to_run = SCRAPERS

    logger.info(f"Running {len(to_run)} scrapers...")
    logger.info("=" * 50)

    all_seminars = []
    statuses = {}

    for key, name, module_path in to_run:
        logger.info(f"→ {name}...")
        seminars, status, duration = run_scraper(key, module_path)
        statuses[key] = {
            "name": name,
            "status": status,
            "count": len(seminars),
            "duration_s": round(duration, 1),
            "last_run": datetime.utcnow().isoformat() + "Z",
        }
        if status == "ok":
            logger.info(f"  ✓ {name}: {len(seminars)} events ({duration:.1f}s)")
            all_seminars.extend(seminars)
        elif status == "empty":
            logger.warning(f"  ⚠ {name}: 0 events ({duration:.1f}s)")
        else:
            logger.error(f"  ✗ {name}: error ({duration:.1f}s)")

    logger.info("=" * 50)

    # Deduplicate
    before = len(all_seminars)
    all_seminars = deduplicate(all_seminars)
    logger.info(f"Deduplication: {before} → {len(all_seminars)} seminars")

    # Filter and sort
    if not args.keep_past:
        all_seminars = filter_and_sort(all_seminars)
    else:
        all_seminars.sort(key=lambda x: (x.get("date") or "9999", x.get("time") or "00:00"))

    logger.info(f"Final count: {len(all_seminars)} upcoming seminars")

    # Summary by institution
    from collections import Counter
    counts = Counter(s["institution"] for s in all_seminars)
    for inst, count in sorted(counts.items()):
        logger.info(f"  {inst}: {count}")

    if args.dry_run:
        print(json.dumps(all_seminars, indent=2))
        return

    # Write seminars.json
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total": len(all_seminars),
        "seminars": all_seminars,
    }
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    logger.info(f"Written to {OUTPUT_FILE}")

    # Write scraper status
    STATUS_FILE.write_text(json.dumps({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "scrapers": statuses,
    }, indent=2))
    logger.info(f"Status written to {STATUS_FILE}")

    # Exit with error code if all scrapers failed
    if all(v["status"] == "error" for v in statuses.values()):
        logger.error("All scrapers failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
