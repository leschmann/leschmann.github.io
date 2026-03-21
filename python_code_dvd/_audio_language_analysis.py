import os
import json
import subprocess
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────

# Hier wieder deine Laufwerke eintragen
DRIVE_CONFIG = {
    r"F:\Movies": "FFM DVD 00001 - 00600",
    # r"E:\Movies": "FFM DVD 00601 - 01200",
}

SCRIPT_DIR = os.path.dirname(__file__)
REPORT_FILE = os.path.join(SCRIPT_DIR, "media_analysis_report.json")


# ───────────────────────────────────────────────────────────────────────────────

def check_ffprobe_installed():
    """Prüft, ob ffprobe im System gefunden wird."""
    try:
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False


def get_largest_mkv(folder_path: Path) -> Path | None:
    """Findet alle .mkv Dateien in einem Ordner und gibt die größte zurück."""
    mkvs = list(folder_path.glob("*.mkv"))
    if not mkvs:
        return None

    # max() sucht das Element mit dem höchsten Wert der key-Funktion (hier: Dateigröße)
    largest_mkv = max(mkvs, key=lambda p: p.stat().st_size)
    return largest_mkv


def analyze_mkv_with_ffprobe(file_path: Path) -> dict:
    """Führt ffprobe aus und extrahiert Audio- und Untertitelspuren."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(file_path)
    ]

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if result.returncode != 0:
            print(f"      ✗ Fehler beim Ausführen von ffprobe für {file_path.name}")
            return {}

        probe_data = json.loads(result.stdout)

        audio_tracks = []
        subtitle_tracks = []

        for stream in probe_data.get("streams", []):
            codec_type = stream.get("codec_type")
            tags = stream.get("tags", {})

            # Manche Spuren haben keine Sprach-Tags, dann nehmen wir 'und' (undefined)
            language = tags.get("language", "und")
            title = tags.get("title", "")
            codec_name = stream.get("codec_name", "unknown")

            track_info = {
                "index": stream.get("index"),
                "language": language,
                "codec": codec_name,
                "title": title
            }

            if codec_type == "audio":
                audio_tracks.append(track_info)
            elif codec_type == "subtitle":
                subtitle_tracks.append(track_info)

        return {
            "audio": audio_tracks,
            "subtitles": subtitle_tracks
        }

    except Exception as e:
        print(f"      ✗ Exception bei ffprobe: {e}")
        return {}


def format_size(size_bytes: int) -> str:
    """Formatiert Bytes in GB."""
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def run_analysis():
    if not check_ffprobe_installed():
        print("❌ FEHLER: 'ffprobe' wurde nicht gefunden!")
        print("Bitte installiere ffmpeg und füge es zu deinen Windows PATH Umgebungsvariablen hinzu.")
        return

    print("=== MKV Audio & Subtitle Analyzer ===")

    analysis_results = {}
    total_folders = 0
    folders_with_mkv = 0

    for root_path_str, drive_name in DRIVE_CONFIG.items():
        root_path = Path(root_path_str)
        if not root_path.exists():
            print(f"\n⚠ Laufwerk nicht gefunden, überspringe: {root_path_str}")
            continue

        print(f"\n📂 Durchsuche {root_path_str} ...")

        for folder_path in sorted(root_path.iterdir()):
            if not folder_path.is_dir():
                continue

            total_folders += 1
            print(f"\n🎬 {folder_path.name}")

            largest_mkv = get_largest_mkv(folder_path)

            if not largest_mkv:
                print("      ✗ Keine .mkv Datei gefunden.")
                continue

            folders_with_mkv += 1
            file_size = format_size(largest_mkv.stat().st_size)
            print(f"      ✓ Größte MKV: {largest_mkv.name} ({file_size})")

            # ffprobe Analyse
            tracks = analyze_mkv_with_ffprobe(largest_mkv)

            if tracks:
                audio_langs = [f"{t['language']} ({t['codec']})" for t in tracks.get("audio", [])]
                sub_langs = [f"{t['language']} ({t['codec']})" for t in tracks.get("subtitles", [])]

                print(f"      🔊 Audio ({len(audio_langs)}): {', '.join(audio_langs) if audio_langs else 'Keine'}")
                print(f"      💬 Subs  ({len(sub_langs)}): {', '.join(sub_langs) if sub_langs else 'Keine'}")

                analysis_results[folder_path.name] = {
                    "folder_path": str(folder_path),
                    "drive": drive_name,
                    "file_name": largest_mkv.name,
                    "file_size_bytes": largest_mkv.stat().st_size,
                    "tracks": tracks
                }

    # Bericht speichern
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, indent=4, ensure_ascii=False)

    print("\n=================================================")
    print(f"✅ Analyse abgeschlossen!")
    print(f"Ordner gesamt:       {total_folders}")
    print(f"Ordner mit MKV:      {folders_with_mkv}")
    print(f"📄 Bericht gespeichert in: {REPORT_FILE}")


if __name__ == "__main__":
    run_analysis()