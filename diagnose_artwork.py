#!/usr/bin/env python3
"""
diagnose_artwork.py — Artwork pipeline diagnostic for iTunes playlist XMLs.

Checks every step of the artwork waterfall for each track and reports exactly
what succeeds or fails — without generating HTML or writing any cache.

Usage:
  python diagnose_artwork.py <path/to/playlist.xml>
  python diagnose_artwork.py <path/to/playlist.xml> 5          # one track
  python diagnose_artwork.py <path/to/playlist.xml> 5 12 19    # specific tracks

Reads music_root and other paths from config.ini in the same folder.
"""

import sys, os, re, time, configparser, plistlib, traceback
from pathlib import Path
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.ini"

# ── Mutagen ──────────────────────────────────────────────────────────────────────
try:
    from mutagen.id3 import ID3, ID3NoHeaderError
    from mutagen.mp4 import MP4
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False
    print("WARNING: mutagen not installed — run: pip install mutagen\n")

import requests

# ── Config ───────────────────────────────────────────────────────────────────────
def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE, encoding="utf-8")
    return cfg

# ── iTunes XML parsing ───────────────────────────────────────────────────────────
def _resolve_location(loc_raw: str, music_root: str) -> str:
    """Convert iTunes file:// URL to a local Windows path using music_root."""
    if not loc_raw:
        return ""
    loc = loc_raw
    # Strip scheme
    for prefix in ("file://localhost/", "file:///", "file://"):
        if loc.startswith(prefix):
            loc = loc[len(prefix):]
            break
    loc = unquote(loc)
    # Find /music/ segment and remap beneath music_root
    m = re.search(r'[/\\]music[/\\](.+)$', loc, re.IGNORECASE)
    if m:
        relative = m.group(1).replace("/", os.sep)
        return os.path.join(music_root, relative)
    return loc

def parse_xml(xml_path: Path, music_root: str):
    with open(xml_path, "rb") as f:
        data = plistlib.load(f)
    playlists = data.get("Playlists", [])
    if not playlists:
        raise ValueError("No playlists found in XML")
    pl = playlists[0]
    playlist_name = pl.get("Name", xml_path.stem)
    track_ids = [item["Track ID"] for item in pl.get("Playlist Items", [])]
    all_tracks = data.get("Tracks", {})
    tracks = []
    for i, tid in enumerate(track_ids, 1):
        t = all_tracks.get(str(tid), {})
        loc_raw = t.get("Location", "")
        tracks.append({
            "number":       i,
            "title":        t.get("Name", ""),
            "artist":       t.get("Artist", ""),
            "album":        t.get("Album", ""),
            "location_raw": loc_raw,
            "location":     _resolve_location(loc_raw, music_root),
        })
    return playlist_name, tracks

# ── Embedded artwork ─────────────────────────────────────────────────────────────
_APIC_TYPES = {
    0: "Other", 1: "File icon", 2: "Other icon", 3: "Cover (front)",
    4: "Cover (back)", 5: "Leaflet", 6: "Media", 7: "Lead artist",
}

def diag_embedded_art(loc: str) -> dict:
    """Deep-inspect embedded artwork in an MP3 or M4A file."""
    r = {"ok": False, "size": 0, "lines": []}
    add = r["lines"].append

    if not MUTAGEN_OK:
        add("mutagen not installed — cannot check embedded art")
        return r
    if not loc:
        add("location is empty")
        return r
    if not os.path.exists(loc):
        add(f"FILE NOT FOUND: {loc!r}")
        return r

    size_kb = os.path.getsize(loc) / 1024
    ext = os.path.splitext(loc)[1].lower()
    add(f"file: {size_kb:.1f} KB | ext: {ext}")

    try:
        if ext == ".m4a":
            add("parsing as M4A (MP4 container)...")
            tags = MP4(loc)
            covers = tags.get("covr", [])
            add(f"covr atoms found: {len(covers)}")
            if covers:
                data = bytes(covers[0])
                r["ok"] = True
                r["size"] = len(data)
                add(f"✓ M4A cover: {len(data):,} bytes")
            else:
                add("✗ no covr atoms — file has no embedded artwork")
        else:
            add("parsing as ID3 (MP3)...")
            try:
                tags = ID3(loc)
            except ID3NoHeaderError as e:
                add(f"✗ ID3NoHeaderError — file has no ID3 header at all")
                add(f"  ({e})")
                add("  Tip: This MP3 has no tags. Try re-tagging it with iTunes or Mp3tag.")
                return r

            all_keys = list(tags.keys())
            apic = [v for k, v in tags.items() if k.startswith("APIC")]
            add(f"ID3 total frames: {len(all_keys)} | APIC frames: {len(apic)}")

            if apic:
                for i, f in enumerate(apic):
                    type_name = _APIC_TYPES.get(f.type, f"type {f.type}")
                    add(f"  APIC[{i}]: type={f.type} ({type_name}) | mime={f.mime} | {len(f.data):,} bytes")
                best = next((f for f in apic if f.type == 3), apic[0])
                if best.data:
                    r["ok"] = True
                    r["size"] = len(best.data)
                    add(f"✓ using APIC[type={best.type}]: {len(best.data):,} bytes")
                else:
                    add("✗ APIC frame exists but data is empty bytes")
            else:
                add("✗ no APIC frames — file has no embedded artwork")
                # Show what tag frames ARE present (helpful for debugging)
                non_text = [k for k in all_keys if not k.startswith("T") and not k.startswith("W")]
                if non_text:
                    add(f"  Non-text frames present: {non_text[:10]}")

    except Exception as e:
        add(f"✗ EXCEPTION: {type(e).__name__}: {e}")
        for line in traceback.format_exc().splitlines():
            add(f"  {line}")

    return r

