#!/usr/bin/env python3
"""Generate Fmovies branding assets (all original artwork, drawn with PIL).

Creates:
  assets/img/logo.svg            (header/footer logo, vector)
  assets/img/logo.png            (transparent logo, 440x96)
  favicon.ico                    (16/32/48)
  favicon-16x16.png, favicon-32x32.png
  apple-touch-icon.png           (180x180)
  android-chrome-192x192.png, android-chrome-512x512.png
  site.webmanifest
  og-image.png                   (1200x630 social image)

Design (original): a teal rounded-square tile with a white play triangle,
plus the wordmark "Fmovies" ("F" teal, "movies" white). Dark navy #0a1424
and teal #00b3a6 are the brand colours.
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "img")
os.makedirs(IMG, exist_ok=True)

NAVY = (10, 20, 36)        # #0a1424
NAVY_SOFT = (15, 30, 51)   # #0f1e33
TEAL = (0, 179, 166)       # #00b3a6
TEAL_BRIGHT = (0, 194, 178)
TEAL_DARK = (0, 148, 138)
WHITE = (255, 255, 255)
MUTED = (143, 163, 189)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def teal_tile(size):
    """Teal rounded-square icon tile with a white play triangle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # vertical teal gradient: draw in horizontal strips
    for y in range(size):
        t = y / max(size - 1, 1)
        c = tuple(int(TEAL_BRIGHT[i] + (TEAL_DARK[i] - TEAL_BRIGHT[i]) * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=c + (255,))
    # rounded mask
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
    img.putalpha(mask)
    # white play triangle, centred, pointing right
    d = ImageDraw.Draw(img)
    cx, cy = size * 0.5, size * 0.5
    w, h = size * 0.30, size * 0.42
    d.polygon([(cx - w * 0.45, cy - h / 2), (cx - w * 0.45, cy + h / 2),
               (cx + w * 0.62, cy)], fill=WHITE + (255,))
    return img


def wordmark(draw, x, y, size, f_color=TEAL_BRIGHT, rest_color=WHITE):
    """Draw 'Fmovies' wordmark; returns width used."""
    f_f = font(size, bold=True)
    draw.text((x, y), "F", font=f_f, fill=f_color + (255,))
    w_f = draw.textlength("F", font=f_f)
    draw.text((x + w_f, y), "movies", font=f_f, fill=rest_color + (255,))
    return w_f + draw.textlength("movies", font=f_f)


# ---------- 1. logo.svg (hand-written vector, same design) ----------
SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="220" height="48" viewBox="0 0 220 48" role="img" aria-label="Fmovies logo">
  <defs>
    <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#00c2b2"/>
      <stop offset="1" stop-color="#00948a"/>
    </linearGradient>
  </defs>
  <rect x="0" y="4" width="40" height="40" rx="9" fill="url(#tg)"/>
  <path d="M16 14 L32 24 L16 34 Z" fill="#ffffff"/>
  <text x="50" y="33" font-family="Arial, Helvetica, sans-serif" font-size="27" font-weight="800"><tspan fill="#00c2b2">F</tspan><tspan fill="#ffffff">movies</tspan></text>
</svg>
"""
with open(os.path.join(IMG, "logo.svg"), "w", encoding="utf-8") as f:
    f.write(SVG)

# ---------- 2. logo.png (transparent, 440x96) ----------
logo = Image.new("RGBA", (440, 96), (0, 0, 0, 0))
tile = teal_tile(88).resize((88, 88), Image.LANCZOS)
logo.alpha_composite(tile, (4, 4))
d = ImageDraw.Draw(logo)
wordmark(d, 104, 22, 54)
logo.save(os.path.join(IMG, "logo.png"))
print("logo.png", logo.size)

# ---------- 3. icon PNGs ----------
for name, size in [("favicon-16x16.png", 16), ("favicon-32x32.png", 32),
                   ("apple-touch-icon.png", 180),
                   ("android-chrome-192x192.png", 192),
                   ("android-chrome-512x512.png", 512)]:
    icon = teal_tile(size)
    if size == 180:
        # apple touch icon: solid navy background (no transparency)
        bg = Image.new("RGBA", (size, size), NAVY + (255,))
        bg.alpha_composite(icon)
        icon = bg.convert("RGB")
    dest = os.path.join(ROOT, name)
    icon.save(dest)
    print(name, icon.size)

# ---------- 4. favicon.ico (16/32/48) ----------
ico_src = teal_tile(48)
ico_src.save(os.path.join(ROOT, "favicon.ico"),
             sizes=[(16, 16), (32, 32), (48, 48)])
print("favicon.ico written")

# ---------- 5. site.webmanifest ----------
manifest = {
    "name": "Fmovies - Watch Free Movies Online",
    "short_name": "Fmovies",
    "description": "Watch free movies and TV series online in HD at Fmovies. No sign-up needed.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#0a1424",
    "theme_color": "#00b3a6",
    "icons": [
        {"src": "/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"},
    ],
}
with open(os.path.join(ROOT, "site.webmanifest"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
print("site.webmanifest written")

# ---------- 6. og-image.png (1200x630) ----------
og = Image.new("RGB", (1200, 630), NAVY)
d = ImageDraw.Draw(og, "RGBA")
# soft teal glow circles (concentric, low alpha)
for r, a in [(420, 18), (340, 26), (260, 34)]:
    d.ellipse([600 - r, 210 - r, 600 + r, 210 + r], fill=(0, 179, 166, a))
# thin teal frame line
d.rectangle([24, 24, 1175, 605], outline=(0, 179, 166, 90), width=3)
# centred logo tile + wordmark
tile_big = teal_tile(150).resize((150, 150), Image.LANCZOS)
og.paste(tile_big, (525, 108), tile_big)
# wordmark centred below the tile
f_big = font(92, bold=True)
label = "Fmovies"
w = d.textlength(label, font=f_big)
# draw "F" teal + "movies" white
x0 = (1200 - w) / 2
d.text((x0, 285), "F", font=f_big, fill=TEAL_BRIGHT)
d.text((x0 + d.textlength("F", font=f_big), 285), "movies", font=f_big, fill=WHITE)
# tagline
tag = "Watch Free Movies Online in HD"
f_tag = font(40, bold=False)
tw = d.textlength(tag, font=f_tag)
d.text(((1200 - tw) / 2, 420), tag, font=f_tag, fill=(216, 226, 238))
# domain line
dom = "fmovies.jo3.org"
f_dom = font(30, bold=True)
dw = d.textlength(dom, font=f_dom)
d.text(((1200 - dw) / 2, 500), dom, font=f_dom, fill=TEAL_BRIGHT)
og.save(os.path.join(ROOT, "og-image.png"))
print("og-image.png", og.size)

print("ALL BRAND ASSETS DONE")
