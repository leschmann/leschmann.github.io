import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_code_common"))
from common import MOVIE_DRIVES, check_ffprobe_installed, get_largest_mkv, ffprobe_streams

# ─── CONFIG ────────────────────────────────────────────────────────────────────
# Laufwerke stehen in python_code_common/common.py (nicht angeschlossene werden übersprungen)

SCRIPT_DIR = os.path.dirname(__file__)
REPORT_FILE = os.path.join(SCRIPT_DIR, "media_analysis_report.json")


# ───────────────────────────────────────────────────────────────────────────────

def analyze_mkv_with_ffprobe(file_path: Path) -> dict:
    """Führt ffprobe aus und extrahiert Audio- und Untertitelspuren."""
    streams = ffprobe_streams(file_path)
    if streams is None:
        print(f"      ✗ Fehler beim Ausführen von ffprobe für {file_path.name}")
        return {}

    audio_tracks = []
    subtitle_tracks = []

    for stream in streams:
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

    for root_path_str, drive_name in MOVIE_DRIVES.items():
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