#!/usr/bin/env python3
"""
build_site.py — iTunes Playlist Site Orchestrator
===================================================
Builds a complete static website from a folder of iTunes XML playlist files.

Usage:
    python3 build_site.py --input /path/to/xmls --output /path/to/output [options]

See --help or itunes_playlist_site.txt for full documentation.
"""

import argparse
import json
import os
import configparser
import re
import unicodedata
import shutil
import subprocess
import concurrent.futures
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import hashlib
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# config.ini Loading
# ---------------------------------------------------------------------------

def _load_ini_config():
    """Load config.ini from the same directory as this script."""
    ini_path = Path(__file__).parent / "config.ini"
    cfg = configparser.ConfigParser(interpolation=None)
    if ini_path.exists():
        cfg.read(ini_path, encoding='utf-8')
    return cfg

_INI = _load_ini_config()

def _ini_get(section, key, fallback=''):
    try:
        return _INI.get(section, key).strip()
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback

def _ini_bool(section, key, fallback=False):
    return _ini_get(section, key, 'true' if fallback else 'false').lower() in ('true', '1', 'yes', 'on')


# ---------------------------------------------------------------------------
# Argument Parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        prog="build_site.py",
        description="Build a static multi-playlist site from iTunes XML files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES
--------
  # Basic build from a folder of XMLs
  python3 build_site.py --input ~/Playlists --output ~/site/output

  # Force rebuild all playlists (ignore cache)
  python3 build_site.py --input ~/Playlists --output ~/site/output --force

  # Build a single playlist only
  python3 build_site.py --input ~/Playlists --output ~/site/output --only "Covers XX"

  # Dry run — show what would be built without writing files
  python3 build_site.py --input ~/Playlists --output ~/site/output --dry-run

  # Serve the output locally for testing
  python3 build_site.py --serve --output ~/site/output

OUTPUT STRUCTURE
----------------
  output/
  ├── index.html          Landing page with playlist card grid
  ├── search.html         Full-text search page (Fuse.js)
  ├── search_index.json   Search index consumed by search.html
  ├── style.css           Shared stylesheet (copied from script dir)
  ├── playlists/
  │   ├── covers-xx/
  │   │   ├── index.html  Playlist page
  │   │   └── img/        Album artwork for this playlist
  │   └── ...
  └── img/
      └── ...             Shared/reused artwork (future use)

OVERRIDES FILE
--------------
  Place a JSON file named <playlist-slug>_overrides.json alongside the XML
  to apply per-track overrides:

  {
    "mbid_overrides":          { "4": "<mbid>" },
    "album_display_overrides": { "5": "Custom Album Name" },
    "art_file_overrides":      { "12": "/absolute/path/to/photo.jpg" }
  }

SITE CONFIG
-----------
  All settings (title, tagline, accent colour, playlist order, etc.)
  are configured in config.ini. See itunes_playlist_site.txt for full details.

GITHUB PAGES DEPLOYMENT
-----------------------
  1. Run build_site.py to generate the output/ folder
  2. cd into the output/ folder
  3. git add -A && git commit -m "Update site" && git push origin main
  4. Your site is live at https://kiwipaulrob.github.io/hearmycovers/
     and at https://hearmycovers.com once DNS has propagated

DEPENDENCIES
------------
  pip install requests mutagen Pillow
