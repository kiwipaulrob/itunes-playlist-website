# iTunes Playlist Static Site — Specification

## Overview

A static website generator that takes a folder of iTunes XML playlist files and produces a
complete multi-page HTML site: one page per playlist, a landing index, and a client-side
search feature. Designed for covers playlists initially, with a structure that accommodates
non-covers playlists in a future refactor.

---

## Goals

- Generate a browsable, self-contained static site from a collection of iTunes XML files
- Each playlist gets its own styled HTML page (same visual design as the existing single-page output)
- A landing index page shows all playlists as a card grid
- A search page lets users find songs/artists and see which playlists they appear on
- Local-first (no server required); built to deploy to GitHub Pages
- Scale to up to 500 playlists without performance problems

---

## Directory Layout

### Input

```
/input/
├── playlists/
│   ├── Nuggets 396 - Covers XX - Final.xml
│   ├── Nuggets 397 - Covers XXI - Final.xml
│   └── ...
├── overrides/
│   ├── nuggets_396_covers_xx_final_overrides.json   ← per-playlist MBID/art/album overrides
│   └── ...
└── config.ini                                        ← all site configuration (see below)
```

### Output

```
/output/
├── index.html                  ← landing page (playlist card grid)
├── search.html                 ← search page
├── stats.html                  ← statistics page with charts (v2.8+)
├── stats.json                  ← pre-computed statistics data (v2.8+)
├── style.css                   ← shared stylesheet (all pages link to this)
├── fuse.min.js                 ← bundled Fuse.js (no CDN dependency)
├── search_index.json           ← pre-built search index
├── CNAME                        ← custom domain file (if configured)
├── playlists/
│   ├── nuggets-396-covers-xx.html
│   ├── nuggets-397-covers-xxi.html
│   └── ...
└── img/
    ├── nuggets-396-covers-xx/
    │   ├── 01.jpg              ← artwork per track, named by track number
    │   ├── 02.jpg
    │   └── ...
    └── nuggets-397-covers-xxi/
        └── ...
```

**Key change from v1:** Artwork is saved as external image files under `img/` rather than
base64-embedded in HTML. This keeps individual HTML files small and allows the browser to
cache images across page loads.

---

## Scripts

### `build_site.py` — Main Orchestrator

Entry point. Scans the input playlists folder, calls per-playlist generation logic, then
generates the index page, search index, and search page.

```
python3 build_site.py --input /path/to/input --output /path/to/output [options]
```

**Options:**

| Flag | Description |
|------|-------------|
| `--input DIR` | Input directory (required) |
| `--output DIR` | Output directory (required) |
| `--force` | Re-generate all playlists even if output is up to date |
| `--playlist SLUG` | Re-generate a single playlist only (useful during editing) |
| `--skip-art` | Skip artwork fetching (use cached only) |
| `--covers-mode` | Apply covers-mode display for all playlists (default: on) |


**Build logic:**
1. For each XML in `input/playlists/`:
   - Derive a URL-safe slug from the filename (e.g. `nuggets-396-covers-xx`)
   - Check if `output/playlists/<slug>.html` already exists and is newer than the XML — skip if so (unless `--force`)
   - Load overrides from `input/overrides/<slug>_overrides.json` if present
   - Call playlist generation logic (see below) to produce the HTML and save artwork to `output/img/<slug>/`
2. Generate `search_index.json` from all track data
3. Generate `index.html` from all playlist metadata
4. Copy `style.css` and `fuse.min.js` to output root

**Incremental builds:** Only re-process playlists whose XML is newer than their output HTML,
making repeated runs fast even at 500 playlists.

---

### `playlist_generator.py` — Per-Playlist Logic (Library)

Refactored from `itunes_playlist_html.py`. Called by `build_site.py` as a module, but also
runnable standalone for development/testing:

```
python3 playlist_generator.py input.xml --output-dir /output --slug my-playlist [options]
```

**Key changes from `itunes_playlist_html.py`:**
- Returns artwork as saved image files (not base64 strings)
- Accepts `slug` and `output_dir` instead of deriving output filename itself
- CSS and JS are linked externally (`../../style.css`, `../../fuse.min.js`) rather than inlined
- Playlist page HTML includes shared nav component
- Returns structured track data (dict) for use by the orchestrator's search index builder

---

### `config.ini` — All Configuration

All settings live in `config.ini` (INI format). See the V2.4 section below for the full
8-group layout. Key settings:

- `[paths]`: input/output directories, cache locations
- `[build]`: covers_mode, force_rebuild, verbose
- `[site]`: site_title, site_tagline, accent_color, custom_domain
- `[playlists]`: playlist_order (newline-separated slug list, oldest first)
- `[links]`: enabled sites, search URL templates
- `[search_terms]`: per-site query mode overrides

Caches are shared across all playlists to avoid redundant MusicBrainz lookups for the same
release appearing in multiple playlists.

---

## Visual Style

The site uses a **magazine / music press** aesthetic throughout — dark, editorial, artwork-led.

| Element | Value |
|---------|-------|
| Background | `#111` (near-black) |
| Card background | `#1a1a1a` |
| Primary text | `#f0f0f0` |
| Muted text | `#888` |
| Accent colour | `#e8b84b` (warm gold — configurable) |
| Heading font | Playfair Display (Google Fonts) or Georgia fallback |
| Body font | Inter or system-ui |
| Border / divider | `#333` |
| Card border radius | `6px` |
| Card hover | `transform: scale(1.02)` + accent border glow |

