# iTunes Playlist Website Builder

A Python-based static site generator that turns iTunes XML playlist exports into a **magazine-style music website**, hosted on GitHub Pages.

Live example: [hearmycovers.com](http://hearmycovers.com)

---

## What It Does

- Reads one or more **iTunes XML playlist** files
- Looks up **album artwork** and **metadata** via MusicBrainz, Deezer, and Cover Art Archive
- Generates a **multi-page static website** — one page per playlist, plus a searchable landing page
- Outputs clean HTML + CSS ready to push to **GitHub Pages** (free hosting)
- Supports a **covers mode** where each song is treated as a cover version, with artwork and links for the *cover artist's* release

---

## Features

- 🎨 **Magazine dark theme** — warm gold accents, near-black background (Mojo/Uncut energy)
- 🖼️ **Smart artwork lookup** — tries embedded MP3/M4A tags (APIC/covr), Deezer, Cover Art Archive, local overrides
- 🔗 **Rich link pills** per track — review sites (Pitchfork, BBC, Guardian, NME, etc.) and database links (AllMusic, Discogs, RYM, MusicBrainz, Spotify, YouTube, Apple Music, Deezer, Bandcamp and more)
- 🔍 **Search** across song title, cover artist, and original artist
- 🗂️ **Sort** playlists alphabetically or by date added
- ⚙️ **Fully configurable** via `config.ini` — no hardcoded paths or settings
- 🌐 **Custom domain support** — auto-generates `CNAME` file on every build
- 📦 **MBID overrides** — force specific MusicBrainz release IDs per track via a JSON sidecar

---

## Requirements

- Python 3.10+
- Packages: `requests`, `mutagen`, `Pillow`, `python-dateutil`

Install with:
```
pip install requests mutagen Pillow python-dateutil
```

---

## File Structure

```
itunes-playlist-website/
├── build_site.py           # Site orchestrator — builds all playlists + landing page
├── playlist_generator.py   # Per-playlist engine — artwork, metadata, HTML generation
├── style.css               # Magazine dark theme stylesheet
├── config.ini              # All settings (paths, MusicBrainz, artwork, links, etc.)
├── rebuild_site.bat        # Windows: run build_site.py
├── upload_site.bat         # Windows: push output folder to GitHub Pages
└── itunes_playlist_site.txt  # Full help manual
```

---

## Quick Start

### 1. Configure `config.ini`

Edit the `[paths]` section to point at your files:

```ini
[paths]
xml_input_dir = C:\path\to\your\iTunes\playlists\
output_dir    = C:\path\to\output\folder\
art_cache_dir = C:\path\to\output\folder\.art_cache\
links_cache   = C:\path\to\output\folder\.links_cache.json
```

Set your custom domain (or leave blank for GitHub Pages default URL):
```ini
[site]
custom_domain = yourdomain.com
```

List your playlists oldest-first in the `[playlists]` section:
```ini
[playlists]
playlist_order =
    my-first-playlist
    my-second-playlist
```

The slug is the playlist name lowercased with spaces replaced by hyphens.

### 2. Add iTunes XML files

Export playlists from iTunes/Music: **File → Library → Export Playlist…** (choose XML format). Place the `.xml` files in your `xml_input_dir`.

### 3. Build the site

```
python build_site.py
```

Or on Windows, double-click `rebuild_site.bat`.

### 4. Upload to GitHub Pages

Double-click `upload_site.bat` (Windows) — it reads `output_dir` from `config.ini` and force-pushes to your GitHub Pages repo.

---

## Artwork Overrides

For any track where automatic artwork lookup fails or you want a specific image, create a sidecar JSON file next to your XML:

**`My Playlist_overrides.json`**
```json
{
  "Track Name": {
    "art_url": "https://example.com/my-image.jpg"
  }
}
```

Or place an image in your `art_cache_dir` and reference it with `"art_local": "filename.jpg"`.

You can also force a specific MusicBrainz release ID:
```json
{
  "Ring of Fire": {
    "mbid": "c1aa4fa7-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

---

## Covers Mode

When `covers_mode = true` in `config.ini`, the site is optimised for playlists of *cover versions*:

- Artwork is sourced for the **cover artist's release**, not the original
- Each card shows: **Cover Artist — Album (Year)**
- Original artist is shown separately and is searchable
- Link pills target the cover artist's release on each platform

---

## Configuration Reference

See `itunes_playlist_site.txt` for the full manual, or run:

```
python build_site.py --help
```

Key config sections:

| Section | Purpose |
|---|---|
| `[paths]` | Input/output directories and cache files |
| `[build]` | covers_mode, force_rebuild, verbose |
| `[musicbrainz]` | API settings, rate limiting, search depth |
| `[artwork]` | Image sizes, Deezer timeout, thumbnail size |
| `[site]` | Title, tagline, accent colour, custom domain |
| `[cdn]` | Fuse.js and favicon CDN URLs |
| `[links]` | Which review/database sites to show; search URL templates |
| `[search_terms]` | Per-site query mode (title+artist vs album+artist) |
| `[playlists]` | Ordered list of playlist slugs (oldest first) |

---

## Hosting on GitHub Pages

1. Create a GitHub repo for your output folder
2. Enable GitHub Pages in repo Settings → Pages → Deploy from branch (`main`)
3. (Optional) Add a custom domain in Pages settings and set DNS A records to:
   ```
   185.199.108.153
   185.199.109.153
   185.199.110.153
   185.199.111.153
   ```
4. Set `custom_domain` in `config.ini` — the `CNAME` file is written automatically on every build

---

## Version History

| Version | Changes |
|---|---|
| V2.6.1 | M4A support: embedded artwork (covr atom) and Deezer ID (freeform atom) now extracted from M4A/AAC files |
| V2.6 | Bug fixes: CSS class mismatches (card footer, nav active, sort bar), unified slugify(), per-thread requests.Session, unclosed file handle |
| V2.5 | site.json fully removed; all settings in config.ini; playlist_order moved to [playlists] section |
| V2.4.1 | Bug fixes: constructed link templates, per-site search terms, search_attempts depth, thumbnail_size CSS variable |
| V2.4 | Full config.ini extraction — all settings moved out of code |
| V2.3 | PyInstaller EXE support |
| V2.2 | MP3 embedded APIC artwork extraction |
| V2.1 | Additional hyperlinked sources (Pitchfork, Discogs, RYM, etc.) |
| V2.0 | Multi-page static site; GitHub Pages deployment |
| V1.x | Single-playlist HTML poster generator |

---

## License

MIT — do whatever you like with it.
