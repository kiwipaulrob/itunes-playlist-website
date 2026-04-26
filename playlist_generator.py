"""
playlist_generator.py — Per-playlist HTML generator.

Reads an iTunes XML file, fetches MusicBrainz metadata + artwork,
and produces:
  - output_dir/playlists/<slug>.html
  - output_dir/img/<slug>/<nn>.jpg  (one per track)

Can be run standalone for development:
  python3 playlist_generator.py input.xml --output-dir /output --slug my-playlist

Or imported as a module by build_site.py:
  from playlist_generator import generate_playlist
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import configparser
import time
import threading
import concurrent.futures
import unicodedata
from pathlib import Path
from urllib.parse import quote, quote_plus, unquote, urlparse
from urllib.request import url2pathname

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    import plistlib
except ImportError:
    sys.exit("plistlib not found (requires Python 3.x standard library)")

try:
    from mutagen.id3 import ID3, ID3NoHeaderError
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


# ── Config (config.ini) ────────────────────────────────────────────────────────

def _load_ini():
    """Load config.ini from the same directory as this script."""
    ini_path = Path(__file__).parent / "config.ini"
    cfg = configparser.ConfigParser(interpolation=None)
    if ini_path.exists():
        cfg.read(ini_path, encoding='utf-8')
    return cfg

_CFG = _load_ini()

def _cget(section, key, fallback=''):
    try:
        return _CFG.get(section, key).strip()
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback

def _cbool(section, key, fallback=False):
    return _cget(section, key, 'true' if fallback else 'false').lower() in ('true', '1', 'yes', 'on')

def _cint(section, key, fallback=0):
    try:
        return int(_cget(section, key, str(fallback)))
    except ValueError:
        return fallback

def _cfloat(section, key, fallback=0.0):
    try:
        return float(_cget(section, key, str(fallback)))
    except ValueError:
        return fallback


# ── Constants ──────────────────────────────────────────────────────────────────

MB_BASE         = _cget('musicbrainz', 'base_url',        'https://musicbrainz.org/ws/2')
CAA_BASE        = _cget('musicbrainz', 'caa_url',         'https://coverartarchive.org')
MB_AGENT        = _cget('musicbrainz', 'user_agent',      'PlaylistSiteGenerator/1.0 (https://github.com/kiwipaulrob/hearmycovers)')
MB_DELAY        = _cfloat('musicbrainz', 'rate_delay',    1.1)
MB_TIMEOUT      = _cint('musicbrainz',  'request_timeout', 15)
MB_SEARCH_LIMIT = _cint('musicbrainz',  'search_limit',   5)
DEEZER_TIMEOUT  = _cint('artwork',      'deezer_timeout',  10)
CAA_IMAGE_SIZE  = _cget('artwork',      'caa_image_size',  '500')
FAVICON_CDN     = _cget('cdn',          'favicon_cdn_url', 'https://www.google.com/s2/favicons')
ORIG_LABEL      = _cget('site',         'orig_label',      'orig.')
CONSTRUCTED_LINK_QUERY = _cget('search_terms', 'constructed_link_query', 'title_and_artist')

MB_SEARCH_ATTEMPTS     = _cint('musicbrainz',  'search_attempts',  4)

# Threading lock for MusicBrainz rate limit
mb_lock = threading.Lock()


# ── Constructed-link URL templates (from config.ini [links] section) ──────────

_CONSTRUCTED_URL_TEMPLATES = {
    "youtube":    _cget('links', 'youtube_search_url',    'https://www.youtube.com/results?search_query={query}'),
    "spotify":    _cget('links', 'spotify_search_url',    'https://open.spotify.com/search/{query}'),
    "applemusic": _cget('links', 'applemusic_search_url', 'https://music.apple.com/search?term={query}'),
    "deezer":     _cget('links', 'deezer_search_url',     'https://www.deezer.com/search/{query}'),
    "bandcamp":   _cget('links', 'bandcamp_search_url',   'https://bandcamp.com/search?q={query}'),
    "soundcloud": _cget('links', 'soundcloud_search_url', 'https://soundcloud.com/search?q={query}'),
}

# ── Per-site query mode overrides (from config.ini [search_terms] section) ────

def _get_site_query_mode(site_key: str) -> str:
    """Return the query mode for a specific site, falling back to the global default."""
    return _cget('search_terms', f'{site_key}_query', CONSTRUCTED_LINK_QUERY)

# Each entry: (key, label, domain_fragment, category)
# category is "review" or "db"
# Reviews appear first on cards, styled in gold; databases in dark.
# Domain fragment is checked as a substring of the lowercased URL.
_ALL_LINK_DEFS = [
    # ── Reviews ────────────────────────────────────────────────────
    ("pitchfork",       "Pitchfork",    "pitchfork",            "review"),
    ("bbc",             "BBC",          "bbc.co.uk",            "review"),
    ("chorus",          "Chorus",       "chorus.",              "review"),  # chorus.fm / chorus.reviews
    ("theguardian",     "Guardian",     "theguardian",          "review"),
    ("rollingstone",    "Rolling Stone","rollingstone",         "review"),
    ("allmusic_rev",    "AllMusic",     "allmusic.com/album",   "review"),  # album review URLs
    ("nme",             "NME",          "nme.com",              "review"),
    ("stereogum",       "Stereogum",    "stereogum",            "review"),
    ("metacritic",      "Metacritic",   "metacritic",           "review"),
    # ── Databases ──────────────────────────────────────────────────
    ("allmusic",        "AllMusic",     "allmusic",             "db"),
    ("discogs",         "Discogs",      "discogs",              "db"),
    ("rateyourmusic",   "RYM",          "rateyourmusic",        "db"),
    ("wikidata",        "Wikidata",     "wikidata",             "db"),
    ("musicbrainz",     "MusicBrainz",  "musicbrainz",          "db"),
    ("last.fm",         "Last.fm",      "last.fm",              "db"),
    ("45cat",           "45cat",        "45cat",                "db"),
    ("secondhandsongs", "SHS",          "secondhandsongs",      "db"),
    ("whosampled",      "WhoSampled",   "whosampled",           "db"),
    ("youtube",         "YouTube",      "youtube.com",          "db"),
    ("spotify",         "Spotify",      "open.spotify.com",     "db"),
    ("applemusic",      "Apple Music",  "music.apple.com",      "db"),
    ("deezer",          "Deezer",       "deezer.com",           "db"),
    ("bandcamp",        "Bandcamp",     "bandcamp.com",         "db"),
    ("soundcloud",      "SoundCloud",   "soundcloud.com",       "db"),
]

LINK_FAVICON_DOMAINS = {
    "pitchfork":        "pitchfork.com",
    "bbc":              "bbc.co.uk",
    "chorus":           "chorus.fm",
    "theguardian":      "theguardian.com",
    "rollingstone":     "rollingstone.com",
    "allmusic_rev":     "allmusic.com",
    "nme":              "nme.com",
    "stereogum":        "stereogum.com",
    "metacritic":       "metacritic.com",
    "allmusic":         "allmusic.com",
    "discogs":          "discogs.com",
    "rateyourmusic":    "rateyourmusic.com",
    "wikidata":         "wikidata.org",
    "musicbrainz":      "musicbrainz.org",
    "last.fm":          "last.fm",
    "45cat":            "45cat.com",
    "secondhandsongs":  "secondhandsongs.com",
    "whosampled":       "whosampled.com",
    "youtube":          "youtube.com",
    "spotify":          "spotify.com",
    "applemusic":       "music.apple.com",
    "deezer":           "deezer.com",
    "bandcamp":         "bandcamp.com",
    "soundcloud":       "soundcloud.com",
}


def _apply_enabled_sites(defs):
    """Filter link definitions based on enabled_review_sites / enabled_db_sites in config.ini."""
    try:
        review_str = _CFG.get('links', 'enabled_review_sites')
        db_str     = _CFG.get('links', 'enabled_db_sites')
        enabled = set(
            [s.strip() for s in review_str.replace('\n', ',').split(',') if s.strip()] +
            [s.strip() for s in db_str.replace('\n', ',').split(',') if s.strip()]
        )
        return [d for d in defs if d[0] in enabled]
    except (configparser.NoSectionError, configparser.NoOptionError):
        return defs


LINK_DEFS = _apply_enabled_sites(_ALL_LINK_DEFS)

# Lookup by key for fast access
_LINK_DEFS_BY_KEY = {d[0]: {"label": d[1], "domain": d[2], "category": d[3]}
                     for d in LINK_DEFS}

ART_PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='400' height='400' viewBox='0 0 400 400'%3E"
    "%3Crect width='400' height='400' fill='%23222'/%3E"
    "%3Ctext x='200' y='215' font-family='sans-serif' font-size='60' "
    "fill='%23444' text-anchor='middle'%3E♪%3C/text%3E%3C/svg%3E"
)


# ── iTunes XML parsing ─────────────────────────────────────────────────────────

def parse_itunes_xml(xml_path: str, playlist_name: str | None = None):
    """
    Parse an iTunes XML library file.
    Returns (playlist_display_name, list_of_track_dicts).
    Each track dict has keys: number, title, artist, album, year, location.
    """
    with open(xml_path, "rb") as f:
        plist = plistlib.load(f)

    tracks_dict = plist.get("Tracks", {})
    playlists   = plist.get("Playlists", [])

    if not playlists:
        raise ValueError("No playlists found in XML")

    # Select playlist
    if playlist_name:
        selected = next(
            (p for p in playlists if p.get("Name", "").lower() == playlist_name.lower()),
            None,
        )
        if not selected:
            names = [p.get("Name", "") for p in playlists]
            raise ValueError(f"Playlist '{playlist_name}' not found. Available: {names}")
    else:
        # Skip the master "Library" playlist; use first real one
        selected = next(
            (p for p in playlists if not p.get("Master") and p.get("Playlist Items")),
            playlists[0],
        )

    display_name = selected.get("Name", "Playlist")
    items        = selected.get("Playlist Items", [])

    tracks = []
    for i, item in enumerate(items, start=1):
        tid  = str(item.get("Track ID", ""))
        info = tracks_dict.get(tid, {})
        loc  = info.get("Location", "")
        if loc.startswith("file://"):
            # url2pathname handles cross-platform correctly:
            # Mac/Linux: file:///path/to/file  → /path/to/file
            # Windows:   file:///C:/path/file  → C:\path\file
            loc = url2pathname(unquote(loc[7:]))
        else:
            loc = unquote(loc)

        title  = info.get("Name", "")
        artist = info.get("Artist", "")
        album  = info.get("Album", "")
        year   = info.get("Year", "")

        # Covers mode: title may be "Song Title [orig. Original Artist]"
        # or "Song Title [Original Artist]"
        orig_artist = ""
        m = re.match(r"^(.*)\s*[\[\(](.*?)[\]\)]$", title)
        if m:
            title       = m.group(1).strip()
            orig_artist = m.group(2).strip()
            # Strip any leading "orig." prefix already in the bracketed text
            orig_artist = re.sub(r"^orig\.\s*", "", orig_artist, flags=re.IGNORECASE)

        tracks.append({
            "number":      i,
            "title":       title,
            "orig_artist": orig_artist,
            "artist":      artist,
            "album":       album,
            "year":        str(year) if year else "",
            "location":    loc,
        })

    return display_name, tracks


def list_playlists(xml_path: str):
    with open(xml_path, "rb") as f:
        plist = plistlib.load(f)
    return [
        p.get("Name", "(unnamed)")
        for p in plist.get("Playlists", [])
        if not p.get("Master")
    ]


# ── Deezer ID extraction ───────────────────────────────────────────────────────

def get_deezer_id(mp3_path: str) -> str | None:
    if not MUTAGEN_AVAILABLE or not mp3_path or not os.path.exists(mp3_path):
        return None
    try:
        tags = ID3(mp3_path)
        for key in tags.keys():
            if key.startswith("TXXX:") and "deezer" in key.lower():
                val = str(tags[key].text[0]).strip()
                if val.isdigit():
                    return val
    except Exception:
        pass
    return None


def get_embedded_artwork(mp3_path: str) -> bytes | None:
    """
    Extract embedded APIC (attached picture) artwork from an MP3 file.
    Returns raw image bytes, or None if not found / file inaccessible.
    Tries all APIC frames, preferring cover-front type (type byte 3).
    """
    if not MUTAGEN_AVAILABLE or not mp3_path or not os.path.exists(mp3_path):
        return None
    try:
        tags = ID3(mp3_path)
        apic_frames = [v for k, v in tags.items() if k.startswith("APIC")]
        if not apic_frames:
            return None
        # Prefer picture type 3 (Cover front), fall back to any APIC
        cover = next((f for f in apic_frames if f.type == 3), apic_frames[0])
        data = cover.data
        return data if data else None
    except Exception:
        return None


def get_deezer_artwork(deezer_id: str, session: requests.Session) -> bytes | None:
    try:
        r = session.get(
            f"https://api.deezer.com/track/{deezer_id}",
            timeout=DEEZER_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            img_url = (
                data.get("album", {}).get("cover_xl")
                or data.get("album", {}).get("cover_big")
                or data.get("album", {}).get("cover")
            )
            if img_url:
                ir = session.get(img_url, timeout=10)
                if ir.status_code == 200:
                    return ir.content
    except Exception:
        pass
    return None


# ── MusicBrainz helpers ────────────────────────────────────────────────────────

def mb_get(path: str, params: dict, session: requests.Session, delay_ref: list) -> dict:
    """Rate-limited MusicBrainz GET. delay_ref is a 1-element list holding last_request_time."""
    with mb_lock:
        elapsed = time.time() - delay_ref[0]
        if elapsed < MB_DELAY:
            time.sleep(MB_DELAY - elapsed)
        delay_ref[0] = time.time()
        
    r = session.get(
        f"{MB_BASE}/{path}",
        params={**params, "fmt": "json"},
        headers={"User-Agent": MB_AGENT},
        timeout=MB_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def find_mbid_by_album_artist(album: str, artist: str, session: requests.Session, delay_ref: list, title: str = "") -> str | None:
    """Search MusicBrainz for a release by album title + artist. Returns MBID or None.

    The number of fallback strategies tried is controlled by the search_attempts
    config value (default 4). Strategies are tried in order until one succeeds:
      1. Strict: release:"album" AND artist:"artist"
      2. Loose:  "album" "artist"
      3. Recording + artist: recording:"title" AND artist:"artist"  (requires title)
      4. Loose title: "title" "artist"  (requires title)
    """
    max_attempts = MB_SEARCH_ATTEMPTS

    # Strategy 1: Strict album + artist
    if max_attempts >= 1:
        try:
            query = f'release:"{album}" AND artist:"{artist}"'
            data = mb_get("release", {"query": query, "limit": MB_SEARCH_LIMIT}, session, delay_ref)
            releases = data.get("releases", [])
            if releases:
                return releases[0]["id"]
        except Exception:
            pass

    # Strategy 2: Looser album + artist
    if max_attempts >= 2:
        try:
            query2 = f'"{album}" "{artist}"'
            data2  = mb_get("release", {"query": query2, "limit": MB_SEARCH_LIMIT}, session, delay_ref)
            releases2 = data2.get("releases", [])
            if releases2:
                return releases2[0]["id"]
        except Exception:
            pass

    # Strategy 3: Recording title + artist (requires title)
    if max_attempts >= 3 and title:
        try:
            query3 = f'recording:"{title}" AND artist:"{artist}"'
            data3  = mb_get("release", {"query": query3, "limit": MB_SEARCH_LIMIT}, session, delay_ref)
            releases3 = data3.get("releases", [])
            if releases3:
                return releases3[0]["id"]
        except Exception:
            pass

    # Strategy 4: Loose title + artist (requires title)
    if max_attempts >= 4 and title:
        try:
            query4 = f'"{title}" "{artist}"'
            data4  = mb_get("release", {"query": query4, "limit": MB_SEARCH_LIMIT}, session, delay_ref)
            releases4 = data4.get("releases", [])
            if releases4:
                return releases4[0]["id"]
        except Exception:
            pass

    return None


def get_release_links(mbid: str, session: requests.Session, delay_ref: list) -> list[dict]:
    """Fetch URL relationships for a MusicBrainz release. Returns list of {type, url}."""
    try:
        data = mb_get(
            f"release/{mbid}",
            {"inc": "url-rels"},
            session,
            delay_ref,
        )
        links = []
        for rel in data.get("relations", []):
            url_obj = rel.get("url", {})
            url     = url_obj.get("resource", "")
            rtype   = rel.get("type", "").lower()
            links.append({"type": rtype, "url": url})
        return links
    except Exception:
        return []


def get_caa_artwork(mbid: str, session: requests.Session) -> bytes | None:
    """Fetch front cover art from Cover Art Archive."""
    try:
        r = session.get(
            f"{CAA_BASE}/release/{mbid}/front-{CAA_IMAGE_SIZE}",
            timeout=MB_TIMEOUT,
            allow_redirects=True,
        )
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
            return r.content
    except Exception:
        pass
    return None


# ── Artwork pipeline ───────────────────────────────────────────────────────────

def fetch_artwork(
    track: dict,
    mbid: str | None,
    art_file_override: str | None,
    art_cache_dir: Path,
    session: requests.Session,
    delay_ref: list,
) -> bytes | None:
    """
    Artwork priority:
    1. Art file override (local disk — highest priority, always fresh)
    2. Embedded APIC frame in the source MP3 (local disk — no network)
    3. Disk cache (skip all network if we have a previous successful fetch)
    4. Deezer API (network — via Deezer track ID in MP3 ID3 TXXX tag)
    5. MusicBrainz Cover Art Archive (network — via MBID)
    Returns raw bytes or None.
    """
    cache_key = _art_cache_key(track, mbid, art_file_override)
    cache_file = art_cache_dir / f"{cache_key}.jpg"

    img_bytes = None

    # 1. Art file override (local disk — highest priority, always fresh)
    if art_file_override and os.path.exists(art_file_override):
        img_bytes = open(art_file_override, "rb").read()

    # 2. Embedded APIC artwork from source MP3 (local disk — no network needed)
    if img_bytes is None:
        img_bytes = get_embedded_artwork(track.get("location", ""))

    # 3. Disk cache (skip all network if we have a previous successful fetch)
    if img_bytes is None and cache_file.exists():
        return cache_file.read_bytes()

    # 4. Deezer (network — via Deezer track ID stored in MP3 ID3 TXXX tag)
    if img_bytes is None:
        deezer_id = get_deezer_id(track.get("location", ""))
        if deezer_id:
            img_bytes = get_deezer_artwork(deezer_id, session)

    # 5. Cover Art Archive (network — via MusicBrainz release ID)
    if img_bytes is None and mbid:
        img_bytes = get_caa_artwork(mbid, session)

    if img_bytes:
        cache_file.write_bytes(img_bytes)

    return img_bytes


def _art_cache_key(track: dict, mbid: str | None, override: str | None) -> str:
    raw = f"{mbid or ''}-{override or ''}-{track.get('artist','')}-{track.get('album','')}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def bytes_to_data_uri(img_bytes: bytes) -> str:
    b64 = base64.b64encode(img_bytes).decode()
    # Detect image type
    if img_bytes[:2] == b"\xff\xd8":
        mime = "image/jpeg"
    elif img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{b64}"


# ── Link helpers ───────────────────────────────────────────────────────────────

def classify_link(url: str) -> str:
    """Map a URL to a short service key using domain fragment matching."""
    url_l = url.lower()
    for key, _label, domain_frag, _cat in LINK_DEFS:
        if domain_frag in url_l:
            return key
    if "musicbrainz.org" in url_l:
        return "musicbrainz"
    return "other"


def _build_query(title: str, artist: str, album: str, mode: str | None = None) -> str:
    """Build a URL-encoded search query string based on the configured query mode."""
    m = mode or CONSTRUCTED_LINK_QUERY
    if m == 'title_only':
        return quote_plus(title)
    elif m == 'artist_only':
        return quote_plus(artist)
    elif m == 'album_only':
        return quote_plus(album)
    elif m == 'album_and_artist':
        return quote_plus(f"{album} {artist}".strip())
    else:  # title_and_artist (default)
        return quote_plus(f"{title} {artist}".strip() if title else f"{artist} {album}".strip())


def best_links(raw_links: list[dict], mbid: str | None, artist: str = "", album: str = "", title: str = "") -> list[dict]:
    """
    De-duplicate, categorise, and sort links.
    Reviews (Pitchfork, BBC, Chorus, etc.) come first, styled in gold on cards.
    Databases (AllMusic, Discogs, RYM, …) follow in dark style.
    Each entry includes favicon_domain for Google's favicon CDN.
    Returns list of {key, label, url, category, favicon_domain}.
    """
    seen_dedup = {}  # dedup key → True
    seen_urls  = set()
    reviews    = []
    databases  = []

    for item in raw_links:
        url   = item["url"]
        rtype = item.get("type", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        key  = classify_link(url)
        defn = _LINK_DEFS_BY_KEY.get(key)

        if defn:
            category = defn["category"]
            label    = defn["label"]
            favicon  = LINK_FAVICON_DOMAINS.get(key, "")
        elif rtype == "review":
            # Unknown review site — label from domain, keep as review
            domain   = urlparse(url).netloc.lstrip("www.")
            category = "review"
            label    = domain.split(".")[0].title()
            favicon  = domain
            key      = f"review:{domain}"
        else:
            # Unknown database/other link
            domain   = urlparse(url).netloc.lstrip("www.")
            category = "db"
            label    = domain.split(".")[0].title()
            favicon  = ""
            key      = f"other:{domain}"

        # Dedup: one entry per known key; unknown sites dedup by URL
        dedup_key = key if not key.startswith(("review:", "other:")) else url
        if dedup_key in seen_dedup:
            continue
        seen_dedup[dedup_key] = True

        entry = {"key": key, "label": label, "url": url,
                 "category": category, "favicon_domain": favicon}
        if category == "review":
            reviews.append(entry)
        else:
            databases.append(entry)

    # Always include a direct MusicBrainz release link
    if mbid and "musicbrainz" not in seen_dedup:
        databases.append({
            "key": "musicbrainz", "label": "MusicBrainz",
            "url": f"https://musicbrainz.org/release/{mbid}",
            "category": "db", "favicon_domain": "musicbrainz.org",
        })

    # Sort each group by order in LINK_DEFS
    def _sort_key(entry):
        for i, d in enumerate(LINK_DEFS):
            if d[0] == entry["key"]:
                return i
        return 999

    reviews.sort(key=_sort_key)
    databases.sort(key=_sort_key)

    # Always append constructed search links (URLs and query modes from config.ini)
    if artist or album:
        _constructed_sites = [
            ("youtube",    "YouTube",     "youtube.com"),
            ("spotify",    "Spotify",     "spotify.com"),
            ("applemusic", "Apple Music", "music.apple.com"),
            ("deezer",     "Deezer",      "deezer.com"),
            ("bandcamp",   "Bandcamp",    "bandcamp.com"),
            ("soundcloud", "SoundCloud",  "soundcloud.com"),
        ]
        for site_key, label, favicon in _constructed_sites:
            if site_key not in seen_dedup:
                mode  = _get_site_query_mode(site_key)
                query = _build_query(title, artist, album, mode=mode)
                tmpl  = _CONSTRUCTED_URL_TEMPLATES.get(site_key, "")
                url   = tmpl.replace("{query}", query) if tmpl else ""
                if url:
                    databases.append({
                        "key": site_key, "label": label,
                        "url": url,
                        "category": "db", "favicon_domain": favicon,
                    })

    return reviews + databases


# ── HTML rendering ─────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text)


def render_track_card(track: dict, art_src: str, links: list[dict], covers_mode: bool) -> str:
    num    = track["number"]
    title  = track["title"]
    artist = track["artist"]
    orig   = track.get("orig_artist", "")
    album  = track.get("album_display", track.get("album", ""))
    year   = track.get("year", "")

    # Artist line: "Cover Artist — Album (Year)" all on one line
    if album:
        year_suffix = f" ({year})" if year else ""
        artist_line = f"{artist} &ndash; {album}{year_suffix}"
    elif year:
        artist_line = f"{artist} ({year})"
    else:
        artist_line = artist

    orig_html = (
        f'<div class="track-original">{ORIG_LABEL} {orig}</div>'
        if covers_mode and orig else ""
    )

    def _pill(lnk):
        favicon_html = ""
        if lnk.get("favicon_domain"):
            favicon_html = (
                f'<img src="{FAVICON_CDN}'
                f'?domain={lnk["favicon_domain"]}&sz=16" class="pill-favicon" alt="" loading="lazy">'
            )
        css = "track-link-pill pill-review" if lnk.get("category") == "review" else "track-link-pill"
        return (
            f'<a class="{css}" href="{lnk["url"]}" '
            f'target="_blank" rel="noopener">{favicon_html}{lnk["label"]}</a>'
        )

    link_pills = "".join(_pill(lnk) for lnk in links)

    return f"""
    <div class="track-card">
      <div class="track-art-wrap">
        <img src="{art_src}" alt="{title} — {artist}" loading="lazy">
        <span class="track-number-badge">{num:02d}</span>
      </div>
      <div class="track-info">
        <div class="track-title">{title}</div>
        <div class="track-artist">{artist_line}</div>
        {orig_html}
      </div>
      <div class="track-links">{link_pills}</div>
    </div>"""


def render_playlist_page(
    display_name: str,
    tracks: list[dict],
    track_arts: list[str],
    track_links: list[list[dict]],
    covers_mode: bool,
    site_title: str,
    accent_color: str,
) -> str:
    track_count = len(tracks)
    years = [int(t["year"]) for t in tracks if t.get("year", "").isdigit()]
    year_range = f"{min(years)}&ndash;{max(years)}" if years else ""

    meta_str = f"{track_count} tracks"
    if year_range:
        meta_str += f" &middot; {year_range}"

    cards_html = "\n".join(
        render_track_card(tracks[i], track_arts[i], track_links[i], covers_mode)
        for i in range(len(tracks))
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{display_name} — {site_title}</title>
<link rel="stylesheet" href="../../style.css">
<style>:root {{ --accent: {accent_color}; }}</style>
</head>
<body>

<header class="site-header">
  <div class="site-header-inner">
    <div class="site-logo"><a href="../../">{site_title}</a></div>
    <nav class="site-nav">
      <a href="../../">Playlists</a>
      <a href="../../search.html">Search</a>
    </nav>
  </div>
</header>

<div class="page-header">
  <div class="page-header-label">Playlist</div>
  <h1 class="page-header-title">{display_name}</h1>
  <div class="page-header-meta">{meta_str}</div>
</div>

<main class="main-content">
  <div class="track-grid">
    {cards_html}
  </div>
</main>

<footer class="site-footer">
  Generated by iTunes Playlist Site Generator
</footer>

</body>
</html>"""


