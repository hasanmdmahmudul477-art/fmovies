/* ==================== Fmovies — app ==================== */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const API_BASE = "https://api.themoviedb.org/3";
const IMG_BASE = "https://image.tmdb.org/t/p/";

document.title = "Fmovies - Watch Free Movies Online in HD | Stream Free Movies & TV Shows";
const _logoEl = $("#logo");
if (_logoEl) _logoEl.textContent = CONFIG.SITE_NAME;
const _footEl = $("#footer-brand");
if (_footEl) _footEl.textContent = CONFIG.SITE_NAME;

const HAS_KEY =
  Boolean(CONFIG.TMDB_API_KEY) && !CONFIG.TMDB_API_KEY.includes("PASTE_YOUR");

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
const img = (p, size = "w500") => (p ? IMG_BASE + size + p : "");
const titleOf = (it) => it.title || it.name || "Untitled";
const yearOf = (it) => (it.release_date || it.first_air_date || "").slice(0, 4) || "—";

/* ---------------- ads ----------------
   Header/footer slots show the normal ad code.
   The detail-modal slot is contextual: 18+ titles get ADS.modalAdult,
   everything else gets ADS.modalMain. A title counts as 18+ when it is
   TMDB adult-flagged OR carries an adult age certification
   (R, NC-17, TV-MA, 18 / 18+) in any country. */
function renderAd(code, el, w, h) {
  if (!el) return;
  el.innerHTML = "";
  if (code && code.trim()) {
    // Each ad runs in its own iframe, written with document.write, so the
    // ad network's <script> tags execute exactly as if pasted into HTML
    // (scripts inserted via innerHTML would never run) and globals like
    // atOptions can't collide between slots.
    const f = document.createElement("iframe");
    f.setAttribute("scrolling", "no");
    f.setAttribute("frameborder", "0");
    f.style.border = "0";
    f.style.overflow = "hidden";
    f.width = w || "100%";
    if (h) f.height = h;
    el.appendChild(f);
    const d = f.contentDocument || f.contentWindow.document;
    d.open();
    d.write(code);
    d.close();
    el.style.display = "flex";
  } else {
    el.style.display = "none";
  }
}

/* ---------------- site-wide ad scripts ----------------
   Slots like Social Bar must run in the top document (not inside an ad
   iframe) so they can position their floating UI over the page. */
function renderSiteWideAd(code) {
  if (!code || !code.trim()) return;
  const tmp = document.createElement("div");
  tmp.innerHTML = code;
  [...tmp.childNodes].forEach((node) => {
    if (node.tagName === "SCRIPT") {
      const s = document.createElement("script");
      [...node.attributes].forEach((a) => s.setAttribute(a.name, a.value));
      s.textContent = node.textContent;
      document.head.appendChild(s);
    }
  });
}

/* ---------------- 18+ detection ----------------
   A title counts as 18+ when it is TMDB adult-flagged OR carries an
   adult age certification (US: R / NC-17 / TV-MA, UK: 18, plus 18+
   variants). Only US/GB ratings count — a single outlier country's
   rating must not flag a title. */
const ADULT_CERTS = new Set(["R", "NC-17", "TV-MA", "18", "18+"]);
const CERT_COUNTRIES = new Set(["US", "GB"]);

function titleCertifications(d, type) {
  const out = [];
  if (type === "tv") {
    (d.content_ratings?.results || [])
      .filter((r) => CERT_COUNTRIES.has(r.iso_3166_1))
      .forEach((r) => out.push(r.rating));
  } else {
    (d.release_dates?.results || [])
      .filter((c) => CERT_COUNTRIES.has(c.iso_3166_1))
      .forEach((c) =>
        (c.release_dates || []).forEach((rd) => out.push(rd.certification))
      );
  }
  return out;
}

function is18Plus(d, type) {
  if (d.adult) return true;
  return titleCertifications(d, type).some((c) =>
    ADULT_CERTS.has(String(c || "").trim().toUpperCase())
  );
}

/* ---------------- TMDB ---------------- */
async function apiGet(path, params = {}) {
  const url = new URL(API_BASE + path);
  url.searchParams.set("api_key", CONFIG.TMDB_API_KEY);
  url.searchParams.set("language", CONFIG.DEFAULT_LANGUAGE);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url);
  if (!res.ok) throw new Error("TMDB " + res.status);
  return res.json();
}

