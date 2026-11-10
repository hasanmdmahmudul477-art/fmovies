#!/usr/bin/env python3
"""Build the F Movies rebrand dataset for CineWave -> fmovies.jo3.org.

Phase 1: collect candidate (type, id) pairs from TMDB list endpoints.
Phase 2: fetch full details (credits + keywords) for the selected titles.

Usage:
    python3 tools/build_fmovies.py collect    # -> tools/data/candidates.json
    python3 tools/build_fmovies.py details    # -> tools/data/details.json (resumable)
    python3 tools/build_fmovies.py stats      # print counts from saved data

Targets: 1,258 movies + 100 TV series (selected round-robin across sources
so the mix includes popular, recent 2025-2027, older, and non-English titles).
Rate limit: max 4 req/sec, retry on 429/5xx with backoff. The TMDB API key
is read from assets/js/config.js and never printed or logged.
"""
import json, os, re, sys, time, urllib.request, urllib.parse, urllib.error
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tools", "data")
os.makedirs(DATA, exist_ok=True)

CANDIDATES = os.path.join(DATA, "candidates.json")
DETAILS = os.path.join(DATA, "details.json")
SELECTED = os.path.join(DATA, "selected.json")

MOVIE_TARGET = 1258
TV_TARGET = 100
# fetch a few extra candidates so filtering (no overview/poster/adult)
# still leaves exactly the targets
MOVIE_FETCH = 1450
TV_FETCH = 130

REQ_PER_SEC = 4          # sequential list calls
MIN_START_INTERVAL = 0.1  # concurrent detail calls: >=0.1s between starts (<=10/s)


def get_api_key():
    src = open(os.path.join(ROOT, "assets/js/config.js")).read()
    m = re.search(r'TMDB_API_KEY: "([^"]+)"', src)
    if not m:
        sys.exit("TMDB API key not found in config.js")
    return m.group(1)


API_KEY = get_api_key()
_last = [0.0]
_api_lock = threading.Lock()


def api(path, params=None, retries=3, concurrent=False):
    """GET a TMDB endpoint with retries. Sequential mode throttles to
    REQ_PER_SEC; concurrent mode enforces MIN_START_INTERVAL between
    request starts across threads (well under TMDB's 40 req/10s)."""
    if concurrent:
        with _api_lock:
            dt = time.time() - _last[0]
            if dt < MIN_START_INTERVAL:
                time.sleep(MIN_START_INTERVAL - dt)
            _last[0] = time.time()
    else:
        dt = time.time() - _last[0]
        if dt < 1.0 / REQ_PER_SEC:
            time.sleep(1.0 / REQ_PER_SEC - dt)
        _last[0] = time.time()
    q = dict(params or {})
    q["api_key"] = API_KEY
    q["language"] = "en-US"
    url = "https://api.themoviedb.org/3" + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(retries + 1):
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FmoviesBuilder/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries:
                wait = 2 ** attempt * 5
                print(f"  HTTP {e.code} on {path}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise
        except Exception:
            if attempt < retries:
                time.sleep(5)
                continue
            raise


# ---------------- collection jobs ----------------
# (endpoint, params, pages, source-name)
MOVIE_JOBS = [
    ("/movie/popular", {}, 15, "popular"),
    ("/movie/top_rated", {}, 15, "top_rated"),
    ("/trending/movie/week", {}, 3, "trending"),
    ("/movie/now_playing", {}, 4, "now_playing"),
    ("/movie/upcoming", {}, 4, "upcoming"),
    ("/discover/movie", {"sort_by": "popularity.desc"}, 15, "discover_pop"),  # pages 16-30
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2025}, 8, "year2025"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2026}, 8, "year2026"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2027}, 2, "year2027"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "hi"}, 4, "lang_hi"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "es"}, 4, "lang_es"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "ja"}, 4, "lang_ja"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "ko"}, 3, "lang_ko"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "fr"}, 2, "lang_fr"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "zh"}, 2, "lang_zh"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "de"}, 2, "lang_de"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "it"}, 2, "lang_it"),
    ("/discover/movie", {"sort_by": "vote_count.desc"}, 8, "most_voted"),
]
# discover_pop job starts at page 16 to avoid pure overlap with /movie/popular
MOVIE_JOB_START_PAGE = {"discover_pop": 16}

