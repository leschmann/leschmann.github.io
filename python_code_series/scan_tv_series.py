import re
import sys
import json
import shutil
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_code_common"))
from common import PROJECT_ROOT, SERIES_DRIVES, TMDB_API_KEY, extract_mkv_languages

# ─── CONFIG ────────────────────────────────────────────────────────────────────
# Laufwerke, TMDB API Key und Sprachtabellen stehen in python_code_common/common.py

FORCE_MKV_RESCAN = ["790", "1399", "1418"]

# Matches: Agatha Christie's Poirot (1989) {tmdb-790}
FOLDER_RE = re.compile(
    r"^(?P<title>.+?)\s+\((?P<year>\d{4})\)\s+\{tmdb-(?P<tmdb_id>\d+)\}$"
)

# ─── SCHEMA ────────────────────────────────────────────────────────────────────
NEW_MEDIA_FIELDS = {
    "audio_languages_german", "audio_languages_english",
    "subtitles_languages_german", "subtitles_languages_english"
}
EXPECTED_FIELDS = {
    "folder_name", "folder_path", "title", "original_title", "year",
    "seasons_count", "creator", "genres", "outline", "tmdb_id",
    "tmdb_link", "tmdb_rating", "stars", "network", "poster_url",
    "cover_file", "folder_location", "local_episodes"
}.union(NEW_MEDIA_FIELDS)

LOCAL_FIELDS = {"folder_name", "folder_path", "folder_location"}


def missing_fields(metadata: dict) -> set[str]:
    return EXPECTED_FIELDS - set(metadata.keys())


# ─── MKV ANALYSIS HELPERS ──────────────────────────────────────────────────────
# Dieser Regex sucht nach "S01E01 - Titel" oder auch "S01E01-E02 - Titel"
EPISODE_RE = re.compile(r"S\d{1,3}(E[\d\-E]+)\s*-\s*(.+)$", re.IGNORECASE)


def scan_local_episodes(series_path: Path) -> dict:
    """
    Sucht rekursiv nach MKV-Dateien und parst den Dateinamen.
    Gibt z.B. zurück: {"Season 01": {"E01": "Köchin gesucht", "E02": "Poirot riecht den Braten"}}
    """
    episodes_dict = {}

    for mkv_path in series_path.rglob("*.mkv"):
        season_folder = mkv_path.parent.name

        if season_folder == series_path.name:
            season_folder = "Main Directory"

        if season_folder not in episodes_dict:
            episodes_dict[season_folder] = {}

        stem = mkv_path.stem  # Dateiname ohne .mkv
        match = EPISODE_RE.search(stem)

        if match:
            # Beispiel: match.group(1) = "E01", match.group(2) = "Köchin gesucht"
            ep_num = match.group(1).upper()
            ep_title = match.group(2).strip()

            # Entfernt " - part1", " - Part 2", "-part3" am Ende des Titels (nur einstellige Zahlen)
            ep_title = re.sub(r'\s*-?\s*part\s*\d$', '', ep_title, flags=re.IGNORECASE).strip()

            episodes_dict[season_folder][ep_num] = ep_title
        else:
            # Fallback: Falls mal eine Datei nicht dem Namensschema entspricht
            episodes_dict[season_folder][stem] = ""

    # Die Staffeln und Episoden alphabetisch sortieren
    sorted_dict = {}
    for season in sorted(episodes_dict.keys()):
        # Sortiert das innere Dictionary nach den Episodennummern ("E01", "E02", etc.)
        sorted_dict[season] = dict(sorted(episodes_dict[season].items()))

    return sorted_dict


def get_sample_mkv(series_path: Path) -> Path | None:
    """Sucht rekursiv nach der ersten MKV-Datei in den Staffel-Ordnern."""
    for mkv_file in series_path.rglob("*.mkv"):
        return mkv_file
    return None


# ─── TMDB API ──────────────────────────────────────────────────────────────────
def tmdb_fetch(tmdb_id: str) -> dict | None:
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits&language=en-US"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"    TMDB Error: {e}")
    return None


def download_image(url: str, dest: Path) -> bool:
    if not url: return False
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            dest.write_bytes(r.content)
            return True
    except:
        pass
    return False


