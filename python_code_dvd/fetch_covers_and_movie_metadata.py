import os
import re
import json
import shutil
import time
import requests
import subprocess
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────

DRIVE_CONFIG = {
    r"G:\Movies": "FFM DVD 00001 - 00600",
    r"F:\Movies": "FFM DVD 01092 - 00000",
    r"E:\Movies": "FFM DVD 00601 - 01091",
}

# Liste von Film-Nummern (5-stellig), bei denen die MKV-Analyse ERZWUNGEN werden soll,
# auch wenn die Felder schon im JSON existieren (z. B. nach manuellen Änderungen).
FORCE_MKV_RESCAN = [
    "00751",
    # "00003",
]

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

OMDB_API_KEYS = ["dea6b6b3", "1f927d1"]

FOLDER_RE = re.compile(
    r"^(?P<num>\d+)\s+(?P<title>.+?)\s+\((?P<year>\d{4})\)\s+\{imdb-(?P<imdb_id>tt\d+)\}$"
)

# ─── LANGUAGE MAPPINGS ─────────────────────────────────────────────────────────

LANGUAGE_MAP_EN = {
    "ara": "Arabic", "bul": "Bulgarian", "chi": "Chinese", "cze": "Czech",
    "dan": "Danish", "dut": "Dutch", "eng": "English", "est": "Estonian",
    "fin": "Finnish", "fre": "French", "ger": "German", "gre": "Greek",
    "heb": "Hebrew", "hin": "Hindi", "hrv": "Croatian", "hun": "Hungarian",
    "ice": "Icelandic", "ita": "Italian", "jpn": "Japanese", "lav": "Latvian",
    "lit": "Lithuanian", "nor": "Norwegian", "per": "Persian", "pol": "Polish",
    "por": "Portuguese", "rum": "Romanian", "rus": "Russian", "sh": "Serbo-Croatian",
    "slv": "Slovenian", "spa": "Spanish", "srp": "Serbian", "swe": "Swedish", "tha": "Thai",
    "tur": "Turkish", "ukr": "Ukrainian", "und": "Unknown"
}

LANGUAGE_MAP_DE = {
    "ara": "Arabisch", "bul": "Bulgarisch", "chi": "Chinesisch", "cze": "Tschechisch",
    "dan": "Dänisch", "dut": "Niederländisch", "eng": "Englisch", "est": "Estnisch",
    "fin": "Finnisch", "fre": "Französisch", "ger": "Deutsch", "gre": "Griechisch",
    "heb": "Hebräisch", "hin": "Hindi", "hrv": "Kroatisch", "hun": "Ungarisch",
    "ice": "Isländisch", "ita": "Italienisch", "jpn": "Japanisch", "lav": "Lettisch",
    "lit": "Litauisch", "nor": "Norwegisch", "per": "Persisch", "pol": "Polnisch", "por": "Portugiesisch",
    "rum": "Rumänisch", "rus": "Russisch", "sh": "Serbokroatisch", "slv": "Slowenisch",
    "spa": "Spanisch", "srp": "Serbisch", "swe": "Schwedisch", "tha": "Thailändisch",
    "tur": "Türkisch", "ukr": "Ukrainisch", "und": "Unbekannt"
}

# ─── SCHEMA ────────────────────────────────────────────────────────────────────

NEW_MEDIA_FIELDS = {
    "audio_languages_german", "audio_languages_english",
    "subtitles_languages_german", "subtitles_languages_english"
}

EXPECTED_FIELDS = {
    "num", "folder_name", "folder_path", "title", "original_title",
    "year", "duration", "director", "genres", "outline", "imdb_id",
    "imdb_link", "imdb_rating", "stars", "rated", "country", "language",
    "poster_url", "cover_file", "folder_location"
}.union(NEW_MEDIA_FIELDS)

LOCAL_FIELDS = {"num", "folder_name", "folder_path", "folder_location"}


def missing_fields(metadata: dict) -> set[str]:
    return EXPECTED_FIELDS - set(metadata.keys())


# ─── MKV ANALYSIS HELPERS ──────────────────────────────────────────────────────

def check_ffprobe_installed():
    try:
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False


def get_largest_mkv(folder_path: Path) -> Path | None:
    mkvs = list(folder_path.glob("*.mkv"))
    return max(mkvs, key=lambda p: p.stat().st_size) if mkvs else None