# ── Deezer ID ────────────────────────────────────────────────────────────────────
def diag_deezer_id(loc: str) -> dict:
    r = {"id": None, "lines": []}
    add = r["lines"].append

    if not MUTAGEN_OK or not loc or not os.path.exists(loc):
        add("file missing or mutagen unavailable")
        return r

    ext = os.path.splitext(loc)[1].lower()
    try:
        if ext == ".m4a":
            tags = MP4(loc)
            dz_keys = [k for k in tags.keys() if "deezer" in k.lower()]
            add(f"M4A deezer keys: {dz_keys if dz_keys else 'none'}")
            for k in dz_keys:
                v = tags[k][0] if isinstance(tags[k], list) else tags[k]
                v = (v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else str(v)).strip()
                if v.isdigit():
                    r["id"] = v
                    add(f"✓ Deezer ID: {v}")
        else:
            try:
                tags = ID3(loc)
            except ID3NoHeaderError:
                add("ID3NoHeaderError (no tags, same as above)")
                return r
            dz_keys = [k for k in tags.keys() if k.startswith("TXXX:") and "deezer" in k.lower()]
            add(f"TXXX deezer keys: {dz_keys if dz_keys else 'none'}")
            for k in dz_keys:
                val = str(tags[k].text[0]).strip()
                if val.isdigit():
                    r["id"] = val
                    add(f"✓ Deezer ID: {val}")
    except Exception as e:
        add(f"EXCEPTION: {type(e).__name__}: {e}")

    if not r["id"]:
        add("✗ no Deezer ID in tags")
    return r

# ── MusicBrainz ──────────────────────────────────────────────────────────────────
MB_BASE  = "https://musicbrainz.org/ws/2"
MB_AGENT = "diagnose-artwork/1.0 (itunes-playlist-site diagnostic)"
MB_DELAY = 1.1
_last_mb  = [0.0]

def _mb_get(session: requests.Session, path: str, params: dict) -> dict:
    elapsed = time.time() - _last_mb[0]
    if elapsed < MB_DELAY:
        time.sleep(MB_DELAY - elapsed)
    _last_mb[0] = time.time()
    r = session.get(f"{MB_BASE}/{path}", params={**params, "fmt": "json"},
                    headers={"User-Agent": MB_AGENT}, timeout=10)
    r.raise_for_status()
    return r.json()

def diag_musicbrainz(session: requests.Session, artist: str, album: str, title: str) -> dict:
    r = {"mbid": None, "release_title": None, "strategy": None, "lines": []}
    add = r["lines"].append

    strategies = [
        (1, "strict",    f'release:"{album}" AND artist:"{artist}"'),
        (2, "loose",     f'"{album}" "{artist}"'),
        (3, "recording", f'recording:"{title}" AND artist:"{artist}"' if title else None),
        (4, "title",     f'"{title}" "{artist}"'                      if title else None),
    ]

    for num, name, query in strategies:
        if not query:
            continue
        add(f"  Strategy {num} ({name}): {query}")
        try:
            data = _mb_get(session, "release", {"query": query, "limit": 5})
            releases = data.get("releases", [])
            add(f"    → {len(releases)} result(s)")
            if releases:
                top = releases[0]
                r["mbid"]          = top["id"]
                r["strategy"]      = num
                r["release_title"] = top.get("title", "")
                add(f"    ✓ {top.get('title','?')} [{top['id'][:8]}…]")
                return r
        except Exception as e:
            add(f"    ERROR: {type(e).__name__}: {e}")

    add("  ✗ no release found on MusicBrainz")
    return r

