#!/usr/bin/env python3
from pathlib import Path
from io import BytesIO
from urllib.parse import urljoin
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BLOG_URL = "https://www.slowspinsociety.com/blog"
FEED_URL = "https://www.slowspinsociety.com/blog/?format=rss"

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUTPUT_DIR / "instagram_blog_latest.png"

W, H = 1080, 1920

SAFE_TOP = 220
SAFE_BOTTOM = 220
SIDE_PAD = 72

HERO_X = 64
HERO_Y = 220
HERO_W = 952
HERO_H = 860
HERO_RADIUS = 36

CONTENT_X = 84
CONTENT_W = W - CONTENT_X * 2

WHITE = (255, 255, 255)
BLACK = (43, 32, 24)

TEXT = (43, 32, 24)
MUTED = (110, 88, 72)

ACCENT = (250, 91, 1)  # #FA5B01
ACCENT_SOFT = (255, 232, 219)
STICKER_BG = (255, 255, 255)
STICKER_BORDER = (230, 214, 203)

BG_BLUR = 36
BG_DARKEN = (245, 240, 234, 176)

CTA_TEXT = "Read the full article"

TITLE_MAX_LINES = 3
TITLE_LINE_GAP = 14
TITLE_FONT_SIZE = 68


def get(url, xml=False):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "xml" if xml else "html.parser")


def first_article_url():
    try:
        soup = get(FEED_URL, xml=True)
        item = soup.find("item")
        if item and item.link and item.link.get_text(strip=True):
            return item.link.get_text(strip=True)
    except Exception:
        pass

    soup = get(BLOG_URL)
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        if not href or not text:
            continue
        if "/blog/" in href and text != "Read More":
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
        if og and og.get("content"):
            title = og["content"].strip()
    if not title:
        title = "Untitled"

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
        return dt.strftime("%b %-d")
    except Exception:
        pass

    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%b %-d")
    except Exception:
        return date_str


