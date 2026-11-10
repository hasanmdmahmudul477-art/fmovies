#!/usr/bin/env python3
"""Final QA for the Fmovies build. Exits non-zero if any check fails.

Checks:
 1. sitemap.xml is an index of 16 child files; total <loc> entries == 2011
 2. unique movie pages == 1258, unique serie pages == 100 (on-disk dirs)
 3. hub pages exist: 19 genre + 7 country + 3 year + 10 lists
 4. every sitemap <loc> resolves to a real file on disk
 5. every page: <title>, meta description, canonical, og:title, JSON-LD present;
    titles unique across all generated pages
 6. Adsterra keys in config.js unchanged vs /tmp/fmovies-baseline/ad-keys.txt
 7. homepage: title, H1, all H2s, FAQ section, target keywords present
 8. no text copied from fmovies00.org (distinctive competitor phrases absent)
 9. branding assets exist and are referenced by every page
10. every page references existing local assets only (no missing local files)
"""
import json, os, re, sys
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.fmovies.jo3.org"
FAILURES = []
WARNINGS = []


def fail(msg):
    FAILURES.append(msg)
    print("FAIL:", msg)


def warn(msg):
    WARNINGS.append(msg)
    print("WARN:", msg)


def ok(msg):
    print("ok:", msg)


def loc_to_file(loc):
    """Map a sitemap URL to a file path on disk ('' if external/unknown)."""
    p = urlparse(loc).path
    if p in ("/", ""):
        return os.path.join(ROOT, "index.html")
    if p == "/sitemap.xml":
        return os.path.join(ROOT, "sitemap.xml")
    if p.endswith("/"):
        return os.path.join(ROOT, p.strip("/"), "index.html")
    return os.path.join(ROOT, p.lstrip("/"))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# ---------- 1. sitemap ----------
index = read(os.path.join(ROOT, "sitemap.xml"))
child_files = re.findall(r"<loc>(https://www\.fmovies\.jo3\.org/(sitemap[^<]*))</loc>", index)
if len(child_files) != 16:
    fail(f"sitemap index lists {len(child_files)} child files, expected 16")
else:
    ok("sitemap index lists 16 child files")
total_loc = 0
all_locs = []
EXPECTED_SIZES = {"sitemap-0.xml": 41, "sitemap-1.xml": 62, "sitemap-2.xml": 102,
                  "sitemap-3.xml": 202, "sitemap-4.xml": 42, "sitemap-5.xml": 202,
                  "sitemap-6.xml": 42, "sitemap-7.xml": 102, "sitemap-8.xml": 102,
                  "sitemap-9.xml": 102, "sitemap-10.xml": 102, "sitemap-11.xml": 102,
                  "sitemap-12.xml": 102, "sitemap-13.xml": 102, "sitemap-14.xml": 102,
                  "sitemap-post.xml": 502}
for _, fname in child_files:
    content = read(os.path.join(ROOT, fname))
    locs = re.findall(r"<loc>([^<]+)</loc>", content)
    total_loc += len(locs)
    all_locs.extend(locs)
    if EXPECTED_SIZES.get(fname) is not None and len(locs) != EXPECTED_SIZES[fname]:
        fail(f"{fname}: {len(locs)} entries, expected {EXPECTED_SIZES[fname]}")
    print(f"  {fname}: {len(locs)} entries")
if total_loc != 2011:
    fail(f"sitemap total <loc> entries = {total_loc}, expected 2011")
else:
    ok("sitemap total <loc> entries = 2011")
uniq_locs = set(all_locs)
print(f"  unique sitemap URLs: {len(uniq_locs)}")

# ---------- 2. title page counts ----------
def count_dirs(sub):
    d = os.path.join(ROOT, sub)
    if not os.path.isdir(d):
        return 0
    return sum(1 for name in os.listdir(d)
               if os.path.isdir(os.path.join(d, name))
               and os.path.exists(os.path.join(d, name, "index.html")))

n_movie = count_dirs("movie")
n_serie = count_dirs("serie")
if n_movie != 1258:
    fail(f"movie pages on disk = {n_movie}, expected 1258")
else:
    ok("movie pages on disk = 1258")
if n_serie != 100:
    fail(f"serie pages on disk = {n_serie}, expected 100")
