"""
Holt die deutsche FSK-Freigabe aller Filme der Sammlung über die TMDB-API und
speichert sie in metadata_fsk_dvd.json (IMDb-ID → "0" / "6" / "12" / "16" / "18" / "N/A").

Bereits bekannte Filme werden übersprungen, mit --refresh werden alle neu abgefragt.
sync_metadata.py ruft update_fsk_cache() automatisch auf, neue Filme bekommen ihre
FSK also ohne extra Schritt. Dieses Skript braucht keine angeschlossenen Laufwerke.
"""
import re
import sys
import json
import time
import argparse
import requests
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python_code_common"))
from common import MOVIE_FSK_PATH, TMDB_API_KEY, load_json, movie_imdb_ids

TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Welche deutsche Freigabe zählt: Kino vor Premiere, DVD/Blu-ray, Digital und TV.
# TMDB-Veröffentlichungsarten: 1 Premiere, 2 Kino (limitiert), 3 Kino, 4 Digital, 5 DVD/Blu-ray, 6 TV
RELEASE_TYPE_PRIORITY = [3, 2, 1, 5, 4, 6]


def tmdb_get(path: str, **params) -> requests.Response:
    return requests.get(f"{TMDB_BASE_URL}{path}", params={"api_key": TMDB_API_KEY, **params}, timeout=10)


def parse_fsk(certification: str) -> str | None:
    """'12' / 'FSK 12' → '12', leere oder unbrauchbare Angaben → None."""
    match = re.search(r"\d+", certification or "")
    return match.group() if match else None


def pick_fsk(release_dates: list[dict]) -> str:
    """Wählt aus den deutschen Veröffentlichungen eines Films die maßgebliche Freigabe."""
    rated = [r for r in release_dates if parse_fsk(r.get("certification"))]
    if not rated:
        return "N/A"

    def rank(release: dict) -> int:
        kind = release.get("type")
        return RELEASE_TYPE_PRIORITY.index(kind) if kind in RELEASE_TYPE_PRIORITY else len(RELEASE_TYPE_PRIORITY)

    # Innerhalb derselben Veröffentlichungsart gewinnt die neueste (z. B. nach einer Neuprüfung)
    rated.sort(key=lambda r: r.get("release_date", ""), reverse=True)
    rated.sort(key=rank)
    return parse_fsk(rated[0]["certification"])


def fetch_fsk(imdb_id: str) -> str:
    """FSK eines Films per IMDb-ID, 'N/A' wenn TMDB keine deutsche Freigabe kennt.
    Netzwerk- und Serverfehler werfen requests.RequestException."""
    r = tmdb_get(f"/movie/{imdb_id}", append_to_response="release_dates")
    if r.status_code == 200:
        countries = r.json().get("release_dates", {}).get("results", [])
        return pick_fsk(next((c.get("release_dates", []) for c in countries if c.get("iso_3166_1") == "DE"), []))
    if r.status_code != 404:
        r.raise_for_status()

    # Kein Kinofilm bei TMDB – vielleicht eine TV-Produktion
    r = tmdb_get(f"/find/{imdb_id}", external_source="imdb_id")
    r.raise_for_status()
    tv_results = r.json().get("tv_results", [])
    if not tv_results:
        return "N/A"

    r = tmdb_get(f"/tv/{tv_results[0]['id']}/content_ratings")
    r.raise_for_status()
    rating = next((c.get("rating") for c in r.json().get("results", []) if c.get("iso_3166_1") == "DE"), "")
    return parse_fsk(rating) or "N/A"


def save_fsk_cache(cache: dict[str, str]) -> None:
    with open(MOVIE_FSK_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(cache.items())), f, indent=2, ensure_ascii=False)
        f.write("\n")


def update_fsk_cache(imdb_ids=None, refresh: bool = False) -> dict[str, str]:
    """Fragt fehlende Filme (oder mit refresh=True alle) bei TMDB ab und speichert den Cache."""
    cache = load_json(MOVIE_FSK_PATH) if MOVIE_FSK_PATH.exists() else {}
    ids = sorted(imdb_ids if imdb_ids is not None else movie_imdb_ids())
    todo = ids if refresh else [imdb_id for imdb_id in ids if imdb_id not in cache]
    if not todo:
        return cache

    print(f"\n[FSK] Frage {len(todo)} Film(e) bei TMDB ab …")
    failed = 0
    try:
        for n, imdb_id in enumerate(todo, start=1):
            try:
                fsk = fetch_fsk(imdb_id)
            except requests.RequestException as e:
                failed += 1
                print(f"  ✗  {imdb_id}: {e}")
                if failed == n and n >= 5:
                    print("[FSK] TMDB scheint nicht erreichbar zu sein – Rest wird beim nächsten Lauf geholt.")
                    break
                continue

            cache[imdb_id] = fsk
            print(f"  {imdb_id} → {'FSK ' + fsk if fsk != 'N/A' else 'keine deutsche Freigabe bekannt'}")
            time.sleep(0.05)
    finally:
        # Auch bei Abbruch (Strg+C) sichern, was schon geholt wurde
        save_fsk_cache(cache)

    if failed:
        print(f"[FSK] {failed} Abfrage(n) fehlgeschlagen – werden beim nächsten Lauf erneut versucht.")
    return cache


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deutsche FSK-Freigaben aller Filme über TMDB holen.")
    parser.add_argument("--refresh", action="store_true", help="alle Filme neu abfragen statt nur fehlende")
    args = parser.parse_args()

    collection = movie_imdb_ids()
    fsk_cache = update_fsk_cache(collection, refresh=args.refresh)

    counts = Counter(fsk_cache.get(imdb_id, "fehlt") for imdb_id in collection)
    print(f"\n✅  FSK für {len(collection)} Filme: " +
          ", ".join(f"{value}: {count}" for value, count in sorted(counts.items(), key=lambda kv: (len(kv[0]), kv[0]))))

    # Erst hier importiert, weil sync_metadata.py selbst update_fsk_cache() aus diesem Modul nutzt
    from sync_metadata import update_data_js
    update_data_js()
