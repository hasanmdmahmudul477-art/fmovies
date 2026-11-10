#!/usr/bin/env python3
"""Fix CineWave SEO weaknesses (approved 2026-09-30):
1. Regenerate sitemap.xml from ALL files in title/ (fixes 10 missing pages).
2. Fix index.html head: better title/meta, canonical, OG/Twitter tags.
3. Add a static crawlable "Popular Titles" link block (top 60 by TMDB votes).
"""
import json, re, os, time, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE_DIR = os.path.join(ROOT, "title")
SITE_URL = "https://www.cinewave.jo3.org"

# ---------- 1. sitemap from actual files ----------
files = sorted(f for f in os.listdir(TITLE_DIR) if f.endswith(".html"))
today = time.strftime("%Y-%m-%d")
urls = [f"  <url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod>"
        f"<changefreq>daily</changefreq><priority>1.0</priority></url>"]
for fn in files:
    urls.append(f"  <url><loc>{SITE_URL}/title/{fn}</loc><lastmod>{today}</lastmod>"
                f"<changefreq>weekly</changefreq><priority>0.8</priority></url>")
with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls) + "\n</urlset>\n")
print(f"sitemap: {len(files)} title pages + homepage = {len(urls)} urls")

# ---------- 2+3. index.html head + popular links ----------
def parse_page(fn):
    src = open(os.path.join(TITLE_DIR, fn), encoding="utf-8").read()
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', src, re.S)
    if not m:
        return None
    try:
        ld = json.loads(m.group(1))
    except Exception:
        return None
    rating = (ld.get("aggregateRating") or {})
    return {
        "file": fn,
        "name": ld.get("name", fn),
        "year": (ld.get("datePublished") or "----")[:4],
        "votes": rating.get("ratingCount", 0) or 0,
        "score": rating.get("ratingValue", 0) or 0,
        "kind": ld.get("@type", ""),
    }

pages = [p for p in (parse_page(fn) for fn in files) if p]
# genuinely popular: most votes first, tie-break by score
pages.sort(key=lambda p: (p["votes"], p["score"]), reverse=True)
top = pages[:60]
print(f"parsed {len(pages)} pages, top pick: {top[0]['name']} ({top[0]['votes']} votes)")

links = "\n".join(
    f'    <a href="/title/{p["file"]}">{html.escape(p["name"])} ({p["year"]})</a>'
    for p in top
)
block = f"""<!-- SEO: static crawlable links to popular titles -->
<section class="seo-popular" aria-label="Popular movies and TV shows">
  <h2>Popular Movies &amp; TV Shows</h2>
  <div class="seo-links">
{links}
  </div>
</section>
"""

css = """<style>
.seo-popular{max-width:1200px;margin:0 auto;padding:26px 16px;border-top:1px solid #1c2333}
.seo-popular h2{font-size:20px;margin:0 0 14px;color:#e8ecf4}
.seo-links{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px 16px}
.seo-links a{color:#9aa4bd;text-decoration:none;font-size:14px;line-height:1.5}
.seo-links a:hover{color:#e50914}
</style>
"""

idx = os.path.join(ROOT, "index.html")
src = open(idx, encoding="utf-8").read()

# head fixes
src = src.replace("<title>CineWave</title>",
    "<title>CineWave — Watch Movies & TV Shows Online in HD</title>", 1)
src = src.replace(
    '<meta name="description" content="Discover trending movies and TV shows.">',
    '<meta name="description" content="Watch movies and TV shows online in HD on CineWave. '
    'Browse trending, top-rated and popular titles with cast, trailers and details — no sign-up needed.">', 1)
head_add = (
    '<link rel="canonical" href="https://www.cinewave.jo3.org/">\n'
    '<meta name="theme-color" content="#0b0e17">\n'
    '<meta property="og:type" content="website">\n'
    '<meta property="og:site_name" content="CineWave">\n'
    '<meta property="og:title" content="CineWave — Watch Movies & TV Shows Online in HD">\n'
    '<meta property="og:description" content="Watch movies and TV shows online in HD. '
    'Browse trending, top-rated and popular titles — no sign-up needed.">\n'
    '<meta property="og:url" content="https://www.cinewave.jo3.org/">\n'
    '<meta name="twitter:card" content="summary">\n'
    '<meta name="twitter:title" content="CineWave — Watch Movies & TV Shows Online in HD">\n'
    '<meta name="twitter:description" content="Watch movies and TV shows online in HD. '
    'Browse trending, top-rated and popular titles — no sign-up needed.">\n'
)
src = src.replace('<link rel="stylesheet" href="assets/css/style.css">',
    '<link rel="stylesheet" href="assets/css/style.css">\n' + head_add + css, 1)

# insert link block before footer
src = src.replace("<footer>", block + "\n<footer>", 1)

open(idx, "w", encoding="utf-8").write(src)
print("index.html updated: head SEO + 60 popular-title links")
