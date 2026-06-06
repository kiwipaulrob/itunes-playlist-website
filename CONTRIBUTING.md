# Contributing

Thanks for your interest in contributing to the **iTunes Playlist Website Builder**!

This document outlines the workflow, code style, and development setup for contributors.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Making Changes](#making-changes)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Reporting Issues](#reporting-issues)

---

## Project Overview

The project is a Python static site generator that converts iTunes XML playlists into a magazine-style website. Key modules:

| File | Purpose |
|---|---|
| `build_site.py` | Site orchestrator — builds all playlists + landing page |
| `playlist_generator.py` | Per-playlist engine — artwork, metadata, HTML generation |
| `stats.py` | Statistics generation — per-artist tracking |
| `style.css` | Magazine dark theme stylesheet |
| `config.ini` | All settings (paths, MusicBrainz, artwork, links, etc.) |

---

## Development Setup

### Prerequisites

- **Python 3.10+**
- **pip** or **uv**

### Clone and Install Dependencies

```bash
git clone https://github.com/yourusername/itunes-playlist-website.git
cd itunes-playlist-website
pip install requests mutagen Pillow python-dateutil
```

### Verify Your Setup

```bash
python build_site.py --help
```

You should see the help screen. For a full test run, point `config.ini` at a directory of iTunes XML exports and run:

```bash
python build_site.py
```

---

## Code Style

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/) with a 100-character line limit
- **Imports**: Group standard library, third-party, then local; separate groups with a blank line
- **Naming**: `snake_case` for functions and variables, `UPPER_CASE` for constants, `CamelCase` for classes
- **Docstrings**: Use triple-double-quotes (`"""`) with a one-line summary followed by details
- **Type hints**: Optional but encouraged for public functions
- **CSS**: Use descriptive class names; avoid deep selector nesting

Run a quick lint check before submitting:

```bash
python -m py_compile build_site.py playlist_generator.py stats.py
```

---

## Making Changes

1. **Find or create an issue** — let others know what you're working on
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/my-descriptive-branch-name
   ```
3. **Make focused commits** (see [Commit Messages](#commit-messages))
4. **Keep `config.ini` clean** — don't commit your personal paths
5. **Test with real XML exports** if possible, or use the `--help` flag to verify CLI changes

Branch naming convention:

| Prefix | Purpose |
|---|---|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `docs/` | Documentation changes |
| `refactor/` | Code restructuring |
| `style/` | CSS or formatting-only changes |
| `chore/` | Build/config/tooling changes |

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

[optional body with details]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

Examples:

```
feat: add Deezer ID extraction from M4A covr atom
fix: correct CSS class mismatch in card footer
docs: update API rate-limit section in README
refactor: unify slugify() across modules
```

Keep the subject line under 72 characters. Use the imperative mood.

---

## Pull Requests

1. **Rebase onto `main`** before opening:
   ```bash
   git fetch origin
   git rebase origin/main
   ```
2. **Open a PR** with a clear title and description referencing the issue number
3. **Describe what changed** and include before/after screenshots for visual changes
4. **Keep PRs small** — one logical change per PR
5. **Expect questions** — maintainers may ask for clarifications or changes

---

## Reporting Issues

Open a [GitHub Issue](https://github.com/yourusername/itunes-playlist-website/issues) with:

- **A clear title** summarising the problem
- **Steps to reproduce** (including sample XML if relevant)
- **Expected vs actual behaviour**
- **Environment** (Python version, OS, config settings)
- **Full error output** (if applicable)

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