def load_font(size, bold=False):
    candidates = [
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def fit_cover(img, target_w, target_h):
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def build_background_from_image(hero):
    bg = (
        fit_cover(hero, W, H)
        .filter(ImageFilter.GaussianBlur(radius=BG_BLUR))
        .convert("RGBA")
    )
    overlay = Image.new("RGBA", (W, H), BG_DARKEN)
    bg.alpha_composite(overlay)
    return bg.convert("RGB")


def download_image(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def add_hero_with_shadow(base, hero, x, y, radius=36):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (x, y + 12, x + hero.width, y + hero.height + 12),
        radius=radius,
        fill=(0, 0, 0, 85),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    base = Image.alpha_composite(base.convert("RGBA"), shadow)

    hero_rgba = hero.convert("RGBA")
    mask = rounded_mask(hero.size, radius)
    hero_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    hero_layer.paste(hero_rgba, (x, y), mask)
    base = Image.alpha_composite(base, hero_layer)
    return base.convert("RGB")


def add_hero_gradients(hero):
    hero = hero.convert("RGBA")
    overlay = Image.new("RGBA", hero.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    top_h = int(hero.height * 0.22)
    bottom_h = int(hero.height * 0.28)

    for i in range(top_h):
        alpha = int(120 * (1 - i / max(1, top_h)))
        d.rectangle((0, i, hero.width, i + 1), fill=(0, 0, 0, alpha))

    for i in range(bottom_h):
        alpha = int(175 * (i / max(1, bottom_h)))
        y = hero.height - bottom_h + i
        d.rectangle((0, y, hero.width, y + 1), fill=(0, 0, 0, alpha))

    hero = Image.alpha_composite(hero, overlay)
    return hero.convert("RGB")


def measure_text(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return left, top, right, bottom, right - left, bottom - top


def wrap_text_keep_start(draw, text, font, max_width, max_lines=3):
    words = " ".join(text.split()).split()
    if not words:
        return []

    lines = []
    current = ""

    for word in words:
        trial = word if not current else f"{current} {word}"
        _, _, _, _, width, _ = measure_text(draw, trial, font)
        if width <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    if len(lines) <= max_lines:
        return lines

    visible = lines[:max_lines]
    last = visible[-1].rstrip()

    while True:
        candidate = last + "..."
        _, _, _, _, width, _ = measure_text(draw, candidate, font)
        if width <= max_width:
            visible[-1] = candidate
            break

        shorter = last.rsplit(" ", 1)[0].rstrip()
        if not shorter or shorter == last:
            while last:
                last = last[:-1].rstrip()
                candidate = last + "..."
                _, _, _, _, width, _ = measure_text(draw, candidate, font)
                if width <= max_width:
                    visible[-1] = candidate
                    return visible
            visible[-1] = "..."
            return visible

        last = shorter

    return visible


def draw_text_shadow(draw, xy, text, font, fill, shadow=(0, 0, 0), offset=2):
    x, y = xy
    draw.text((x + offset, y + offset), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def draw_pill(draw, xy, text, font, bg, fg, pad_x=24, pad_y=14, radius=24):
    x, y = xy
    left, top, right, bottom, tw, th = measure_text(draw, text, font)
    w = tw + pad_x * 2
    h = th + pad_y * 2
    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=bg)
    draw.text((x + pad_x - left, y + pad_y - top), text, font=font, fill=fg)
    return w, h


def draw_link_placeholder(draw, x, y, w, h):
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=30,
        fill=STICKER_BG,
        outline=STICKER_BORDER,
        width=3,
    )
    chain_r = 20
    cy = y + h // 2
    cx1 = x + 58
    cx2 = x + 88
    draw.ellipse(
        (cx1 - chain_r, cy - chain_r, cx1 + chain_r, cy + chain_r),
        outline=(120, 120, 120),
        width=4,
    )
    draw.ellipse(
        (cx2 - chain_r, cy - chain_r, cx2 + chain_r, cy + chain_r),
        outline=(120, 120, 120),
        width=4,
    )


def draw_text_line_left(draw, x, y, text, font, fill):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((x - left, y - top), text, font=font, fill=fill)
    return bottom - top


def draw_multiline_from_start(draw, x, y, lines, font, fill, line_gap=14):
    current_y = y
    for line in lines:
        h = draw_text_line_left(draw, x, current_y, line, font, fill)
        current_y += h + line_gap
    return current_y


def main():
    article_url = first_article_url()
    title, date_str, image_url = parse_article(article_url)
    date = format_date(date_str)

    if image_url:
        hero = download_image(image_url)
    else:
        hero = Image.new("RGB", (HERO_W, HERO_H), (220, 220, 220))

    background = build_background_from_image(hero)
    hero_fg = fit_cover(hero, HERO_W, HERO_H)
    hero_fg = add_hero_gradients(hero_fg)

    canvas = background.copy()
    canvas = add_hero_with_shadow(canvas, hero_fg, HERO_X, HERO_Y, HERO_RADIUS)

    draw = ImageDraw.Draw(canvas)

    date_font = load_font(42, bold=True)
    kicker_font = load_font(40, bold=False)
    title_font = load_font(TITLE_FONT_SIZE, bold=True)
    cta_font = load_font(44, bold=True)

    kicker = "JUST PUBLISHED"
    main_title = " ".join(title.split())

    title_lines = wrap_text_keep_start(
        draw,
        main_title,
        title_font,
        CONTENT_W,
        max_lines=TITLE_MAX_LINES,
    )

    if date:
        date_y = HERO_Y + HERO_H - 120
        draw_text_shadow(
            draw,
            (CONTENT_X + 22, date_y),
            date.upper(),
            date_font,
            WHITE,
            shadow=(0, 0, 0),
        )

    text_y = HERO_Y + HERO_H + 60

    kicker_h = draw_text_line_left(
        draw,
        CONTENT_X,
        text_y,
        kicker.upper(),
        kicker_font,
        ACCENT,
    )
    text_y += kicker_h + 24

    text_y = draw_multiline_from_start(
        draw,
        CONTENT_X,
        text_y,
        title_lines,
        title_font,
        TEXT,
        line_gap=TITLE_LINE_GAP,
    )

    bottom_safe_y = H - SAFE_BOTTOM

    sticker_w = 620
    sticker_h = 120
    cta_gap = 26

    _, _, _, _, _, cta_text_h = measure_text(draw, CTA_TEXT, cta_font)
    cta_h = cta_text_h + 18 * 2

    sticker_y = bottom_safe_y - sticker_h
    cta_y = sticker_y - cta_gap - cta_h

    draw_pill(
        draw,
        (CONTENT_X, cta_y),
        CTA_TEXT,
        cta_font,
        ACCENT,
        WHITE,
        pad_x=28,
        pad_y=18,
        radius=30,
    )
    draw_link_placeholder(draw, CONTENT_X, sticker_y, sticker_w, sticker_h)

    canvas.save(OUT_FILE, quality=95)

    print(f"Saved to {OUT_FILE}")
    print(f"Article: {title}")
    print(f"Date: {date}")
    print(f"URL: {article_url}")


if __name__ == "__main__":
    main()