The same `style.css` governs all pages — landing, playlist, and search. Dark theme only (no light mode toggle in v1).

---

## Pages

### `index.html` — Landing Page

#### Visual Style: Magazine

The landing page uses a magazine-style editorial layout — dark background, high-contrast
typography, and artwork as the dominant visual element. Inspired by music press front pages
(think Mojo, Uncut, or a record shop window).

#### Hero Section

A full-width banner at the top of the page:

- **Site title** — large, bold, serif or slab-serif font (e.g. Georgia or a Google Font such
  as Playfair Display). Set in `config.ini [site] site_title`.
- **Tagline** — short optional subtitle set in `config.ini [site] site_tagline`. The template
  appends " – brought to you by [Hearmoretunes](http://hearmoretunes.com)" automatically,
  so `site_tagline` should just be the descriptive text (e.g. "A curated music collection").
- **Stats bar** — e.g. "42 playlists · 1,043 tracks · 2019–2024". Generated at build time.
- Dark background (`#111` or near-black), light text, accent colour (configurable in
  `config.ini [site] accent_color`, default `#e8b84b` — warm gold).

#### Playlist Card Grid

Below the hero, a responsive card grid of all playlists:

- **Layout:** 3 columns on desktop, 2 on tablet, 1 on mobile (CSS Grid)
- Each card is a large, visually bold tile:
  - **Playlist name** — prominently at the top in gold (`var(--accent)`) Playfair Display
    serif, bold. This is the primary identity element of the card.
  - **Art cloud** — below the name, all available track artwork thumbnails (~44×44 px each)
    displayed as a wrapping mosaic. Scales naturally with however many images were fetched.
    Replaces the old 2×2 fixed collage.
  - **Track count + year range** — smaller, muted text in the card footer
    (e.g. "25 tracks · 1966–1992")
  - **Hover effect** — subtle scale-up; accent-colour glow border on the card
  - Full card is a clickable link to the playlist page

#### Sort Order

**Default on page load: Alphabetic** (natural sort, `localeCompare` with `{ numeric: true }`).

Two sort buttons are shown on the landing page:
- **Alphabetic** — active by default; natural sort on playlist display name
- **Date Added** — newest first, based on reversed position in `playlist_order` in `config.ini [playlists]`

The old "Default" button (insertion order) has been removed. `playlist_order` still controls
Date Added ordering (oldest-first entry → newest-first display).

#### Playlist Order in `config.ini`

```ini
[playlists]
playlist_order =
    nuggets-396-covers-xx
    nuggets-397-covers-xxi
```

The list is optional — if empty, all XMLs in the input directory are included and sorted
alphabetically. Slugs are listed oldest-first; the Date Added sort reverses the list so the
newest playlist appears at the top.

---

### `playlists/<slug>.html` — Playlist Page

Same visual design as current output (`covers_xx_v5.html`), with these additions:

- **Shared nav bar** at the top:
  - Site title / home link (→ `index.html`)
  - "Search" link (→ `search.html`)
  - Previous / Next playlist links (alphabetical or sort order)
- **Page title** uses playlist name from XML (same as current)
- **Track cards** (3-column grid):
  - Artwork loaded from `../img/<slug>/NN.jpg` (external file, not base64)
  - Song title
  - Cover artist and album on one line: `Artist Name — Album Name (Year)` (same colour, em-dash separator)
  - Review/info links (Pitchfork, BBC, Chorus, AllMusic, Discogs, MusicBrainz, etc.)
  - Original artist label (covers mode)

---

### `search.html` — Search Page

- Single text input (autofocused)
- Loads `search_index.json` once on page load
- Uses Fuse.js for fuzzy search across song title and artist fields
- Results displayed as a styled list:
  - Song title — Artist
  - Below each result: pill badges for each playlist the song appears on (clickable, links to that playlist page anchored to the track card)
- No results / empty state message
- Results update live as the user types (debounced ~200ms)
- "Back to home" link

---

### `search_index.json` — Search Data

Array of track objects, one per track across all playlists:

```json
[
  {
    "title": "Ring of Fire",
    "artist": "Eric Burdon & The Animals",
    "original_artist": "Johnny Cash",
    "album": "Good Times: A Collection",
    "year": 1992,
    "playlist_name": "Nuggets 396 – Covers XX",
    "playlist_slug": "nuggets-396-covers-xx",
    "track_num": 4
  },
  ...
]
```

Fuse.js is configured to search `title` and `artist` fields only (per spec).

---

## Artwork Strategy

Priority waterfall — first source that returns bytes wins:

1. Art file override (local disk — highest priority, always read fresh)
2. **Embedded artwork** from source MP3 (APIC frame) or M4A (covr atom) — local disk, no network *(V2.2 / V2.6.1)*
3. Disk cache (keyed by MBID + artist + album — skips all network if hit)
4. Deezer API (network — via Deezer track ID in MP3 `TXXX` tag or M4A freeform atom)
5. MusicBrainz Cover Art Archive (network — via MBID, override or looked up)
6. Placeholder image (grey SVG with music note)

Artwork is saved to `output/img/<slug>/NN.jpg` (JPEG, max 500×500px).
The **shared art cache** (configured in `config.ini [paths] art_cache_dir`) stores raw downloaded images keyed by
source URL, so the same release artwork is only fetched once across all playlists.

