#!/usr/bin/env python3
from pathlib import Path
from io import BytesIO
from urllib.parse import urljoin
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

BLOG_URL = "https://www.slowspinsociety.com/news-rodeo"
FEED_URL = "https://www.slowspinsociety.com/news-rodeo/?format=rss"
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUTPUT_DIR / "instagram_story_latest.png"

W, H = 1080, 1920
TOP_X = 64
TOP_Y = 190
TOP_W = 952
TOP_H = 870
BG = "#a7a6a1"
TEXT = "#ffffff"


def get(url, xml=False):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "xml" if xml else "html.parser")


def first_article_url():
    try:
        soup = get(FEED_URL, xml=True)
        item = soup.find("item")
        if item and item.link and item.link.get_text(strip=True):
            return item.link.get_text(strip=True)
    except Exception:
        pass

    soup = get(BLOG_URL)
    articles = soup.select('a[href^="/news-rodeo/"]')
    for a in articles:
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        if text and text != "Read More":
            return urljoin(BLOG_URL, href)
    raise RuntimeError("Could not find latest article link")


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
    if ogimg and ogimg.get("content"):
        image_url = ogimg["content"]
    else:
        img = soup.find("img")
        if img and img.get("src"):
            image_url = urljoin(url, img["src"])

    return title, date, image_url


def format_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%-m/%-d/%y")
    except Exception:
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return dt.strftime("%-m/%-d/%y")
        except Exception:
            return date_str


def load_font(size, bold=False):
    candidates = [
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def fit_cover(img, target_w, target_h):
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def wrap_title(text, font, draw, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = word if not current else current + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def main():
    article_url = first_article_url()
    title, date, image_url = parse_article(article_url)
    date = format_date(date)

    if image_url:
        img_data = requests.get(image_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).content
        hero = Image.open(BytesIO(img_data)).convert("RGB")
    else:
        hero = Image.new("RGB", (TOP_W, TOP_H), (220, 220, 220))

    hero = fit_cover(hero, TOP_W, TOP_H)
    canvas = Image.new("RGB", (W, H), BG)
    canvas.paste(hero, (TOP_X, TOP_Y))

    draw = ImageDraw.Draw(canvas)
    date_font = load_font(64, bold=False)
    title_font = load_font(74, bold=True)

    date_bbox = draw.textbbox((0, 0), date, font=date_font)
    date_x = (W - (date_bbox[2] - date_bbox[0])) // 2
    date_y = 1100
    draw.text((date_x, date_y), date, fill=TEXT, font=date_font)

    max_text_width = 800
    lines = wrap_title(title, title_font, draw, max_text_width)
    if len(lines) > 4:
        lines = lines[:4]
    line_height = 82
    title_y = 1200

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=title_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        y = title_y + i * line_height
        draw.text((x, y), line, fill=TEXT, font=title_font)

    canvas.save(OUT_FILE, quality=95)
    print(f"Saved to {OUT_FILE}")
    print(f"Article: {title}")
    print(f"Date: {date}")
    print(f"URL: {article_url}")


if __name__ == "__main__":
    main()
