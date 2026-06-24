import csv
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.project_paths.dataset_paths import COLLABORATIVE_RECOMMENDER_MODELS_DIR
from app.recommenders.collaborative.algorithms.popularity_baseline.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    MODEL_VERSION,
    VARIANT_ID,
    PopularityBaselineArtifacts,
    PopularityBaselineBuildConfig,
    PopularityRankingEntry,
)


def get_popularity_baseline_artifacts() -> PopularityBaselineArtifacts:
    variant_dir = COLLABORATIVE_RECOMMENDER_MODELS_DIR / ALGORITHM_ID / VARIANT_ID

    return PopularityBaselineArtifacts(
        variant_dir=variant_dir,
        ranking_csv_path=variant_dir / "ranking.csv",
        ranking_sqlite_path=variant_dir / "ranking.sqlite",
        manifest_path=variant_dir / "model_manifest.json",
    )


def prepare_popularity_baseline_artifacts(
    config: PopularityBaselineBuildConfig,
) -> PopularityBaselineArtifacts:
    artifacts = get_popularity_baseline_artifacts()

    if artifacts.variant_dir.exists():
        if not config.overwrite:
            raise RuntimeError(
                f"Popularity baseline variant already exists: {artifacts.variant_dir}. "
                "Use --overwrite to rebuild it."
            )

        shutil.rmtree(artifacts.variant_dir)

    artifacts.variant_dir.mkdir(parents=True, exist_ok=False)
    return artifacts


def write_popularity_ranking(
    *,
    artifacts: PopularityBaselineArtifacts,
    ranking: list[PopularityRankingEntry],
) -> None:
    with artifacts.ranking_csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "rank",
                "movieId",
                "score",
                "averageRating",
                "ratingCount",
                "standDisplayScore",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {
                "rank": item.rank,
                "movieId": item.movie_id,
                "score": f"{item.score:.9f}",
                "averageRating": f"{item.average_rating:.6f}",
                "ratingCount": item.rating_count,
                "standDisplayScore": f"{item.stand_display_score:.6f}",
            }
            for item in ranking
        )

    connection = sqlite3.connect(artifacts.ranking_sqlite_path)
    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute(
            """
            CREATE TABLE popularity_ranking (
                rank INTEGER PRIMARY KEY,
                movie_id INTEGER NOT NULL UNIQUE,
                score REAL NOT NULL,
                average_rating REAL NOT NULL,
                rating_count INTEGER NOT NULL,
                stand_display_score REAL NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO popularity_ranking (
                rank,
                movie_id,
                score,
                average_rating,
                rating_count,
                stand_display_score
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.rank,
                    item.movie_id,
                    item.score,
                    item.average_rating,
                    item.rating_count,
                    item.stand_display_score,
                )
                for item in ranking
            ],
        )
        connection.execute(
            """
            CREATE INDEX idx_popularity_ranking_movie
            ON popularity_ranking (movie_id)
            """
        )
        connection.commit()
    finally:
        connection.close()


def load_popularity_ranking() -> list[PopularityRankingEntry]:
    artifacts = get_popularity_baseline_artifacts()

    if not artifacts.ranking_sqlite_path.exists():
        raise RuntimeError(
            "Popularity baseline SQLite artifact is missing: "
            f"{artifacts.ranking_sqlite_path}"
        )

    connection = sqlite3.connect(artifacts.ranking_sqlite_path)
    try:
        rows = connection.execute(
            """
            SELECT rank, movie_id, score, average_rating, rating_count, stand_display_score
            FROM popularity_ranking
            ORDER BY rank
            """
        ).fetchall()
    finally:
        connection.close()

    return [
        PopularityRankingEntry(
            rank=int(rank),
            movie_id=int(movie_id),
            score=float(score),
            average_rating=float(average_rating),
            rating_count=int(rating_count),
            stand_display_score=float(stand_display_score),
        )
        for rank, movie_id, score, average_rating, rating_count, stand_display_score in rows
    ]


def load_popularity_baseline_manifest() -> dict[str, Any]:
    artifacts = get_popularity_baseline_artifacts()

    if not artifacts.manifest_path.exists():
        raise RuntimeError(
            "Popularity baseline manifest is missing: "
            f"{artifacts.manifest_path}"
        )

    return json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))


def write_model_manifest(
    *,
    artifacts: PopularityBaselineArtifacts,
    counts: dict[str, Any],
) -> None:
    manifest = {
        "algorithmId": ALGORITHM_ID,
        "algorithmLabel": ALGORITHM_LABEL,
        "modelVersion": MODEL_VERSION,
        "variantId": VARIANT_ID,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "rankingCsv": "ranking.csv",
            "rankingSqlite": "ranking.sqlite",
        },
        "parameters": {
            "rankingSignal": "weighted_rating_popularity",
            "ratingConfidenceK": 250,
            "averageRatingWeight": 0.85,
            "standDisplayScoreWeight": 0.15,
        },
        "counts": counts,
    }

    artifacts.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def file_size_mb(path: Path) -> float:
    return round(path.stat().st_size / 1024 / 1024, 3)