import os
import sys
import json
import shutil
import glob
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_code_common"))
from common import (MOVIE_DRIVES, MOVIE_METADATA_DIR, MOVIE_HTML_DIR, MOVIE_FSK_PATH, MOVIE_PARENTAL_GUIDES_DIR,
                    load_json, normalize_languages, write_js_constants)
from fetch_fsk import update_fsk_cache

# --- Config ---
# Laufwerke stehen in python_code_common/common.py
OUTPUT_DIR = str(MOVIE_METADATA_DIR)
DATA_JS_PATH = str(MOVIE_HTML_DIR / "data.js")
PARENTAL_GUIDES_JS_PATH = str(MOVIE_HTML_DIR / "parental_guides.js")


# ── JSON helpers ──────────────────────────────────────────────────────────────

def find_metadata_json(movie_folder: str) -> str | None:
    matches = glob.glob(os.path.join(movie_folder, "*_metadata_tt*.json"))
    return matches[0] if matches else None


def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Metadata → data.js entry ──────────────────────────────────────────────────

def parse_duration_min(duration_str: str) -> int:
    """'110 min' → 110"""
    match = re.search(r"(\d+)", duration_str or "")
    return int(match.group(1)) if match else 0


def metadata_to_entry(meta: dict, fsk: str, has_parental_guide: bool) -> dict:
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
        "imdb_rating_val": float(meta.get("imdb_rating")) if meta.get("imdb_rating") not in (None, "", "N/A") else 0.0,
        "us_rating": meta.get("rated", "N/A"),  # US-Freigabe laut OMDb (R, PG-13, …)
        "fsk": fsk,  # deutsche Freigabe laut TMDB ("12", …) oder "N/A"
        "genres_str": ", ".join(genres_list),
        "genres_list": genres_list,
        "outline": meta.get("outline", ""),
        "stars": ", ".join(stars_list),
        "imdb_id": imdb_id,
        "img_uri": f"covers/{imdb_id}.jpg",
        "num": meta.get("num", ""),
        "folder_location": meta.get("folder_location", "N/A"),
        "folder_path": meta.get("folder_path", ""),
        # Sprachfelder (Codes wie "deu" werden hier zu "German"/"Deutsch" übersetzt):
        "audio_languages_german": normalize_languages(meta.get("audio_languages_german", []), "de"),
        "audio_languages_english": normalize_languages(meta.get("audio_languages_english", []), "en"),
        "subtitles_languages_german": normalize_languages(meta.get("subtitles_languages_german", []), "de"),
        "subtitles_languages_english": normalize_languages(meta.get("subtitles_languages_english", []), "en"),
        "has_parental_guide": has_parental_guide,
    }


def parental_guide_for_web(guide: dict) -> dict:
    """Nur die Felder, die die Website anzeigt (siehe import_parental_guides.py)."""
    return {
        "rating_reason": guide.get("rating_reason", ""),
        "machine_translated": guide.get("machine_translated", False),
        "categories": guide.get("categories", []),
    }


# ── Build & write data.js ─────────────────────────────────────────────────────

def update_data_js():
    json_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_metadata_tt*.json")))

    if not json_files:
        print("\n[data.js] No metadata JSONs found — skipping.")
        return

    # FSK (fetch_fsk.py) und Elternleitfäden (import_parental_guides.py), je nach IMDb-ID
    fsk_by_id = load_json(MOVIE_FSK_PATH) if MOVIE_FSK_PATH.exists() else {}
    parental_guides = {p.stem: load_json(p) for p in MOVIE_PARENTAL_GUIDES_DIR.glob("tt*.json")}

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
        imdb_id = meta.get("imdb_id", "")
        entry = metadata_to_entry(meta, fsk_by_id.get(imdb_id, "N/A"), imdb_id in parental_guides)
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

    # Nach Titel sortieren
    movies.sort(key=lambda m: m["title"].lower())

    # Sets in sortierte Listen umwandeln
    genres_list = sorted(all_genres)
    directors_list = sorted(all_directors)
    stars_list = sorted(all_stars)
    audio_ger_list = sorted(all_audio_languages_german)
    audio_eng_list = sorted(all_audio_languages_english)
    sub_ger_list = sorted(all_subtitle_languages_german)
    sub_eng_list = sorted(all_subtitle_languages_english)

    write_js_constants(DATA_JS_PATH, {
        "allMovies": movies,
        "allGenres": genres_list,
        "allDirectors": directors_list,
        "allStars": stars_list,
        "allAudioLanguagesGerman": audio_ger_list,
        "allSubtitleLanguagesGerman": sub_ger_list,
        "allAudioLanguagesEnglish": audio_eng_list,
        "allSubtitleLanguagesEnglish": sub_eng_list,
    })

    # Elternleitfäden in eigener Datei – app.js lädt sie erst beim Öffnen eines Films nach
    movie_ids = {m["imdb_id"] for m in movies}
    web_guides = {imdb_id: parental_guide_for_web(guide)
                  for imdb_id, guide in sorted(parental_guides.items()) if imdb_id in movie_ids}
    write_js_constants(PARENTAL_GUIDES_JS_PATH, {"parentalGuides": web_guides})

    with_fsk = sum(1 for m in movies if m["fsk"] != "N/A")

    print(f"\n[data.js] Updated → {len(movies)} movies.")
    print(f"  - {len(genres_list)} genres, {len(directors_list)} directors, {len(stars_list)} stars")
    print(f"  - {len(audio_ger_list)} Audio (GER), {len(sub_ger_list)} Subs (GER)")
    print(f"  - {len(audio_eng_list)} Audio (ENG), {len(sub_eng_list)} Subs (ENG)")
    print(f"  - {with_fsk} mit FSK, {len(web_guides)} mit Elternleitfaden (parental_guides.js)")


# ── Sync metadata JSONs ───────────────────────────────────────────────────────

def sync_metadata():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    movie_folders = []

    # Iteriere über alle in MOVIE_DRIVES eingetragenen Laufwerke
    for drive_path in MOVIE_DRIVES.keys():
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

    # FSK für neue Filme bei TMDB nachschlagen (bekannte werden übersprungen)
    update_fsk_cache()

    # Always rebuild data.js after sync
    update_data_js()


if __name__ == "__main__":
    sync_metadata()