# ── Main generation function ───────────────────────────────────────────────────

def generate_playlist(
    xml_path: str,
    output_dir: str,
    slug: str,
    playlist_name: str | None    = None,
    overrides: dict              = None,
    covers_mode: bool            = True,
    site_title: str              = "Playlists",
    accent_color: str            = "#e8b84b",
    art_cache_dir: str | None    = None,
    links_cache_file: str | None = None,
    save_art_files: bool         = True,
    img_dir: str | None          = None,
    site_root: bool              = True,
    verbose: bool                = True,
) -> dict:
    """
    Generate a playlist HTML page and save artwork image files.

    Returns a dict with keys:
      display_name, slug, track_count, year_min, year_max,
      art_paths (list of relative paths like img/<slug>/01.jpg or None),
      html_path
    """
    overrides = overrides or {}

    mbid_overrides         = overrides.get("mbid_overrides", {})
    album_display_overrides = overrides.get("album_display_overrides", {})
    art_file_overrides     = overrides.get("art_file_overrides", {})

    output_dir  = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # img_dir: explicit override, or default to output_dir/img/
    if img_dir:
        _img_dir = Path(img_dir)
    else:
        _img_dir = output_dir / "img"
    _img_dir.mkdir(parents=True, exist_ok=True)

    # HTML goes to output_dir/index.html (each playlist is its own directory)
    html_output_path = output_dir / "index.html"

    # Cache dirs — explicit arg > config.ini > default inside output_dir
    if art_cache_dir:
        _art_cache = Path(art_cache_dir)
    else:
        _ini_art = _cget('paths', 'art_cache_dir', '')
        _art_cache = Path(_ini_art) if _ini_art else output_dir / "_cache" / "art"
    _art_cache.mkdir(parents=True, exist_ok=True)

    if links_cache_file:
        _links_cache_path = Path(links_cache_file)
    else:
        _ini_lc = _cget('paths', 'links_cache', '')
        _links_cache_path = Path(_ini_lc) if _ini_lc else output_dir / "_cache" / f"{slug}_links.json"
    _links_cache_path.parent.mkdir(parents=True, exist_ok=True)

    links_cache = {}
    if _links_cache_path.exists():
        with open(_links_cache_path, encoding='utf-8') as f:
            links_cache = json.load(f)

    session   = requests.Session()
    delay_ref = [0.0]

    # Parse XML
    if verbose: print(f"  Parsing {xml_path}…")
    display_name, tracks = parse_itunes_xml(xml_path, playlist_name)

    # Apply album display overrides

    def process_track(t_idx, t):
        num = str(t["number"])
        num_padded = f"{t['number']:02d}"
        if verbose:
            print(f"  [{num_padded}] {t['title']} — {t['artist']}")
            
        mbid = mbid_overrides.get(num)
        if not mbid:
            cache_key = f"{t['artist']}|{t['album']}"
            if cache_key in links_cache and "mbid" in links_cache[cache_key]:
                mbid = links_cache[cache_key]["mbid"]
            else:
                mbid = find_mbid_by_album_artist(t["album"], t["artist"], session, delay_ref, title=t.get("title", ""))
                if cache_key not in links_cache:
                    links_cache[cache_key] = {}
                links_cache[cache_key]["mbid"] = mbid
                
        cache_key = f"{t['artist']}|{t['album']}"
        if cache_key in links_cache and "links" in links_cache[cache_key]:
            raw_links = links_cache[cache_key]["links"]
        elif mbid:
            raw_links = get_release_links(mbid, session, delay_ref)
            if cache_key not in links_cache:
                links_cache[cache_key] = {}
            links_cache[cache_key]["links"] = raw_links
        else:
            raw_links = []
            
        tl = best_links(raw_links, mbid, artist=t["artist"], album=t.get("album_display", t.get("album", "")), title=t.get("title", ""))
        
        art_override = art_file_overrides.get(num)
        img_bytes = fetch_artwork(t, mbid, art_override, _art_cache, session, delay_ref)
        
        m_art = None
        if img_bytes and save_art_files:
            out_path = _img_dir / f"{num_padded}.jpg"
            out_path.write_bytes(img_bytes)
            art_src = f"img/{num_padded}.jpg"
        elif img_bytes:
            art_src = bytes_to_data_uri(img_bytes)
        else:
            art_src = ART_PLACEHOLDER
            m_art = {
                "num": num,
                "num_padded": num_padded,
                "title": t["title"],
                "artist": t["artist"],
                "album": t.get("album_display", t.get("album", "")),
                "img_filename": f"{num_padded}.jpg",
            }
            
        return t_idx, art_src, tl, m_art

    track_arts = [None] * len(tracks)
    track_links = [None] * len(tracks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_track, i, t): i for i, t in enumerate(tracks)}
        for future in concurrent.futures.as_completed(futures):
            i, art_src, tl, m_art = future.result()
            track_arts[i] = art_src
            track_links[i] = tl
            if m_art:
                missing_art.append(m_art)

    # Save links cache
    with open(_links_cache_path, "w", encoding='utf-8') as f:
        json.dump(links_cache, f, indent=2)

    # ── Missing art report ────────────────────────────────────────────────────
    if missing_art:
        img_dir_display = str(_img_dir)
        print(f"\n  ⚠  {len(missing_art)} track(s) missing artwork for: {display_name}")
        print(f"     Save images as JPG to:\n     {img_dir_display}\n")
        print(f"     {'#':<4}  {'File':<10}  {'Search for (Google Images / Discogs / MusicBrainz)'}")
        print(f"     {'-'*4}  {'-'*10}  {'-'*50}")
        for m in missing_art:
            search_hint = f"{m['album']}  —  {m['artist']}"
            print(f"     {m['num']:<4}  {m['img_filename']:<10}  {search_hint}")
        print()

    # Render HTML
    html = render_playlist_page(
        display_name, tracks, track_arts, track_links,
        covers_mode, site_title, accent_color,
    )
    html_output_path.write_text(html, encoding="utf-8")

    if verbose:
        print(f"  ✓ Written: {html_output_path}")

    years = [int(t["year"]) for t in tracks if t.get("year", "").isdigit()]
    year_range = f"{min(years)}–{max(years)}" if years else ""

    # Art thumbnails for landing page collage (first 4 tracks)
    art_thumbnails = [
        src for src in track_arts[:4]
        if not src.startswith("data:")  # skip placeholders/base64
    ]

    meta = {
        "name":          display_name,
        "slug":          slug,
        "track_count":   len(tracks),
        "year_range":    year_range,
        "year_min":      min(years) if years else None,
        "year_max":      max(years) if years else None,
        "url":           f"playlists/{slug}/",
        "art_thumbnails": art_thumbnails,
        "tracks": [
            {
                "title":       t["title"],
                "artist":      t["artist"],
                "orig_artist": t.get("orig_artist", ""),
                "album":       t.get("album_display", t.get("album", "")),
                "year":        t.get("year", ""),
            }
            for t in tracks
        ],
        "html_path": str(html_output_path),
        "missing_art": missing_art,
    }

    # Write playlist_meta.json for build_site.py to consume
    meta_path = output_dir / "playlist_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return meta


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a single playlist HTML page from an iTunes XML file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 playlist_generator.py playlist.xml --output-dir ./output --slug my-playlist
  python3 playlist_generator.py library.xml --list-playlists
  python3 playlist_generator.py library.xml --output-dir ./output --playlist "Covers XX" \\
      --overrides overrides.json --covers-mode
        """,
    )
    parser.add_argument("xml", help="iTunes XML file path")
    parser.add_argument("--output-dir",     default="./output", help="Output directory")
    parser.add_argument("--slug",           help="URL slug (derived from playlist name if omitted)")
    parser.add_argument("--playlist",       help="Playlist name to use (if XML has multiple)")
    parser.add_argument("--overrides",      help="JSON overrides file")
    parser.add_argument("--covers-mode",    action="store_true", default=True,
                        help="Enable covers display mode (default: on)")
    parser.add_argument("--no-covers-mode", action="store_false", dest="covers_mode")
    parser.add_argument("--site-title",     default="Playlists")
    parser.add_argument("--accent-color",   default="#e8b84b")
    parser.add_argument("--art-cache-dir",  help="Shared artwork cache directory")
    parser.add_argument("--img-dir",        help="Output directory for artwork images (default: output-dir/img/)")
    parser.add_argument("--site-root",      action="store_true",
                        help="Use root-relative paths (/playlists/slug/img/...) in generated HTML")
    parser.add_argument("--verbose", "-v",  action="store_true",
                        help="Verbose output")
    parser.add_argument("--list-playlists", action="store_true",
                        help="List playlists in XML and exit")
    args = parser.parse_args()

    if args.list_playlists:
        names = list_playlists(args.xml)
        print("Playlists in XML:")
        for n in names:
            print(f"  • {n}")
        return

    overrides = {}
    if args.overrides:
        with open(args.overrides, encoding='utf-8') as f:
            overrides = json.load(f)

    slug = args.slug
    if not slug:
        # Derive from playlist name or filename
        names = list_playlists(args.xml)
        base  = names[0] if names else Path(args.xml).stem
        slug  = slugify(base)

    result = generate_playlist(
        xml_path      = args.xml,
        output_dir    = args.output_dir,
        slug          = slug,
        playlist_name = args.playlist,
        overrides     = overrides,
        covers_mode   = args.covers_mode,
        site_title    = args.site_title,
        accent_color  = args.accent_color,
        art_cache_dir = args.art_cache_dir,
        img_dir       = args.img_dir,
        site_root     = args.site_root,
        verbose       = args.verbose,
    )

    print(f"\nDone: {result['name']} ({result['track_count']} tracks)")
    print(f"HTML: {result['html_path']}")


if __name__ == "__main__":
    main()