/* ---------------- cards & rows ---------------- */
function cardHTML(it, mediaType) {
  const type = it.media_type || mediaType || "movie";
  const rating = it.vote_average ? it.vote_average.toFixed(1) : "—";
  return `
  <div class="card" data-type="${type}" data-id="${it.id}">
    <span class="badge">★ ${rating}</span>
    <img loading="lazy" src="${img(it.poster_path)}" alt="${esc(titleOf(it))}" onerror="this.style.opacity=0">
    <div class="card-body">
      <div class="card-title">${esc(titleOf(it))}</div>
      <div class="card-sub">${esc(yearOf(it))} · ${type === "tv" ? "TV" : "Movie"}</div>
    </div>
  </div>`;
}

function bindCards(scope) {
  scope.querySelectorAll(".card").forEach((c) =>
    c.addEventListener("click", () => openDetail(c.dataset.type, c.dataset.id))
  );
}

function rowHTML(title, items, mediaType) {
  const cards = items
    .filter((i) => i.poster_path)
    .map((i) => cardHTML(i, mediaType))
    .join("");
  if (!cards) return "";
  return `<section class="row"><h2>${esc(title)}</h2><div class="row-scroll">${cards}</div></section>`;
}

/* ---------------- views ---------------- */
function showView(name) {
  $("#home-view").classList.toggle("hidden", name !== "home");
  $("#grid-view").classList.toggle("hidden", name !== "grid");
  window.scrollTo({ top: 0 });
}

function setNav(name) {
  $$(".nav-links a").forEach((a) =>
    a.classList.toggle("active", a.dataset.view === name)
  );
}

function showGrid(title, items, mediaType) {
  $("#grid-title").textContent = title;
  const cards = items
    .filter((i) => i.poster_path)
    .map((i) => cardHTML(i, mediaType))
    .join("");
  $("#grid").innerHTML = cards || `<p class="loading">Nothing found.</p>`;
  bindCards($("#grid"));
  showView("grid");
}

async function loadCategory(kind) {
  const isTv = kind === "tv";
  const label = isTv ? "Popular TV Shows" : "Popular Movies";
  setNav(kind);
  $("#grid-title").textContent = label;
  $("#grid").innerHTML = `<p class="loading">Loading...</p>`;
  showView("grid");
  try {
    const data = await apiGet(isTv ? "/discover/tv" : "/discover/movie", {
      sort_by: "popularity.desc",
      "vote_count.gte": 50,
    });
    showGrid(label, data.results, isTv ? "tv" : "movie");
  } catch (e) {
    $("#grid").innerHTML = `<p class="loading">Failed to load. Check your API key.</p>`;
  }
}

/* ---------------- hero ---------------- */
let heroItems = [];
let heroIdx = 0;
let heroTimer = null;

function setHero(i) {
  heroIdx = i;
  const it = heroItems[i];
  if (!it) return;
  const bd = $("#hero-backdrop");
  bd.style.opacity = 0;
  setTimeout(() => {
    bd.style.backgroundImage = `url('${img(it.backdrop_path, "original")}')`;
    bd.style.opacity = 1;
  }, 160);
  $("#hero-title").textContent = titleOf(it);
  $("#hero-meta").innerHTML =
    `<span class="rating">★ ${it.vote_average ? it.vote_average.toFixed(1) : "—"}</span>` +
    `<span>${esc(yearOf(it))}</span>` +
    `<span>${it.media_type === "tv" ? "TV Series" : "Movie"}</span>`;
  $("#hero-overview").textContent = it.overview || "";
  const type = it.media_type || "movie";
  $("#hero-info").onclick = () => openDetail(type, it.id);
  $("#hero-watch").onclick = () => openPlayer(type, it.id);
  $("#hero-trailer").onclick = () => playTrailer(type, it.id);
  $$("#hero-dots span").forEach((d, di) => d.classList.toggle("on", di === i));
}

function restartHeroTimer() {
  clearInterval(heroTimer);
  if (heroItems.length > 1) {
    heroTimer = setInterval(() => setHero((heroIdx + 1) % heroItems.length), 7000);
  }
}

function startHero(items) {
  heroItems = items.filter((i) => i.backdrop_path).slice(0, 6);
  const dots = $("#hero-dots");
  dots.innerHTML = heroItems.map((_, i) => `<span data-i="${i}"></span>`).join("");
  dots.querySelectorAll("span").forEach((d) =>
    d.addEventListener("click", () => {
      setHero(+d.dataset.i);
      restartHeroTimer();
    })
  );
  setHero(0);
  restartHeroTimer();
}

