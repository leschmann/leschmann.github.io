import json
import os
import re
import shutil

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


def generate_html():
    index_path    = os.path.join(PROJECT_ROOT, "movies_index.json")
    covers_dir    = os.path.join(PROJECT_ROOT, "covers")
    html_path     = os.path.join(PROJECT_ROOT, "dvd_collection.html")
    template_path = os.path.join(SCRIPT_DIR, "dvd_collection_template.html")

    if not os.path.exists(index_path):
        print("movies_index.json not found! Run the scraper script first.")
        return

    with open(index_path, "r", encoding="utf-8-sig") as f:
        movies = json.load(f)

    os.makedirs(covers_dir, exist_ok=True)

    processed_movies = []
    all_genres    = set()
    all_directors = set()
    all_stars     = set()

    for movie in movies:
        # ── Duration ──────────────────────────────────────────────────────
        dur_str   = movie.get("duration", "N/A")
        dur_match = re.search(r'\d+', dur_str)
        dur_val   = int(dur_match.group()) if dur_match else 0

        # ── Rating ────────────────────────────────────────────────────────
        rating_str = movie.get("imdb_rating", "0")
        try:
            rating_val = float(rating_str)
        except (ValueError, TypeError):
            rating_val = 0.0

        # ── Year ──────────────────────────────────────────────────────────
        year_str   = movie.get("year", "0")
        year_match = re.search(r'\d{4}', str(year_str))
        year_val   = int(year_match.group()) if year_match else 0

        # ── Genres (already a list) ────────────────────────────────────────
        genres_list = movie.get("genres", [])
        if isinstance(genres_list, str):          # safety fallback
            genres_list = [g.strip() for g in genres_list.split(",") if g.strip() and g.strip() != "N/A"]
        all_genres.update(genres_list)
        genres_str = ", ".join(genres_list)

        # ── Director ──────────────────────────────────────────────────────
        dir_str = movie.get("director", "N/A")
        if dir_str and dir_str != "N/A":
            all_directors.add(dir_str.strip())

        # ── Stars (already a list) ────────────────────────────────────────
        stars_list = movie.get("stars", [])
        if isinstance(stars_list, str):           # safety fallback
            stars_list = [s.strip() for s in stars_list.split(",") if s.strip() and s.strip() != "N/A"]
        all_stars.update(stars_list)
        stars_str = ", ".join(stars_list)

        # ── Cover image ───────────────────────────────────────────────────
        imdb_id        = movie.get("imdb_id", "unknown")
        safe_cover     = f"{imdb_id}.jpg"
        dest_cover     = os.path.join(covers_dir, safe_cover)

        if os.path.exists(dest_cover):
            img_uri = f"covers/{safe_cover}"
        else:
            # cover_file is just the filename; folder_path has the full path
            cover_filename  = movie.get("cover_file")
            folder_path     = movie.get("folder_path", "")
            original_cover  = os.path.join(folder_path, cover_filename) if cover_filename and folder_path else None

            if original_cover and os.path.exists(original_cover):
                shutil.copy2(original_cover, dest_cover)
                print(f"  📋 Cover copied: {safe_cover}")
                img_uri = f"covers/{safe_cover}"
            else:
                img_uri = "https://via.placeholder.com/300x450/000000/FFFFFF/?text=No+Cover"

        processed_movies.append({
            "title":           movie.get("title", "Unknown"),
            "director":        dir_str,
            "year":            year_val,
            "duration_str":    dur_str,
            "duration_min":    dur_val,
            "imdb_rating_str": movie.get("imdb_rating", "N/A"),
            "imdb_rating_val": rating_val,
            "fsk_rating":      movie.get("rated", "N/A"),
            "genres_str":      genres_str,
            "genres_list":     genres_list,
            "outline":         movie.get("outline", "N/A"),
            "stars":           stars_str,
            "imdb_id":         imdb_id,
            "img_uri":         img_uri,
            "num":             movie.get("num", "N/A"),
            "folder_location": movie.get("folder_location", "N/A"),
            "folder_path":     movie.get("folder_path", ""),
        })

    # Read the HTML template from the external file
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"🎬  dvd_collection.html written → {html_path}")
    print(f"✅  {len(processed_movies)} movies processed.")


if __name__ == "__main__":
    generate_html()