"""
    )

    parser.add_argument("--input", "-i", metavar="DIR",
                        default=_ini_get('paths', 'xml_input_dir') or None,
                        help="Directory containing iTunes XML playlist files")
    parser.add_argument("--output", "-o", metavar="DIR",
                        default=_ini_get('paths', 'output_dir') or "./output",
                        help="Output directory for the generated site")
    parser.add_argument("--only", metavar="NAME",
                        help="Build only the playlist matching this name (partial match)")
    parser.add_argument("--force", action="store_true",
                        help="Force rebuild all playlists, ignoring incremental cache")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be built without writing any files")
    parser.add_argument("--serve", action="store_true",
                        help="Start a local HTTP server from the output directory after building")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to use for --serve (default: 8000)")
    parser.add_argument("--no-search", action="store_true",
                        help="Skip generating search.html and search_index.json")
    parser.add_argument("--no-index", action="store_true",
                        help="Skip generating index.html (useful when building a single playlist)")
    parser.add_argument("--covers-mode", action="store_true",
                        help="Enable covers mode for all playlists (orig. Artist labels)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    parser.add_argument("--print-config", metavar="SECTION.KEY",
                        help="Print a single config.ini value and exit (e.g. paths.output_dir)")

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Site Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "site_title": "Playlist Archive",
    "site_tagline": "A curated music collection",
    "accent_color": "#e8b84b",
    "playlist_order": [],
    "covers_mode": True,
}


def load_config(input_dir=None):
    """Load site config from config.ini, falling back to built-in defaults."""
    config = dict(DEFAULT_CONFIG)

    # [site] settings
    _ini_site_map = {
        'site_title':    'site_title',
        'site_tagline':  'site_tagline',
        'accent_color':  'accent_color',
        'custom_domain': 'custom_domain',
    }
    for ini_key, cfg_key in _ini_site_map.items():
        val = _ini_get('site', ini_key)
        if val:
            config[cfg_key] = val

    # covers_mode from [build]
    if _INI.has_option('build', 'covers_mode'):
        config['covers_mode'] = _ini_bool('build', 'covers_mode', True)

    # playlist_order from [playlists] — newline-separated slug list
    raw_order = _ini_get('playlists', 'playlist_order')
    if raw_order:
        slugs = [s.strip() for s in raw_order.replace(',', '\n').split('\n') if s.strip()]
        config['playlist_order'] = slugs

    return config


# ---------------------------------------------------------------------------
# Playlist Discovery
# ---------------------------------------------------------------------------

def slugify(name):
    """Convert playlist name to URL-safe slug.
    Identical logic to playlist_generator.py — must stay in sync to avoid
    slug mismatches on playlist names containing non-ASCII characters.
    """
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text)


def discover_playlists(input_dir, only_filter=None):
    """Find all iTunes XML files in the input directory."""
    input_path = Path(input_dir)
    # Deduplicate after combining globs — Windows is case-insensitive so
    # *.xml and *.XML both match the same files.
    _seen_paths = set()
    xmls = []
    for _x in sorted(input_path.glob("*.xml")) + sorted(input_path.glob("*.XML")):
        _key = _x.resolve()
        if _key not in _seen_paths:
            _seen_paths.add(_key)
            xmls.append(_x)

    playlists = []
    for xml_path in xmls:
        # Skip overrides files
        if "_overrides" in xml_path.name:
            continue
        name = xml_path.stem
        slug = slugify(name)
        overrides_path = xml_path.parent / f"{slug}_overrides.json"
        if not overrides_path.exists():
            # Also try stem-based overrides filename
            overrides_path = xml_path.parent / f"{xml_path.stem}_overrides.json"

        entry = {
            "name": name,
            "slug": slug,
            "xml_path": str(xml_path),
            "overrides_path": str(overrides_path) if overrides_path.exists() else None,
        }
        playlists.append(entry)

    if only_filter:
        playlists = [p for p in playlists if only_filter.lower() in p["name"].lower()]
        if not playlists:
            print(f"  ERROR: No playlists matching '{only_filter}' found in {input_dir}")
            sys.exit(1)

    return playlists


# ---------------------------------------------------------------------------
# Incremental Build Cache
# ---------------------------------------------------------------------------

def get_xml_hash(xml_path):
    """Return MD5 hash of the XML file for change detection."""
    h = hashlib.md5()
    with open(xml_path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def load_build_state(output_dir):
    """Load incremental build state from output/.build_state.json."""
    state_path = Path(output_dir) / ".build_state.json"
    if state_path.exists():
        with open(state_path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_build_state(output_dir, state):
    """Save incremental build state."""
    state_path = Path(output_dir) / ".build_state.json"
    with open(state_path, "w", encoding='utf-8') as f:
        json.dump(state, f, indent=2)


def needs_rebuild(playlist, build_state, force=False):
    """Determine if a playlist needs to be rebuilt."""
    if force:
        return True
    slug = playlist["slug"]
    if slug not in build_state:
        return True
    stored_hash = build_state[slug].get("xml_hash")
    current_hash = get_xml_hash(playlist["xml_path"])
    return stored_hash != current_hash


# ---------------------------------------------------------------------------
# Per-Playlist Build
# ---------------------------------------------------------------------------

def build_playlist(playlist, output_dir, config, covers_mode=False, dry_run=False, verbose=False):
    """
    Build a single playlist page by invoking playlist_generator.py.
    Returns a dict of playlist metadata for use in index/search generation.
    """
    import subprocess

    slug = playlist["slug"]
    playlist_output_dir = Path(output_dir) / "playlists" / slug

    if dry_run:
        print(f"  [DRY RUN] Would build: {playlist['name']} -> playlists/{slug}/")
        return None

    # Ensure output dir exists
    playlist_output_dir.mkdir(parents=True, exist_ok=True)

    # Build command for playlist_generator.py
    script_dir = Path(__file__).parent
    generator = script_dir / "playlist_generator.py"

    cmd = [
        sys.executable, str(generator),
        playlist["xml_path"],
        "--output-dir", str(playlist_output_dir),
        "--img-dir", str(playlist_output_dir / "img"),
        "--site-root",   # Use root-relative paths
    ]

    if covers_mode or config.get("covers_mode"):
        cmd.append("--covers-mode")

    if playlist["overrides_path"]:
        cmd.extend(["--overrides", playlist["overrides_path"]])

    if verbose:
        cmd.append("--verbose")

    print(f"  Building: {playlist['name']}")
    if verbose:
        print(f"    Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=not verbose, text=True)

    if result.returncode != 0:
        print(f"  ERROR building {playlist['name']}:")
        if result.stderr:
            print(result.stderr[-2000:])
        # Still try to read meta if it was written before the crash
        meta_path = playlist_output_dir / "playlist_meta.json"
        if meta_path.exists():
            with open(meta_path, encoding='utf-8') as f:
                return json.load(f)
        return None

    # Load the metadata JSON that playlist_generator.py emits
    meta_path = playlist_output_dir / "playlist_meta.json"
    if meta_path.exists():
        with open(meta_path, encoding='utf-8') as f:
            return json.load(f)
    else:
        # Fallback minimal metadata
        return {
            "name": playlist["name"],
            "slug": slug,
            "track_count": 0,
            "tracks": [],
            "year_range": "",
            "url": f"playlists/{slug}/",
        }


# ---------------------------------------------------------------------------
# Search Index Generation
# ---------------------------------------------------------------------------

def build_search_index(all_playlist_meta, output_dir):
    """Build search_index.json from all playlist metadata."""
    entries = []
    for meta in all_playlist_meta:
        if not meta:
            continue
        playlist_name = meta.get("name", "")
        playlist_url = meta.get("url", "")
        for track in meta.get("tracks", []):
            entries.append({
                "title":       track.get("title", ""),
                "artist":      track.get("artist", ""),
                "orig_artist": track.get("orig_artist", ""),
                "album":       track.get("album", ""),
                "year":        str(track.get("year", "")),
                "playlist":    playlist_name,
                "url":         playlist_url,
            })

    index_path = Path(output_dir) / "search_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=None, separators=(',', ':'))

    print(f"  Search index: {len(entries)} entries -> search_index.json")
    return entries


# ---------------------------------------------------------------------------
# Search Page Generation
# ---------------------------------------------------------------------------

SEARCH_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Search — {site_title}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="site-header">
    <nav class="site-nav">
      <a href="./" class="nav-home">{site_title}</a>
      <span class="nav-sep">&middot;</span>
      <a href="search.html" class="active">Search</a>
    </nav>
  </header>

  <main class="search-page">
    <h1 class="search-heading">Search</h1>
    <div class="search-bar-wrap">
      <input type="search" id="searchInput" class="search-input"
             placeholder="Song title, cover or original artist…" autofocus autocomplete="off">
    </div>
    <div id="searchStats" class="search-stats"></div>
    <div id="searchResults" class="search-results"></div>
  </main>

  <script src="{fuse_js_url}"></script>
  <script>
    const SITE_TITLE = {site_title_js};
    let fuse = null;
    let allEntries = [];

    async function loadIndex() {{
      const resp = await fetch('search_index.json');
      allEntries = await resp.json();
      fuse = new Fuse(allEntries, {{
        keys: [
          {{ name: 'title',       weight: 0.6 }},
          {{ name: 'artist',      weight: 0.3 }},
          {{ name: 'orig_artist', weight: 0.3 }},
        ],
        threshold: 0.35,
        includeScore: true,
        minMatchCharLength: 2,
      }});
    }}

    function groupByPlaylist(results) {{
      const map = {{}};
      for (const r of results) {{
        const item = r.item;
        const key = item.playlist;
        if (!map[key]) map[key] = {{ playlist: item.playlist, url: item.url, tracks: [] }};
        map[key].tracks.push(item);
      }}
      return Object.values(map).sort((a, b) => a.playlist.localeCompare(b.playlist));
    }}

    function renderResults(query) {{
      const container = document.getElementById('searchResults');
      const stats = document.getElementById('searchStats');

      if (!query || query.length < 2) {{
        container.innerHTML = '';
        stats.textContent = '';
        return;
      }}

      const results = fuse.search(query);

      if (results.length === 0) {{
        stats.textContent = 'No results found.';
        container.innerHTML = '';
        return;
      }}

      const grouped = groupByPlaylist(results);
      const totalTracks = results.length;
      stats.textContent = `${{totalTracks}} result${{totalTracks !== 1 ? 's' : ''}} across ${{grouped.length}} playlist${{grouped.length !== 1 ? 's' : ''}}`;

      container.innerHTML = grouped.map(group => `
        <div class="search-group">
          <h2 class="search-group-title">
            <a href="${{group.url}}">${{group.playlist}}</a>
            <span class="search-group-count">${{group.tracks.length}} match${{group.tracks.length !== 1 ? 'es' : ''}}</span>
          </h2>
          <div class="search-tracks">
            ${{group.tracks.map(t => `
              <div class="search-track">
                <span class="st-title">${{t.title}}</span>
                <span class="st-sep">—</span>
                <span class="st-artist">${{t.artist}}</span>
                ${{t.orig_artist ? `<span class="st-orig">orig. ${{t.orig_artist}}</span>` : ''}}
                ${{t.year ? `<span class="st-year">${{t.year}}</span>` : ''}}
              </div>
            `).join('')}}
          </div>
        </div>
      `).join('');
    }}

    document.getElementById('searchInput').addEventListener('input', (e) => {{
      renderResults(e.target.value.trim());
    }});

    loadIndex();
  </script>
</body>
</html>
'''


def build_search_page(output_dir, config):
    """Write search.html."""
    site_title = config.get("site_title", "Playlist Archive")
    fuse_js_url = _ini_get('cdn', 'fuse_js_url',
                           'https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js')
    html = SEARCH_HTML.format(
        site_title=site_title,
        site_title_js=json.dumps(site_title),
        fuse_js_url=fuse_js_url,
    )
    out_path = Path(output_dir) / "search.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("  Generated: search.html")


# ---------------------------------------------------------------------------
# Landing Page (index.html) Generation
# ---------------------------------------------------------------------------

INDEX_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{site_title}</title>
  <link rel="stylesheet" href="style.css">
  <style>:root {{ --thumb-size: {thumb_size}px; }}</style>
</head>
<body>
  <header class="site-header">
    <nav class="site-nav">
      <a href="./" class="nav-home active">{site_title}</a>
      <span class="nav-sep">&middot;</span>
      <a href="search.html">Search</a>
      <span class="nav-sep">&middot;</span>
      <a href="stats.html">Statistics</a>
    </nav>
  </header>

  <section class="hero">
    <div class="hero-inner">
      <h1 class="hero-title">{site_title}</h1>
      <p class="hero-tagline">{site_tagline} &ndash; brought to you by <a href="{hearmoretunes_url}" target="_blank" rel="noopener">Hearmoretunes</a></p>
      <div class="hero-stats">
        <span>{playlist_count} playlists</span>
        <span class="stat-sep">&middot;</span>
        <span>{track_count} tracks</span>
        {year_range_html}
      </div>
    </div>
  </section>

  <main class="index-grid-wrap">
    <div class="playlist-sort-bar">
      <span class="sort-label">Sort by:</span>
      <button class="sort-btn active" data-sort="name">Alphabetic</button>
      <button class="sort-btn" data-sort="date">Date Added</button>
    </div>
    <div class="playlist-grid" id="playlistGrid">
{playlist_cards}
    </div>
  </main>

  <script>
    const grid = document.getElementById('playlistGrid');
    const cards = Array.from(grid.querySelectorAll('.playlist-card'));
    const originalOrder = [...cards];

    // Apply alphabetic sort on load (default)
    (function() {{
      cards.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name, undefined, {{ numeric: true, sensitivity: 'base' }}));
      cards.forEach(c => grid.appendChild(c));
    }})();

    document.querySelectorAll('.sort-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const sort = btn.dataset.sort;
        let sorted;
        if (sort === 'name') {{
          sorted = [...cards].sort((a, b) => a.dataset.name.localeCompare(b.dataset.name, undefined, {{ numeric: true, sensitivity: 'base' }}));
        }} else if (sort === 'date') {{
          sorted = [...cards].sort((a, b) => parseInt(b.dataset.order) - parseInt(a.dataset.order));
        }} else {{
          sorted = [...originalOrder];
        }}
        sorted.forEach(c => grid.appendChild(c));
      }});
    }});
  </script>
</body>
</html>
'''

PLAYLIST_CARD_HTML = '''      <a class="playlist-card" href="{url}" data-name="{name_escaped}" data-tracks="{track_count}" data-order="{order_index}">
        <div class="card-header">
          <h2 class="card-name">{name}</h2>
        </div>
        <div class="art-cloud">
{cloud_imgs}
        </div>
        <div class="playlist-card-footer">
          <span class="card-track-count">{track_count} tracks</span>
          {year_range_html}
        </div>
      </a>'''


def build_index_page(all_playlist_meta, output_dir, config, playlist_order=None):
    """Generate index.html landing page."""
    site_title = config.get("site_title", "Playlist Archive")
    site_tagline = config.get("site_tagline", "")
    accent = config.get("accent_color", "#e8b84b")

    # Apply playlist order if specified
    order = playlist_order or config.get("playlist_order", [])
    if order:
        slug_to_meta = {m["slug"]: m for m in all_playlist_meta if m}
        ordered = [slug_to_meta[s] for s in order if s in slug_to_meta]
        remaining = [m for m in all_playlist_meta if m and m["slug"] not in order]
        all_meta_sorted = ordered + remaining
    else:
        all_meta_sorted = [m for m in all_playlist_meta if m]

    total_tracks = sum(m.get("track_count", 0) for m in all_meta_sorted)
    all_years = []
    for m in all_meta_sorted:
        yr = m.get("year_range", "")
        if yr:
            parts = yr.split("–")
            try:
                all_years.extend([int(p) for p in parts if p.isdigit()])
            except:
                pass

    year_range_html = ""
    if all_years:
        yr_str = str(min(all_years)) if min(all_years) == max(all_years) else f"{min(all_years)}&ndash;{max(all_years)}"
        year_range_html = f'<span class="stat-sep">&middot;</span><span>{yr_str}</span>'

    # Build playlist cards
    cards_html = []
    for order_index, meta in enumerate(all_meta_sorted):
        if not meta:
            continue
        # Art cloud: scan the actual img/ folder for what's really there
        # (cached art_thumbnails may have stale paths from an old slug, so we ignore it)
        slug = meta.get("slug", "")
        img_dir = Path(output_dir) / "playlists" / slug / "img"
        if img_dir.is_dir():
            art_imgs = sorted([
                f"playlists/{slug}/img/{p.name}"
                for p in img_dir.iterdir()
                if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
            ])
        else:
            # Last resort: construct paths and let browser silently drop 404s
            track_count = meta.get("track_count", 0)
            art_imgs = [
                f"playlists/{slug}/img/{str(i).zfill(2)}.jpg"
                for i in range(1, min(track_count, 25) + 1)
            ]
        cloud_lines = []
        for img_src in art_imgs:
            cloud_lines.append(f'          <img class="cloud-img" src="{img_src}" alt="" loading="lazy" onerror="this.style.display=\'none\'">')
        if not cloud_lines:
            cloud_lines.append('          <div class="cloud-placeholder"></div>')

        yr_range = meta.get("year_range", "").replace("–", "&ndash;")
        card_year_html = f'<span class="card-year-range">{yr_range}</span>' if yr_range else ''

        card = PLAYLIST_CARD_HTML.format(
            url=meta.get("url", "#"),
            name_escaped=meta.get("name", "").replace('"', '&quot;'),
            name=meta.get("name", ""),
            track_count=meta.get("track_count", 0),
            order_index=order_index,
            cloud_imgs="\n".join(cloud_lines),
            year_range_html=card_year_html,
        )
        cards_html.append(card)

    hearmoretunes_url = _ini_get('site', 'hearmoretunes_url', 'http://hearmoretunes.com')
    thumb_size = _ini_get('artwork', 'thumbnail_size', '44')
    html = INDEX_HTML.format(
        site_title=site_title,
        site_tagline=site_tagline,
        playlist_count=len(all_meta_sorted),
        track_count=total_tracks,
        year_range_html=year_range_html,
        playlist_cards="\n".join(cards_html),
        hearmoretunes_url=hearmoretunes_url,
        thumb_size=thumb_size,
    )

    out_path = Path(output_dir) / "index.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Generated: index.html ({len(all_meta_sorted)} playlist cards)")


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


def write_cname_file(output_dir, config):
    """Write CNAME file for GitHub Pages custom domain.

    Reads custom_domain from site config. If not set, skips silently.
    Without this file GitHub Pages will not serve the site at the custom domain,
    and it would be deleted on every rebuild if managed manually.
    """
    domain = config.get("custom_domain", "").strip()
    if not domain:
        return
    out_path = Path(output_dir) / "CNAME"
    out_path.write_text(domain + "\n", encoding="utf-8")
    print(f"  Generated: CNAME ({domain})")


# ---------------------------------------------------------------------------
# Static Asset Copying
# ---------------------------------------------------------------------------

def copy_static_assets(output_dir):
    """Copy style.css and any other static assets from the script directory."""
    script_dir = Path(__file__).parent
    css_src = script_dir / "style.css"
    css_dst = Path(output_dir) / "style.css"

    if css_src.exists():
        shutil.copy2(css_src, css_dst)
        print(f"  Copied: style.css")
    else:
        print(f"  WARNING: style.css not found at {css_src}")


# ---------------------------------------------------------------------------
# Statistics Generation
# ---------------------------------------------------------------------------

def build_statistics(input_dir, output_dir):
    """Generate statistics JSON and copy stats.html to output directory."""
    import subprocess
    
    script_dir = Path(__file__).parent
    stats_script = script_dir / "stats.py"
    
    if not stats_script.exists():
        print(f"  WARNING: stats.py not found at {stats_script}")
        return
    
    stats_json = Path(output_dir) / "stats.json"
    stats_html = script_dir / "stats.html"
    stats_html_dst = Path(output_dir) / "stats.html"
    
    # Run stats.py to generate stats.json
    cmd = [
        sys.executable,
        str(stats_script),
        "--xml-dir", input_dir,
        "--output", str(stats_json),
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"  Generated: stats.json")
        else:
            print(f"  ERROR running stats.py:")
            if result.stderr:
                print(result.stderr[-500:])
            return
    except subprocess.TimeoutExpired:
        print(f"  ERROR: stats.py timed out")
        return
    except Exception as e:
        print(f"  ERROR running stats.py: {e}")
        return
    
    # Copy stats.html to output
    if stats_html.exists():
        shutil.copy2(stats_html, stats_html_dst)
        print(f"  Copied: stats.html")
    else:
        print(f"  WARNING: stats.html not found at {stats_html}")


# ---------------------------------------------------------------------------
# Local Server
# ---------------------------------------------------------------------------

def serve_output(output_dir, port=8000):
    """Start a local HTTP server from the output directory."""
    import http.server
    import socketserver
    import threading

    os.chdir(output_dir)
    handler = http.server.SimpleHTTPRequestHandler

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\n  🌐  Serving at http://localhost:{port}/")
        print(f"  Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # Handle --print-config mode (used by bat files to read config values)
    if hasattr(args, 'print_config') and args.print_config:
        parts = args.print_config.split('.', 1)
        if len(parts) == 2:
            print(_ini_get(parts[0], parts[1], ''))
        sys.exit(0)

    if not args.input and not args.serve:
        print("ERROR: --input is required (specify via CLI or set xml_input_dir in config.ini)")
        sys.exit(1)

    print("\n=== iTunes Playlist Site Builder ===\n")

    # Load config from config.ini
    config = load_config(args.input)

    # Apply CLI overrides to config
    if args.covers_mode:
        config["covers_mode"] = True

    # Prepare output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "playlists").mkdir(exist_ok=True)

    if args.serve and not args.input:
        serve_output(str(output_dir), args.port)
        return

    # Discover playlists
    print(f"Scanning: {args.input}")
    playlists = discover_playlists(args.input, only_filter=args.only)
    print(f"  Found {len(playlists)} playlist(s)\n")

    if not playlists:
        print("No XML files found. Exiting.")
        sys.exit(1)

    # Load incremental build state
    build_state = load_build_state(str(output_dir))
    new_build_state = dict(build_state)

    # Build each playlist
    print("Building playlists:")
    all_playlist_meta = []
    built_count = 0
    skipped_count = 0

    # --force CLI flag overrides config.ini force_rebuild
    force_rebuild = args.force or _ini_bool('build', 'force_rebuild', False)
    verbose = args.verbose or _ini_bool('build', 'verbose', False)


    def process_playlist(playlist):
        meta = None
        if needs_rebuild(playlist, build_state, force=force_rebuild):
            meta = build_playlist(
                playlist, str(output_dir), config,
                covers_mode=config.get("covers_mode", False),
                dry_run=args.dry_run,
                verbose=verbose,
            )
            return ('built', playlist, meta)
        else:
            meta_path = output_dir / "playlists" / playlist["slug"] / "playlist_meta.json"
            if meta_path.exists():
                with open(meta_path, encoding='utf-8') as f:
                    meta = json.load(f)
                return ('skipped_cached', playlist, meta)
            else:
                meta = {"name": playlist["name"], "slug": playlist["slug"], "tracks": [], "track_count": 0}
                return ('skipped_nocached', playlist, meta)

    # Dictionary to keep the correct original order while collecting metas
    order_map = {p['slug']: idx for idx, p in enumerate(playlists)}
    all_playlist_meta = [None] * len(playlists)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_playlist, p): p for p in playlists}
        for future in concurrent.futures.as_completed(futures):
            status, playlist, meta = future.result()
            all_playlist_meta[order_map[playlist['slug']]] = meta
            
            if status == 'built':
                if meta and not args.dry_run:
                    new_build_state[playlist["slug"]] = {
                        "xml_hash": get_xml_hash(playlist["xml_path"]),
                        "built_at": datetime.now(timezone.utc).isoformat(),
                        "track_count": meta.get("track_count", 0),
                    }
                built_count += 1
            else:
                if status == 'skipped_cached':
                    print(f"  Skipped (unchanged): {playlist['name']}")
                skipped_count += 1

    print(f"\n  Built: {built_count}  Skipped (cached): {skipped_count}\n")

    if args.dry_run:
        print("[DRY RUN] No files written.")
        return

    # Copy static assets
    print("Copying assets:")
    copy_static_assets(str(output_dir))

    # Generate site-wide files
    print("\nGenerating site files:")

    if not args.no_index:
        build_index_page(all_playlist_meta, str(output_dir), config)

    if not args.no_search:
        build_search_index(all_playlist_meta, str(output_dir))
        build_search_page(str(output_dir), config)

    # Generate statistics page
    build_statistics(args.input, str(output_dir))

    write_cname_file(str(output_dir), config)

    # Save updated build state
    save_build_state(str(output_dir), new_build_state)

    print(f"\n✅  Site built successfully → {output_dir}/")
    print(f"   To preview: cd {output_dir} && python3 -m http.server 8000")
    print(f"   Then open:  http://localhost:8000/\n")

    # ── Consolidated missing-art report ──────────────────────────────────────
    all_missing = [
        (meta.get("name", "?"), m)
        for meta in all_playlist_meta if meta
        for m in meta.get("missing_art", [])
    ]
    if all_missing:
        print("─" * 70)
        print(f"🖼   MISSING ARTWORK  ({len(all_missing)} track(s))")
        print("─" * 70)
        print("  Save each image as a JPG file into the playlist's img/ folder.")
        print("  Good sources: Google Images, Discogs, MusicBrainz Cover Art Archive\n")
        cur_playlist = None
        for playlist_name, m in all_missing:
            if playlist_name != cur_playlist:
                cur_playlist = playlist_name
                print(f"  Playlist: {playlist_name}")
                # Derive img path from slug
                slug = next(
                    (meta["slug"] for meta in all_playlist_meta if meta.get("name") == playlist_name),
                    "unknown"
                )
                img_folder = str(output_dir / "playlists" / slug / "img")
                print(f"  Folder:   {img_folder}\n")
                print(f"  {'#':<4}  {'Filename':<12}  Search for")
                print(f"  {'-'*4}  {'-'*12}  {'-'*48}")
            search_hint = f"{m['album']}  —  {m['artist']}"
            print(f"  {m['num']:<4}  {m['img_filename']:<12}  {search_hint}")
        print("─" * 70 + "\n")

    if args.serve:
        serve_output(str(output_dir), args.port)


if __name__ == "__main__":
    main()
