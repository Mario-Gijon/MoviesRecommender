import argparse
import time

from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.algorithms.popularity_baseline.models import (
    PopularityBaselineBuildConfig,
    PopularityRankingEntry,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.storage import (
    file_size_mb,
    prepare_popularity_baseline_artifacts,
    write_model_manifest,
    write_popularity_ranking,
)


def build_popularity_baseline_model(config: PopularityBaselineBuildConfig) -> None:
    started_at = time.perf_counter()
    artifacts = prepare_popularity_baseline_artifacts(config)

    print("Building popularity baseline ranking.")
    print(f"Output directory: {artifacts.variant_dir}")

    candidates = catalog_repository.get_recommendation_candidates()

    scored_candidates = [
        _score_movie(movie)
        for movie in candidates
        if _has_rating_signal(movie)
    ]
    scored_candidates.sort(key=lambda item: item["score"], reverse=True)

    ranking = [
        PopularityRankingEntry(
            rank=rank,
            movie_id=int(item["movie"]["movieId"]),
            score=float(item["score"]),
            average_rating=float(item["averageRating"]),
            rating_count=int(item["ratingCount"]),
            stand_display_score=float(item["standDisplayScore"]),
        )
        for rank, item in enumerate(scored_candidates, start=1)
    ]

    write_popularity_ranking(
        artifacts=artifacts,
        ranking=ranking,
    )

    elapsed_seconds = round(time.perf_counter() - started_at, 3)

    write_model_manifest(
        artifacts=artifacts,
        counts={
            "publicCandidates": len(candidates),
            "rankedMovies": len(ranking),
            "buildTimeSeconds": int(elapsed_seconds),
            "rankingCsvSizeMb": file_size_mb(artifacts.ranking_csv_path),
            "rankingSqliteSizeMb": file_size_mb(artifacts.ranking_sqlite_path),
        },
    )

    print("Popularity baseline build completed.")
    print(f"Ranked movies: {len(ranking)}")
    print(f"CSV: {artifacts.ranking_csv_path}")
    print(f"SQLite: {artifacts.ranking_sqlite_path}")
    print(f"Manifest: {artifacts.manifest_path}")
    print(f"Elapsed seconds: {elapsed_seconds}")


def _has_rating_signal(movie: dict) -> bool:
    rating_count = _rating_count(movie)
    average_rating = _average_rating(movie)
    return rating_count > 0 and average_rating > 0


def _score_movie(movie: dict) -> dict:
    rating_count = _rating_count(movie)
    average_rating = _average_rating(movie)
    stand_display_score = _float_value(movie.get("standDisplayScore"))
    confidence = rating_count / (rating_count + 250)
    weighted_rating = average_rating * confidence
    normalized_stand_score = stand_display_score / 100 if stand_display_score > 1 else stand_display_score
    score = weighted_rating * 0.85 + normalized_stand_score * 0.15

    return {
        "movie": movie,
        "score": score,
        "averageRating": average_rating,
        "ratingCount": rating_count,
        "standDisplayScore": stand_display_score,
    }


def _rating_count(movie: dict) -> int:
    filtered_rating_count = movie.get("filteredRatingCount")
    rating_count = movie.get("ratingCount")
    return int(filtered_rating_count or rating_count or 0)


def _average_rating(movie: dict) -> float:
    filtered_average_rating = movie.get("filteredAverageRating")
    average_rating = movie.get("averageRating")
    return _float_value(filtered_average_rating or average_rating)


def _float_value(value: object) -> float:
    if value is None:
        return 0.0

    return float(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_popularity_baseline_model(
        PopularityBaselineBuildConfig(
            overwrite=args.overwrite,
        )
    )


if __name__ == "__main__":
    main()