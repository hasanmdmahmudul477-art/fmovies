#!/usr/bin/env python3
"""Generate static SEO pages (one per popular movie/TV title) for CineWave.

Each page has real meta tags, Open Graph, JSON-LD and crawlable content so
Google can index individual titles. "Watch Now" deep-links into the SPA.

Usage: python3 tools/gen_seo_pages.py
"""
import json, re, time, html, urllib.request, urllib.parse, os, sys

SITE_URL = "https://www.cinewave.jo3.org"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE_DIR = os.path.join(ROOT, "title")
MAX_TITLES = 600
REQ_PER_SEC = 4

def get_api_key():
    src = open(os.path.join(ROOT, "assets/js/config.js")).read()
    m = re.search(r'TMDB_API_KEY:\s*"([^"]+)"', src)
    if not m:
        sys.exit("TMDB API key not found in config.js")
    return m.group(1)

def get_socialbar():
    src = open(os.path.join(ROOT, "assets/js/config.js")).read()
    m = re.search(r"socialBar:\s*`(.*?)`", src, re.S)
    return m.group(1).strip() if m else ""

API_KEY = get_api_key()
SOCIALBAR = get_socialbar()
_last = [0.0]

def api(path, params=None):
    # throttle
    dt = time.time() - _last[0]
    if dt < 1.0 / REQ_PER_SEC:
        time.sleep(1.0 / REQ_PER_SEC - dt)
    q = dict(params or {})
    q["api_key"] = API_KEY
    q["language"] = "en-US"
    url = "https://api.themoviedb.org/3" + path + "?" + urllib.parse.urlencode(q)
    _last[0] = time.time()
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)

def slugify(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60].strip("-") or "title"

def esc(s):
    return html.escape(s or "", quote=True)

def collect():
    """Gather candidate (type, id) pairs from TMDB list endpoints."""
    jobs = [
        ("trending/all/week", {}, 2),
        ("movie/popular", {}, 6),
        ("movie/top_rated", {}, 6),
        ("movie/now_playing", {}, 3),
        ("tv/popular", {}, 4),
        ("tv/top_rated", {}, 4),
        ("tv/airing_today", {}, 2),
    ]
    seen, out = set(), []
    for path, params, pages in jobs:
        for p in range(1, pages + 1):
            try:
                data = api("/" + path, {**params, "page": p})
            except Exception as e:
                print("list failed", path, p, e)
                continue
            for it in data.get("results", []):
                mt = it.get("media_type") or ("movie" if path.startswith("movie") else "tv")
                if mt not in ("movie", "tv"):
                    continue
                key = (mt, it["id"])
                if key not in seen:
                    seen.add(key)
                    out.append(key)
            if p >= data.get("total_pages", p):
                break
    return out[:MAX_TITLES]