def extract_mkv_languages(mkv_path: Path):
    """Liest die MKV aus und gibt die 4 formatierten Sprachlisten zurück."""
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(mkv_path)]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if result.returncode != 0:
            return [], [], [], []

        data = json.loads(result.stdout)
        audio_codes = set()
        sub_codes = set()

        for stream in data.get("streams", []):
            ctype = stream.get("codec_type")
            lang = stream.get("tags", {}).get("language", "und").lower().strip()

            if ctype == "audio":
                audio_codes.add(lang)
            elif ctype == "subtitle":
                sub_codes.add(lang)

        # Übersetze die 3-stelligen Codes mit Fallback auf den Originalcode, falls unbekannt
        aud_de = sorted(list({LANGUAGE_MAP_DE.get(c, c) for c in audio_codes}))
        aud_en = sorted(list({LANGUAGE_MAP_EN.get(c, c) for c in audio_codes}))
        sub_de = sorted(list({LANGUAGE_MAP_DE.get(c, c) for c in sub_codes}))
        sub_en = sorted(list({LANGUAGE_MAP_EN.get(c, c) for c in sub_codes}))

        return aud_de, aud_en, sub_de, sub_en
    except Exception as e:
        print(f"        ✗ ffprobe Fehler: {e}")
        return [], [], [], []


# ─── OMDB API & HELPERS ────────────────────────────────────────────────────────

def omdb_fetch(imdb_id: str) -> dict | None:
    for key in OMDB_API_KEYS:
        url = f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={key}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if data.get("Response") == "True":
                return data
        except Exception:
            pass
    return None


def download_image(url: str, dest: Path) -> bool:
    if not url or url == "N/A": return False
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
            dest.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def parse_folder(name: str) -> dict | None:
    m = FOLDER_RE.match(name)
    return m.groupdict() if m else None


def safe_list(raw: str) -> list[str]:
    if not raw: return []
    return [s.strip() for s in raw.split(",") if s.strip() and s.strip() != "N/A"]


def meta_filename(title: str, imdb_id: str) -> str:
    return f"{title}_metadata_{imdb_id}.json"


# ─── CORE PROCESSING ───────────────────────────────────────────────────────────