# ── Cover Art Archive ─────────────────────────────────────────────────────────────
def diag_caa(session: requests.Session, mbid: str) -> dict:
    r = {"ok": False, "lines": []}
    add = r["lines"].append
    if not mbid:
        add("skipped (no MBID)")
        return r
    try:
        resp = session.get(f"https://coverartarchive.org/release/{mbid}/front-500",
                           timeout=10, allow_redirects=True)
        ct = resp.headers.get("Content-Type", "")
        if resp.status_code == 200 and ct.startswith("image"):
            r["ok"] = True
            add(f"✓ {len(resp.content):,} bytes ({ct})")
        else:
            add(f"✗ HTTP {resp.status_code} ({ct})")
    except Exception as e:
        add(f"✗ {type(e).__name__}: {e}")
    return r

# ── Main ──────────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    xml_path    = Path(sys.argv[1])
    filter_nums = {int(x) for x in sys.argv[2:]} if len(sys.argv) > 2 else None

    cfg        = load_config()
    music_root = cfg.get("paths", "music_root", fallback=r"P:\music")

    print(f"\n{'='*70}")
    print(f"  Artwork Diagnostic")
    print(f"  XML:        {xml_path.name}")
    print(f"  music_root: {music_root}")
    if filter_nums:
        print(f"  Tracks:     {sorted(filter_nums)}")
    print(f"{'='*70}\n")

    try:
        playlist_name, tracks = parse_xml(xml_path, music_root)
    except Exception as e:
        print(f"ERROR parsing XML: {e}")
        sys.exit(1)

    print(f"Playlist : {playlist_name}")
    print(f"Tracks   : {len(tracks)}\n")

    session = requests.Session()
    session.headers["User-Agent"] = MB_AGENT

    summary = {"total": 0, "apic": 0, "deezer": 0, "caa": 0, "none": 0}

    for t in tracks:
        n = t["number"]
        if filter_nums and n not in filter_nums:
            continue

        summary["total"] += 1
        title  = t["title"]
        artist = t["artist"]
        album  = t["album"]
        loc    = t["location"]

        print(f"{'─'*70}")
        print(f"  #{n:02d}  {title}")
        print(f"        {artist} — {album}")
        print(f"        loc: {loc or '(empty)'}")
        print()

        # ── File check
        exists = os.path.exists(loc) if loc else False
        print(f"  [File]    {'FOUND ✓' if exists else 'NOT FOUND ✗'}")
        if not exists and loc:
            # Show what part of the path does exist (helps spot truncation)
            p = Path(loc)
            while p != p.parent:
                p = p.parent
                if p.exists():
                    print(f"            deepest existing parent: {p}")
                    break

        # ── Embedded art
        art = diag_embedded_art(loc)
        print(f"\n  [APIC]    {'✓ %d bytes' % art['size'] if art['ok'] else '✗ none'}")
        for line in art["lines"]:
            print(f"            {line}")

        # ── Deezer ID
        dz = diag_deezer_id(loc)
        print(f"\n  [Deezer]  {'✓ id=' + dz['id'] if dz['id'] else '✗ none'}")
        for line in dz["lines"]:
            print(f"            {line}")

        # ── MusicBrainz
        print(f"\n  [MB]      Searching…")
        mb = diag_musicbrainz(session, artist, album, title)
        label = f"✓ mbid={mb['mbid'][:8]}… ({mb['release_title']})" if mb["mbid"] else "✗ not found"
        print(f"  [MB]      {label}")
        for line in mb["lines"]:
            print(f"            {line}")

        # ── CAA
        caa = diag_caa(session, mb["mbid"])
        print(f"\n  [CAA]     {'✓ artwork available' if caa['ok'] else '✗ none'}")
        for line in caa["lines"]:
            print(f"            {line}")

        # ── Result
        if art["ok"]:
            src = "APIC/covr (embedded)"
            summary["apic"] += 1
        elif dz["id"]:
            src = "Deezer (would fetch via API)"
            summary["deezer"] += 1
        elif caa["ok"]:
            src = "Cover Art Archive"
            summary["caa"] += 1
        else:
            src = "MISSING — no source found"
            summary["none"] += 1

        print(f"\n  ► Best source: {src}\n")

    # ── Summary
    print(f"\n{'='*70}")
    print(f"  SUMMARY  ({summary['total']} track(s) checked)")
    print(f"  ✓ Embedded (APIC/covr) : {summary['apic']}")
    print(f"  ✓ Deezer ID in tags    : {summary['deezer']}")
    print(f"  ✓ Cover Art Archive    : {summary['caa']}")
    print(f"  ✗ No source found      : {summary['none']}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
