#!/usr/bin/env python3
"""Generate the Fmovies static site: movie/serie pages, hub pages, sitemap,
robots.txt and the rendered homepage — from tools/data/details.json.

All visible copy is written originally for this site. Movie facts (titles,
years, ratings, cast, overviews) come from TMDB, which is factual data.
The TMDB API key is never printed or logged.

Usage: python3 tools/generate_fmovies.py
Outputs (under ~/workspace/movie-site/):
  movie/<slug>-<year>-<id>x/index.html   (1,258 pages)
  serie/<slug>-<year>-<id>x/index.html   (100 pages)
  genre/<slug>/index.html                (19 hubs)
  country/<code>/index.html              (7 hubs)
  year/<yyyy>/index.html                 (3 hubs)
  <list-hub>/index.html                  (10 hubs)
  index.html                             (rendered from tools/homepage_template.html)
  sitemap.xml (index) + sitemap-0..14.xml + sitemap-post.xml  (2,011 <loc> total)
  robots.txt
"""
import html, json, os, re, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tools", "data")
DETAILS = os.path.join(DATA, "details.json")
SELECTED = os.path.join(DATA, "selected.json")
TEMPLATE = os.path.join(ROOT, "tools", "homepage_template.html")

SITE = "https://www.fmovies.jo3.org"
LASTMOD = "2026-11-10"
MOVIE_TARGET = 1258
TV_TARGET = 100

GENRES = [  # (tmdb id, name, slug) — the 19 hubs
    (28, "Action", "action"), (12, "Adventure", "adventure"),
    (16, "Animation", "animation"), (35, "Comedy", "comedy"),
    (80, "Crime", "crime"), (99, "Documentary", "documentary"),
    (18, "Drama", "drama"), (10751, "Family", "family"),
    (14, "Fantasy", "fantasy"), (36, "History", "history"),
    (27, "Horror", "horror"), (10402, "Music", "music"),
    (9648, "Mystery", "mystery"), (10749, "Romance", "romance"),
    (878, "Science Fiction", "science-fiction"), (10770, "TV Movie", "tv-movie"),
    (53, "Thriller", "thriller"), (10752, "War", "war"),
    (37, "Western", "western"),
]
GENRE_BY_ID = {g[0]: g for g in GENRES}
COUNTRIES = [("us", "United States"), ("gb", "United Kingdom"),
             ("in", "India"), ("ca", "Canada"), ("au", "Australia"),
             ("cn", "China"), ("jp", "Japan")]
YEARS = ["2025", "2026", "2027"]
LISTS = ["featured-movies", "popular-movies", "top-rated-movies",
         "upcoming-movies", "anime-movies", "popular-tv-series",
         "top-rated-tv-series", "airing-today-tv-series",
         "on-the-air-tv-series", "movies"]

SOCIALBAR = ""
AD_HEADER = ""
AD_FOOTER = ""


def js_unescape(s):
    """Decode the escapes used in config.js template literals (\" and \\/).
    config.js stores ad HTML as JS strings, so a raw copy would leave
    '<\\/script>' in the static HTML — which the HTML parser does NOT treat
    as a closing tag, swallowing everything up to the next '</script>' and
    breaking the page. Decoding restores plain '</script>' / '"'."""
    return (s.replace("\\\\", "\x00")
             .replace("\\/", "/")
             .replace('\\"', '"')
             .replace("\\n", "\n")
             .replace("\\t", "\t")
             .replace("\x00", "\\"))


def load_ads():
    """Read the CURRENT Adsterra codes from config.js (unchanged)."""
    global SOCIALBAR, AD_HEADER, AD_FOOTER
    src = open(os.path.join(ROOT, "assets", "js", "config.js")).read()
    m = re.search(r"socialBar:\s*`(.*?)`", src, re.S)
    SOCIALBAR = js_unescape(m.group(1).strip()) if m else ""
    m = re.search(r"header:\s*`(.*?)`,\s*\n\s*modalMain", src, re.S)
    AD_HEADER = js_unescape(m.group(1).strip()) if m else ""
    m = re.search(r"footer:\s*`(.*?)`,\s*\n\s*socialBar", src, re.S)
    AD_FOOTER = js_unescape(m.group(1).strip()) if m else ""
    for name, code in (("header", AD_HEADER), ("footer", AD_FOOTER),
                       ("socialBar", SOCIALBAR)):
        assert "<\\/script>" not in code and '\\"' not in code, \
            f"ad code {name} still contains JS escapes"


def esc(s):
    return html.escape(s or "", quote=True)


def slugify(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60].strip("-") or "title"


def two_sentences(overview):
    """First two sentences of the TMDB overview."""
    ov = (overview or "").strip()
    if not ov:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", ov)
    return " ".join(parts[:2])


def first_names(text, n=2):
    return text


