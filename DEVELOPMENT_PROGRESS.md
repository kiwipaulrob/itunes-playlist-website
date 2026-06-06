# Development Progress

This document tracks the overall development status, completed milestones, and planned future work for the **iTunes Playlist Website Builder**.

---

## Overview

A Python-based static site generator that converts iTunes XML playlist exports into a magazine-style music website, hosted on GitHub Pages. The project has evolved from a single-playlist HTML poster generator (V1.x) into a multi-page, searchable, artwork-rich static site builder (V2.x current).

**Current version**: [2.10](CHANGELOG.md)

---

## Status

| Area | Status | Notes |
|---|---|---|
| **Core build pipeline** | ✅ Stable | Multi-playlist orchestration, incremental builds |
| **Artwork lookup** | ✅ Stable | MusicBrainz, Deezer, Cover Art Archive, embedded tags (MP3/M4A), local overrides |
| **HTML generation** | ✅ Stable | Per-playlist pages, landing page with search, link pills |
| **Search** | ✅ Stable | Cross-playlist search via Fuse.js (client-side) |
| **Statistics** | ✅ Stable | Per-artist tracking across all playlists (`stats.py`, `stats.html`) |
| **Configuration** | ✅ Stable | All settings in `config.ini` |
| **GitHub Pages deployment** | ✅ Stable | Custom domain, CNAME auto-generation, upload scripts |
| **Covers mode** | ✅ Stable | Optimised for cover-version playlists |
| **Windows support** | ✅ Stable | `.bat` scripts for rebuild and upload |
| **Tests** | ❌ Not started | No automated test suite yet |
| **CI/CD** | ❌ Not started | No GitHub Actions or CI pipeline |
| **Package structure** | ❌ Not started | Single-file modules, not yet a pip-installable package |

---

## Completed Milestones

### V1.x — Single-Playlist Poster Generator
- Generate a single HTML poster from one iTunes XML playlist
- Basic metadata display (song title, artist, album)

### V2.0 — Multi-Page Static Site
- Multi-page output: one page per playlist + landing page
- Magazine-style dark theme (warm gold accents, near-black background)
- Smart artwork lookup chain (tags → Deezer → Cover Art Archive → local overrides)
- Rich link pills per track (Pitchfork, Discogs, RYM, MusicBrainz, Spotify, YouTube, etc.)
- Fuse.js-based cross-playlist search
- Full GitHub Pages deployment support with custom domains
- Configurable via `config.ini`

### V2.1–V2.5 — Feature Expansion & Config Extraction
- Additional hyperlinked sources added
- MP3 embedded APIC artwork extraction
- PyInstaller EXE support for Windows
- All settings moved from code into `config.ini`
- Per-site search terms, constructed link templates

### V2.6–V2.7 — Robustness & M4A Support
- M4A/AAC support: covr atom extraction, Deezer ID from freeform atoms
- CSS class consistency fixes
- Unified `slugify()` across modules
- Per-thread `requests.Session`, unclosed file handle fix
- Unicode/encoding robustness

### V2.8 — Statistics
- Per-artist tracking page (`stats.html`) generated via `stats.py`
- Index page layout updated for stats and search navigation

### V2.9–V2.10 — Artist Name Cleaning & Navigation Polish
- `clean_artist_name()` filters descriptive labels (live, acoustic, remix, version)
- Navigation reordered to Playlists, Search, Statistics
- Precision regex for covers mode "(orig. Artist)" parsing

---

## Future Ideas & Roadmap

### Short-term (Next)

- [ ] **Automated test suite** — unit tests for artwork lookup, slugify, artist name cleaning, HTML generation
- [ ] **GitHub Actions CI** — lint, test, and optionally auto-deploy
- [ ] **Dark/light theme toggle** — CSS custom properties for user-switchable themes

### Medium-term

- [ ] **PyPI package** — `pip install itunes-playlist-website`
- [ ] **CLI improvements** — richer `--help`, subcommands, JSON output mode
- [ ] **Image caching** — persistent artwork cache with expiry/refresh logic
- [ ] **More metadata sources** — Spotify API, Apple Music API, Discogs API
- [ ] **Responsive design improvements** — better mobile layout for the magazine theme
- [ ] **Pagination** — for playlists with many tracks (50+)

### Long-term / Stretch

- [ ] **Docker image** — one-command containerised build
- [ ] **Web UI** — simple local web server with form-based config and one-click build
- [ ] **Multi-language support** — i18n for search labels, page titles, link text
- [ ] **RSS/Atom feed generation** — subscribe to new playlist additions
- [ ] **Social preview images** — auto-generated OG images per playlist
- [ ] **Plugin system** — hook-based architecture for custom artwork sources, link generators, or output formats
- [ ] **YouTube Music / Spotify playlist import** — convert streaming-service playlists to the same format

---

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and pull request guidelines.