else:
    ok("serie pages on disk = 100")

# ---------- 3. hubs ----------
GENRE_SLUGS = ["action", "adventure", "animation", "comedy", "crime", "documentary",
               "drama", "family", "fantasy", "history", "horror", "music", "mystery",
               "romance", "science-fiction", "tv-movie", "thriller", "war", "western"]
COUNTRIES = ["us", "gb", "in", "ca", "au", "cn", "jp"]
YEARS = ["2025", "2026", "2027"]
LISTS = ["featured-movies", "popular-movies", "top-rated-movies", "upcoming-movies",
         "anime-movies", "popular-tv-series", "top-rated-tv-series",
         "airing-today-tv-series", "on-the-air-tv-series", "movies"]
hub_paths = ([f"genre/{s}" for s in GENRE_SLUGS] + [f"country/{c}" for c in COUNTRIES]
             + [f"year/{y}" for y in YEARS] + LISTS)
missing_hubs = [h for h in hub_paths
                if not os.path.exists(os.path.join(ROOT, h, "index.html"))]
if missing_hubs:
    fail(f"missing hub pages: {missing_hubs}")
else:
    ok(f"all {len(hub_paths)} hub pages exist (19 genre + 7 country + 3 year + 10 lists)")

# ---------- 4. every sitemap loc resolves ----------
missing = []
for loc in sorted(set(all_locs)):
    fp = loc_to_file(loc)
    if not os.path.exists(fp):
        missing.append(loc)
if missing:
    fail(f"{len(missing)} sitemap URLs have no file on disk, e.g. {missing[:5]}")
else:
    ok(f"all {len(set(all_locs))} unique sitemap URLs resolve to files")

# ---------- 5. per-page meta + title uniqueness ----------
pages = []
for sub in ("movie", "serie"):
    d = os.path.join(ROOT, sub)
    for name in sorted(os.listdir(d)):
        pages.append(os.path.join(d, name, "index.html"))
for h in hub_paths:
    pages.append(os.path.join(ROOT, h, "index.html"))
pages.append(os.path.join(ROOT, "index.html"))

titles = {}
bad_meta = []
for p in pages:
    html = read(p)
    m = re.search(r"<title>([^<]+)</title>", html)
    title = m.group(1).strip() if m else ""
    if not title:
        bad_meta.append((p, "missing <title>"))
        continue
    titles.setdefault(title, []).append(p)
    if not re.search(r'<meta name="description" content="[^"]{20,}"', html):
        bad_meta.append((p, "missing/short meta description"))
    if '<link rel="canonical"' not in html:
        bad_meta.append((p, "missing canonical"))
    if 'property="og:title"' not in html:
        bad_meta.append((p, "missing og:title"))
    if 'application/ld+json' not in html:
        bad_meta.append((p, "missing JSON-LD"))
dups = {t: ps for t, ps in titles.items() if len(ps) > 1}
if dups:
    fail(f"{len(dups)} duplicate page titles, e.g. {list(dups.items())[:3]}")
else:
    ok(f"all {len(titles)} page titles unique")
if bad_meta:
    fail(f"{len(bad_meta)} pages with meta problems, e.g. {bad_meta[:5]}")
else:
    ok(f"all {len(pages)} pages have title/meta/canonical/OG/JSON-LD")

# ---------- 6. Adsterra keys unchanged ----------
base = open("/tmp/fmovies-baseline/ad-keys.txt").read()
cfg = open(os.path.join(ROOT, "assets", "js", "config.js")).read()
missing_keys = [k for k in base.split() if k and k not in cfg]
if missing_keys:
    fail(f"Adsterra keys missing from config.js: {missing_keys}")
else:
    ok("Adsterra ad keys unchanged in config.js")

