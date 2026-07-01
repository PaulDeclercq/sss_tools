#!/usr/bin/env python3
from pathlib import Path
from io import BytesIO
from urllib.parse import urljoin
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

BLOG_URL = "https://www.slowspinsociety.com/blog"
FEED_URL = "https://www.slowspinsociety.com/blog/?format=rss"
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUTPUT_DIR / "instagram_story_blog.png"

W, H = 1080, 1920
TOP_X = 64
TOP_Y = 190
TOP_W = 952
TOP_H = 870
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get(url, xml=False):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "xml" if xml else "html.parser")


def latest_post():
    soup = get(FEED_URL, xml=True)
    item = soup.find("item")
    if not item:
        raise RuntimeError("No RSS item found")

    link = item.link.get_text(strip=True) if item.link else ""
    title = item.title.get_text(strip=True) if item.title else "Untitled"
    date = item.pubDate.get_text(strip=True) if item.pubDate else ""

    if not link:
        raise RuntimeError("RSS item has no link")

    return urljoin(BLOG_URL, link), title, date


def parse_article(url):
    soup = get(url)

    title = None
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    if not title:
        og = soup.find("meta", attrs={"property": "og:title"})
        title = og["content"].strip() if og and og.get("content") else "Untitled"

    date = ""
    time_tag = soup.find("time")
    if time_tag:
        date = time_tag.get("datetime", "") or time_tag.get_text(" ", strip=True)
    if not date:
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date and meta_date.get("content"):
            date = meta_date["content"]

    image_url = None
    ogimg = soup.find("meta", attrs={"property": "og:image"})