TV_JOBS = [
    ("/tv/popular", {}, 4, "tv_popular"),
    ("/tv/top_rated", {}, 4, "tv_top_rated"),
    ("/tv/airing_today", {}, 2, "tv_airing_today"),
    ("/tv/on_the_air", {}, 2, "tv_on_the_air"),
    ("/trending/tv/week", {}, 2, "tv_trending"),
    ("/discover/tv", {"sort_by": "popularity.desc"}, 3, "tv_discover"),
]


def run_jobs(jobs, media):
    """Run list jobs; return ordered dict key -> {type, id, sources:[...]}."""
    out = {}
    for path, params, pages, source in jobs:
        start = MOVIE_JOB_START_PAGE.get(source, 1)
        for p in range(start, start + pages):
            try:
                data = api(path, {**params, "page": p})
            except Exception as e:
                print(f"  LIST FAILED {path} p{p}: {e}")
                continue
            for it in data.get("results", []):
                tid = it.get("id")
                if not tid:
                    continue
                key = f"{media}:{tid}"
                if key not in out:
                    out[key] = {"type": media, "id": tid, "sources": []}
                if source not in out[key]["sources"]:
                    out[key]["sources"].append(source)
            if p >= data.get("total_pages", p):
                break
        print(f"  {source}: {len(out)} unique so far")
    return out


def round_robin(cands, target):
    """Interleave per-first-source lists so the final selection keeps the mix."""
    # first source per candidate, preserving collection order
    by_source = {}
    order = []
    for key, c in cands.items():
        s = c["sources"][0]
        if s not in by_source:
            by_source[s] = []
            order.append(s)
        by_source[s].append(c)
    out, idx = [], {s: 0 for s in order}
    while len(out) < target:
        progressed = False
        for s in order:
            if len(out) >= target:
                break
            lst = by_source[s]
            if idx[s] < len(lst):
                out.append(lst[idx[s]])
                idx[s] += 1
                progressed = True
        if not progressed:
            break
    return out


# round-2 expansion jobs (run when round 1 yields too few unique titles)
MOVIE_JOBS_2 = [
    ("/discover/movie", {"sort_by": "popularity.desc"}, 30, "discover_pop2"),  # pages 31-60
    ("/movie/top_rated", {}, 15, "top_rated2"),  # pages 16-30
    ("/movie/popular", {}, 10, "popular2"),  # pages 16-25
    ("/discover/movie", {"sort_by": "vote_average.desc", "vote_count.gte": 500}, 10, "best_rated"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2024}, 6, "year2024"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2023}, 4, "year2023"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2022}, 3, "year2022"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2021}, 3, "year2021"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2020}, 3, "year2020"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2019}, 2, "year2019"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2015}, 2, "year2015"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2010}, 2, "year2010"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 2000}, 2, "year2000"),
    ("/discover/movie", {"sort_by": "popularity.desc", "primary_release_year": 1990}, 2, "year1990"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "pt"}, 2, "lang_pt"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "ru"}, 2, "lang_ru"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "th"}, 2, "lang_th"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "id"}, 2, "lang_id"),
    ("/discover/movie", {"sort_by": "popularity.desc", "with_original_language": "tr"}, 2, "lang_tr"),
    ("/trending/movie/day", {}, 2, "trending_day"),
]
MOVIE_JOB_START_PAGE.update({
    "discover_pop2": 31, "top_rated2": 16, "popular2": 16,
})
# one discover job per genre (2 pages each) for genre-hub depth
GENRE_IDS = [28, 12, 16, 35, 80, 99, 18, 10751, 14, 36, 27, 10402, 9648, 10749, 878, 10770, 53, 10752]
for _gid in GENRE_IDS:
    MOVIE_JOBS_2.append(
        ("/discover/movie", {"sort_by": "popularity.desc", "with_genres": _gid}, 2, f"genre_{_gid}"))


def cmd_collect_more():
    if not os.path.exists(CANDIDATES):
        sys.exit("run 'collect' first")
    data = json.load(open(CANDIDATES, encoding="utf-8"))
    existing = {f"{c['type']}:{c['id']}": c for c in data["movie"]}
    print(f"starting with {len(existing)} movie candidates")
    new = run_jobs(MOVIE_JOBS_2, "movie")
    merged = 0
    for key, c in new.items():
        if key in existing:
            for s in c["sources"]:
                if s not in existing[key]["sources"]:
                    existing[key]["sources"].append(s)
        else:
            existing[key] = c
            merged += 1
    data["movie"] = list(existing.values())
    with open(CANDIDATES, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"added {merged} new movie candidates; total {len(data['movie'])} movies, {len(data['tv'])} tv")


