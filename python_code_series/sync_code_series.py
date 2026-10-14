import os
import sys
import shutil
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_code_common"))
from common import SERIES_DRIVES, SERIES_METADATA_DIR, SERIES_HTML_DIR, load_json, normalize_languages, write_js_constants

# --- Config ---
# Laufwerke stehen in python_code_common/common.py
OUTPUT_DIR = str(SERIES_METADATA_DIR)
DATA_JS_PATH = str(SERIES_HTML_DIR / "data.js")


def update_data_js():
    json_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_metadata_tmdb*.json")))
    series_list = []

    all_genres, all_creators, all_stars = set(), set(), set()
    all_audio, all_subs = set(), set()

    for path in json_files:
        meta = load_json(path)

        genres_list = meta.get("genres", [])
        stars_list = meta.get("stars", [])
        tmdb_id = meta.get("tmdb_id", "")
        seasons = int(meta.get("seasons_count", 1))

        entry = {
            "title": meta.get("title", ""),
            "creator": meta.get("creator", ""),
            "network": meta.get("network", ""),
            "year": int(meta.get("year", 0)),

            # 🔥 Serien-spezifische Felder gemappt für die Movie-app.js
            "seasons_count": seasons,
            "duration_str": f"{seasons} Season{'s' if seasons > 1 else ''}",
            "duration_min": seasons,  # Erlaubt dir, den Dauer-Slider in der UI für Staffeln zu nutzen!
            "imdb_rating_str": str(meta.get("tmdb_rating", "N/A")),
            "imdb_rating_val": float(meta.get("tmdb_rating", 0) or 0),
            "fsk_rating": meta.get("rated", "N/A"),

            "genres_str": ", ".join(genres_list),
            "genres_list": genres_list,
            "outline": meta.get("outline", ""),
            "stars": ", ".join(stars_list),
            "tmdb_id": tmdb_id,
            "img_uri": f"covers/{tmdb_id}.jpg",
            "folder_location": meta.get("folder_location", "N/A"),
            "folder_path": meta.get("folder_path", ""),

            # Codes wie "deu" werden hier zu "German" übersetzt
            "audio_languages_english": normalize_languages(meta.get("audio_languages_english", []), "en"),
            "subtitles_languages_english": normalize_languages(meta.get("subtitles_languages_english", []), "en"),

            # 🔥 HIER DIE EPISODEN EINGEFÜGT 🔥
            "local_episodes": meta.get("local_episodes", {}),
        }
        series_list.append(entry)

        all_genres.update(genres_list)
        if entry["creator"] and entry["creator"] != "N/A":
            for c in entry["creator"].split(", "): all_creators.add(c)
        for star in stars_list: all_stars.add(star)
        all_audio.update(entry["audio_languages_english"])
        all_subs.update(entry["subtitles_languages_english"])

    series_list.sort(key=lambda m: m["title"].lower())

    write_js_constants(DATA_JS_PATH, {
        "allMovies": series_list,  # Wir nennen es allMovies, damit app.js nicht angepasst werden muss!
        "allGenres": sorted(all_genres),
        "allDirectors": sorted(all_creators),
        "allStars": sorted(all_stars),
        "allAudioLanguagesEnglish": sorted(all_audio),
        "allSubtitleLanguagesEnglish": sorted(all_subs),
    })

    print(f"\n[data.js] Updated → {len(series_list)} TV Shows.")


def sync_metadata():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    copied = 0
    updated = 0

    for drive_path in SERIES_DRIVES.keys():
        if not os.path.exists(drive_path): continue
        for d in os.listdir(drive_path):
            folder_path = os.path.join(drive_path, d)
            if os.path.isdir(folder_path):
                matches = glob.glob(os.path.join(folder_path, "*_metadata_tmdb*.json"))
                if matches:
                    source_json = matches[0]
                    dest_json = os.path.join(OUTPUT_DIR, os.path.basename(source_json))

                    # 🔥 Nur kopieren, wenn die Datei nicht existiert oder auf der Festplatte NEUER ist
                    if not os.path.exists(dest_json):
                        shutil.copy2(source_json, dest_json)
                        print(f"[COPIED]  {os.path.basename(source_json)}")
                        copied += 1
                    elif os.path.getmtime(source_json) > os.path.getmtime(dest_json):
                        shutil.copy2(source_json, dest_json)
                        print(f"[UPDATED] {os.path.basename(source_json)}")
                        updated += 1

    print(f"\n--- Sync done ---")
    print(f"  Copied:  {copied}")
    print(f"  Updated: {updated}")

    update_data_js()


if __name__ == "__main__":
    sync_metadata()