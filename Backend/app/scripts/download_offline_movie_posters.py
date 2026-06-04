import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from app.infrastructure.datasets.movielens_paths import (
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_POSTERS_DIR,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)


TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


def main() -> None:
    args = _parse_args()

    if not OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH.exists():
        raise RuntimeError(
            "Run python -m app.scripts.export_offline_dataset_from_movielens_32m first."
        )

    OFFLINE_DATASET_POSTERS_DIR.mkdir(parents=True, exist_ok=True)

    public_movies = _read_public_movies(limit=args.limit)
    public_movies_read = len(public_movies)
    posters_already_present = 0
    posters_downloaded = 0
    missing_poster_path_rows = 0
    failed_downloads = 0

    for movie in public_movies:
        movie_id = str(movie.get("movieId", "")).strip()
        poster_path = str(movie.get("posterPath", "")).strip()
        output_path = OFFLINE_DATASET_POSTERS_DIR / f"{movie_id}.jpg"

        if not poster_path:
            missing_poster_path_rows += 1
            continue

        if output_path.exists() and not args.force:
            posters_already_present += 1
            continue

        try:
            _download_poster(poster_path=poster_path, output_path=output_path)
            posters_downloaded += 1
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            failed_downloads += 1

        if args.sleep > 0:
            time.sleep(args.sleep)

    _update_manifest(
        downloaded_public_posters=_count_downloaded_public_posters(public_movies),
        missing_public_posters=missing_poster_path_rows,
        failed_public_poster_downloads=failed_downloads,
    )

    print(f"Input public movies CSV path: {OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH}")
    print(f"Output posters directory: {OFFLINE_DATASET_POSTERS_DIR}")
    print(f"Public movies read: {public_movies_read}")
    print(f"Posters already present: {posters_already_present}")
    print(f"Posters downloaded: {posters_downloaded}")
    print(f"Missing posterPath rows: {missing_poster_path_rows}")
    print(f"Failed downloads: {failed_downloads}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sleep", type=float, default=0.05)
    return parser.parse_args()


def _read_public_movies(*, limit: int | None) -> list[dict]:
    public_movies: list[dict] = []
    with OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            public_movies.append(row)
            if limit is not None and len(public_movies) >= limit:
                break
    return public_movies


def _count_downloaded_public_posters(public_movies: list[dict]) -> int:
    downloaded_count = 0
    for movie in public_movies:
        movie_id = str(movie.get("movieId", "")).strip()
        poster_path = str(movie.get("posterPath", "")).strip()
        if not movie_id or not poster_path:
            continue
        if (OFFLINE_DATASET_POSTERS_DIR / f"{movie_id}.jpg").exists():
            downloaded_count += 1
    return downloaded_count


def _download_poster(*, poster_path: str, output_path) -> None:
    if not poster_path.startswith("/"):
        raise ValueError("Poster path must start with '/'.")

    request = urllib.request.Request(
        f"{TMDB_IMAGE_BASE_URL}{poster_path}",
        headers={"User-Agent": "offline-dataset-poster-downloader/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        poster_bytes = response.read()

    output_path.write_bytes(poster_bytes)


def _update_manifest(
    *,
    downloaded_public_posters: int,
    missing_public_posters: int,
    failed_public_poster_downloads: int,
) -> None:
    if not OFFLINE_DATASET_MANIFEST_PATH.exists():
        return

    manifest = json.loads(OFFLINE_DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["downloadedPublicPosters"] = downloaded_public_posters
    manifest["missingPublicPosters"] = missing_public_posters
    manifest["failedPublicPosterDownloads"] = failed_public_poster_downloads
    manifest["posterDownloadCompletedAt"] = _utc_timestamp()
    OFFLINE_DATASET_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