# ─── CORE PROCESSING ───────────────────────────────────────────────────────────
def process_root(root: str, drive_name: str) -> list[dict]:
    root_path = Path(root)
    covers_dir = Path(PROJECT_ROOT) / "html_series_collection/covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    if not root_path.exists(): return []

    print(f"\n📂  Scanning {root} (Location: {drive_name}) …")
    series_list = []

    for folder_path in sorted(root_path.iterdir()):
        if not folder_path.is_dir(): continue

        m = FOLDER_RE.match(folder_path.name)
        if not m: continue

        parsed = m.groupdict()
        title, year, tmdb_id = parsed["title"], parsed["year"], parsed["tmdb_id"]

        print(f"  📺  {title} ({year})  —  TMDB: {tmdb_id}")

        meta_file = folder_path / f"{title}_metadata_tmdb{tmdb_id}.json"
        cover_file = folder_path / f"{title}_cover.jpg"
        metadata = {}
        is_new = not meta_file.exists()

        if is_new:
            data = tmdb_fetch(tmdb_id)
            time.sleep(0.2)
            if not data:
                print("        ✗ TMDB fetch failed.")
                continue

            # Parse TMDB Data
            genres = [g["name"] for g in data.get("genres", [])]
            creators = [c["name"] for c in data.get("created_by", [])]
            networks = [n["name"] for n in data.get("networks", [])]
            cast = [c["name"] for c in data.get("credits", {}).get("cast", [])[:6]]
            poster_path = data.get("poster_path")
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""

            if not cover_file.exists() and download_image(poster_url, cover_file):
                print(f"        ✓  Cover saved")

            if cover_file.exists():
                dest_cover = covers_dir / f"{tmdb_id}.jpg"
                if not dest_cover.exists(): shutil.copy2(cover_file, dest_cover)

            metadata = {
                "folder_name": folder_path.name,
                "folder_path": str(folder_path),
                "title": data.get("name", title),
                "original_title": data.get("original_name", title),
                "year": year,
                "seasons_count": data.get("number_of_seasons", 1),
                "creator": ", ".join(creators) if creators else "N/A",
                "network": ", ".join(networks) if networks else "N/A",
                "genres": genres,
                "outline": data.get("overview", "N/A"),
                "tmdb_id": tmdb_id,
                "tmdb_link": f"https://www.themoviedb.org/tv/{tmdb_id}",
                "tmdb_rating": round(data.get("vote_average", 0), 1),
                "stars": cast,
                "poster_url": poster_url,
                "cover_file": cover_file.name if cover_file.exists() else None,
                "folder_location": drive_name,
            }
        else:
            with meta_file.open("r", encoding="utf-8-sig") as f:
                metadata = json.load(f)
            metadata["folder_path"] = str(folder_path)
            metadata["folder_location"] = drive_name

            # MKV Scan
            needs_mkv_scan = any(f not in metadata for f in NEW_MEDIA_FIELDS) or tmdb_id in FORCE_MKV_RESCAN
            if needs_mkv_scan:
                print("        🔍 Analysiere MKV-Datei in einer der Staffeln...")
                sample_mkv = get_sample_mkv(folder_path)
                if sample_mkv:
                    # Hier nehmen wir nun alle 4 Rückgabewerte entgegen:
                    aud_de, aud_en, sub_de, sub_en = extract_mkv_languages(sample_mkv)

                    metadata["audio_languages_german"] = aud_de
                    metadata["audio_languages_english"] = aud_en
                    metadata["subtitles_languages_german"] = sub_de
                    metadata["subtitles_languages_english"] = sub_en

                    print(f"        ✓  Sprachen aus {sample_mkv.name} gelesen")
                else:
                    print("        ⚠  Keine MKV gefunden.")
                    metadata["audio_languages_german"] = []
                    metadata["audio_languages_english"] = []
                    metadata["subtitles_languages_german"] = []
                    metadata["subtitles_languages_english"] = []

        # Episoden immer frisch scannen (dauert nur Millisekunden)
        local_eps = scan_local_episodes(folder_path)
        metadata["local_episodes"] = local_eps

        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)

        series_list.append(metadata)
    return series_list


if __name__ == "__main__":
    if not TMDB_API_KEY or TMDB_API_KEY == "DEIN_TMDB_API_KEY_HIER":
        print("❌ FEHLER: Bitte trage oben im Skript deinen TMDB_API_KEY ein!")
        sys.exit(1)

    print("=== TV Shows Metadaten Scanner ===")
    all_series = []
    for root, name in SERIES_DRIVES.items():
        all_series.extend(process_root(root, name))

    print(f"\n✅ {len(all_series)} Serien gescannt.")