def process_root(root: str, drive_name: str) -> list[dict]:
    root_path = Path(root)
    covers_dir = Path(PROJECT_ROOT) / "html_dvd_collection/covers"
    covers_dir.mkdir(parents=True, exist_ok=True)

    if not root_path.exists():
        print(f"\n⚠  Drive not found, skipping: {root}")
        return []

    print(f"\n📂  Scanning {root} (Location: {drive_name}) …")

    movies: list[dict] = []
    added = 0
    cached = 0
    skipped = 0

    for folder_path in sorted(root_path.iterdir()):
        if not folder_path.is_dir(): continue

        parsed = parse_folder(folder_path.name)
        if not parsed:
            print(f"  ✗  Cannot parse: {folder_path.name}")
            continue

        title = parsed["title"]
        year = parsed["year"]
        imdb_id = parsed["imdb_id"]
        num = parsed["num"]

        print(f"  🎬  [{num}] {title} ({year})  —  {imdb_id}")

        meta_file = folder_path / meta_filename(title, imdb_id)
        cover_file = folder_path / f"{title}_cover.jpg"

        metadata = {}
        is_new_movie = not meta_file.exists()

        # ── 1. Metadaten laden oder OMDB abfragen ────────────────────────────────
        if not is_new_movie:
            with meta_file.open(encoding="utf-8-sig") as f:
                metadata = json.load(f)

            # Immer die lokalen Pfade/Namen aktualisieren
            metadata["num"] = num
            metadata["folder_name"] = folder_path.name
            metadata["folder_path"] = str(folder_path)
            metadata["folder_location"] = drive_name

            # Prüfen, ob OMDB-Felder fehlen
            missing_omdb = missing_fields(metadata) - LOCAL_FIELDS - NEW_MEDIA_FIELDS
            if missing_omdb:
                print(f"        🔄  Re-fetching OMDB data for missing: {missing_omdb}")
                data = omdb_fetch(imdb_id)
                time.sleep(0.25)
                if data:
                    field_map = {
                        "title": data.get("Title", metadata.get("title")),
                        "original_title": data.get("Title", metadata.get("original_title")),
                        "duration": data.get("Runtime", "N/A"),
                        "director": data.get("Director", "N/A"),
                        "genres": safe_list(data.get("Genre", "")),
                        "outline": data.get("Plot", "N/A"),
                        "imdb_link": f"https://www.imdb.com/title/{imdb_id}/",
                        "imdb_rating": data.get("imdbRating", "N/A"),
                        "stars": safe_list(data.get("Actors", "")),
                        "rated": data.get("Rated", "N/A"),
                        "country": data.get("Country", "N/A"),
                        "language": data.get("Language", "N/A"),
                        "poster_url": data.get("Poster", ""),
                    }
                    for field in missing_omdb:
                        if field in field_map:
                            metadata[field] = field_map[field]

            # Cover prüfen
            cover_filename = metadata.get("cover_file")
            if cover_filename:
                src_cover = folder_path / cover_filename
                dest_cover = covers_dir / f"{imdb_id}.jpg"
                if src_cover.exists() and not dest_cover.exists():
                    shutil.copy2(src_cover, dest_cover)
                    print(f"        ✓  Cover kopiert → covers/{imdb_id}.jpg")

        else:
            # GANZ NEUER FILM
            data = omdb_fetch(imdb_id)
            time.sleep(0.25)
            if not data:
                print(f"        ✗  Could not fetch OMDB data — skipping")
                skipped += 1
                continue

            # Cover herunterladen
            poster_url = data.get("Poster", "")
            cover_filename = None
            if not cover_file.exists():
                if download_image(poster_url, cover_file):
                    print(f"        ✓  Cover gespeichert → {cover_file.name}")
                    cover_filename = cover_file.name
            else:
                cover_filename = cover_file.name

            if cover_file.exists():
                dest_cover = covers_dir / f"{imdb_id}.jpg"
                if not dest_cover.exists():
                    shutil.copy2(cover_file, dest_cover)

            metadata = {
                "num": num,
                "folder_name": folder_path.name,
                "folder_path": str(folder_path),
                "title": data.get("Title", title),
                "original_title": data.get("Title", title),
                "year": year,
                "duration": data.get("Runtime", "N/A"),
                "director": data.get("Director", "N/A"),
                "genres": safe_list(data.get("Genre", "")),
                "outline": data.get("Plot", "N/A"),
                "imdb_id": imdb_id,
                "imdb_link": f"https://www.imdb.com/title/{imdb_id}/",
                "imdb_rating": data.get("imdbRating", "N/A"),
                "stars": safe_list(data.get("Actors", "")),
                "rated": data.get("Rated", "N/A"),
                "country": data.get("Country", "N/A"),
                "language": data.get("Language", "N/A"),
                "poster_url": poster_url,
                "cover_file": cover_filename,
                "folder_location": drive_name,
            }

        # ── 2. MKV Sprachen analysieren (Bedingt) ─────────────────────────────
        needs_mkv_scan = False

        # Prüfen, ob die Felder fehlen
        for f in NEW_MEDIA_FIELDS:
            if f not in metadata:
                needs_mkv_scan = True
                break

        # Prüfen, ob der User den Scan in der Config erzwingt
        if num in FORCE_MKV_RESCAN:
            needs_mkv_scan = True

        if needs_mkv_scan:
            reason = "Erzwungen durch FORCE_MKV_RESCAN" if num in FORCE_MKV_RESCAN else "Fehlende Felder"
            print(f"        🔍 Analysiere MKV-Datei für Sprachen... ({reason})")

            largest_mkv = get_largest_mkv(folder_path)
            if largest_mkv:
                aud_de, aud_en, sub_de, sub_en = extract_mkv_languages(largest_mkv)
                metadata["audio_languages_german"] = aud_de
                metadata["audio_languages_english"] = aud_en
                metadata["subtitles_languages_german"] = sub_de
                metadata["subtitles_languages_english"] = sub_en
                print(f"        ✓  MKV Sprachen aktualisiert")
            else:
                print(f"        ⚠  Keine MKV gefunden. Setze leere Listen.")
                metadata["audio_languages_german"] = []
                metadata["audio_languages_english"] = []
                metadata["subtitles_languages_german"] = []
                metadata["subtitles_languages_english"] = []

        # ── 3. JSON Speichern ─────────────────────────────────────────────────
        with meta_file.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)

        if is_new_movie:
            print(f"        ✓  Neu angelegt → {meta_file.name}")
            added += 1
        else:
            cached += 1

        movies.append(metadata)

    return movies


def scan_all_configured() -> list[dict]:
    all_movies: list[dict] = []
    for root, drive_name in DRIVE_CONFIG.items():
        all_movies.extend(process_root(root, drive_name))
    return all_movies


# ─── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Movie Metadata & Media Scanner ===")

    if not check_ffprobe_installed():
        print("❌ FEHLER: 'ffprobe' wurde nicht gefunden!")
        print("Bitte installiere ffmpeg, damit MKV-Sprachen ausgelesen werden können.")
        exit(1)

    print("Scanning all configured drives...\n")
    movies = scan_all_configured()

    print(f"\n✅  Done — {len(movies)} movies processed total.")

    index_path = Path(PROJECT_ROOT) / "html_dvd_collection/movies_index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(movies, f, indent=4, ensure_ascii=False)
    print(f"📄  Combined index written → {index_path}")