class Title:
    def __init__(self, key, d):
        self.key = key
        self.type = "movie" if key.startswith("movie:") else "tv"
        self.id = d["id"]
        self.title = d.get("title") or d.get("name") or "Untitled"
        self.orig_lang = d.get("original_language") or ""
        date = d.get("release_date") or d.get("first_air_date") or ""
        self.year = date[:4] or "—"
        self.date = date
        self.rating = d.get("vote_average") or 0
        self.votes = d.get("vote_count") or 0
        self.popularity = d.get("popularity") or 0
        self.overview = d.get("overview") or ""
        self.genres = d.get("genres") or []
        self.genre_ids = [g["id"] for g in self.genres]
        self.genre_names = [g["name"] for g in self.genres]
        self.poster = ("https://image.tmdb.org/t/p/w500" + d["poster_path"]) if d.get("poster_path") else ""
        self.poster_small = ("https://image.tmdb.org/t/p/w342" + d["poster_path"]) if d.get("poster_path") else ""
        self.backdrop = ("https://image.tmdb.org/t/p/w1280" + d["backdrop_path"]) if d.get("backdrop_path") else ""
        self.runtime = d.get("runtime")
        self.seasons = d.get("number_of_seasons")
        self.countries = [c.get("iso_3166_1", "").lower() for c in d.get("production_countries", [])]
        self.country_names = [c.get("name", "") for c in d.get("production_countries", [])]
        crew = (d.get("credits", {}) or {}).get("crew", []) or []
        dirs = [c.get("name") for c in crew if c.get("job") == "Director" and c.get("name")]
        self.director = dirs[0] if dirs else ""
        cast = (d.get("credits", {}) or {}).get("cast", []) or []
        self.cast = cast[:8]
        kw = d.get("keywords", {}) or {}
        kws = kw.get("keywords") or kw.get("results") or []
        self.keywords = [k.get("name") for k in kws if k.get("name")][:12]
        self.companies = [c.get("name") for c in (d.get("production_companies", []) or []) if c.get("name")][:5]
        self.sources = d.get("_sources", [])
        self.slug = slugify(self.title)
        # set by load_titles() when two titles share (type, title, year)
        self.disambig = ""

    @property
    def kind_label(self):
        return "Movie" if self.type == "movie" else "TV Series"

    @property
    def dir_name(self):
        return "movie" if self.type == "movie" else "serie"

    @property
    def url_path(self):
        return f"/{self.dir_name}/{self.slug}-{self.year}-{self.id}x/"

    @property
    def canonical(self):
        return SITE + self.url_path

    @property
    def head_title(self):
        if self.disambig:
            return (f"Watch {self.title} ({self.year}) by {self.disambig} "
                    f"{self.kind_label} Online Free | Fmovies")
        return f"Watch {self.title} ({self.year}) {self.kind_label} Online Free | Fmovies"

    @property
    def extra_meta(self):
        if self.type == "movie":
            return f"{self.runtime} min" if self.runtime else "Movie"
        return f"{self.seasons} Season{'s' if self.seasons != 1 else ''}" if self.seasons else "TV Series"

    def tags(self):
        out = []
        for t in self.genre_names + self.keywords + self.companies:
            t = (t or "").strip()
            if t and t.lower() not in [x.lower() for x in out]:
                out.append(t)
        out.append(f"{self.title} {self.year}")
        out.append(f"watch {self.title} online free")
        return out[:20]

    def desc_short(self):
        return two_sentences(self.overview)


def load_titles():
    details = json.load(open(DETAILS, encoding="utf-8"))
    selected = json.load(open(SELECTED, encoding="utf-8"))
    movies, tvs = [], []
    for c in selected:
        key = f"{c['type']}:{c['id']}"
        d = details.get(key)
        if not d:
            continue
        t = Title(key, d)
        if t.type == "movie":
            if len(movies) < MOVIE_TARGET:
                movies.append(t)
        else:
            if len(tvs) < TV_TARGET:
                tvs.append(t)
    # Disambiguate same (type, title, year): the most popular keeps the plain
    # title; the rest get "by {Director}" in their <title>/OG title so every
    # page title stays unique (e.g. two different "The Odyssey" films, 2026).
    from collections import defaultdict
    groups = defaultdict(list)
    for t in movies + tvs:
        groups[(t.type, t.title, t.year)].append(t)
    for key, g in groups.items():
        if len(g) < 2:
            continue
        g.sort(key=lambda x: -x.popularity)
        for t in g[1:]:
            t.disambig = t.director or (t.genre_names[0] if t.genre_names else "Film")
            print(f"  disambiguated: {key} -> by {t.disambig} (id {t.id})")
    return movies, tvs

# ---------------- shared chrome ----------------
HEAD_LINKS = """<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#00b3a6">
<meta property="og:image" content="https://www.fmovies.jo3.org/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:image" content="https://www.fmovies.jo3.org/og-image.png">"""

HEADER = """<header class="topbar">
<div class="topbar-inner">
<a class="logo" href="/" aria-label="Fmovies home"><img src="/assets/img/logo.svg" alt="Fmovies" width="220" height="48"></a>
<nav class="mainnav">
<a href="/">Home</a>
<a href="/movies/">Movies</a>
<a href="/popular-tv-series/">TV Series</a>
<a href="/#browse-genres">Genres</a>
</nav>
<form class="search" action="/" method="get" role="search">
<input type="search" name="q" placeholder="Search movies, shows..." aria-label="Search movies and shows" autocomplete="off">
</form>
<a class="login-btn" href="/#browse-genres">Login</a>
</div>
</header>"""

