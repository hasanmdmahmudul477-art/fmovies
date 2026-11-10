# F Movies

Free movie & TV streaming discovery site — **Fmovies** — live at
https://www.fmovies.jo3.org/

## What this is

A fast, static, programmatic SEO site:

- **1,258 movie pages** (`/movie/slug-year-id x/`) and **100 TV series pages**
  (`/serie/…`), each with unique title, meta, canonical, Open Graph and
  JSON-LD, poster/backdrop, rating, runtime, cast, director and related titles.
- **39 hub pages**: 19 genres, 7 countries, 3 years, 10 lists
  (featured / popular / top-rated / upcoming / anime / airing-today / on-the-air).
- **Homepage** with original SEO copy, FAQ and links to every hub.
- **Sitemap index**: 16 files, exactly **2,011 entries**; `robots.txt` points at it.
- Dark navy + teal theme, original logo/favicon/OG assets in the repo root
  (`favicon.ico`, `apple-touch-icon.png`, `android-chrome-*.png`,
  `site.webmanifest`, `og-image.png`).

Movie/TV data comes from TMDB (facts only — titles, years, ratings, cast,
overviews). All editorial copy on the site is originally written.

## Deploy

Static files — served by Render (service `cinewave-58m4`, custom domain
`www.fmovies.jo3.org`). Any push to `main` auto-deploys.

## Rebuild

- `tools/generate_fmovies.py` — regenerates every page, hub, homepage and
  sitemap from TMDB (see `tools/build_fmovies.py` for the fetch step).
- `tools/verify_sitemap.py` — verifies sitemap totals, page counts, hubs,
  meta/canonical/OG/JSON-LD, unique titles and ad keys (must report
  0 failures before any deploy).
- `tools/make_brand_assets.py` — regenerates logo/favicon/OG assets.
- `tools/data/manifest.json` — counts from the last successful build.
