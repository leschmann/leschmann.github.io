import os
import re
import json
import shutil
import time
import requests
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────
MOVIE_ROOTS = [
    r"F:\Movies",
]

HARDDRIVE_NAME = "FRA DVD 0001 - 00600"

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

OMDB_API_KEYS = ["dea6b6b3", "1f927d1"]

# matches: 00003 Emil of Lonneberga (1971) {imdb-tt0067047}
FOLDER_RE = re.compile(
    r"^(?P<num>\d+)\s+(?P<title>.+?)\s+\((?P<year>\d{4})\)\s+\{imdb-(?P<imdb_id>tt\d+)\}$"
)
# ───────────────────────────────────────────────────────────────────────────────

# ── Full schema we expect every JSON to have ──────────────────────────────
EXPECTED_FIELDS = {
    "num", "folder_name", "folder_path", "title", "original_title",
    "year", "duration", "director", "genres", "outline", "imdb_id",
    "imdb_link", "imdb_rating", "stars", "rated", "country", "language",
    "poster_url", "cover_file", "folder_location",
}

LOCAL_FIELDS = {"num", "folder_name", "folder_path", "folder_location"}

def missing_fields(metadata: dict) -> set[str]:
    return EXPECTED_FIELDS - set(metadata.keys())

# ── API ────────────────────────────────────────────────────────────────────────

def omdb_fetch(imdb_id: str) -> dict | None:
    """Try each API key in order until one works."""
    for key in OMDB_API_KEYS:
        url = f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={key}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if data.get("Response") == "True":
                return data
            else:
                print(f"    OMDB key '{key}' returned: {data.get('Error')}")
        except Exception as e:
            print(f"    Request error with key '{key}': {e}")
    return None


def download_image(url: str, dest: Path) -> bool:
    """Download a poster image. Returns True on success."""
    if not url or url == "N/A":
        return False
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
            dest.write_bytes(r.content)
            return True
    except Exception as e:
        print(f"    Image download error: {e}")
    return False


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_folder(name: str) -> dict | None:
    m = FOLDER_RE.match(name)
    return m.groupdict() if m else None


def safe_list(raw: str) -> list[str]:
    """'Actor A, Actor B, N/A' → ['Actor A', 'Actor B']"""
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip() and s.strip() != "N/A"]


def meta_filename(title: str, imdb_id: str) -> str:
    """Matches your existing naming: Das Sams_metadata_tt0265691.json"""
    return f"{title}_metadata_{imdb_id}.json"




# ── Core processing ────────────────────────────────────────────────────────────