### Missing Art Report

After each build, both `playlist_generator.py` and `build_site.py` emit a missing-art report
listing every track that ended up with a placeholder image. The report tells the user:

- The playlist name and the `img/` folder path to drop files into
- The track number, exact target filename (e.g. `10.jpg`), and a "search for" hint of
  `<album>  —  <artist>` to use on Google Images, Discogs, or MusicBrainz

This supports a **best-effort + manual fallback** workflow:
1. Run the build — auto-fetching finds as many images as possible
2. Review the missing-art report printed at the end of the run
3. Manually find and save the missing images into the `img/` folder with the filename shown
4. Run `upload_site.bat` to push to GitHub Pages

The list of missing tracks is also written to `playlist_meta.json` under a `missing_art` key
so it is available to `build_site.py` for the consolidated cross-playlist summary.

---

## Caching

| Cache | Location | Keyed by |
|-------|----------|----------|
| Artwork images | `output/img/<slug>/` | Track number (final output) |
| Raw art downloads | `<art_cache_dir>/` | Source URL hash |
| MusicBrainz link lookups | `<links_cache_dir>/` | `<slug>_<track_num>` |

Caches persist between runs. `--force` clears and rebuilds all caches for the targeted playlist(s).

---

## Non-Covers Mode (Future)

The `covers_mode` flag (global in `config.ini [build]`, overridable per-playlist via overrides JSON)
controls:

- Whether to parse `[Original Artist]` from the track Name field
- Whether to show "original artist" and "cover artist" labels on track cards
- Whether MusicBrainz search uses album + cover artist vs. album + track artist

When `covers_mode: false`:
- Artist field is treated as the sole artist (no bracket parsing)
- Card layout omits "original artist" row
- MusicBrainz lookup uses album + artist as-is

This means the same codebase handles both playlist types with no structural changes.

---

## Overrides File Format

Per-playlist JSON sidecar, placed in `input/overrides/<slug>_overrides.json`:

```json
{
  "mbid_overrides": {
    "4": "c1aa4fa7-...",
    "5": "66813847-..."
  },
  "album_display_overrides": {
    "5": "The Whitey Album"
  },
  "art_file_overrides": {
    "12": "/absolute/path/to/feelies_main.jpg"
  },
  "covers_mode": true
}
```

The `covers_mode` key in the overrides file overrides the global `config.ini` setting for
that playlist only.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP calls to MusicBrainz, Deezer, CAA |
| `mutagen` | Read MP3 ID3 tags and M4A atoms; extract embedded artwork |
| `Pillow` | Resize and convert artwork images |
| `fuse.min.js` | Client-side fuzzy search (bundled, no CDN) |

No other dependencies. Python 3.9+.

---

## Development Sequence

1. ✅ Refactor `itunes_playlist_html.py` → `playlist_generator.py` (external images, root-relative CSS/JS paths, nav component, return track data)
2. ✅ Write shared `style.css` (extract from current inline styles)
3. ✅ Write `build_site.py` orchestrator (scan, incremental build, index, search index, CNAME output)
4. ✅ Write `index.html` template (magazine-style landing page)
5. ✅ Write `search.html` + Fuse.js integration
6. ✅ Deploy to GitHub Pages — site live at `https://kiwipaulrob.github.io/hearmycovers/` and `https://hearmycovers.com`
7. ✅ Add missing-art report to `playlist_generator.py` and `build_site.py` (best-effort auto-fetch + manual fallback)
8. ✅ Fix Windows cp1252 UnicodeEncodeError — emoji in print statements (`⚠`, `🖼`) crashed on Windows console; fixed by adding `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at startup of both scripts
9. ✅ Fix `NoneType` crash in `build_site.py` missing-art loop — guarded `for meta in all_playlist_meta if meta` to skip entries where subprocess crashed before writing `playlist_meta.json`
10. ✅ Fix duplicate playlist detection on Windows — `glob("*.xml") + glob("*.XML")` matched same files twice on case-insensitive filesystem; fixed by deduplicating via `path.resolve()` before processing
11. ✅ XML file and playlist name corrected to `Nuggets 396 - Covers XX`; overrides file renamed to match new slug `nuggets-396-covers-xx`
12. ✅ Fix `Â·` / garbled-character encoding bug in browser — added `charset=utf-8` meta tag to all HTML pages
13. ✅ Fix "orig. orig." double-prefix bug — iTunes XML Name field contains `[orig. Artist]`; parser now strips any leading `orig.` from the captured `orig_artist` group so the card renders "orig. Artist" not "orig. orig. Artist"
14. ✅ Landing page card redesign — replaced 2×2 collage with **name-prominent + art-cloud** layout: playlist name in gold serif at top; wrapping mosaic of all available 44×44 px album art thumbnails below; footer with track count + year range
15. ✅ Hero tagline updated — appends " – brought to you by [Hearmoretunes](http://hearmoretunes.com)" automatically; `site_tagline` in `config.ini` remains just the descriptive text
16. ✅ Fix all UTF-8 encoding garble (`â€"`, `Â·`) — replaced literal `–`/`·` chars in HTML output with `&ndash;`/`&middot;` HTML entities throughout `build_site.py` and `playlist_generator.py`
17. ✅ Fix Windows `open()` encoding bug — all JSON file reads/writes now use `encoding='utf-8'` to prevent cp1252 double-encoding of special characters
18. ✅ Fix landing page art-cloud showing only 4 images — `build_index_page` now scans the actual `img/` folder on disk instead of trusting stale `art_thumbnails` from cached `playlist_meta.json`
19. ✅ V2.2 — MP3 embedded APIC artwork extraction (see V2.2 section above)
20. ✅ Fix `file:///` path parsing on Windows — `url2pathname` + `unquote` now correctly resolves iTunes `Location` URIs; Deezer lookups also benefit from this fix
21. ⬜ Re-run with `--force` to pick up embedded artwork from MP3 files and fresh Deezer lookups
22. ⬜ Fill remaining missing artwork via manual fallback (missing-art report will guide)
23. ⬜ Scale test with larger playlist set

