import json
import os
import shutil

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


def sync_covers():
    index_path = os.path.join(PROJECT_ROOT, "html_dvd_collection/movies_index.json")
    covers_dir = os.path.join(PROJECT_ROOT, "html_dvd_collection/covers")
    os.makedirs(covers_dir, exist_ok=True)

    if not os.path.exists(index_path):
        print("movies_index.json not found! Run the scraper script first.")
        return

    with open(index_path, "r", encoding="utf-8-sig") as f:
        movies = json.load(f)

    copied = 0
    skipped = 0

    print("Checking cover images...")

    for movie in movies:
        imdb_id = movie.get("imdb_id", "unknown")
        safe_cover = f"{imdb_id}.jpg"
        dest_cover = os.path.join(covers_dir, safe_cover)

        # If it's already in the covers folder, skip it
        if os.path.exists(dest_cover):
            skipped += 1
            continue

        # Otherwise, try to copy it from the original hard drive location
        cover_filename = movie.get("cover_file")
        folder_path = movie.get("folder_path", "")

        if cover_filename and folder_path:
            original_cover = os.path.join(folder_path, cover_filename)
            if os.path.exists(original_cover):
                shutil.copy2(original_cover, dest_cover)
                copied += 1
                print(f"  📋 Copied: {safe_cover}")

    print(f"\n✅ Done! Copied {copied} new covers. Skipped {skipped} existing covers.")


if __name__ == "__main__":
    sync_covers()