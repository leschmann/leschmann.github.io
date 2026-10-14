"""
Übernimmt IMDb-Elternleitfäden in die Sammlung.

IMDb blockiert automatische Abrufe (Bot-Schutz), deshalb kommen die Daten über ein
Bookmarklet, das du auf der IMDb-Seite im eigenen Browser klickst. Einrichtung und
Anleitung: parental_guide_bookmarklet.html (im Browser öffnen).

  1. Film auf IMDb öffnen – der erste Klick aufs Lesezeichen wechselt zum deutschen
     Elternleitfaden, der zweite lädt imdb_parental_guide_tt….json herunter
  2. Dieses Skript ausführen: übernimmt alle Exporte aus dem Download-Ordner nach
     metadata_parental_guides_dvd/, löscht sie dort und baut data.js / parental_guides.js neu

Jeder Export enthält die MPA-Begründung, die fünf Stufen und je Kategorie die ersten
(max. 5) Kommentare ohne Spoiler. Ein erneuter Export desselben Films ersetzt den alten.
"""
import re
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_code_common"))
from common import MOVIE_PARENTAL_GUIDES_DIR, load_json, movie_imdb_ids
from sync_metadata import update_data_js

EXPORT_PATTERN = "imdb_parental_guide_tt*.json"
CATEGORY_IDS = ["nudity", "violence", "profanity", "alcohol", "frightening"]  # Reihenfolge wie auf IMDb
SEVERITIES = {"none", "mild", "moderate", "severe"}
MAX_ITEMS = 5


def clean_guide(raw: dict) -> dict:
    """Prüft einen Bookmarklet-Export und bringt ihn ins gespeicherte Format (ValueError, wenn unbrauchbar)."""
    imdb_id = str(raw.get("imdb_id", ""))
    if not re.fullmatch(r"tt\d+", imdb_id):
        raise ValueError(f"ungültige IMDb-ID {imdb_id!r}")

    categories = {}
    for cat in raw.get("categories", []):
        cat_id = str(cat.get("id", "")).lower()
        if cat_id not in CATEGORY_IDS:
            continue
        items = [str(text).strip() for text in cat.get("items", []) if str(text).strip()][:MAX_ITEMS]
        categories[cat_id] = {
            "id": cat_id,
            "severity": cat.get("severity") if cat.get("severity") in SEVERITIES else None,
            "total_items": max(int(cat.get("total_items") or 0), len(items)),
            "items": items,
        }

    rating_reason = str(raw.get("rating_reason") or "").strip()
    if not rating_reason and not any(c["severity"] or c["items"] for c in categories.values()):
        raise ValueError("IMDb hat für diesen Film (noch) keinen Elternleitfaden")

    return {
        "imdb_id": imdb_id,
        "source_url": str(raw.get("source_url", "")),
        "exported_at": str(raw.get("exported_at", "")),
        "machine_translated": bool(raw.get("machine_translated")),
        "rating_reason": rating_reason,
        "categories": [categories[c] for c in CATEGORY_IDS if c in categories],
    }


def import_exports(downloads_dir: Path, keep: bool = False) -> int:
    """Importiert alle Bookmarklet-Exporte aus downloads_dir, gibt die Anzahl zurück."""
    # Älteste zuerst: Gibt es mehrere Exporte eines Films ("… (1).json"), gewinnt der neueste
    exports = sorted(downloads_dir.glob(EXPORT_PATTERN), key=lambda p: p.stat().st_mtime)
    if not exports:
        print(f"Keine Exporte ({EXPORT_PATTERN}) in {downloads_dir} gefunden.")
        return 0

    MOVIE_PARENTAL_GUIDES_DIR.mkdir(exist_ok=True)
    collection = movie_imdb_ids()
    imported = 0

    for path in exports:
        try:
            guide = clean_guide(load_json(path))
        except (ValueError, TypeError, AttributeError) as e:
            print(f"[FEHLER]   {path.name}: {e}")
            continue

        dest = MOVIE_PARENTAL_GUIDES_DIR / f"{guide['imdb_id']}.json"
        with dest.open("w", encoding="utf-8") as f:
            json.dump(guide, f, indent=4, ensure_ascii=False)
            f.write("\n")

        note = "" if guide["imdb_id"] in collection else "  (⚠ Film ist nicht in der Sammlung)"
        print(f"[IMPORTIERT] {path.name} → {dest.relative_to(MOVIE_PARENTAL_GUIDES_DIR.parent)}{note}")
        imported += 1

        if not keep:
            path.unlink()

    print(f"\n✅  {imported} von {len(exports)} Export(en) importiert.")
    return imported


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMDb-Elternleitfäden aus Bookmarklet-Exporten übernehmen.")
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads",
                        help="Ordner mit den Exporten (Standard: %(default)s)")
    parser.add_argument("--keep", action="store_true", help="Exporte nach dem Import nicht löschen")
    args = parser.parse_args()

    if import_exports(args.downloads, keep=args.keep):
        update_data_js()