def process_root(root: str) -> list[dict]:
    """Scan one movie root folder and return a list of metadata dicts."""
    root_path = Path(root)
    covers_dir = Path(PROJECT_ROOT) / "covers"
    if not root_path.exists():
        print(f"\n⚠  Drive not found, skipping: {root}")
        return []

    print(f"\n📂  Scanning {root} …")

    movies: list[dict] = []
    added        = 0
    cached       = 0
    skipped      = 0
    missing_parse = []

    for folder_path in sorted(root_path.iterdir()):
        if not folder_path.is_dir():
            continue

        parsed = parse_folder(folder_path.name)
        if not parsed:
            print(f"  ✗  Cannot parse: {folder_path.name}")
            missing_parse.append(folder_path.name)
            continue

        title   = parsed["title"]
        year    = parsed["year"]
        imdb_id = parsed["imdb_id"]
        num     = parsed["num"]

        print(f"  🎬  [{num}] {title} ({year})  —  {imdb_id}")

        meta_file  = folder_path / meta_filename(title, imdb_id)
        cover_file = folder_path / f"{title}_cover.jpg"

        # ── Already cached → check if update needed ────────────────────────
        if meta_file.exists():
            with meta_file.open(encoding="utf-8-sig") as f:
                metadata = json.load(f)

            # ── Ensure cover is in covers/ ────────────────────────────────
            cover_filename = metadata.get("cover_file")
            if cover_filename:
                src_cover = folder_path / cover_filename
                dest_cover = covers_dir / f"{imdb_id}.jpg"
                if src_cover.exists() and not dest_cover.exists():
                    shutil.copy2(src_cover, dest_cover)
                    print(f"        ✓  Cover copied → covers/{imdb_id}.jpg")

            # Always overwrite local fields first
            metadata["num"]             = num
            metadata["folder_name"]     = folder_path.name
            metadata["folder_path"]     = str(folder_path)
            metadata["folder_location"] = HARDDRIVE_NAME

            missing = missing_fields(metadata)
            needs_api = missing - LOCAL_FIELDS

            if not missing:
                with meta_file.open("w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=4, ensure_ascii=False)
                print(f"        ↩  Cache up to date, local fields refreshed …")
                movies.append(metadata)
                cached += 1
                continue

            print(f"        ⚠  Cache missing fields: {missing}")

            if not needs_api:
                with meta_file.open("w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=4, ensure_ascii=False)
                print(f"        ✓  Patched local fields → {meta_file.name}")
                movies.append(metadata)
                cached += 1
                continue

            # Missing OMDB fields → re-fetch
            print(f"        🔄  Re-fetching OMDB data for missing: {needs_api}")
            data = omdb_fetch(imdb_id)
            time.sleep(0.25)

            if not data:
                print(f"        ✗  Could not re-fetch — using existing cache")
                movies.append(metadata)
                cached += 1
                continue

            field_map = {
                "title":          data.get("Title",       metadata.get("title")),
                "original_title": data.get("Title",       metadata.get("original_title")),
                "duration":       data.get("Runtime",     "N/A"),
                "director":       data.get("Director",    "N/A"),
                "genres":         safe_list(data.get("Genre",   "")),
                "outline":        data.get("Plot",        "N/A"),
                "imdb_link":      f"https://www.imdb.com/title/{imdb_id}/",
                "imdb_rating":    data.get("imdbRating",  "N/A"),
                "stars":          safe_list(data.get("Actors",  "")),
                "rated":          data.get("Rated",       "N/A"),
                "country":        data.get("Country",     "N/A"),
                "language":       data.get("Language",    "N/A"),
                "poster_url":     data.get("Poster",      ""),
            }

            for field in needs_api:
                if field in field_map:
                    metadata[field] = field_map[field]

            with meta_file.open("w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)
            print(f"        ✓  Patched {len(missing)} fields → {meta_file.name}")
            movies.append(metadata)
            cached += 1
            continue

        # ── New movie → fetch from OMDB ────────────────────────────────────
        data = omdb_fetch(imdb_id)
        time.sleep(0.25)

        if not data:
            print(f"        ✗  Could not fetch OMDB data — skipping")
            skipped += 1
            continue

        # ── Download cover ─────────────────────────────────────────────────
        poster_url     = data.get("Poster", "")
        cover_filename = None

        if cover_file.exists():
            print(f"        ✓  Cover already present")
            cover_filename = cover_file.name
        else:
            if download_image(poster_url, cover_file):
                print(f"        ✓  Cover saved → {cover_file.name}")
                cover_filename = cover_file.name
            else:
                print(f"        ✗  No cover available")

        if cover_file.exists():
            dest_cover = covers_dir / f"{imdb_id}.jpg"
            if not dest_cover.exists():
                shutil.copy2(cover_file, dest_cover)
                print(f"        ✓  Cover copied → covers/{imdb_id}.jpg")

        # ── Build metadata ─────────────────────────────────────────────────
        metadata = {
            "num":             num,
            "folder_name":     folder_path.name,
            "folder_path":     str(folder_path),
            "title":           data.get("Title", title),
            "original_title":  data.get("Title", title),
            "year":            year,
            "duration":        data.get("Runtime",    "N/A"),
            "director":        data.get("Director",   "N/A"),
            "genres":          safe_list(data.get("Genre",   "")),
            "outline":         data.get("Plot",       "N/A"),
            "imdb_id":         imdb_id,
            "imdb_link":       f"https://www.imdb.com/title/{imdb_id}/",
            "imdb_rating":     data.get("imdbRating", "N/A"),
            "stars":           safe_list(data.get("Actors",  "")),
            "rated":           data.get("Rated",      "N/A"),
            "country":         data.get("Country",    "N/A"),
            "language":        data.get("Language",   "N/A"),
            "poster_url":      poster_url,
            "cover_file":      cover_filename,
            "folder_location": HARDDRIVE_NAME,
        }

        # ── Save metadata JSON ─────────────────────────────────────────────
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        print(f"        ✓  Metadata saved → {meta_file.name}")

        movies.append(metadata)
        added += 1

    # ── Per-root summary ───────────────────────────────────────────────────
    print(f"\n  --- {root} summary ---")
    print(f"    Added:   {added}")
    print(f"    Cached:  {cached}")
    print(f"    Skipped: {skipped}")
    if missing_parse:
        print(f"    Could not parse ({len(missing_parse)}):")
        for name in missing_parse:
            print(f"      {name}")

    return movies


def scan_all_configured() -> list[dict]:
    """Process every root defined in MOVIE_ROOTS."""
    all_movies: list[dict] = []
    for root in MOVIE_ROOTS:
        all_movies.extend(process_root(root))
    return all_movies


def scan_single_drive() -> list[dict]:
    """Prompt for a drive letter and scan that drive only."""
    raw = input("Enter the drive letter (e.g. F): ").strip().upper()
    drive_letter = raw.replace(":", "").replace("\\", "").replace("/", "")
    root = f"{drive_letter}:\\Movies"
    return process_root(root)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Movie Metadata Scanner ===")
    print("1) Scan all configured drives  (MOVIE_ROOTS in script)")
    print("2) Scan a single drive         (enter drive letter)")
    choice = input("\nChoice [1/2]: ").strip()

    if choice == "2":
        movies = scan_single_drive()
    else:
        movies = scan_all_configured()

    print(f"\n✅  Done — {len(movies)} movies processed total.")

    # Write combined index (optional, used by other tools)
    index_path = Path(PROJECT_ROOT) / "movies_index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(movies, f, indent=4, ensure_ascii=False)
    print(f"📄  Combined index written → {index_path}")