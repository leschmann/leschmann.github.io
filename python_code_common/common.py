"""
Gemeinsame Konfiguration und Hilfsfunktionen für die Skripte in python_code_dvd/
und python_code_series/.

Einbinden in einem Skript:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_code_common"))
    from common import ...
"""
import json
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─── LAUFWERKE ─────────────────────────────────────────────────────────────────
# Laufwerksbuchstabe → Name der Festplatte (wird als "folder_location" gespeichert)

DRIVES = {
    "G:": "FFM DVD 00001 - 00600",
    "F:": "FFM DVD 01092 - 00000",
    "E:": "FFM DVD 00601 - 01091",
}

MOVIE_DRIVES = {rf"{letter}\Movies": name for letter, name in DRIVES.items()}
SERIES_DRIVES = {rf"{letter}\Serien - TV Shows": name for letter, name in DRIVES.items()}

# ─── API KEYS ──────────────────────────────────────────────────────────────────

OMDB_API_KEYS = ["dea6b6b3", "1f927d1"]
TMDB_API_KEY = "6a0da576bde6cc997fec24a6b700791c"

# ─── PFADE IM PROJEKT ──────────────────────────────────────────────────────────

MOVIE_METADATA_DIR = PROJECT_ROOT / "metadata_jsons_dvd"
MOVIE_FSK_PATH = PROJECT_ROOT / "metadata_fsk_dvd.json"
MOVIE_PARENTAL_GUIDES_DIR = PROJECT_ROOT / "metadata_parental_guides_dvd"
MOVIE_HTML_DIR = PROJECT_ROOT / "html_dvd_collection"

SERIES_METADATA_DIR = PROJECT_ROOT / "metadata_jsons_series"
SERIES_HTML_DIR = PROJECT_ROOT / "html_series_collection"

# ─── SPRACHEN ──────────────────────────────────────────────────────────────────
# MKV-Dateien nutzen für dieselbe Sprache mal den bibliografischen ISO-639-2-Code
# (ger, fre, …), mal den terminologischen (deu, fra, …) – beide werden übersetzt.
# (Codes) → (Englisch, Deutsch)

_LANGUAGE_NAMES = {
    ("ara",): ("Arabic", "Arabisch"),
    ("bul",): ("Bulgarian", "Bulgarisch"),
    ("cat",): ("Catalan", "Katalanisch"),
    ("chi", "zho"): ("Chinese", "Chinesisch"),
    ("cze", "ces"): ("Czech", "Tschechisch"),
    ("dan",): ("Danish", "Dänisch"),
    ("dut", "nld"): ("Dutch", "Niederländisch"),
    ("eng",): ("English", "Englisch"),
    ("est",): ("Estonian", "Estnisch"),
    ("fin",): ("Finnish", "Finnisch"),
    ("fre", "fra"): ("French", "Französisch"),
    ("ger", "deu"): ("German", "Deutsch"),
    ("gre", "ell"): ("Greek", "Griechisch"),
    ("heb",): ("Hebrew", "Hebräisch"),
    ("hin",): ("Hindi", "Hindi"),
    ("hrv",): ("Croatian", "Kroatisch"),
    ("hun",): ("Hungarian", "Ungarisch"),
    ("ice", "isl"): ("Icelandic", "Isländisch"),
    ("ind",): ("Indonesian", "Indonesisch"),
    ("ita",): ("Italian", "Italienisch"),
    ("jpn",): ("Japanese", "Japanisch"),
    ("kor",): ("Korean", "Koreanisch"),
    ("lav",): ("Latvian", "Lettisch"),
    ("lit",): ("Lithuanian", "Litauisch"),
    ("may", "msa"): ("Malay", "Malaiisch"),
    ("nor",): ("Norwegian", "Norwegisch"),
    ("per", "fas"): ("Persian", "Persisch"),
    ("pol",): ("Polish", "Polnisch"),
    ("por",): ("Portuguese", "Portugiesisch"),
    ("rum", "ron"): ("Romanian", "Rumänisch"),
    ("rus",): ("Russian", "Russisch"),
    ("sh",): ("Serbo-Croatian", "Serbokroatisch"),
    ("slo", "slk"): ("Slovak", "Slowakisch"),
    ("slv",): ("Slovenian", "Slowenisch"),
    ("spa",): ("Spanish", "Spanisch"),
    ("srp",): ("Serbian", "Serbisch"),
    ("swe",): ("Swedish", "Schwedisch"),
    ("tha",): ("Thai", "Thailändisch"),
    ("tur",): ("Turkish", "Türkisch"),
    ("ukr",): ("Ukrainian", "Ukrainisch"),
    ("urd",): ("Urdu", "Urdu"),
    ("vie",): ("Vietnamese", "Vietnamesisch"),
    ("und",): ("Unknown", "Unbekannt"),
}

