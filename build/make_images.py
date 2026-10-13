"""One-off: generates the social share image and touch icon in build/static/assets/.
Run locally (needs Pillow and Windows fonts): python build/make_images.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "static" / "assets"
FONTS = Path("C:/Windows/Fonts")
BG, ACCENT, TEXT, MUTED, PAGE_L, PAGE_R = "#fbf7ef", "#7a3e1d", "#2a2420", "#6f655c", "#fbf7ef", "#f1e6d2"


def book_icon(draw, x, y, s):
    """The site's open-book logo at (x, y) with size s."""
    draw.rounded_rectangle([x, y, x + s, y + s], radius=s * 14 // 64, fill=ACCENT)
    k = s / 64
    draw.polygon([(x + 14 * k, y + 18 * k), (x + 32 * k, y + 20 * k), (x + 32 * k, y + 48 * k), (x + 14 * k, y + 46 * k)], fill=PAGE_L)
    draw.polygon([(x + 50 * k, y + 18 * k), (x + 32 * k, y + 20 * k), (x + 32 * k, y + 48 * k), (x + 50 * k, y + 46 * k)], fill=PAGE_R)


def og_image():
    img = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1200, 14], fill=ACCENT)
    book_icon(d, 90, 110, 110)
    title = ImageFont.truetype(str(FONTS / "georgiab.ttf"), 84)
    sub = ImageFont.truetype(str(FONTS / "georgia.ttf"), 40)
    small = ImageFont.truetype(str(FONTS / "segoeuib.ttf"), 28)
    d.text((90, 260), "Readable English Bible", font=title, fill=TEXT)
    d.text((90, 370), "A free, open-source Bible in clear, simple English", font=sub, fill=MUTED)
    d.text((90, 520), "READABLE.BIBLE", font=small, fill=ACCENT)
    w = d.textlength("READ  \u00b7  CC BY 4.0", font=small)
    d.text((1110 - w, 520), "READ  \u00b7  CC BY 4.0", font=small, fill=MUTED)
    img.save(OUT / "og.png", optimize=True)


def touch_icon():
    img = Image.new("RGB", (180, 180), ACCENT)
    book_icon(ImageDraw.Draw(img), 0, 0, 180)
    img.save(OUT / "apple-touch-icon.png", optimize=True)


if __name__ == "__main__":
    og_image()
    touch_icon()
    print("wrote og.png and apple-touch-icon.png")
