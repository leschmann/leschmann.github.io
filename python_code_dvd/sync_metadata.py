import os
import json
import shutil
import glob
import re

# --- Config ---
# Hier die gleiche Config wie im Metadaten-Skript nutzen:
DRIVE_CONFIG = {
    r"F:\Movies": "FFM DVD 00001 - 00600",
    r"E:\Movies": "FFM DVD 00601 - 01091",
}

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "metadata_jsons_dvd")
DATA_JS_PATH = os.path.join(PROJECT_ROOT, "html_dvd_collection/data.js")


# ── JSON helpers ──────────────────────────────────────────────────────────────

def find_metadata_json(movie_folder: str) -> str | None:
    matches = glob.glob(os.path.join(movie_folder, "*_metadata_tt*.json"))
    return matches[0] if matches else None


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Metadata → data.js entry ──────────────────────────────────────────────────

def parse_duration_min(duration_str: str) -> int:
    """'110 min' → 110"""
    match = re.search(r"(\d+)", duration_str or "")
    return int(match.group(1)) if match else 0


def metadata_to_entry(meta: dict) -> dict:
    genres_list = meta.get("genres", [])
    stars_list = meta.get("stars", [])
    imdb_id = meta.get("imdb_id", "")
    duration_str = meta.get("duration", "N/A")

    return {
        "title": meta.get("title", ""),
        "director": meta.get("director", ""),
        "year": int(meta.get("year", 0)),
        "duration_str": duration_str,
        "duration_min": parse_duration_min(duration_str),
        "imdb_rating_str": meta.get("imdb_rating", "N/A"),
        "imdb_rating_val": float(meta.get("imdb_rating", 0) or 0),
        "fsk_rating": meta.get("rated", "N/A"),
        "genres_str": ", ".join(genres_list),
        "genres_list": genres_list,
        "outline": meta.get("outline", ""),
        "stars": ", ".join(stars_list),
        "imdb_id": imdb_id,
        "img_uri": f"covers/{imdb_id}.jpg",
        "num": meta.get("num", ""),
        "folder_location": meta.get("folder_location", "N/A"),
        "folder_path": meta.get("folder_path", ""),
        # Neue Sprachfelder:
        "audio_languages_german": meta.get("audio_languages_german", []),
        "audio_languages_english": meta.get("audio_languages_english", []),
        "subtitles_languages_german": meta.get("subtitles_languages_german", []),
        "subtitles_languages_english": meta.get("subtitles_languages_english", []),
    }


# ── Build & write data.js ─────────────────────────────────────────────────────

