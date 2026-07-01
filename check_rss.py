#!/usr/bin/env python3
from pathlib import Path
import sys
import requests
from bs4 import BeautifulSoup

FEED_URL = "https://www.slowspinsociety.com/news-rodeo/?format=rss"
LAST_SEEN = Path("last_seen.txt")
LATEST_URL_FILE = Path("latest_url.txt")
NEW_ITEM_FILE = Path("new_item.txt")

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_latest():
    r = requests.get(FEED_URL, timeout=30, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "xml")
    item = soup.find("item")
    if not item:
        raise RuntimeError("No RSS item found")
    link = item.link.get_text(strip=True) if item.link else ""
    guid = item.guid.get_text(strip=True) if item.guid else ""
    latest_id = guid or link
    latest_url = link or guid
    if not latest_id or not latest_url:
        raise RuntimeError("RSS item missing id or link")
    return latest_id, latest_url


def main():
    latest_id, latest_url = fetch_latest()
    previous = LAST_SEEN.read_text().strip() if LAST_SEEN.exists() else ""

    if latest_id == previous:
        NEW_ITEM_FILE.write_text("no\n")
        print("No new RSS item")
        sys.exit(0)

    LAST_SEEN.write_text(latest_id)
    LATEST_URL_FILE.write_text(latest_url + "\n")
    NEW_ITEM_FILE.write_text("yes\n")
    print("New RSS item detected")


if __name__ == "__main__":
    main()
