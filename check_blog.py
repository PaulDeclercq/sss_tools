from pathlib import Path
import requests
from bs4 import BeautifulSoup
import sys

FEED_URL = "https://www.slowspinsociety.com/blog/?format=rss"
LAST_SEEN = Path("last_seen.txt")
LATEST_URL_FILE = Path("latest_url.txt")


def fetch_latest():
    r = requests.get(FEED_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "xml")
    item = soup.find("item")
    if not item:
        raise RuntimeError("No RSS item found")
    link = item.link.get_text(strip=True) if item.link else ""
    guid = item.guid.get_text(strip=True) if item.guid else ""
    return guid or link, link or guid


latest_id, latest_url = fetch_latest()
previous = LAST_SEEN.read_text().strip() if LAST_SEEN.exists() else ""

if latest_id == previous:
    print("No new RSS item")
    sys.exit(0)

LAST_SEEN.write_text(latest_id)
LATEST_URL_FILE.write_text(latest_url)
print("New RSS item detected")