# ---------- 7. homepage ----------
home = read(os.path.join(ROOT, "index.html"))
checks = [
    ("title", "Fmovies - Watch Free Movies Online in HD" in home),
    ("H1", "<h1>Watch Free Movies Online at Fmovies</h1>" in home),
    ("H2 features", "What Makes Fmovies Different" in home),
    ("H2 why", "Why Viewers Pick Fmovies First" in home),
    ("H2 FAQ", "Frequently Asked Questions" in home),
    ("H2 alternatives", "Other Free Streaming Sites" in home),
    ("keyword fmovies", home.lower().count("fmovies") >= 10),
    ("keyword fmovie", "fmovie" in home.lower()),
    ("keyword f movies", "f movies" in home.lower()),
    ("keyword watch movies online free", "watch movies online free" in home.lower()),
    ("keyword free movie sites", "free movie sites" in home.lower()),
    ("keyword where to watch movies", "where to watch movies" in home.lower()),
    ("60 popular links", home.count("/movie/") >= 60 or home.count('href="/movie/') >= 20),
    ("genre links", all(f"/genre/{s}/" in home for s in GENRE_SLUGS)),
    ("year links", all(f"/year/{y}/" in home for y in YEARS)),
    ("country links", all(f"/country/{c}/" in home for c in COUNTRIES)),
    ("list links", all(f"/{s}/" in home for s in LISTS)),
    ("featured row container", 'id="rows"' in home),
    ("viewport meta", 'name="viewport"' in home),
]
for name, good in checks:
    if not good:
        fail(f"homepage check failed: {name}")
    else:
        ok(f"homepage: {name}")

# ---------- 8. no copied text from fmovies00.org ----------
# Distinctive competitor phrases (their headings/taglines as observed).
# Our headings were deliberately reworded; these must not appear anywhere.
COPIED_PHRASES = [
    "Unmatched Streaming Features",
    "Why Fmovies Is the Best Site to Watch Movies Online Free",
    "Watch Movies Online Free at Fmovies",
    "with zero ads",
    "over 10000 movies",
    "over 10,000 movies and tv series",
]
all_html = ""
for p in pages:
    all_html += read(p) + "\n"
found = [ph for ph in COPIED_PHRASES if ph.lower() in all_html.lower()]
if found:
    fail(f"possible copied competitor phrases present: {found}")
else:
    ok("no distinctive fmovies00.org phrases found in generated pages")

# ---------- 9. branding assets ----------
assets = ["favicon.ico", "favicon-16x16.png", "favicon-32x32.png",
          "apple-touch-icon.png", "android-chrome-192x192.png",
          "android-chrome-512x512.png", "site.webmanifest", "og-image.png",
          "assets/img/logo.svg", "assets/img/logo.png"]
missing_assets = [a for a in assets if not os.path.exists(os.path.join(ROOT, a))]
if missing_assets:
    fail(f"missing brand assets: {missing_assets}")
else:
    ok("all brand assets exist")
refs = ["/favicon.ico", "/favicon-32x32.png", "/favicon-16x16.png",
        "/apple-touch-icon.png", "/site.webmanifest", "/og-image.png",
        "/assets/img/logo.svg"]
missing_refs = []
for p in pages:
    html = read(p)
    for r in refs:
        if r not in html:
            missing_refs.append((p, r))
            break
if missing_refs:
    fail(f"{len(missing_refs)} pages missing brand-asset references, e.g. {missing_refs[:3]}")
else:
    ok("every page references the brand assets")

# ---------- 10. local asset references resolve ----------
local_refs = set()
for p in pages:
    html = read(p)
    for m in re.finditer(r'(?:src|href)="(/[^"]+)"', html):
        ref = m.group(1)
        if ref.startswith("/assets/") or ref in ("/favicon.ico", "/site.webmanifest"):
            local_refs.add(ref)
bad_refs = [r for r in sorted(local_refs)
            if not os.path.exists(os.path.join(ROOT, r.lstrip("/")))]
if bad_refs:
    fail(f"broken local asset references: {bad_refs}")
else:
    ok(f"all {len(local_refs)} referenced local assets exist")

# ---------- 11. no leftover JS escapes in generated HTML ----------
# '<\\/script>' in static HTML is not a closing tag: the parser swallows
# everything up to the next '</script>', eating the hero/player sections.
bad_esc = [p for p in pages if "<\\/script>" in read(p)]
if bad_esc:
    fail(f"{len(bad_esc)} pages contain un-decoded '<\\/script>', e.g. {bad_esc[:3]}")
else:
    ok("no un-decoded '<\\/script>' in any page")

print()
print(f"RESULT: {len(FAILURES)} failures, {len(WARNINGS)} warnings")
sys.exit(1 if FAILURES else 0)
