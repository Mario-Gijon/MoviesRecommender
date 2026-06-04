import csv
import json

from app.infrastructure.datasets.movielens_paths import (
    ML_32M_DEMO_CATALOG_PATH,
    ML_32M_DEMO_RATINGS_BY_MOVIE_PATH,
    ML_32M_DEMO_RATINGS_PATH,
    ML_32M_DEMO_RATINGS_SUMMARY_PATH,
    ML_32M_RATINGS_CSV_PATH,
)


FILTERED_RATINGS_COLUMNS = ["userId", "movieId", "rating", "timestamp"]
BY_MOVIE_COLUMNS = [
    "movieId",
    "title",
    "year",
    "isPublicCatalog",
    "isCollaborativeCore",
    "isExcludedOrSensitive",
    "catalogRatingCount",
    "catalogAverageRating",
    "filteredRatingCount",
    "filteredAverageRating",
]


def main() -> None:
    if not ML_32M_DEMO_CATALOG_PATH.exists():
        raise RuntimeError(
            "Processed MovieLens 32M demo catalog is missing. "
            "Run python -m app.scripts.build_demo_catalog_from_movielens_32m first."
        )

    if not ML_32M_RATINGS_CSV_PATH.exists():
        raise RuntimeError(
            "Raw MovieLens 32M ratings file is missing. "
            "Run python -m app.scripts.download_movielens_32m first."
        )

    catalog = json.loads(ML_32M_DEMO_CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_index = _build_catalog_index(catalog)

    ML_32M_DEMO_RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

    source_ratings_read = 0
    ratings_written = 0
    unique_users: set[str] = set()
    filtered_counts_by_movie: dict[int, int] = {}
    filtered_sums_by_movie: dict[int, float] = {}

    with ML_32M_RATINGS_CSV_PATH.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        with ML_32M_DEMO_RATINGS_PATH.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=FILTERED_RATINGS_COLUMNS)
            writer.writeheader()

            for row in reader:
                source_ratings_read += 1

                movie_id = _parse_int(row.get("movieId"))
                if movie_id not in catalog_index["collaborative_core_movie_ids"]:
                    continue

                writer.writerow(
                    {
                        "userId": row.get("userId", ""),
                        "movieId": row.get("movieId", ""),
                        "rating": row.get("rating", ""),
                        "timestamp": row.get("timestamp", ""),
                    }
                )

                ratings_written += 1
                unique_users.add(row.get("userId", ""))

                rating_value = _parse_float(row.get("rating"))
                filtered_counts_by_movie[movie_id] = filtered_counts_by_movie.get(movie_id, 0) + 1
                filtered_sums_by_movie[movie_id] = (
                    filtered_sums_by_movie.get(movie_id, 0.0) + rating_value
                )

    _write_by_movie_csv(
        catalog_index=catalog_index,
        filtered_counts_by_movie=filtered_counts_by_movie,
        filtered_sums_by_movie=filtered_sums_by_movie,
    )

    summary = _build_summary(
        catalog_index=catalog_index,
        source_ratings_read=source_ratings_read,
        ratings_written=ratings_written,
        unique_users=unique_users,
        filtered_counts_by_movie=filtered_counts_by_movie,
    )
    ML_32M_DEMO_RATINGS_SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(f"Input catalog path: {ML_32M_DEMO_CATALOG_PATH}")
    print(f"Raw ratings path: {ML_32M_RATINGS_CSV_PATH}")
    print(f"Source ratings read: {source_ratings_read}")
    print(f"Ratings written: {ratings_written}")
    print(f"Unique users in filtered ratings: {len(unique_users)}")
    print(f"Public catalog movies: {len(catalog_index['public_movie_ids'])}")
    print(f"Collaborative core movies: {len(catalog_index['collaborative_core_movie_ids'])}")
    print(f"Movies with filtered ratings: {summary['moviesWithFilteredRatings']}")
    print(f"Output ratings path: {ML_32M_DEMO_RATINGS_PATH}")
    print(f"Output by-movie path: {ML_32M_DEMO_RATINGS_BY_MOVIE_PATH}")
    print(f"Output summary path: {ML_32M_DEMO_RATINGS_SUMMARY_PATH}")