/* ---------------- search ---------------- */
let searchTimer = null;
$("#search-input").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  searchTimer = setTimeout(() => {
    if (q.length >= 3) doSearch(q);
    else if (q.length === 0) {
      setNav("home");
      showView("home");
    }
  }, 450);
});

async function doSearch(q) {
  setNav(null);
  $("#grid-title").textContent = `Results for "${q}"`;
  $("#grid").innerHTML = `<p class="loading">Searching...</p>`;
  showView("grid");
  try {
    const data = await apiGet("/search/multi", { query: q, include_adult: false });
    const items = data.results.filter(
      (i) => (i.media_type === "movie" || i.media_type === "tv") && i.poster_path
    );
    showGrid(`Results for "${q}"`, items);
  } catch (e) {
    $("#grid").innerHTML = `<p class="loading">Search failed.</p>`;
  }
}

/* ---------------- genres ---------------- */
let activeGenre = null;

async function loadGenres() {
  try {
    const data = await apiGet("/genre/movie/list");
    const bar = $("#genre-bar");
    bar.innerHTML = data.genres
      .map((g) => `<button class="chip" data-id="${g.id}">${esc(g.name)}</button>`)
      .join("");
    bar.querySelectorAll(".chip").forEach((c) =>
      c.addEventListener("click", () => toggleGenre(c))
    );
  } catch (e) {
    /* genres are optional — site works without them */
  }
}

async function toggleGenre(chip) {
  const id = chip.dataset.id;
  if (activeGenre === id) {
    activeGenre = null;
    chip.classList.remove("on");
    setNav("home");
    showView("home");
    return;
  }
  $$("#genre-bar .chip").forEach((c) => c.classList.remove("on"));
  chip.classList.add("on");
  activeGenre = id;
  setNav(null);
  const name = chip.textContent;
  $("#grid-title").textContent = name + " Movies";
  $("#grid").innerHTML = `<p class="loading">Loading...</p>`;
  showView("grid");
  try {
    const data = await apiGet("/discover/movie", {
      with_genres: id,
      sort_by: "popularity.desc",
    });
    showGrid(name + " Movies", data.results, "movie");
  } catch (e) {
    $("#grid").innerHTML = `<p class="loading">Failed to load.</p>`;
  }
}

/* ---------------- detail modal ---------------- */
function openModal(html) {
  $("#modal-content").innerHTML = html;
  $("#modal").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}
function closeModal() {
  $("#modal").classList.add("hidden");
  document.body.style.overflow = "";
}
$("#modal-close").addEventListener("click", closeModal);
$("#modal-backdrop").addEventListener("click", closeModal);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeModal();
    closeTrailer();
    closePlayer();
  }
});

const castHTML = (c) => `
  <div class="cast">
    <img loading="lazy" src="${img(c.profile_path, "w185")}" alt="" onerror="this.style.opacity=0">
    <div class="c-name">${esc(c.name)}</div>
    <div class="c-char">${esc(c.character || "")}</div>
  </div>`;

function providersHTML(d) {
  const all = (d["watch/providers"] && d["watch/providers"].results) || {};
  const region = all["BD"] ? "BD" : all["US"] ? "US" : Object.keys(all)[0];
  if (!region) return "";
  const flat = all[region].flatrate || [];
  if (!flat.length) return "";
  return `
    <div class="section-title">Where to Watch</div>
    <div class="providers">
      ${flat.map((p) => `<img loading="lazy" src="${img(p.logo_path, "w92")}" title="${esc(p.provider_name)}" alt="${esc(p.provider_name)}">`).join("")}
      <span class="provider-region">Streaming availability · ${esc(region)}</span>
    </div>`;
}