---

## Hosting — GitHub Pages

The output directory is deployed to GitHub Pages via a Git-backed repo.  
**Cloudflare Pages was abandoned** — wrangler uploads the entire repo including `.git` (53MB pack file, over 25MB limit). Not worth restructuring.

### Live URLs

| | URL |
|---|---|
| GitHub repo | `https://github.com/kiwipaulrob/hearmycovers/` |
| GitHub Pages | `https://kiwipaulrob.github.io/hearmycovers/` |
| Custom domain | `https://hearmycovers.com` |

### Deployment Workflow

1. Run `playlist_generator.py` for any new/changed playlists
2. Run `rebuild_site.bat` — regenerates `index.html`, `search.html`, playlist pages
3. Run `upload_site.bat` — `git add . && git commit && git push origin main`
4. GitHub Pages auto-deploys within ~30 seconds

> **Note:** Output folder (`hearmycovers`) must NOT be inside OneDrive — OneDrive file locking causes `git push` permission errors. Pause OneDrive sync before pushing if needed.

### Custom Domain DNS (hearmycovers.com)

Four A records (apex) + one CNAME (www) at your registrar:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `kiwipaulrob.github.io` |

In GitHub → Settings → Pages: set Custom domain to `hearmycovers.com`, tick **Enforce HTTPS**.

**CNAME file:** `build_site.py` automatically writes a `CNAME` file to the output root on every build, containing the value of `custom_domain` from `config.ini [site]`. Without this file GitHub Pages will not serve the site at the custom domain — and manually-placed files would be wiped on every rebuild.

### Local Testing

```bash
cd /path/to/output
python3 -m http.server 8000
# Open http://localhost:8000
```

This is optional for v1 but recommended once the site is in regular use.

### `_redirects` File (Optional)

A `_redirects` file can be added for a clean URL redirect from `/search` → `/search.html`
if desired. Not required for v1.

---

## Out of Scope (v1)

- RSS feed
- Sitemap XML
- Server-side search
- User accounts / favourites
- Genre or year filtering on index page
- Pagination of search results (Fuse.js handles this client-side)
- Serverless functions (beyond GitHub Pages static hosting)

---

## Version 2 — Planned Features

### V2.1 — Additional Hyperlinked Sources ✅ DONE

Six streaming/search services are now always shown as **database pills** on every track card.
Links are constructed from `title + cover artist` — no additional API calls required.

| Service | Link pattern |
|---------|-------------|
| **YouTube** | `https://www.youtube.com/results?search_query=Title+Artist` |
| **Spotify** | `https://open.spotify.com/search/Title+Artist` |
| **Apple Music** | `https://music.apple.com/search?term=Title+Artist` |
| **Deezer** | `https://www.deezer.com/search/Title+Artist` |
| **Bandcamp** | `https://bandcamp.com/search?q=Title+Artist` |
| **SoundCloud** | `https://soundcloud.com/search?q=Title+Artist` |

All use `urllib.parse.quote_plus(title + " " + artist)`. If `title` is empty, falls back to
`artist + " " + album`. These are appended to the `databases` list in `best_links()` after any
MusicBrainz-sourced pills, so they always appear last in the database pill row.

Hype Machine dropped — Bandcamp/SoundCloud/Deezer cover that niche better.

---

### V2.6.1 — M4A Embedded Artwork + Deezer ID Support ✅ DONE

Extended `playlist_generator.py` to handle **M4A (AAC/iTunes) files** in addition to MP3:

- `get_embedded_artwork()` — detects `.m4a` → reads `covr` atom via `MP4()`; MP3 APIC path unchanged
- `get_deezer_id()` — detects `.m4a` → reads `----:com.apple.iTunes:Deezer_track_ID` freeform atom; MP3 TXXX path unchanged
- `from mutagen.mp4 import MP4` added to import block (part of standard `mutagen` package — no new dependency)
- Both functions renamed `mp3_path` → `file_path`; called with positional args only — no callers needed updating
- All errors caught by `except Exception: return None` — malformed M4A files fail silently, same as MP3

---

### V2.2 — MP3 Embedded Artwork Extraction ✅ DONE

Extended the artwork waterfall in `playlist_generator.py` to extract `APIC` (attached picture) frames
from the source MP3 file before hitting any network source.

**Implementation:**
- New `get_embedded_artwork(mp3_path)` function — tries all APIC frames, prefers type 3 (Cover front)
- Fixed `Location` URI parsing to use `url2pathname` + `unquote` for cross-platform correctness:
  iTunes `file:///C:/Users/...` paths now resolve correctly on Windows (previously `os.path.exists`
  was silently failing, blocking both APIC and Deezer lookups)