def _build_catalog_index(catalog: dict) -> dict:
    public_items = catalog.get("publicCatalog", [])
    collaborative_items = catalog.get("collaborativeCore", [])
    excluded_items = catalog.get("excludedOrSensitive", [])

    public_movie_ids = {_parse_int(item.get("movieId")) for item in public_items}
    collaborative_core_movie_ids = {_parse_int(item.get("movieId")) for item in collaborative_items}
    excluded_movie_ids = {_parse_int(item.get("movieId")) for item in excluded_items}

    all_movie_ids = public_movie_ids | collaborative_core_movie_ids | excluded_movie_ids
    movie_metadata_by_id = {movie_id: {} for movie_id in all_movie_ids if movie_id is not None}

    for item in public_items:
        _merge_movie_metadata(movie_metadata_by_id, item)
    for item in collaborative_items:
        _merge_movie_metadata(movie_metadata_by_id, item)
    for item in excluded_items:
        _merge_movie_metadata(movie_metadata_by_id, item)

    return {
        "public_movie_ids": {movie_id for movie_id in public_movie_ids if movie_id is not None},
        "collaborative_core_movie_ids": {
            movie_id for movie_id in collaborative_core_movie_ids if movie_id is not None
        },
        "excluded_movie_ids": {movie_id for movie_id in excluded_movie_ids if movie_id is not None},
        "movie_metadata_by_id": movie_metadata_by_id,
    }


def _merge_movie_metadata(movie_metadata_by_id: dict[int, dict], item: dict) -> None:
    movie_id = _parse_int(item.get("movieId"))
    if movie_id is None:
        return

    movie_metadata_by_id[movie_id] = {
        **movie_metadata_by_id.get(movie_id, {}),
        "movieId": movie_id,
        "title": item.get("title", ""),
        "year": item.get("year", ""),
        "catalogRatingCount": item.get("ratingCount", ""),
        "catalogAverageRating": item.get("averageRating", ""),
    }


def _write_by_movie_csv(
    *,
    catalog_index: dict,
    filtered_counts_by_movie: dict[int, int],
    filtered_sums_by_movie: dict[int, float],
) -> None:
    rows = []
    public_movie_ids = catalog_index["public_movie_ids"]
    collaborative_core_movie_ids = catalog_index["collaborative_core_movie_ids"]
    excluded_movie_ids = catalog_index["excluded_movie_ids"]

    for movie_id, metadata in catalog_index["movie_metadata_by_id"].items():
        filtered_rating_count = filtered_counts_by_movie.get(movie_id, 0)
        filtered_average_rating = ""
        if filtered_rating_count > 0:
            filtered_average_rating = _format_float(
                filtered_sums_by_movie[movie_id] / filtered_rating_count
            )

        rows.append(
            {
                "movieId": movie_id,
                "title": metadata.get("title", ""),
                "year": metadata.get("year", ""),
                "isPublicCatalog": "true" if movie_id in public_movie_ids else "false",
                "isCollaborativeCore": (
                    "true" if movie_id in collaborative_core_movie_ids else "false"
                ),
                "isExcludedOrSensitive": "true" if movie_id in excluded_movie_ids else "false",
                "catalogRatingCount": metadata.get("catalogRatingCount", ""),
                "catalogAverageRating": metadata.get("catalogAverageRating", ""),
                "filteredRatingCount": filtered_rating_count,
                "filteredAverageRating": filtered_average_rating,
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row["isPublicCatalog"] == "true" else 1,
            -int(row["filteredRatingCount"]),
            -_sort_float(row["filteredAverageRating"]),
            row["title"] or "",
        )
    )

    with ML_32M_DEMO_RATINGS_BY_MOVIE_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=BY_MOVIE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _build_summary(
    *,
    catalog_index: dict,
    source_ratings_read: int,
    ratings_written: int,
    unique_users: set[str],
    filtered_counts_by_movie: dict[int, int],
) -> dict:
    public_movie_ids = catalog_index["public_movie_ids"]
    collaborative_core_movie_ids = catalog_index["collaborative_core_movie_ids"]
    excluded_movie_ids = catalog_index["excluded_movie_ids"]

    movies_with_filtered_ratings = {
        movie_id for movie_id, count in filtered_counts_by_movie.items() if count > 0
    }

    return {
        "sourceDataset": "ml-32m",
        "sourceRatingsRead": source_ratings_read,
        "ratingsWritten": ratings_written,
        "uniqueUsers": len(unique_users),
        "publicCatalogMovies": len(public_movie_ids),
        "collaborativeCoreMovies": len(collaborative_core_movie_ids),
        "excludedOrSensitiveMovies": len(excluded_movie_ids),
        "moviesWithFilteredRatings": len(movies_with_filtered_ratings),
        "publicCatalogMoviesWithFilteredRatings": len(
            movies_with_filtered_ratings & public_movie_ids
        ),
        "collaborativeCoreMoviesWithFilteredRatings": len(
            movies_with_filtered_ratings & collaborative_core_movie_ids
        ),
        "outputRatingsPath": str(ML_32M_DEMO_RATINGS_PATH),
        "outputByMoviePath": str(ML_32M_DEMO_RATINGS_BY_MOVIE_PATH),
    }


def _parse_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _parse_float(value: object) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _format_float(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _sort_float(value: object) -> float:
    if value in (None, ""):
        return float("-inf")
    return float(value)


if __name__ == "__main__":
    main()