def update_data_js():
    json_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_metadata_tt*.json")))

    if not json_files:
        print("\n[data.js] No metadata JSONs found — skipping.")
        return

    movies = []

    # Sets initialisieren
    all_genres = set()
    all_directors = set()
    all_stars = set()
    all_audio_languages_german = set()
    all_subtitle_languages_german = set()
    all_audio_languages_english = set()
    all_subtitle_languages_english = set()

    for path in json_files:
        meta = load_json(path)
        entry = metadata_to_entry(meta)
        movies.append(entry)

        # Basis-Sets füllen
        all_genres.update(entry["genres_list"])
        if entry["director"]:
            all_directors.add(entry["director"])
        for star in entry["stars"].split(", "):
            if star:
                all_stars.add(star)

        # Neue Sprach-Sets füllen
        all_audio_languages_german.update(entry["audio_languages_german"])
        all_audio_languages_english.update(entry["audio_languages_english"])
        all_subtitle_languages_german.update(entry["subtitles_languages_german"])
        all_subtitle_languages_english.update(entry["subtitles_languages_english"])

    # Sort movies by their folder number (from num field) — fall back to title
    movies.sort(key=lambda m: m["title"].lower())

    # Sets in sortierte Listen umwandeln
    genres_list = sorted(all_genres)
    directors_list = sorted(all_directors)
    stars_list = sorted(all_stars)
    audio_ger_list = sorted(all_audio_languages_german)
    audio_eng_list = sorted(all_audio_languages_english)
    sub_ger_list = sorted(all_subtitle_languages_german)
    sub_eng_list = sorted(all_subtitle_languages_english)

    with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
        # allMovies
        f.write("const allMovies = ")
        json.dump(movies, f, ensure_ascii=False)
        f.write(";\n\n")

        # allGenres
        f.write("const allGenres = ")
        json.dump(genres_list, f, ensure_ascii=False)
        f.write(";\n\n")

        # allDirectors
        f.write("const allDirectors = ")
        json.dump(directors_list, f, ensure_ascii=False)
        f.write(";\n\n")

        # allStars
        f.write("const allStars = ")
        json.dump(stars_list, f, ensure_ascii=False)
        f.write(";\n\n")

        # allAudioLanguagesGerman
        f.write("const allAudioLanguagesGerman = ")
        json.dump(audio_ger_list, f, ensure_ascii=False)
        f.write(";\n\n")

        # allSubtitleLanguagesGerman
        f.write("const allSubtitleLanguagesGerman = ")
        json.dump(sub_ger_list, f, ensure_ascii=False)
        f.write(";\n\n")

        # allAudioLanguagesEnglish
        f.write("const allAudioLanguagesEnglish = ")
        json.dump(audio_eng_list, f, ensure_ascii=False)
        f.write(";\n\n")

        # allSubtitleLanguagesEnglish
        f.write("const allSubtitleLanguagesEnglish = ")
        json.dump(sub_eng_list, f, ensure_ascii=False)
        f.write(";\n")

    print(f"\n[data.js] Updated → {len(movies)} movies.")
    print(f"  - {len(genres_list)} genres, {len(directors_list)} directors, {len(stars_list)} stars")
    print(f"  - {len(audio_ger_list)} Audio (GER), {len(sub_ger_list)} Subs (GER)")
    print(f"  - {len(audio_eng_list)} Audio (ENG), {len(sub_eng_list)} Subs (ENG)")


# ── Sync metadata JSONs ───────────────────────────────────────────────────────

def sync_metadata():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    movie_folders = []

    # Iteriere über alle in DRIVE_CONFIG eingetragenen Laufwerke
    for drive_path in DRIVE_CONFIG.keys():
        if not os.path.exists(drive_path):
            print(f"⚠ Laufwerk nicht gefunden, überspringe: {drive_path}")
            continue

        for d in os.listdir(drive_path):
            folder_path = os.path.join(drive_path, d)
            if os.path.isdir(folder_path):
                movie_folders.append(folder_path)

    print(f"\nFound {len(movie_folders)} movie folders across all drives.\n")

    copied = 0
    updated = 0
    skipped = 0
    missing_folders = []

    for folder in sorted(movie_folders):
        folder_name = os.path.basename(folder)
        source_json = find_metadata_json(folder)

        if not source_json:
            print(f"[MISSING]  No metadata JSON found in: {folder_name}")
            missing_folders.append(folder_name)
            continue

        json_filename = os.path.basename(source_json)
        dest_json = os.path.join(OUTPUT_DIR, json_filename)

        if not os.path.exists(dest_json):
            shutil.copy2(source_json, dest_json)
            print(f"[COPIED]   {json_filename}")
            copied += 1
        else:
            source_mtime = os.path.getmtime(source_json)
            dest_mtime = os.path.getmtime(dest_json)

            if source_mtime > dest_mtime:
                source_data = load_json(source_json)
                dest_data = load_json(dest_json)

                if source_data != dest_data:
                    save_json(dest_json, source_data)
                    print(f"[UPDATED]  {json_filename}")
                    updated += 1
                else:
                    print(f"[SKIPPED]  {json_filename} (same content)")
                    skipped += 1
            else:
                print(f"[SKIPPED]  {json_filename} (destination is up to date)")
                skipped += 1

    print(f"\n--- Sync done ---")
    print(f"  Copied:  {copied}")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Missing: {len(missing_folders)}")

    if missing_folders:
        print("\n--- Folders with no metadata JSON ---")
        for name in missing_folders:
            print(f"  {name}")

    # Always rebuild data.js after sync
    update_data_js()


if __name__ == "__main__":
    sync_metadata()