- Slotted as step 3 in waterfall (after override + disk cache, before Deezer + MusicBrainz)
- Gracefully skips if file not found (path may be on a different machine or drive)
- `mutagen` was already a project dependency — no new packages required

**To benefit from embedded artwork and Deezer lookups:** run with `--force` on each playlist
to clear cached `None` results from the old broken Windows path handling.

---

### V2.3 — PyInstaller Single-File Windows Executable

Package the CLI tools as a single `.exe` so the build can be run by double-clicking without
opening a terminal or having Python installed.

**Approach:**
- Use PyInstaller `--onefile` mode to bundle `build_site.py` and all dependencies
- Entry point: `build_site.py` — wraps `playlist_generator.py` as a library (already the case)
- At startup, if no `--input` / `--output` args are supplied, prompt the user interactively
  (simple `input()` prompts in the same terminal window that opens on double-click)
- Alternatively, ship a `run_build.bat` launcher alongside the `.exe` with paths pre-configured

**Build command (developer machine):**
```powershell
pyinstaller --onefile --name hearmycovers build_site.py
```

**Output:** `dist/hearmycovers.exe` — single redistributable file (~15–20 MB with all deps bundled)

**Known PyInstaller considerations:**
- `requests`, `mutagen`, `Pillow` are all PyInstaller-compatible; no hidden imports expected
- Test on a clean Windows machine without Python installed to verify bundling
- `--collect-data mutagen` may be needed if mutagen reads format definition files at runtime

**Estimated effort:** ~5 hours (build, test on clean machine, write launcher `.bat`, update help manual).

---

## Bug Fix Log (2026-04)

### Sort buttons non-functional + ASCII sort (2026-04-07)
- **Root cause:** IIFE used `getElementById('playlist-grid')` (hyphenated) but the actual HTML
  element has `id="playlistGrid"` (camelCase). JS returned `null`, threw `TypeError`, crashed the
  entire `<script>` block before click listeners were attached. Sort buttons rendered but were inert.
- **Side effect:** Alphabetic sort never ran either — cards displayed in Python insertion order
  (effectively ASCII/filesystem glob order).
- **Fix:** Change `getElementById('playlist-grid')` → `getElementById('playlistGrid')` in
  `build_site.py`.

### Landing page art-cloud blank on cached builds
- **Root cause:** Build caches by XML hash; cached `playlist_meta.json` pre-dating the art-cloud feature lacks `art_thumbnails`, so `meta.get("art_thumbnails", [])` returned `[]` → card showed only dark placeholder.
- **Fix 1 (`build_site.py`):** Fallback in `build_index_page` — if `art_thumbnails` absent, construct paths `/playlists/{slug}/img/01.jpg … NN.jpg` for all tracks; browser hides 404s via `onerror="this.style.display='none'"`.
- **Fix 2 (user action):** Run with `--force` after upgrading scripts to regenerate meta with proper `art_thumbnails` key.


## Links

Each track card shows clickable pill links in two categories.

**Two visual categories:**
- **Review pills** — gold background (site accent colour), shown first. Sourced from MusicBrainz
  `review`-type URL relationships: Pitchfork, BBC, Chorus (chorus.fm / chorus.reviews), Guardian,
  Rolling Stone, NME, Stereogum, Metacritic, and any other review site MB knows about.
- **Database pills** — dark border, shown after reviews. MusicBrainz-sourced: AllMusic, Discogs,
  RYM, Wikidata, MusicBrainz, Last.fm, 45cat, SecondHandSongs, WhoSampled. Plus always-present
  constructed links (see V2.1): YouTube, Spotify, Apple Music, Deezer, Bandcamp, SoundCloud.

Every pill includes a **16×16 px favicon** (Google Favicon CDN: `www.google.com/s2/favicons`)
so services are visually recognisable without reading the label.

**Pill appearance logic — two mechanisms:**

1. **MusicBrainz-sourced pills** (Pitchfork, BBC, Guardian, AllMusic, Discogs, RYM, Wikidata,
   Last.fm, 45cat, SHS, WhoSampled, MusicBrainz):
   - Only appear if MB has a URL relationship stored against that specific release MBID.
   - Process: MB queried → URL relationships returned → each URL matched against `LINK_DEFS`
     domain patterns → match found → pill shown with exact MB-stored URL.
   - If MB has no relationship for a site → **no pill** for that site on that card.
   - Planned fallback (V2.x): if no MB direct link, fall back to a configured `*_search_url`
     so the pill always appears as a search link rather than being hidden.

2. **Always-constructed pills** (YouTube, Spotify, Apple Music, Deezer, Bandcamp, SoundCloud):
   - Always appear on every card — no MB lookup required.
   - URL template read from `config.ini [links]` (e.g. `youtube_search_url`).
   - Query mode defaults to `constructed_link_query` in `config.ini [search_terms]`,
     but each site can override it (e.g. `discogs_query = album_and_artist`).
   - The `_build_query()` function builds the URL-encoded query string per mode.

**MusicBrainz search strategy** (controlled by `search_attempts` in config.ini, default 4):
1. `release:"Album" AND artist:"Cover Artist"` — precise album search
2. `"Album" "Cover Artist"` — loose album fallback
3. `recording:"Song Title" AND artist:"Cover Artist"` — title-based fallback
4. `"Song Title" "Cover Artist"` — loose title fallback

Set `search_attempts = 2` in config.ini to skip title-based fallbacks (faster but less thorough).