PAGE_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{head_title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{keywords}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="video.{og_type}">
<meta property="og:title" content="{head_title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="CineWave">
{og_image}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{head_title}">
<meta name="twitter:description" content="{meta_desc}">
{tw_image}
<script type="application/ld+json">{jsonld}</script>
<style>
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b0e17;color:#e8ecf4}}
a{{color:#e50914}}.wrap{{max-width:1000px;margin:0 auto;padding:0 16px}}
.topbar{{display:flex;align-items:center;justify-content:space-between;padding:14px 0;border-bottom:1px solid #1c2333}}
.logo{{font-size:22px;font-weight:800;color:#e50914;text-decoration:none}}
.hero{{display:flex;gap:22px;padding:26px 0;flex-wrap:wrap}}
.poster{{width:220px;max-width:40vw;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.5)}}
.info{{flex:1;min-width:240px}}
h1{{margin:0 0 8px;font-size:30px}}
.meta{{color:#9aa4bd;margin:6px 0}}
.stars{{color:#f5c518;font-weight:700}}
.overview{{line-height:1.65;color:#cdd5e4;margin:14px 0}}
.watch{{display:inline-block;background:#e50914;color:#fff!important;font-weight:700;padding:13px 34px;border-radius:8px;text-decoration:none;font-size:17px;margin:10px 0}}
.watch:hover{{background:#f6121d}}
.sec{{padding:8px 0 22px}}.sec h2{{font-size:20px;border-left:4px solid #e50914;padding-left:10px}}
.cast{{display:flex;gap:14px;overflow-x:auto;padding:4px 0}}
.person{{min-width:110px;text-align:center}}.person img{{width:110px;height:165px;object-fit:cover;border-radius:8px;background:#1c2333}}
.person div{{font-size:13px;margin-top:6px}}.person small{{color:#9aa4bd}}
.rel{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px}}
.rel a{{background:#141a29;border-radius:8px;overflow:hidden;text-decoration:none;color:#e8ecf4}}
.rel img{{width:100%;aspect-ratio:2/3;object-fit:cover;background:#1c2333}}
.rel span{{display:block;padding:8px 10px;font-size:13px}}
footer{{border-top:1px solid #1c2333;padding:20px 0;color:#9aa4bd;font-size:13px;text-align:center}}
.faq p{{color:#cdd5e4;line-height:1.6}}
</style>
</head>
<body>
<div class="wrap">
<div class="topbar"><a class="logo" href="/">CineWave</a><a href="/">Home</a></div>
<div class="hero">
<img class="poster" src="{poster}" alt="{title} poster" loading="eager">
<div class="info">
<h1>{title} ({year})</h1>
<div class="meta"><span class="stars">★ {rating}</span> &nbsp;·&nbsp; {year} &nbsp;·&nbsp; {extra_meta}</div>
<div class="meta">{genres}</div>
<a class="watch" href="{watch_url}">▶ Watch Now</a>
<p class="overview">{overview}</p>
</div>
</div>
<div class="sec faq">
<h2>About {title}</h2>
{about_paras}
</div>
<div class="sec">
<h2>Top Cast</h2>
<div class="cast">{cast_html}</div>
</div>
<div class="sec">
<h2>You May Also Like</h2>
<div class="rel">{rel_html}</div>
</div>
<footer>CineWave — watch movies and TV shows online in HD.<br>Data and artwork provided by TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.</footer>
</div>
{socialbar}
</body>
</html>
"""

def build_page(tp, d, related):
    is_movie = tp == "movie"
    title = d.get("title") or d.get("name") or "Untitled"
    date = d.get("release_date") or d.get("first_air_date") or ""
    year = date[:4] or "—"
    rating = d.get("vote_average") or 0
    rating_s = f"{rating:.1f}/10" if rating else "NR"
    overview = d.get("overview") or ""
    genres = ", ".join(g["name"] for g in d.get("genres", [])) or "—"
    poster = ("https://image.tmdb.org/t/p/w500" + d["poster_path"]) if d.get("poster_path") else ""
    backdrop = ("https://image.tmdb.org/t/p/w1280" + d["backdrop_path"]) if d.get("backdrop_path") else ""
    kind = "Movie" if is_movie else "TV Series"
    if is_movie:
        rt = d.get("runtime")
        extra = f"{rt} min" if rt else kind
    else:
        ns = d.get("number_of_seasons")
        extra = f"{ns} Season{'s' if ns != 1 else ''}" if ns else kind
    slug = slugify(title)
    fname = f"{'m' if is_movie else 's'}-{d['id']}-{slug}.html"
    canonical = f"{SITE_URL}/title/{fname}"
    watch_url = f"{SITE_URL}/?watch={'movie' if is_movie else 'tv'}-{d['id']}"

    head_title = f"Watch {title} ({year}) Full {kind} Online in HD - CineWave"
    meta_desc = (f"Watch {title} ({year}) full {kind.lower()} online in HD on CineWave. "
                 f"{overview[:140]}".strip())[:160]
    keywords = f"{title}, {title} {year}, watch {title} online, {title} full {kind.lower()}, {title} cast"

    cast = (d.get("credits", {}).get("cast") or [])[:8]
    cast_html = "".join(
        f'<div class="person"><img loading="lazy" src="https://image.tmdb.org/t/p/w185{c["profile_path"]}" alt="{esc(c["name"])}">'
        f'<div>{esc(c["name"])}<br><small>{esc(c.get("character") or "")}</small></div></div>'
        if c.get("profile_path") else
        f'<div class="person"><div>{esc(c["name"])}<br><small>{esc(c.get("character") or "")}</small></div></div>'
        for c in cast
    ) or "<p>No cast info.</p>"

    about_paras = (
        f"<p><strong>{esc(title)}</strong> ({year}) is a {esc(genres.lower())} {kind.lower()} "
        f"rated <strong>{rating_s}</strong> by viewers. {esc(overview)}</p>"
        f"<p>Stream <strong>{esc(title)}</strong> full {kind.lower()} online in HD quality on CineWave — "
        f"no sign-up needed, just press Watch Now and pick a server. You can also browse the cast, "
        f"watch the trailer and explore similar {kind.lower()}s below.</p>"
    )

    rel_html = "".join(
        f'<a href="{SITE_URL}/title/{r["file"]}"><img loading="lazy" src="{r["poster"]}" alt="{esc(r["title"])}"><span>{esc(r["title"])} ({r["year"]})</span></a>'
        for r in related
    )

    schema_type = "Movie" if is_movie else "TVSeries"
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": title,
        "image": poster or backdrop,
        "description": overview[:300],
        "datePublished": date or None,
        "genre": [g["name"] for g in d.get("genres", [])],
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": round(rating, 1),
                            "ratingCount": d.get("vote_count", 0)} if rating else None,
        "url": canonical,
    }, ensure_ascii=False)
    jsonld = re.sub(r',\s*"[^"]+": null', '', jsonld)

    return fname, PAGE_TMPL.format(
        head_title=esc(head_title), meta_desc=esc(meta_desc), keywords=esc(keywords),
        canonical=canonical, og_type="movie" if is_movie else "tv_show",
        og_image=f'<meta property="og:image" content="{backdrop or poster}">' if (backdrop or poster) else "",
        tw_image=f'<meta name="twitter:image" content="{backdrop or poster}">' if (backdrop or poster) else "",
        jsonld=jsonld, poster=poster, title=esc(title), year=year, rating=rating_s,
        extra_meta=esc(extra), genres=esc(genres), watch_url=watch_url,
        overview=esc(overview), about_paras=about_paras, cast_html=cast_html,
        rel_html=rel_html, socialbar=SOCIALBAR,
    )

def main():
    os.makedirs(TITLE_DIR, exist_ok=True)
    print("collecting title list...")
    cands = collect()
    print(f"{len(cands)} candidates")
    pages = []  # dicts: type,id,title,year,poster,file
    details = {}
    for i, (tp, tid) in enumerate(cands):
        try:
            d = api(f"/{tp}/{tid}", {"append_to_response": "credits"})
        except Exception as e:
            print("detail failed", tp, tid, e)
            continue
        title = d.get("title") or d.get("name")
        if not title or not d.get("overview") or len(d["overview"]) < 40 or not d.get("poster_path"):
            continue
        if d.get("adult"):
            continue
        details[(tp, tid)] = d
        date = d.get("release_date") or d.get("first_air_date") or ""
        pages.append({"type": tp, "id": tid, "title": title, "year": date[:4] or "—",
                      "poster": "https://image.tmdb.org/t/p/w342" + d["poster_path"]})
        print(f"[{i+1}/{len(cands)}] {tp} {tid} {title}")
    print(f"{len(pages)} pages to write")

    # related: deterministic neighbors of same type (crawl graph)
    by_type = {}
    for idx, p in enumerate(pages):
        by_type.setdefault(p["type"], []).append(idx)
    for idx, p in enumerate(pages):
        pool = by_type[p["type"]]
        at = pool.index(idx)
        rel_idx = [pool[(at + k) % len(pool)] for k in range(1, 9) if len(pool) > 1]
        d = details[(p["type"], p["id"])]
        related = []
        for r in rel_idx:
            rp = pages[r]
            rd = details[(rp["type"], rp["id"])]
            rslug = slugify(rp["title"])
            related.append({"file": f"{'m' if rp['type']=='movie' else 's'}-{rp['id']}-{rslug}.html",
                            "poster": rp["poster"], "title": rp["title"], "year": rp["year"]})
        fname, html_doc = build_page(p["type"], d, related)
        p["file"] = fname
        # fix related file names (computed before p['file'] existed — recompute not needed; rel uses own slugs)
        with open(os.path.join(TITLE_DIR, fname), "w", encoding="utf-8") as f:
            f.write(html_doc)

    # sitemap
    today = time.strftime("%Y-%m-%d")
    urls = [f"  <url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    for p in pages:
        urls.append(f"  <url><loc>{SITE_URL}/title/{p['file']}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "\n".join(urls) + "\n</urlset>\n")
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    print(f"DONE: {len(pages)} title pages + sitemap.xml + robots.txt")

if __name__ == "__main__":
    main()
