"""
stats.py — Statistics generator for cover playlists.

Reads all iTunes XML files and computes:
  - Total tracks, playlists, unique artists
  - Total duration (hours)
  - Top original artists by frequency
  - Songs by decade
  - Most prolific cover artists

Outputs JSON for use by stats.html.
"""

import os
import re
import sys
import json
import argparse
import plistlib
from pathlib import Path
from collections import defaultdict, Counter
from urllib.request import url2pathname
from urllib.parse import unquote


def parse_itunes_xml(xml_path: str):
    """
    Parse iTunes XML file and return list of track dicts.
    Each track has: title, orig_artist, artist, album, year, total_time_ms.
    """
    try:
        with open(xml_path, "rb") as f:
            plist = plistlib.load(f)
    except Exception as e:
        print(f"Error reading {xml_path}: {e}", file=sys.stderr)
        return []

    tracks_dict = plist.get("Tracks", {})
    playlists = plist.get("Playlists", [])

    if not playlists:
        return []

    # Get first non-master playlist
    selected = next(
        (p for p in playlists if not p.get("Master") and p.get("Playlist Items")),
        None,
    )
    if not selected:
        return []

    items = selected.get("Playlist Items", [])
    tracks = []

    for item in items:
        tid = str(item.get("Track ID", ""))
        info = tracks_dict.get(tid, {})

        title = info.get("Name", "")
        artist = info.get("Artist", "")
        album = info.get("Album", "")
        year = info.get("Year", "")
        total_time_ms = info.get("Total Time", 0)

        # Covers mode: title format is always "Song Title (orig. Original Artist Name)"
        orig_artist = ""
        m = re.match(r"^(.+?)\s*\(orig\.\s*(.+?)\)$", title)
        if m:
            title = m.group(1).strip()
            orig_artist = m.group(2).strip()

        tracks.append({
            "title": title,
            "orig_artist": orig_artist,
            "artist": artist,
            "album": album,
            "year": str(year) if year else "",
            "total_time_ms": int(total_time_ms) if total_time_ms else 0,
        })

    return tracks


def clean_artist_name(artist: str) -> str:
    """
    Remove descriptive labels from artist names (e.g., 'Elvis - live' -> 'Elvis').
    Filters out: live, live version, live at, acoustic, remix, version, etc.
    """
    if not artist:
        return artist
    
    # List of patterns to remove (case-insensitive)
    labels_to_remove = [
        r'\s*-?\s*(live|live version|live at|acoustic|remix|version|cover|remaster|remastered)\s*$',
        r'\s*\(live\)\s*$',
        r'\s*\[live\]\s*$',
    ]
    
    cleaned = artist
    for pattern in labels_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()


def compute_statistics(xml_input_dir: str):
    """
    Scan all XML files in directory, compute statistics, return dict.
    """
    xml_files = list(Path(xml_input_dir).glob("*.xml"))
    if not xml_files:
        print(f"No XML files found in {xml_input_dir}", file=sys.stderr)
        return {}

    all_tracks = []
    playlist_count = 0

    for xml_file in xml_files:
        tracks = parse_itunes_xml(str(xml_file))
        all_tracks.extend(tracks)
        if tracks:
            playlist_count += 1

    if not all_tracks:
        print("No tracks found in any playlist", file=sys.stderr)
        return {}

    # === Compute statistics ===

    total_tracks = len(all_tracks)
    
    # Clean artist names and filter out empty strings
    # Unique artists (cleaned of descriptive labels)
    orig_artists = set(
        clean_artist_name(t.get("orig_artist", "")) 
        for t in all_tracks 
        if clean_artist_name(t.get("orig_artist", "")).strip()
    )
    cover_artists = set(t.get("artist", "") for t in all_tracks if t.get("artist", "").strip())
    
    total_orig_artists = len(orig_artists)
    total_cover_artists = len(cover_artists)

    # Total duration in hours
    total_ms = sum(t.get("total_time_ms", 0) for t in all_tracks)
    total_hours = total_ms / (1000 * 3600)

    # Top original artists by frequency (cleaned of descriptive labels)
    orig_artist_counts = Counter()
    for t in all_tracks:
        cleaned = clean_artist_name(t.get("orig_artist", ""))
        if cleaned.strip():
            orig_artist_counts[cleaned] += 1
    
    top_orig_artists = orig_artist_counts.most_common(10)

    # Songs by decade
    songs_by_decade = defaultdict(int)
    for t in all_tracks:
        if t.get("year", "").strip():
            try:
                year = int(t["year"])
                decade = (year // 10) * 10
                songs_by_decade[decade] += 1
            except (ValueError, TypeError):
                pass
    
    decades_sorted = sorted(songs_by_decade.items())

    # Most prolific cover artists
    cover_artist_counts = Counter()
    for t in all_tracks:
        if t.get("artist", "").strip():
            cover_artist_counts[t["artist"]] += 1
    
    top_cover_artists = cover_artist_counts.most_common(10)

    return {
        "total_tracks": total_tracks,
        "total_playlists": playlist_count,
        "total_orig_artists": total_orig_artists,
        "total_cover_artists": total_cover_artists,
        "total_hours": round(total_hours, 1),
        "top_orig_artists": [{"artist": a, "count": c} for a, c in top_orig_artists],
        "songs_by_decade": [{"decade": d, "count": c} for d, c in decades_sorted],
        "top_cover_artists": [{"artist": a, "count": c} for a, c in top_cover_artists],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate statistics JSON from iTunes XML files")
    parser.add_argument("--xml-dir", required=True, help="Path to input XML directory")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()

    stats = compute_statistics(args.xml_dir)
    
    if not stats:
        print("Failed to compute statistics", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    if args.verbose:
        print(json.dumps(stats, indent=2))

    print(f"Statistics written to {args.output}")


if __name__ == "__main__":
    main()