LANGUAGE_NAMES = {code: names for codes, names in _LANGUAGE_NAMES.items() for code in codes}


def language_name(value: str, lang: str = "en") -> str:
    """'deu' oder 'ger' → 'German' (lang="en") bzw. 'Deutsch' (lang="de").
    Bereits übersetzte Namen und unbekannte Codes bleiben unverändert."""
    names = LANGUAGE_NAMES.get(value.strip().lower())
    if names is None:
        return value
    return names[0] if lang == "en" else names[1]


def normalize_languages(values, lang: str = "en") -> list[str]:
    """Übersetzt alle Codes einer Sprachliste und entfernt Doppelte (z. B. 'German' + 'deu')."""
    return sorted({language_name(v, lang) for v in values if v})


# ─── MKV / FFPROBE ─────────────────────────────────────────────────────────────

def check_ffprobe_installed() -> bool:
    try:
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False


def get_largest_mkv(folder_path: Path) -> Path | None:
    mkvs = list(folder_path.glob("*.mkv"))
    return max(mkvs, key=lambda p: p.stat().st_size) if mkvs else None


def ffprobe_streams(media_path: Path) -> list[dict] | None:
    """Liest alle Streams einer Mediendatei per ffprobe aus (None, wenn ffprobe scheitert)."""
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(media_path)]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if result.returncode != 0:
            return None
        return json.loads(result.stdout).get("streams", [])
    except (OSError, ValueError) as e:
        print(f"        ✗ ffprobe Fehler: {e}")
        return None


def extract_mkv_languages(mkv_path: Path) -> tuple[list[str], list[str], list[str], list[str]]:
    """Liest die MKV aus und gibt die 4 formatierten Sprachlisten zurück:
    Audio (Deutsch), Audio (Englisch), Untertitel (Deutsch), Untertitel (Englisch)."""
    streams = ffprobe_streams(mkv_path)
    if streams is None:
        return [], [], [], []

    audio_codes = set()
    sub_codes = set()
    for stream in streams:
        lang = stream.get("tags", {}).get("language", "und").lower().strip()
        if stream.get("codec_type") == "audio":
            audio_codes.add(lang)
        elif stream.get("codec_type") == "subtitle":
            sub_codes.add(lang)

    return (
        normalize_languages(audio_codes, "de"),
        normalize_languages(audio_codes, "en"),
        normalize_languages(sub_codes, "de"),
        normalize_languages(sub_codes, "en"),
    )


# ─── DATEIEN ───────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_js_constants(path, constants: dict) -> None:
    """Schreibt Daten als `const name = …;`-Blöcke in eine JS-Datei (z. B. data.js)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(";\n\n".join(f"const {name} = {json.dumps(value, ensure_ascii=False)}" for name, value in constants.items()))
        f.write(";\n")


def movie_imdb_ids() -> set[str]:
    """IMDb-IDs aller Filme der Sammlung (aus den Dateinamen in metadata_jsons_dvd/)."""
    ids = set()
    for path in MOVIE_METADATA_DIR.glob("*_metadata_tt*.json"):
        match = re.search(r"_metadata_(tt\d+)\.json$", path.name)
        if match:
            ids.add(match.group(1))
    return ids