FOOTER = """<footer>
<div class="foot-inner">
<a class="logo" href="/"><img src="/assets/img/logo.svg" alt="Fmovies" width="220" height="48"></a>
<nav class="footnav">
<a href="/movies/">Movies</a><a href="/popular-tv-series/">TV Series</a>
<a href="/featured-movies/">Featured</a><a href="/top-rated-movies/">Top Rated</a>
<a href="/genre/action/">Action</a><a href="/genre/comedy/">Comedy</a>
<a href="/genre/drama/">Drama</a><a href="/genre/horror/">Horror</a>
</nav>
<p class="copy">Copyright &copy; 2026 - Fmovies</p>
<p class="tmdb-note">Fmovies — watch free movies and TV shows online in HD.<br>Data and artwork provided by TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.</p>
</div>
</footer>"""

PAGE_CSS = """
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0a1424;color:#e8eef7}
a{color:#00c2b2}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
.topbar{background:#0d1b2e;border-bottom:1px solid #1b2f47;position:sticky;top:0;z-index:50}
.topbar-inner{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:22px;flex-wrap:wrap}
.logo img{display:block;height:40px;width:auto}
.mainnav{display:flex;gap:18px}
.mainnav a{color:#c7d3e2;text-decoration:none;font-size:15px;font-weight:600}
.mainnav a:hover{color:#fff}
.search{margin-left:auto}
.search input{background:#0a1424;border:1px solid #2a4258;color:#fff;border-radius:20px;padding:8px 16px;width:210px;font-size:14px;outline:none}
.search input:focus{border-color:#00b3a6}
.login-btn{background:#00b3a6;color:#fff!important;font-weight:700;padding:8px 18px;border-radius:8px;text-decoration:none;font-size:14px}
.login-btn:hover{background:#00c9b8}
.hero{display:flex;gap:22px;padding:26px 0;flex-wrap:wrap}
.poster{width:220px;max-width:40vw;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.5)}
.info{flex:1;min-width:240px}
h1{margin:0 0 8px;font-size:30px;line-height:1.2}
.meta{color:#8fa3bd;margin:6px 0}
.stars{color:#f5c518;font-weight:700}
.hd{background:#00b3a6;color:#fff;font-size:12px;font-weight:800;padding:2px 8px;border-radius:5px;vertical-align:middle}
.overview{line-height:1.65;color:#cdd5e4;margin:14px 0}
.watch{display:inline-block;background:#00b3a6;color:#fff!important;font-weight:700;padding:13px 30px;border-radius:8px;text-decoration:none;font-size:16px;margin:10px 10px 10px 0}
.watch:hover{background:#00c9b8}
.download{display:inline-block;background:#13263f;color:#e8eef7!important;font-weight:700;padding:13px 30px;border-radius:8px;text-decoration:none;font-size:16px;margin:10px 0;border:1px solid #2a4258}
.download:hover{border-color:#00b3a6}
.player{margin:10px 0 22px}
.video-wrap{position:relative;padding-bottom:56.25%;height:0;background:#000;border-radius:10px;overflow:hidden}
.video-wrap iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.server-row{display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
.server-row span{color:#8fa3bd;font-size:13px}
.server-row button{background:#13263f;color:#c7d3e2;border:1px solid #2a4258;border-radius:16px;padding:6px 14px;font-size:13px;cursor:pointer}
.server-row button.on{background:#00b3a6;border-color:#00b3a6;color:#fff}
.layout{display:flex;gap:28px;align-items:flex-start}
.main{flex:1;min-width:0}
.side{flex:0 0 250px}
.side h3{font-size:16px;border-left:4px solid #00b3a6;padding-left:10px;margin:22px 0 12px}
.side a{display:flex;gap:10px;text-decoration:none;color:#e8eef7;margin-bottom:12px}
.side a img{width:52px;height:78px;object-fit:cover;border-radius:6px;background:#13263f}
.side a span{font-size:13px;line-height:1.4}
.side a small{color:#8fa3bd;display:block;margin-top:3px}
.sec{padding:8px 0 22px}.sec h2{font-size:20px;border-left:4px solid #00b3a6;padding-left:10px}
.cast{display:flex;gap:14px;overflow-x:auto;padding:4px 0}
.person{min-width:110px;text-align:center}.person img{width:110px;height:165px;object-fit:cover;border-radius:8px;background:#13263f}
.person div{font-size:13px;margin-top:6px}.person small{color:#8fa3bd}
.rel{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px}
.rel a{background:#101d33;border-radius:8px;overflow:hidden;text-decoration:none;color:#e8eef7}
.rel img{width:100%;aspect-ratio:2/3;object-fit:cover;background:#13263f}
.rel span{display:block;padding:8px 10px;font-size:13px}
.tags{display:flex;gap:8px;flex-wrap:wrap}
.tags a{background:#101d33;border:1px solid #1b2f47;color:#9fb2c8;font-size:12px;padding:5px 12px;border-radius:14px;text-decoration:none}
.tags a:hover{border-color:#00b3a6;color:#fff}
.detail-table{width:100%;border-collapse:collapse;font-size:14px}
.detail-table td{padding:7px 4px;border-bottom:1px solid #16283d;color:#cdd5e4}
.detail-table td:first-child{color:#8fa3bd;width:110px}
.comments textarea,.comments input{width:100%;background:#101d33;border:1px solid #2a4258;color:#fff;border-radius:8px;padding:10px 12px;font-size:14px;margin:6px 0;box-sizing:border-box;font-family:inherit}
.comments button{background:#00b3a6;color:#fff;border:none;font-weight:700;padding:10px 24px;border-radius:8px;cursor:pointer;font-size:14px}
.comments .note{color:#8fa3bd;font-size:12px;margin-top:8px}
footer{border-top:1px solid #1b2f47;padding:26px 0 30px;color:#8fa3bd;font-size:13px;text-align:center;margin-top:20px}
.foot-inner{max-width:1100px;margin:0 auto;padding:0 16px}
.footnav{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;margin:14px 0}
.footnav a{color:#9fb2c8;text-decoration:none;font-size:13px}
.footnav a:hover{color:#fff}
footer .copy{color:#c7d3e2}
footer .tmdb-note{margin-top:8px;font-size:12px;line-height:1.6}
.ad-slot{display:flex;justify-content:center;padding:14px 0}
.ad-slot iframe,.ad-slot img{max-width:100%}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px}
.grid a{background:#101d33;border-radius:10px;overflow:hidden;text-decoration:none;color:#e8eef7}
.grid img{width:100%;aspect-ratio:2/3;object-fit:cover;background:#13263f}
.grid .g-body{padding:10px 12px}
.grid .g-title{font-size:14px;font-weight:600}
.grid .g-sub{font-size:12px;color:#8fa3bd;margin-top:3px}
.grid .g-sub .stars{color:#f5c518}
.hub-intro{color:#cdd5e4;line-height:1.65;margin:6px 0 20px}
@media(max-width:760px){.layout{flex-direction:column;align-items:stretch}.main{width:100%}.side{flex:none;width:100%}.search{display:none}.mainnav{gap:12px}.hero{padding:18px 0}h1{font-size:24px}}
"""


