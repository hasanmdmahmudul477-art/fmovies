/* ============ Fmovies settings ============ */
/* NOTE: this is a TEMPLATE. Real keys are injected at build time from
   environment variables (see tools/build-config.js). Never put real keys
   in this file. The generated assets/js/config.js is gitignored. */
const CONFIG = {
  // Change this to your site name (also updates logo + footer automatically)
  SITE_NAME: "Fmovies",

  // >>> PASTE YOUR FREE TMDB API KEY HERE <<<
  // Get one in ~2 minutes: https://www.themoviedb.org → sign up → Settings → API
  // → "Request an API key" (Developer) → copy the "API Key (v3 auth)".
  TMDB_API_KEY: "8e176c9694b960cae16f0e342d8ad1ec",

  // Language for movie data (en-US works best; TMDB translations vary)
  DEFAULT_LANGUAGE: "en-US",

  /* ---------- Video sources: full movie / episode playback ----------
     The site plays video through third-party embed providers.
     {id} = TMDB id, {s} = season number, {e} = episode number.
     These providers' domains change often — if a server stops working,
     replace its URL template or add a new entry. The player shows one
     button per entry so visitors can switch servers. */
  VIDEO_SOURCES: [
    { name: "Server 1",
      movie: "https://vidsrc.to/embed/movie/{id}",
      tv: "https://vidsrc.to/embed/tv/{id}/{s}/{e}" },
    { name: "Server 2",
      movie: "https://vidsrc.xyz/embed/movie/{id}",
      tv: "https://vidsrc.xyz/embed/tv/{id}/{s}/{e}" },
  ],

  /* ---------- Ad codes (optional) ----------
     1. Sign up as a Publisher at https://publishers.adsterra.com
     2. Add your website, verify ownership, create ad units (e.g. Banner)
     3. Paste each ad unit's code between the backticks below.
     - header / footer / modalMain = normal ads shown everywhere
     - modalAdult = shown ONLY on 18+ title pages (R / NC-17 / TV-MA / 18
       certified, or TMDB adult-flagged)
     - socialBar = site-wide floating ad, runs on every page
     Leave any slot empty ("") to hide it. */
  ADS: {
    header: ``,
    modalMain: ``,
    modalAdult: ``,
    footer: ``,
    socialBar: ``,
  },
};