**Constructed search links** use per-site query mode and URL templates from config.ini.

Unknown review sites (MB `type = review`, unrecognised domain) are added automatically with
the domain name as label — no code change required when MB gains new review partnerships.

---

## config.ini  ✅ IMPLEMENTED (V2.4, config wiring fixes V2.4.1)

All configurable values are stored in `config.ini` alongside the scripts. Scripts read it at
startup via Python's `configparser`. Neither script nor `.bat` file contains hardcoded paths.

**V2.4.1 fixes** — previously dead config values now wired up:
- `*_search_url` templates: constructed link URLs read from config.ini (was hardcoded)
- Per-site `[search_terms]` overrides (e.g. `discogs_query = album_and_artist`): now passed to `_build_query()`
- `search_attempts`: controls how many MusicBrainz fallback strategies are tried (was always 4)
- `thumbnail_size`: injected as CSS variable `--thumb-size` into landing page `<head>`; `style.css` uses `var(--thumb-size, 44px)`
- `--help` epilog: removed misleading `site.json` example showing `covers_mode`/`custom_domain`

**Format:** `config.ini` (INI format — human-readable, no Python knowledge required).
**`.bat` files:** Fully updated — zero hardcoded paths. `rebuild_site.bat` calls `python build_site.py` with no arguments. `upload_site.bat` reads `output_dir` dynamically via `python build_site.py --print-config paths.output_dir`.

**Priority:** `config.ini` > built-in defaults. `site.json` has been fully removed — `playlist_order` now lives in `config.ini [playlists]`.

```ini
# ─────────────────────────────────────────────────────────────────
# config.ini — iTunes Playlist Site Builder
# ─────────────────────────────────────────────────────────────────

[paths]
xml_input_dir    = C:\Users\prob\OneDrive\Documents2\Playlists
output_dir       = C:\Users\prob\OneDrive\Documents2\hearmycovers
art_cache_dir    =          # leave blank → output_dir\art_cache
links_cache      =          # leave blank → script_dir\links_cache.json

[build]
covers_mode      = true     # show "orig. Artist" labels on cards
force_rebuild    = false    # regenerate all playlists even if unchanged
verbose          = false    # print detailed progress to console

[musicbrainz]
base_url         = https://musicbrainz.org/ws/2
caa_url          = https://coverartarchive.org
user_agent       = PlaylistSiteGenerator/1.0 (https://github.com/kiwipaulrob/hearmycovers)
rate_delay       = 1.1      # seconds between requests (MB rate limit)
request_timeout  = 15       # seconds per HTTP request
search_limit     = 5        # results fetched per search attempt
search_attempts  = 4        # number of fallback search strategies

[artwork]
caa_image_size   = 500      # CAA resolution: 250, 500, or 1200
deezer_timeout   = 10       # seconds for Deezer API calls
thumbnail_size   = 44       # px — art-cloud thumbnails on landing page

[site]
site_title          = Hear My Covers
site_tagline        = A curated music collection
accent_color        = #e8b84b
orig_label          = orig.     # prefix on cover cards e.g. "orig. The Smiths"
hearmoretunes_url   = http://hearmoretunes.com
custom_domain       = hearmycovers.com   # written to CNAME file on every build; leave blank to skip

[cdn]
fuse_js_url      = https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js
favicon_cdn_url  = https://www.google.com/s2/favicons

# [cache_control] — removed; GitHub Pages does not support custom cache headers
# (was used for Cloudflare Pages _headers file — no longer applicable)

[links]
# Comma-separated list of enabled sites in display order.
# Remove any entry to hide that pill from all cards.
enabled_review_sites  = pitchfork, bbc, chorus, theguardian, rollingstone,
                        allmusic_rev, nme, stereogum, metacritic
enabled_db_sites      = allmusic, discogs, rateyourmusic, wikidata, musicbrainz,
                        last.fm, 45cat, secondhandsongs, whosampled,
                        youtube, spotify, applemusic, deezer, bandcamp, soundcloud

# Review site search URLs — used as fallback when MB has no direct link for a release.
# Remove a line to suppress that pill when no MB link exists.
pitchfork_search_url    = https://pitchfork.com/search/?query={query}
bbc_search_url          = https://www.bbc.co.uk/music/search?q={query}
chorus_search_url       = https://chorus.fm/search?q={query}
theguardian_search_url  = https://www.theguardian.com/music/search?q={query}
rollingstone_search_url = https://www.rollingstone.com/music/?s={query}
allmusic_rev_search_url = https://www.allmusic.com/search/all/{query}
nme_search_url          = https://www.nme.com/search?q={query}
stereogum_search_url    = https://www.stereogum.com/?s={query}
metacritic_search_url   = https://www.metacritic.com/search/{query}/

# Database site search URLs — used as fallback when MB has no direct link for a release.
allmusic_search_url         = https://www.allmusic.com/search/all/{query}
discogs_search_url          = https://www.discogs.com/search/?q={query}
rateyourmusic_search_url    = https://rateyourmusic.com/search?searchterm={query}
wikidata_search_url         = https://www.wikidata.org/w/index.php?search={query}
musicbrainz_search_url      = https://musicbrainz.org/search?query={query}&type=release
lastfm_search_url           = https://www.last.fm/search?q={query}
45cat_search_url            = https://www.45cat.com/search/?q={query}
secondhandsongs_search_url  = https://secondhandsongs.com/search?q={query}
whosampled_search_url       = https://www.whosampled.com/search/?q={query}

# Always-constructed links (no MB lookup needed)
youtube_search_url    = https://www.youtube.com/results?search_query={query}
spotify_search_url    = https://open.spotify.com/search/{query}
applemusic_search_url = https://music.apple.com/search?term={query}
deezer_search_url     = https://www.deezer.com/search/{query}
bandcamp_search_url   = https://bandcamp.com/search?q={query}
soundcloud_search_url = https://soundcloud.com/search?q={query}

[search_terms]
# What {query} is built from for all search URL templates above.
# Options: title_only, artist_only, title_and_artist, album_only, album_and_artist
constructed_link_query = title_and_artist

# Per-site overrides — uncomment to override the default above for specific sites.
# pitchfork_query           = album_and_artist
# discogs_query             = album_and_artist
# secondhandsongs_query     = title_only
# whosampled_query          = title_only
```