def head_block(title, desc, canonical, og_type="website", keywords=""):
    kw = f'\n<meta name="keywords" content="{esc(keywords)}">' if keywords else ""
    return f"""<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">{kw}
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:site_name" content="Fmovies">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
{HEAD_LINKS}"""


def jsonld_movie(t):
    d = {
        "@context": "https://schema.org",
        "@type": "Movie" if t.type == "movie" else "TVSeries",
        "name": t.title,
        "image": t.poster or t.backdrop,
        "description": t.overview[:300],
        "datePublished": t.date or None,
        "genre": t.genre_names,
        "url": t.canonical,
    }
    if t.director:
        d["director"] = {"@type": "Person", "name": t.director}
    if t.cast:
        d["actor"] = [{"@type": "Person", "name": c.get("name")} for c in t.cast[:5] if c.get("name")]
    if t.rating:
        d["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": round(t.rating, 1),
                                "ratingCount": t.votes}
    if t.type == "movie" and t.runtime:
        d["duration"] = f"PT{t.runtime}M"
    js = json.dumps(d, ensure_ascii=False)
    js = re.sub(r',\s*"[^"]+": null', '', js)
    return js


def movie_page(t, related, most_viewed, recommended):
    is_movie = t.type == "movie"
    desc = two_sentences(t.overview)
    meta_desc = (f"Watch {t.title} ({t.year}) full {t.kind_label.lower()} online free in HD on Fmovies. "
                 f"{desc}"[:160]).strip()
    keywords = (f"{t.title}, {t.title} {t.year}, watch {t.title} online, "
                f"{t.title} full {t.kind_label.lower()}, {t.title} cast, fmovies")
    genres = ", ".join(t.genre_names) or "—"
    countries = ", ".join(t.country_names) or "—"
    rating_s = f"{t.rating:.1f}/10" if t.rating else "NR"
    votes_s = f"{t.votes:,} votes" if t.votes else ""
    if is_movie:
        srv1 = f"https://vidsrc.to/embed/movie/{t.id}"
        srv2 = f"https://vidsrc.xyz/embed/movie/{t.id}"
        watch_label = "Watch Movie"
    else:
        srv1 = f"https://vidsrc.to/embed/tv/{t.id}/1/1"
        srv2 = f"https://vidsrc.xyz/embed/tv/{t.id}/1/1"
        watch_label = "Watch TV Series"

    cast_html = "".join(
        f'<div class="person"><img loading="lazy" src="https://image.tmdb.org/t/p/w185{c["profile_path"]}" alt="{esc(c["name"])}">'
        f'<div>{esc(c["name"])}<br><small>{esc(c.get("character") or "")}</small></div></div>'
        if c.get("profile_path") else
        f'<div class="person"><div>{esc(c["name"])}<br><small>{esc(c.get("character") or "")}</small></div></div>'
        for c in t.cast
    ) or "<p>No cast information available.</p>"

    rel_html = "".join(
        f'<a href="{r.canonical}"><img loading="lazy" src="{r.poster_small}" alt="{esc(r.title)}">'
        f'<span>{esc(r.title)} ({r.year})</span></a>'
        for r in related
    )

    def side_list(items, title):
        rows = "".join(
            f'<a href="{x.canonical}"><img loading="lazy" src="{x.poster_small}" alt="{esc(x.title)}">'
            f'<span>{esc(x.title)}<small>{x.year} &middot; &#9733; {x.rating:.1f}</small></span></a>'
            for x in items
        )
        return f"<h3>{title}</h3>{rows}"

    tags_html = "".join(
        f'<a href="/movies/">#{esc(tag)}</a>' for tag in t.tags()
    )
    about = (
        f"<p><strong>{esc(t.title)}</strong> ({t.year}) is a {esc(', '.join(t.genre_names).lower())} "
        f"{t.kind_label.lower()} rated <strong>{rating_s}</strong> by viewers. {esc(desc)}</p>"
        f"<p>Stream <strong>{esc(t.title)}</strong> online free in HD quality on Fmovies — "
        f"no sign-up needed. Pick a server below and the episode starts right away. "
        f"You can also browse the cast, explore similar titles, and find more {t.kind_label.lower()}s "
        f"from the same genres.</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head_block(t.head_title, meta_desc, t.canonical, "video.movie" if is_movie else "video.tv_show", keywords)}
<script type="application/ld+json">{jsonld_movie(t)}</script>
<style>{PAGE_CSS}</style>
</head>
<body>
{HEADER}
<div class="ad-slot">{AD_HEADER}</div>
<div class="wrap">
<div class="hero">
<img class="poster" src="{t.poster}" alt="{esc(t.title)} poster" loading="eager">
<div class="info">
<h1>{esc(t.title)} ({t.year})</h1>
<div class="meta"><span class="stars">&#9733; {rating_s}</span> &nbsp;&middot;&nbsp; {votes_s} &nbsp;&middot;&nbsp; {t.year} &nbsp;&middot;&nbsp; {esc(t.extra_meta)} &nbsp;<span class="hd">HD</span></div>
<div class="meta">{esc(genres)}</div>
<a class="watch" href="#player" onclick="showPlayer();return false;">&#9654; {watch_label} &nbsp;QUALITY: 4K-HD</a>
<a class="download" href="{srv1}" target="_blank" rel="noopener">&#8681; Download &nbsp;QUALITY: 4K-HD</a>
<p class="overview">{esc(desc)}</p>
</div>
</div>
<div class="player" id="player" style="display:none">
<div class="server-row"><span>Server:</span>
<button type="button" class="on" onclick="setSrv(0,this)">Server 1</button>
<button type="button" onclick="setSrv(1,this)">Server 2</button>
</div>
<div class="video-wrap"><iframe id="player-frame" src="" title="Video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
</div>
<script>
var SRV=["{srv1}","{srv2}"];
function showPlayer(){{var p=document.getElementById('player');p.style.display='block';document.getElementById('player-frame').src=SRV[0];p.scrollIntoView({{behavior:'smooth'}});}}
function setSrv(i,btn){{document.getElementById('player-frame').src=SRV[i];var b=btn.parentNode.querySelectorAll('button');for(var k=0;k<b.length;k++)b[k].classList.remove('on');btn.classList.add('on');}}
</script>
<div class="layout">
<div class="main">
<div class="sec">
<h2>About {esc(t.title)}</h2>
{about}
</div>
<div class="sec">
<h2>Details</h2>
<table class="detail-table">
<tr><td>Title</td><td>{esc(t.title)}</td></tr>
<tr><td>Year</td><td>{t.year}</td></tr>
<tr><td>Rating</td><td>{rating_s} ({votes_s})</td></tr>
<tr><td>Genre</td><td>{esc(genres)}</td></tr>
<tr><td>Country</td><td>{esc(countries)}</td></tr>
<tr><td>Director</td><td>{esc(t.director) or "—"}</td></tr>
<tr><td>Quality</td><td>4K-HD</td></tr>
</table>
</div>
<div class="sec">
<h2>Top Cast</h2>
<div class="cast">{cast_html}</div>
</div>
<div class="sec">
<h2>Tags</h2>
<div class="tags">{tags_html}</div>
</div>
<div class="sec comments">
<h2>Comments</h2>
<form onsubmit="document.getElementById('cmt-note').style.display='block';this.reset();return false;">
<input type="text" name="name" placeholder="Your name" required>
<textarea name="comment" rows="3" placeholder="Share your thoughts about {esc(t.title)}..." required></textarea>
<button type="submit">Post Comment</button>
</form>
<p class="note" id="cmt-note" style="display:none">Thanks! Your comment is awaiting moderation and will appear shortly.</p>
</div>
<div class="sec">
<h2>Related {t.kind_label}s</h2>
<div class="rel">{rel_html}</div>
</div>
</div>
<div class="side">
{side_list(most_viewed, "MOST VIEWED")}
{side_list(recommended, "RECOMMENDED")}
</div>
</div>
</div>
<div class="ad-slot">{AD_FOOTER}</div>
{FOOTER}
{SOCIALBAR}
</body>
</html>
"""

# ---------------- hub pages ----------------
def hub_page(title, desc, canonical, h1, intro, items, kind_label):
    keywords = f"{title}, fmovies, watch movies online free, free movie sites"
    cards = "".join(
        f'<a href="{x.canonical}"><img loading="lazy" src="{x.poster_small}" alt="{esc(x.title)}">'
        f'<div class="g-body"><div class="g-title">{esc(x.title)}</div>'
        f'<div class="g-sub"><span class="stars">&#9733; {x.rating:.1f}</span> &middot; {x.year} &middot; {x.kind_label}</div></div></a>'
        for x in items
    )
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": title, "description": desc, "url": canonical,
        "hasPart": [{"@type": "ListItem", "position": i + 1, "url": x.canonical,
                     "name": x.title} for i, x in enumerate(items[:20])],
    }, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head_block(title, desc, canonical, "website", keywords)}
<script type="application/ld+json">{jsonld}</script>
<style>{PAGE_CSS}</style>
</head>
<body>
{HEADER}
<div class="wrap">
<div class="sec" style="padding-top:22px">
<h1>{esc(h1)}</h1>
<p class="hub-intro">{esc(intro)}</p>
<div class="grid">{cards}</div>
</div>
</div>
<div class="ad-slot">{AD_FOOTER}</div>
{FOOTER}
{SOCIALBAR}
</body>
</html>
"""


def hub_lists(movies, tvs):
    """Return (hub_url_path, hub_page_html) for all 39 hubs."""
    hubs = []
    by_genre = {g[0]: [] for g in GENRES}
    for t in movies + tvs:
        for gid in t.genre_ids:
            if gid in by_genre:
                by_genre[gid].append(t)
    for gid, name, slug in GENRES:
        items = sorted(by_genre[gid], key=lambda x: -x.popularity)[:20]
        hubs.append((f"/genre/{slug}/",
                     hub_page(f"{name} Movies - Watch Free Movies Online | Fmovies",
                              f"Watch the best {name.lower()} movies and TV series online free in HD on Fmovies. "
                              f"Browse top {name.lower()} titles, no sign-up needed.",
                              SITE + f"/genre/{slug}/", f"{name} Movies",
                              f"Explore {name.lower()} movies and TV shows on Fmovies. "
                              f"From new releases to all-time favourites, stream every {name.lower()} title "
                              f"in HD for free — pick a poster and press play.",
                              items, "Movies")))
    for code, name in COUNTRIES:
        items = sorted([t for t in movies + tvs if code in t.countries],
                       key=lambda x: -x.popularity)[:20]
        hubs.append((f"/country/{code}/",
                     hub_page(f"Movies from {name} - Watch Free Online | Fmovies",
                              f"Watch movies and TV series from {name} online free in HD on Fmovies.",
                              SITE + f"/country/{code}/", f"Movies from {name}",
                              f"Stream the best movies and TV shows from {name} on Fmovies — "
                              f"free in HD, no account needed.",
                              items, "Movies")))
    for y in YEARS:
        items = sorted([t for t in movies + tvs if t.year == y],
                       key=lambda x: -x.popularity)[:20]
        hubs.append((f"/year/{y}/",
                     hub_page(f"{y} Movies - Watch Free Movies Online | Fmovies",
                              f"Watch {y} movies and TV series online free in HD on Fmovies. "
                              f"New {y} releases and the most popular titles of the year.",
                              SITE + f"/year/{y}/", f"{y} Movies",
                              f"The biggest {y} movies and TV series, streaming free in HD on Fmovies. "
                              f"Browse the year's new releases and most-watched titles.",
                              items, "Movies")))

    def by_source(src, pool, key=None):
        items = [t for t in pool if src in t.sources]
        items.sort(key=lambda x: -(key(x) if key else x.popularity))
        return items[:20]

    m_by_pop = sorted(movies, key=lambda x: -x.popularity)
    m_by_rate = sorted([t for t in movies if t.votes >= 300], key=lambda x: (-x.rating, -x.votes))
    t_by_pop = sorted(tvs, key=lambda x: -x.popularity)
    t_by_rate = sorted([t for t in tvs if t.votes >= 300], key=lambda x: (-x.rating, -x.votes))
    anime = sorted([t for t in movies if 16 in t.genre_ids and t.orig_lang == "ja"],
                   key=lambda x: -x.popularity)
    if len(anime) < 10:
        anime = sorted([t for t in movies if 16 in t.genre_ids], key=lambda x: -x.popularity)
    list_defs = [
        ("featured-movies", "Featured Movies - Watch Free Movies Online | Fmovies",
         "Featured Movies", "The movies everyone is watching right now on Fmovies. "
         "Hand-picked highlights across every genre — stream them free in HD.",
         m_by_pop[:20]),
        ("popular-movies", "Popular Movies - Watch Free Movies Online | Fmovies",
         "Popular Movies", "The most popular movies on Fmovies this week. "
         "See what viewers are streaming most, and press play in HD for free.",
         by_source("popular", movies)),
        ("top-rated-movies", "Top Rated Movies - Watch Free Movies Online | Fmovies",
         "Top Rated Movies", "The highest-rated movies of all time, as voted by viewers. "
         "Stream the best-rated films free in HD on Fmovies.",
         m_by_rate[:20]),
        ("upcoming-movies", "Upcoming Movies - Watch Free Movies Online | Fmovies",
         "Upcoming Movies", "Movies coming soon to Fmovies. Preview the next big releases "
         "and be ready to stream them the moment they arrive.",
         by_source("upcoming", movies)),
        ("anime-movies", "Anime Movies - Watch Free Anime Online | Fmovies",
         "Anime Movies", "Watch anime movies online free in HD on Fmovies. "
         "From beloved classics to the newest Japanese animation.",
         anime[:20]),
        ("popular-tv-series", "Popular TV Series - Watch Free TV Shows Online | Fmovies",
         "Popular TV Series", "The most popular TV series streaming now on Fmovies. "
         "Binge full seasons free in HD, no sign-up needed.",
         t_by_pop[:20]),
        ("top-rated-tv-series", "Top Rated TV Series - Watch Free Online | Fmovies",
         "Top Rated TV Series", "The highest-rated TV series of all time. "
         "Stream the best shows free in HD on Fmovies.",
         t_by_rate[:20]),
        ("airing-today-tv-series", "TV Series Airing Today - Watch Free Online | Fmovies",
         "TV Series Airing Today", "TV shows with new episodes airing today. "
         "Catch up on the latest episodes, free in HD on Fmovies.",
         by_source("tv_airing_today", tvs)),
        ("on-the-air-tv-series", "TV Series On The Air - Watch Free Online | Fmovies",
         "TV Series On The Air", "TV series currently on the air. "
         "Follow ongoing shows and stream new episodes free on Fmovies.",
         by_source("tv_on_the_air", tvs)),
        ("movies", "Movies - Watch Free Movies Online | Fmovies",
         "Movies", "Browse every movie on Fmovies. Thousands of films across all genres, "
         "streaming free in HD — no account, no subscription.",
         m_by_pop[:20]),
    ]
    for slug, title, h1, intro, items in list_defs:
        hubs.append((f"/{slug}/",
                     hub_page(title,
                              intro + " Watch on Fmovies — free movies online in HD.",
                              SITE + f"/{slug}/", h1, intro, items, "Movies")))
    return hubs


# ---------------- sitemap ----------------
# File sizes mirror the competitor's sitemap index (total exactly 2,011),
# verified 2026-11-10 by counting <loc> occurrences in their live child
# sitemaps (copies in /tmp): sitemap-0: 41 | sitemap-1: 62 | sitemap-2: 102
# | sitemap-3: 202 | sitemap-4: 42 | sitemap-5: 202 | sitemap-6: 42
# | sitemap-7: 102 (all 100 series) | sitemap-8..14: 102 each (7 files)
# | sitemap-post: 502. Movie slots total 1840 (1258 unique + 582 repeats
# by cycling the title list, as they do); series slots 100.
SITEMAP_SIZES = [("sitemap-0.xml", 41), ("sitemap-1.xml", 62),
                 ("sitemap-2.xml", 102), ("sitemap-3.xml", 202),
                 ("sitemap-4.xml", 42), ("sitemap-5.xml", 202),
                 ("sitemap-6.xml", 42), ("sitemap-7.xml", 102)]
SITEMAP_SIZES += [(f"sitemap-{i}.xml", 102) for i in range(8, 15)]
SITEMAP_SIZES += [("sitemap-post.xml", 502)]
assert sum(s for _, s in SITEMAP_SIZES) == 2011, "sitemap size plan must total 2011"


def write_sitemap(hub_paths, movie_paths, serie_paths):
    """Write sitemap.xml (index) + 16 child files, exactly 2,011 <loc> total.
    Every child file lists the homepage + sitemap.xml itself (the competitor's
    pattern). sitemap-7 holds the 100 series URLs; all other title files hold
    movie URLs, cycling the title list so the file sizes match exactly."""
    home = SITE + "/"
    sitemap_self = SITE + "/sitemap.xml"
    files = {}

    # sitemap-0: home + sitemap.xml + all 39 hubs
    entries = [(home, "daily", "1.0"), (sitemap_self, "weekly", "0.5")]
    for hp in hub_paths:
        entries.append((SITE + hp, "daily", "0.8"))
    assert len(entries) == 41, f"sitemap-0 has {len(entries)} entries, expected 41"
    files["sitemap-0.xml"] = entries

    # remaining files: home + sitemap.xml + title URLs
    series = list(serie_paths)
    if len(series) < 100:
        series = (series * ((100 // len(series)) + 1))[:100]
    movies = list(movie_paths)
    pos = 0
    for fname, size in SITEMAP_SIZES[1:]:
        n_titles = size - 2
        if fname == "sitemap-7.xml":
            batch = series[:n_titles]
        else:
            batch = []
            for _ in range(n_titles):
                batch.append(movies[pos % len(movies)])
                pos += 1
        entries = [(home, "daily", "1.0"), (sitemap_self, "weekly", "0.5")]
        entries += [(SITE + p, "weekly", "0.8") for p in batch]
        assert len(entries) == size, f"{fname} has {len(entries)} entries, expected {size}"
        files[fname] = entries

    total = 0
    for fname, entries in files.items():
        body = "\n".join(
            f'  <url><loc>{loc}</loc><lastmod>{LASTMOD}</lastmod>'
            f'<changefreq>{cf}</changefreq><priority>{pr}</priority></url>'
            for loc, cf, pr in entries)
        with open(os.path.join(ROOT, fname), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                    + body + "\n</urlset>\n")
        total += len(entries)
    assert total == 2011, f"sitemap total {total} != 2011"

    idx = "\n".join(
        f'  <sitemap><loc>{SITE}/{fname}</loc><lastmod>{LASTMOD}</lastmod></sitemap>'
        for fname, _ in SITEMAP_SIZES)
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + idx + "\n</sitemapindex>\n")
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\nSitemap: https://www.fmovies.jo3.org/sitemap.xml\n")
    return total


# ---------------- homepage ----------------
def render_homepage(movies):
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    top60 = sorted(movies, key=lambda x: -x.popularity)[:60]
    links = "\n".join(
        f'    <a href="{t.canonical}">{esc(t.title)} ({t.year})</a>' for t in top60)
    return tpl.replace("<!--POPULAR_LINKS-->", links)


# ---------------- main ----------------
def main():
    load_ads()
    print("ads loaded:", bool(AD_HEADER), bool(AD_FOOTER), bool(SOCIALBAR))
    movies, tvs = load_titles()
    print(f"final selection: {len(movies)} movies, {len(tvs)} tv")
    if len(movies) != MOVIE_TARGET or len(tvs) != TV_TARGET:
        print(f"WARNING: targets are {MOVIE_TARGET} movies / {TV_TARGET} tv — "
              f"got {len(movies)} / {len(tvs)}")
    all_titles = movies + tvs

    # related / sidebar data
    def related_for(t, pool):
        tg = set(t.genre_ids)
        scored = []
        for o in pool:
            if o is t:
                continue
            shared = len(tg & set(o.genre_ids))
            scored.append((-shared, -o.popularity, o))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [s[2] for s in scored[:12]]

    mv_m = sorted(movies, key=lambda x: -x.votes)[:5]
    mv_t = sorted(tvs, key=lambda x: -x.votes)[:5]
    rec_m = [t for t in sorted([x for x in movies if x.votes >= 500],
                               key=lambda x: (-x.rating, -x.votes)) if t not in mv_m][:5]
    rec_t = [t for t in sorted([x for x in tvs if x.votes >= 500],
                               key=lambda x: (-x.rating, -x.votes)) if t not in mv_t][:5]

    # write title pages
    n_written = 0
    for i, t in enumerate(all_titles):
        pool = movies if t.type == "movie" else tvs
        rel = related_for(t, pool)
        mv = mv_m if t.type == "movie" else mv_t
        rc = rec_m if t.type == "movie" else rec_t
        doc = movie_page(t, rel, mv, rc)
        outdir = os.path.join(ROOT, t.dir_name, f"{t.slug}-{t.year}-{t.id}x")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
            f.write(doc)
        n_written += 1
        if (i + 1) % 200 == 0:
            print(f"  pages: {i+1}/{len(all_titles)}")
    print(f"title pages written: {n_written}")

    # hub pages
    hubs = hub_lists(movies, tvs)
    print(f"hub pages: {len(hubs)}")
    for path, doc in hubs:
        outdir = os.path.join(ROOT, path.strip("/"))
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as f:
            f.write(doc)

    # homepage
    home = render_homepage(movies)
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(home)
    print("homepage written")

    # sitemap + robots
    hub_paths = [p for p, _ in hubs]
    movie_paths = [t.url_path for t in movies]
    serie_paths = [t.url_path for t in tvs]
    total = write_sitemap(hub_paths, movie_paths, serie_paths)
    print(f"sitemap total <loc> entries: {total}")

    manifest = {
        "movies": len(movies), "tv": len(tvs), "hubs": len(hubs),
        "title_pages": n_written, "sitemap_entries": total,
        "lastmod": LASTMOD, "site": SITE,
    }
    with open(os.path.join(DATA, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("DONE:", json.dumps(manifest))


if __name__ == "__main__":
    main()
