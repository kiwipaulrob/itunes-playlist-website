# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.10] - 2025-06-06

### Added

- Precision regex for "(orig. Artist)" format in covers mode
- `clean_artist_name()` to filter descriptive labels (live, acoustic, remix, version) from original artist names in statistics

### Changed

- Navigation link order updated to Playlists, Search, Statistics
- Landing page link label changed from site title to "Playlists"
- Spec documentation (`SPEC.md`, `itunes_playlist_site_spec.md`) updated with V2.9–V2.10 changelog entries

### Fixed

- Artist name cleaning now handles parenthesised markers during statistics generation

## [2.9] - 2025-06-05

### Changed

- Navigation link order: Playlists, Search, Statistics
- Landing page link label now reads "Playlists" instead of the site title

## [2.8] - 2025-06-04

### Added

- Statistics page (`stats.py`, `stats.html`) for per-artist tracking across all playlists

### Changed

- Index page layout updated to accommodate new search- and stats-related navigation

## [2.7] - 2025-06-03

### Fixed

- Unicode/encoding robustness for non-ASCII track metadata

### Changed

- Internal slugify function unified across modules

## [2.6.1] - 2025-05-28

### Added

- M4A support: embedded artwork (covr atom) and Deezer ID (freeform atom) extraction from M4A/AAC files

### Fixed

- CSS class mismatches (card footer, nav active, sort bar)
- Unified `slugify()` across modules
- Per-thread `requests.Session` usage
- Unclosed file handle

## [2.6] - 2025-05-20

### Changed

- `site.json` fully removed; all settings moved to `config.ini`
- `playlist_order` moved to `[playlists]` config section

## [2.5] - 2025-05-15

### Fixed

- Constructed link templates
- Per-site search terms
- `search_attempts` depth
- `thumbnail_size` CSS variable

### Changed

- Config extraction completed — all settings moved out of code into `config.ini`

## [2.4] - 2025-05-10

### Added

- Full `config.ini` extraction — all settings moved out of code

## [2.3] - 2025-05-05

### Added

- PyInstaller EXE support for Windows users without Python

## [2.2] - 2025-05-01

### Added

- MP3 embedded APIC artwork extraction

## [2.1] - 2025-04-25

### Added

- Additional hyperlinked sources: Pitchfork, Discogs, RYM, and more

## [2.0] - 2025-04-15

### Added

- Multi-page static site generation
- GitHub Pages deployment support
- Magazine-style dark theme with warm gold accents
- Smart artwork lookup (MusicBrainz, Deezer, Cover Art Archive)
- Rich link pills per track
- Cross-playlist search with Fuse.js
- Configurable via `config.ini`

## [1.x] - 2025-03

### Added

- Single-playlist HTML poster generator (precursor to V2)