---

## Code Quality Notes

### `import urllib.parse` placement
Must be at the top of `playlist_generator.py` with all other imports — not inside `best_links()`.

### Sort JS — no redundant variable declarations
In `build_site.py`, the sort IIFE must use the outer-scope `grid` and `cards` variables already declared — do not re-declare them inside the IIFE.

### `site_root` parameter is dead code
`generate_playlist()` accepts `--site-root` but does not use it. The HTML template hardcodes `../../style.css`. Parameter retained for backward compatibility but has no effect.

### `art_thumbnails` in `playlist_meta.json`
The `art_thumbnails` key is written to `playlist_meta.json` but `build_site.py` ignores it — the art cloud scans the actual `img/` folder on disk instead. Retained in JSON for possible future use.

### CSS class names must match HTML templates exactly
The following mappings are authoritative (bugs existed before V2.6 where HTML and CSS diverged):
- Playlist card footer: HTML `class="playlist-card-footer"` ↔ CSS `.playlist-card-footer`
- Year range span: HTML `class="card-year-range"` ↔ CSS `.card-year-range`
- Active nav link: HTML `class="active"` ↔ CSS `.site-nav a.active`
- Sort bar: `.playlist-sort-bar`, `.sort-btn`, `.sort-label`, `.sort-btn.active` — all defined in `style.css`
- Search page: `.search-page`, `.search-heading`, `.search-stats` — all defined in `style.css`
- Nav separator dot: `.nav-sep` — defined in `style.css`

### `slugify()` must be identical in both Python files
`build_site.py` and `playlist_generator.py` each define their own `slugify()`. They **must** produce identical output for all inputs (including non-ASCII playlist names), otherwise `build_site.py` constructs the wrong folder path and cannot find `playlist_meta.json`.

Both functions use NFKD Unicode normalization → ASCII encode → strip non-word chars → lowercase → collapse separators to `-`.

---

---

## V2.8 — Statistics Page ✅ DONE

### Overview
Generates a statistics summary page showing aggregate data across all playlists: track counts, artist frequencies, timeline distribution, and total duration.

### Components

#### 1. `stats.py`
New CLI tool that:
- **Input**: Path to iTunes XML input directory
- **Output**: `stats.json` (contains aggregated statistics)
- **Data computed**:
  - Total tracks across all playlists
  - Total playlists
  - Unique original artists (count)
  - Unique cover artists (count)
  - Total duration in hours (sum of "Total Time" from all tracks)
  - Top 10 original artists by frequency
  - Songs grouped by decade (1920s → 2020s)
  - Top 10 most prolific cover artists

**Parsing**: Reuses iTunes XML format from `parse_itunes_xml()` in `playlist_generator.py`.

#### 2. `stats.html`
Interactive statistics page featuring:
- **Header**: Navigation bar (matching landing page style) with links to Playlists, Search, Statistics
- **"By the Numbers"**: 5 stat cards (gold accent borders) showing: Tracks, Playlists, Original Artists, Cover Artists, Total Hours
- **Charts** (using Chart.js):
  - **Top Original Artists** (horizontal bar chart, 10 artists, gold bars)
  - **Songs By Decade** (vertical bar chart showing distribution from 1920s–2020s, purple bars)
  - **Most Prolific Cover Artists** (horizontal bar chart, 10 artists, teal bars)
- **Styling**: Dark magazine aesthetic matching landing page; gold accents (`#e8b84b`); responsive layout
- **Data loading**: Fetches `stats.json` via client-side JavaScript; displays "Loading..." while waiting

#### 3. Build Integration (`build_site.py`)
- New `build_statistics()` function:
  - Calls `stats.py` with `--xml-dir` and `--output` flags
  - Generates `stats.json` in output root
  - Copies `stats.html` to output root
- Invoked during site build (after search/index, before CNAME write)
- Added `subprocess` import

#### 4. Navigation Updates
- **Landing page** (`index.html`): Nav bar now includes "Statistics" link
- **Stats page**: Has nav bar with "Playlists" and "Search" links; "Statistics" marked active
- **Search page**: Updated to include "Statistics" link (for consistency)

### Data Isolation
- No genre tagging; all data derived purely from iTunes metadata:
  - Artist names (cover artist + original artist from title brackets)
  - Track duration (Total Time in ms)
  - Year (from Year field)
- Decades are computed as `(year // 10) * 10`; tracks with no year are skipped in decade grouping