async function openDetail(type, id) {
  openModal(`<p class="loading">Loading...</p>`);
  try {
    const d = await apiGet(`/${type}/${id}`, {
      append_to_response:
        "videos,credits,watch/providers," +
        (type === "tv" ? "content_ratings" : "release_dates"),
    });
    const videos = d.videos?.results || [];
    const trailer =
      videos.find((v) => v.site === "YouTube" && v.type === "Trailer") ||
      videos.find((v) => v.site === "YouTube");
    const cast = (d.credits?.cast || []).slice(0, 10);
    const genres = (d.genres || []).map((g) => `<span>${esc(g.name)}</span>`).join("");
    const runtime = d.runtime
      ? `${d.runtime} min`
      : d.number_of_seasons
        ? `${d.number_of_seasons} Season${d.number_of_seasons > 1 ? "s" : ""}`
        : "";
    const is18 = is18Plus(d, type);
    const adultBadge = is18
      ? `<span class="badge" style="position:static">18+</span>`
      : "";

    openModal(`
      <div class="detail-hero" style="background-image:url('${img(d.backdrop_path, "original")}')"></div>
      <div class="detail-body">
        <div class="detail-main">
          <img class="detail-poster" src="${img(d.poster_path)}" alt="" onerror="this.style.opacity=0">
          <div class="detail-info">
            <h2>${esc(titleOf(d))} ${adultBadge}</h2>
            ${d.tagline ? `<div class="tagline">${esc(d.tagline)}</div>` : ""}
            <div class="meta-line">
              <span class="rating">★ ${d.vote_average ? d.vote_average.toFixed(1) : "—"}</span>
              <span>${esc(yearOf(d))}</span>
              <span>${esc(runtime)}</span>
            </div>
            <div class="genres">${genres}</div>
            <div class="detail-actions">
              <button class="btn btn-primary" id="m-watch">Watch Now</button>
              ${trailer ? `<button class="btn btn-secondary" id="m-trailer">Watch Trailer</button>` : ""}
            </div>
          </div>
        </div>
        <p class="overview">${esc(d.overview || "")}</p>
        <div id="ad-modal" class="ad-slot"></div>
        ${providersHTML(d)}
        ${cast.length ? `<div class="section-title">Top Cast</div><div class="cast-row">${cast.map(castHTML).join("")}</div>` : ""}
      </div>`);

    // Contextual ad: 18+ titles get the adult ad code, everything else the normal one
    renderAd(is18 ? CONFIG.ADS.modalAdult : CONFIG.ADS.modalMain, $("#ad-modal"), 300, 250);

    if (trailer) {
      $("#m-trailer").addEventListener("click", () => playTrailerByKey(trailer.key));
    }
    $("#m-watch").addEventListener("click", () => {
      closeModal();
      openPlayer(type, id);
    });
  } catch (e) {
    openModal(`<p class="loading">Failed to load details.</p>`);
  }
}

/* ---------------- trailer ---------------- */
function playTrailerByKey(key) {
  $("#trailer-frame").src = `https://www.youtube.com/embed/${key}?autoplay=1&rel=0`;
  $("#trailer-modal").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}
function closeTrailer() {
  $("#trailer-frame").src = "";
  $("#trailer-modal").classList.add("hidden");
  document.body.style.overflow = "";
}
$$("[data-close-trailer]").forEach((el) =>
  el.addEventListener("click", closeTrailer)
);

async function playTrailer(type, id) {
  try {
    const d = await apiGet(`/${type}/${id}`, { append_to_response: "videos" });
    const videos = d.videos?.results || [];
    const t =
      videos.find((v) => v.site === "YouTube" && v.type === "Trailer") ||
      videos.find((v) => v.site === "YouTube");
    if (t) playTrailerByKey(t.key);
  } catch (e) {
    /* no trailer available */
  }
}

/* ---------------- player (full movie / episode) ---------------- */
let playerState = { type: null, id: null, season: 1, episode: 1, server: 0 };

function playerUrl() {
  const src = (CONFIG.VIDEO_SOURCES || [])[playerState.server];
  if (!src) return "";
  const tpl = playerState.type === "tv" ? src.tv : src.movie;
  return tpl
    .replace("{id}", playerState.id)
    .replace("{s}", playerState.season)
    .replace("{e}", playerState.episode);
}

function loadPlayer() {
  $("#player-frame").src = playerUrl();
  $$("#player-servers .chip").forEach((b) =>
    b.classList.toggle("on", +b.dataset.i === playerState.server)
  );
}

function showPlayerModal() {
  $("#player-modal").classList.remove("hidden");
  document.body.style.overflow = "hidden";
  loadPlayer();
}

function closePlayer() {
  $("#player-frame").src = "";
  $("#player-modal").classList.add("hidden");
  document.body.style.overflow = "";
}
$$("[data-close-player]").forEach((el) =>
  el.addEventListener("click", closePlayer)
);