def cmd_collect():
    print("collecting movie candidates...")
    movies = run_jobs(MOVIE_JOBS, "movie")
    print("collecting tv candidates...")
    tvs = run_jobs(TV_JOBS, "tv")
    data = {"movie": list(movies.values()), "tv": list(tvs.values())}
    with open(CANDIDATES, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"candidates: {len(data['movie'])} movies, {len(data['tv'])} tv")
    print(f"saved {CANDIDATES}")


def cmd_details():
    if not os.path.exists(CANDIDATES):
        sys.exit("run 'collect' first")
    cands = json.load(open(CANDIDATES, encoding="utf-8"))
    # selection: round-robin, fetch a few extra for filtering headroom
    movie_sel = round_robin({f"movie:{c['id']}": c for c in cands["movie"]}, MOVIE_FETCH)
    tv_sel = round_robin({f"tv:{c['id']}": c for c in cands["tv"]}, TV_FETCH)
    selected = movie_sel + tv_sel
    with open(SELECTED, "w", encoding="utf-8") as f:
        json.dump(selected, f)
    print(f"selected for details: {len(movie_sel)} movies, {len(tv_sel)} tv")

    details = {}
    if os.path.exists(DETAILS):
        details = json.load(open(DETAILS, encoding="utf-8"))
        print(f"resuming: {len(details)} already fetched")
    todo = [c for c in selected if f"{c['type']}:{c['id']}" not in details]
    print(f"to fetch: {len(todo)} titles (8 workers)")
    n_ok = n_skip = n_fail = 0
    done = [0]
    lock = threading.Lock()

    def fetch_one(c):
        key = f"{c['type']}:{c['id']}"
        try:
            d = api(f"/{c['type']}/{c['id']}",
                    {"append_to_response": "credits,keywords"}, concurrent=True)
        except Exception as e:
            print(f"  DETAIL FAILED {key}: {e}")
            return ("fail", key, None)
        if d.get("adult"):
            return ("skip", key, None)
        ov = d.get("overview") or ""
        if len(ov) < 40 or not d.get("poster_path"):
            return ("skip", key, None)
        d["_sources"] = c["sources"]
        return ("ok", key, d)

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, c): c for c in todo}
        for fut in as_completed(futs):
            status, key, d = fut.result()
            with lock:
                if status == "ok":
                    details[key] = d
                    n_ok += 1
                elif status == "skip":
                    n_skip += 1
                else:
                    n_fail += 1
                done[0] += 1
                if done[0] % 100 == 0:
                    print(f"  [{done[0]}/{len(todo)}] fetched {len(details)} ok, "
                          f"{n_skip} skipped, {n_fail} failed")
                    with open(DETAILS, "w", encoding="utf-8") as f:
                        json.dump(details, f)
    with open(DETAILS, "w", encoding="utf-8") as f:
        json.dump(details, f)
    nm = sum(1 for k in details if k.startswith("movie:"))
    nt = sum(1 for k in details if k.startswith("tv:"))
    print(f"DONE details: {nm} movies, {nt} tv (targets {MOVIE_TARGET}/{TV_TARGET}), "
          f"skipped {n_skip}, failed {n_fail}")
    print(f"saved {DETAILS}")


def cmd_stats():
    if os.path.exists(CANDIDATES):
        c = json.load(open(CANDIDATES, encoding="utf-8"))
        print(f"candidates: {len(c['movie'])} movies, {len(c['tv'])} tv")
    if os.path.exists(DETAILS):
        d = json.load(open(DETAILS, encoding="utf-8"))
        nm = sum(1 for k in d if k.startswith("movie:"))
        nt = sum(1 for k in d if k.startswith("tv:"))
        print(f"details: {nm} movies, {nt} tv, total {len(d)}")
        # year / language mix for movies
        from collections import Counter
        years = Counter()
        langs = Counter()
        for k, v in d.items():
            if k.startswith("movie:"):
                date = v.get("release_date") or ""
                years[date[:4] or "?"] += 1
                langs[v.get("original_language") or "?"] += 1
        print("movie years:", dict(sorted(years.items())[-8:]))
        print("movie languages:", dict(langs.most_common(10)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    {"collect": cmd_collect, "collect_more": cmd_collect_more, "details": cmd_details, "stats": cmd_stats}[cmd]()