### Limitations
- Statistics reset on every build (no incremental updates to `stats.json`)
- Covers only playlists that have parsed successfully
- No per-user customization or filtering

### Future Enhancements (V2.9+)
- Filter by decade / original artist / cover artist
- Export statistics as CSV
- Year-on-year comparisons (if tracking builds over time)
- Genre classification (when available in future refactor)

---

## V2.7 — Planned Features

### M3U / M3U8 Input Support
**Priority:** Low (all current playlists are iTunes XML; implement only if needed)
**Estimated effort:** 3–4 hours

#### What M3U provides
Standard `#EXTINF` lines supply: duration, a combined "Artist - Title" string, and a local file path. No album, year or artwork is embedded in the M3U format itself.

#### Implementation plan

1. **`parse_m3u(path)`** — new function alongside `parse_itunes_xml()`:
   - Parse `#EXTM3U` header
   - Extract playlist name from `#PLAYLIST:` tag if present; fall back to filename stem
   - Split each `#EXTINF` artist–title string on first ` - ` (handle edge cases: multiple dashes, missing delimiter)
   - Return same track-dict format as `parse_itunes_xml()` so the rest of the pipeline is unchanged

2. **`mutagen` ID3 reader** — called after `parse_m3u()` to enrich each track:
   - Read `TPE1` (artist), `TIT2` (title), `TALB` (album), `TDRC` (year), `APIC` (embedded artwork), `TXXX:DEEZER_ID` from the MP3 file at the path listed in the M3U
   - Falls back gracefully if file is not accessible (network share offline, etc.)
   - `mutagen` added to `requirements.txt`

3. **`discover_playlists()` in `build_site.py`** — glob `*.m3u` and `*.m3u8` in addition to `*.xml` / `*.XML`; route to the correct parser based on file extension

4. **MusicBrainz search strategy** — when album is available (from ID3) use existing Album+Artist search; when album is missing fall back to Title+Artist (less accurate — noted in missing-art report)

5. **`#PLAYLIST:` tag** — used as playlist display name if present

#### Limitations vs iTunes XML
- Album metadata only available if ID3 tags are populated or `mutagen` can read the file
- MusicBrainz matches less reliable when album is missing (Title+Artist search instead of Album+Artist)
- MP3 files must be accessible at build time for ID3 extraction

#### Config changes needed
- No new config.ini keys required; `xml_input_dir` becomes `input_dir` semantically (rename optional)

---

## Changelog

### V2.9 — Navigation Refactor + Artist Name Cleaning ✅
- **Navigation**: Updated all three pages (landing, search, stats) to show consistent navigation order: **Playlists → Search → Statistics**
- **Navigation labels**: Changed landing page nav link from site title to **"Playlists"** (matches search & stats pages)
- **Search page**: Now includes all three nav links (previously was missing Statistics link)
- **Stats page**: Updated to use "Playlists" label instead of hardcoded site title
- **Artist name cleaning** (`stats.py`): Added `clean_artist_name()` function to filter descriptive labels from original artist names:
  - Removes: "live", "live version", "live at", "acoustic", "remix", "version", "cover", "remaster", "remastered"
  - Also handles `(live)` and `[live]` formats
  - Prevents false artist entries in statistics (e.g., prevents "Elvis - live" being counted as two separate artists)
  - Applied in both unique artist count and top-artist frequency calculations

### V2.8 — Statistics Page
- Added `stats.py`: CLI tool to compute aggregate statistics (track count, artist frequencies, decade distribution, total hours)
- Added `stats.html`: Interactive statistics page with Chart.js visualizations (top original artists, songs by decade, prolific cover artists)
- Updated `build_site.py`: New `build_statistics()` function integrates stats generation into build pipeline
- Updated navigation: Landing page, stats, and search pages all link to each other
- Output directory now includes `stats.json` and `stats.html`

### V2.6.1 — M4A Embedded Artwork + Deezer ID Support ✅
- Added M4A format support via `mutagen.mp4.MP4()`
- `get_embedded_artwork()`: Reads M4A `covr` atom (equivalent to MP3 APIC frame)
- `get_deezer_id()`: Reads M4A freeform atom `----:com.apple.iTunes:Deezer_track_ID` (decoded as UTF-8)
- Inline comments updated: "MP3" → "MP3/M4A" in three places describing artwork waterfall

### V2.6 — Bug fixes (post-PR audit)
- **CSS class mismatches fixed**: `card-meta` → `playlist-card-footer`; `card-year` → `card-year-range` in `build_site.py` HTML templates
- **Active nav highlight fixed**: `nav-active` → `active` class in `INDEX_HTML` and `SEARCH_HTML` (CSS rule is `.site-nav a.active`)
- **Missing CSS added**: `.playlist-sort-bar`, `.sort-btn`, `.sort-label`, `.sort-btn.active`, `.index-grid-wrap`, `.search-page`, `.search-heading`, `.search-stats`, `.nav-sep` — all were referenced in HTML but absent from `style.css`
- **`slugify()` unified**: `build_site.py` updated to use same NFKD normalization as `playlist_generator.py`; divergence caused wrong folder paths for non-ASCII playlist names
- **Per-thread HTTP sessions**: `playlist_generator.py` now creates one `requests.Session` per worker thread via `_get_thread_session()` / `threading.local()` instead of sharing a single session across 5 concurrent threads
- **File handle fixed**: `fetch_artwork()` now uses `with open(...)` context manager for the art file override path