function openPlayer(type, id) {
  playerState = { type, id, season: 1, episode: 1, server: 0 };
  $("#player-servers").innerHTML =
    `<span class="server-label">Server:</span>` +
    (CONFIG.VIDEO_SOURCES || [])
      .map(
        (s, i) =>
          `<button class="chip${i === 0 ? " on" : ""}" data-i="${i}">${esc(s.name)}</button>`
      )
      .join("");
  $$("#player-servers .chip").forEach((b) =>
    b.addEventListener("click", () => {
      playerState.server = +b.dataset.i;
      loadPlayer();
    })
  );
  if (type === "tv") {
    buildTvControls(id);
  } else {
    $("#player-controls").innerHTML = "";
    showPlayerModal();
  }
}

async function buildTvControls(id) {
  $("#player-controls").innerHTML = `<span class="loading">Loading episodes...</span>`;
  showPlayerModal();
  try {
    const d = await apiGet(`/tv/${id}`);
    const seasons = (d.seasons || []).filter((s) => s.season_number > 0);
    if (!seasons.length) throw new Error("no seasons");
    $("#player-controls").innerHTML =
      `<select id="p-season">${seasons
        .map((s) => `<option value="${s.season_number}">Season ${s.season_number}</option>`)
        .join("")}</select><select id="p-episode"></select>`;
    const loadEps = async () => {
      const sn = +$("#p-season").value;
      playerState.season = sn;
      $("#p-episode").innerHTML = `<option>Loading...</option>`;
      const sd = await apiGet(`/tv/${id}/season/${sn}`);
      const eps = sd.episodes || [];
      $("#p-episode").innerHTML = eps
        .map((e) => `<option value="${e.episode_number}">E${e.episode_number} · ${esc(e.name || "")}</option>`)
        .join("");
      playerState.episode = +(($("#p-episode").value) || 1);
      loadPlayer();
    };
    $("#p-season").addEventListener("change", loadEps);
    $("#p-episode").addEventListener("change", () => {
      playerState.episode = +$("#p-episode").value;
      loadPlayer();
    });
    await loadEps();
  } catch (e) {
    $("#player-controls").innerHTML = `<span class="loading">Could not load episodes.</span>`;
    loadPlayer();
  }
}

/* ---------------- nav ---------------- */
$$(".nav-links a").forEach((a) =>
  a.addEventListener("click", (e) => {
    const v = a.dataset.view;
    if (v === "genres") {
      e.preventDefault();
      showView("home");
      const el = document.getElementById("browse-genres");
      if (el) el.scrollIntoView({ behavior: "smooth" });
      return;
    }
    e.preventDefault();
    activeGenre = null;
    $$("#genre-bar .chip").forEach((c) => c.classList.remove("on"));
    $("#search-input").value = "";
    if (v === "home") {
      setNav("home");
      showView("home");
    } else {
      loadCategory(v);
    }
  })
);

/* ---------------- init ---------------- */
async function init() {
  renderAd(CONFIG.ADS.header, $("#ad-header"), 728, 90);
  renderAd(CONFIG.ADS.footer, $("#ad-footer"), 300, 250);
  renderSiteWideAd(CONFIG.ADS.socialBar);

  if (!HAS_KEY) {
    $("#setup-banner").classList.remove("hidden");
    return;
  }
  setNav("home");
  try {
    const trending = await apiGet("/trending/all/week");
    // Single compact "Featured Movies" row under the SEO text
    $("#rows").innerHTML = rowHTML("Featured Movies", (trending.results || []).slice(0, 20));
    bindCards($("#rows"));
    loadGenres();
  } catch (e) {
    $("#rows").innerHTML = `<p class="loading">Could not reach TMDB. Check your API key in <code>assets/js/config.js</code>.</p>`;
  }
  openDeepLink();
  // Static pages link their search box here as /?q=...
  const q = new URLSearchParams(location.search).get("q");
  if (q && q.trim()) {
    $("#search-input").value = q.trim();
    doSearch(q.trim());
  }
}

/* Deep link: title pages link to /?watch=movie-123 or /?watch=tv-456
   (also supports #movie/123 / #tv/456). Opens that title's detail
   modal automatically. */
function openDeepLink() {
  let type = null, id = null;
  const q = new URLSearchParams(location.search).get("watch");
  const m = q
    ? q.match(/^(movie|tv)-(\d+)$/)
    : location.hash.match(/^#(movie|tv)\/(\d+)$/);
  if (m) { type = m[1]; id = m[2]; }
  if (type && id && HAS_KEY) openDetail(type, id);
}

init();
