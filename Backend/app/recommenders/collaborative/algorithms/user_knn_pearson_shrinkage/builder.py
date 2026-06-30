import argparse
import sqlite3
import time

import pandas as pd

from app.recommenders.collaborative.common.offline_context import (
    CollaborativeOfflineContext,
    get_default_collaborative_offline_context,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import (
    UserKnnPearsonShrinkageBuildConfig,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.storage import (
    file_size_mb,
    prepare_user_knn_pearson_shrinkage_artifacts,
    write_model_manifest,
)


def build_user_knn_pearson_shrinkage_model(
    config: UserKnnPearsonShrinkageBuildConfig,
    *,
    offline_context: CollaborativeOfflineContext | None = None,
) -> None:
    context = offline_context or get_default_collaborative_offline_context()
    started_at = time.perf_counter()
    artifacts = prepare_user_knn_pearson_shrinkage_artifacts(
        config,
        artifact_root=context.collaborative_model_artifact_root,
    )

    print("Building UserKNN Pearson Shrinkage runtime artifact.")
    print(f"Output directory: {artifacts.variant_dir}")

    public_movie_ids = _load_public_movie_ids(context)

    user_stats = _build_user_stats(
        chunksize=config.chunksize,
        ratings_csv_path=context.ratings_csv_path,
    )
    user_stats.to_csv(
        artifacts.user_stats_csv_path,
        index=False,
        encoding="utf-8",
    )

    counts = _build_ratings_sqlite(
        sqlite_path=artifacts.ratings_sqlite_path,
        user_stats=user_stats,
        public_movie_ids=public_movie_ids,
        chunksize=config.chunksize,
        ratings_csv_path=context.ratings_csv_path,
    )

    elapsed_seconds = round(time.perf_counter() - started_at, 3)

    write_model_manifest(
        artifacts=artifacts,
        counts={
            **counts,
            "buildTimeSeconds": int(elapsed_seconds),
            "ratingsSqliteSizeMb": file_size_mb(artifacts.ratings_sqlite_path),
            "userStatsCsvSizeMb": file_size_mb(artifacts.user_stats_csv_path),
        },
    )

    print("UserKNN Pearson Shrinkage artifact build completed.")
    print(f"Users: {counts['users']}")
    print(f"Ratings: {counts['ratings']}")
    print(f"Public movies: {counts['publicMovies']}")
    print(f"Public ratings: {counts['publicRatings']}")
    print(f"SQLite: {artifacts.ratings_sqlite_path}")
    print(f"User stats CSV: {artifacts.user_stats_csv_path}")
    print(f"Manifest: {artifacts.manifest_path}")
    print(f"Elapsed seconds: {elapsed_seconds}")


def _load_public_movie_ids(
    context: CollaborativeOfflineContext,
) -> set[int]:
    public_movies = pd.read_csv(
        context.public_movies_csv_path,
        usecols=["movieId"],
        dtype={"movieId": "int32"},
    )
    return set(public_movies["movieId"].astype(int))


def _build_user_stats(
    *,
    chunksize: int,
    ratings_csv_path,
) -> pd.DataFrame:
    partial_stats = []

    for chunk_index, chunk in enumerate(
        _read_ratings_chunks(
            chunksize=chunksize,
            ratings_csv_path=ratings_csv_path,
        ),
        start=1,
    ):
        chunk["ratingSquared"] = chunk["rating"] * chunk["rating"]

        grouped = (
            chunk.groupby("userId", sort=False)
            .agg(
                ratingCount=("rating", "count"),
                ratingSum=("rating", "sum"),
                ratingSquaredSum=("ratingSquared", "sum"),
            )
            .reset_index()
        )

        partial_stats.append(grouped)

        print(
            "Processed stats chunk",
            chunk_index,
            "partial users:",
            len(grouped),
        )

    if not partial_stats:
        raise RuntimeError("No collaborative ratings were found to build user stats.")

    user_stats = (
        pd.concat(partial_stats, ignore_index=True)
        .groupby("userId", sort=False)
        .agg(
            ratingCount=("ratingCount", "sum"),
            ratingSum=("ratingSum", "sum"),
            ratingSquaredSum=("ratingSquaredSum", "sum"),
        )
        .reset_index()
    )

    user_stats["meanRating"] = user_stats["ratingSum"] / user_stats["ratingCount"]
    variance = (
        user_stats["ratingSquaredSum"] / user_stats["ratingCount"]
    ) - user_stats["meanRating"].pow(2)
    user_stats["ratingStd"] = variance.clip(lower=0).pow(0.5)

    user_stats = user_stats[
        [
            "userId",
            "ratingCount",
            "ratingSum",
            "ratingSquaredSum",
            "meanRating",
            "ratingStd",
        ]
    ].sort_values(
        by="userId",
        kind="mergesort",
    )

    return user_stats


def _build_ratings_sqlite(
    *,
    sqlite_path,
    user_stats: pd.DataFrame,
    public_movie_ids: set[int],
    chunksize: int,
    ratings_csv_path,
) -> dict:
    user_mean_by_id = user_stats.set_index("userId")["meanRating"]

    connection = sqlite3.connect(sqlite_path)
    try:
        _configure_sqlite_for_bulk_load(connection)
        _create_schema(connection)
        _insert_user_stats(connection, user_stats)

        total_ratings = 0
        public_ratings = 0
        distinct_movies: set[int] = set()
        public_movies_with_ratings: set[int] = set()

        for chunk_index, chunk in enumerate(
            _read_ratings_chunks(
                chunksize=chunksize,
                ratings_csv_path=ratings_csv_path,
            ),
            start=1,
        ):
            chunk["meanRating"] = chunk["userId"].map(user_mean_by_id)
            chunk = chunk.dropna(subset=["meanRating"]).copy()

            chunk["centeredRating"] = chunk["rating"] - chunk["meanRating"]
            chunk["isPublicCandidate"] = chunk["movieId"].isin(public_movie_ids).astype("int8")

            _insert_user_ratings(connection, chunk)

            chunk_rating_count = len(chunk)
            chunk_public_rating_count = int(chunk["isPublicCandidate"].sum())

            total_ratings += chunk_rating_count
            public_ratings += chunk_public_rating_count
            distinct_movies.update(int(movie_id) for movie_id in chunk["movieId"].unique())
            public_movies_with_ratings.update(
                int(movie_id)
                for movie_id in chunk.loc[
                    chunk["isPublicCandidate"] == 1,
                    "movieId",
                ].unique()
            )

            print(
                "Inserted ratings chunk",
                chunk_index,
                "ratings:",
                chunk_rating_count,
                "public ratings:",
                chunk_public_rating_count,
            )

        _create_indexes(connection)
        connection.commit()
    finally:
        connection.close()

    return {
        "ratings": total_ratings,
        "users": int(len(user_stats)),
        "movies": len(distinct_movies),
        "publicMovies": len(public_movie_ids),
        "publicMoviesWithRatings": len(public_movies_with_ratings),
        "publicRatings": public_ratings,
        "avgRatingsPerUser": round(total_ratings / len(user_stats), 6),
    }


def _read_ratings_chunks(
    *,
    chunksize: int,
    ratings_csv_path,
):
    return pd.read_csv(
        ratings_csv_path,
        usecols=["userId", "movieId", "rating"],
        dtype={
            "userId": "int32",
            "movieId": "int32",
            "rating": "float32",
        },
        chunksize=chunksize,
    )


def _configure_sqlite_for_bulk_load(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode = OFF")
    connection.execute("PRAGMA synchronous = OFF")
    connection.execute("PRAGMA temp_store = MEMORY")
    connection.execute("PRAGMA cache_size = -200000")


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE user_stats (
            user_id INTEGER PRIMARY KEY,
            rating_count INTEGER NOT NULL,
            rating_sum REAL NOT NULL,
            rating_squared_sum REAL NOT NULL,
            mean_rating REAL NOT NULL,
            rating_std REAL NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE user_ratings (
            user_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            rating REAL NOT NULL,
            centered_rating REAL NOT NULL,
            is_public_candidate INTEGER NOT NULL CHECK (is_public_candidate IN (0, 1)),
            PRIMARY KEY (user_id, movie_id)
        )
        """
    )


def _insert_user_stats(
    connection: sqlite3.Connection,
    user_stats: pd.DataFrame,
) -> None:
    connection.executemany(
        """
        INSERT INTO user_stats (
            user_id,
            rating_count,
            rating_sum,
            rating_squared_sum,
            mean_rating,
            rating_std
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                int(row.userId),
                int(row.ratingCount),
                float(row.ratingSum),
                float(row.ratingSquaredSum),
                float(row.meanRating),
                float(row.ratingStd),
            )
            for row in user_stats.itertuples(index=False)
        ),
    )


def _insert_user_ratings(
    connection: sqlite3.Connection,
    ratings: pd.DataFrame,
) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO user_ratings (
            user_id,
            movie_id,
            rating,
            centered_rating,
            is_public_candidate
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            (
                int(row.userId),
                int(row.movieId),
                float(row.rating),
                float(row.centeredRating),
                int(row.isPublicCandidate),
            )
            for row in ratings.itertuples(index=False)
        ),
    )


def _create_indexes(connection: sqlite3.Connection) -> None:
    print("Creating SQLite indexes.")

    connection.execute(
        """
        CREATE INDEX idx_user_ratings_movie_user
        ON user_ratings (movie_id, user_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX idx_user_ratings_user_movie
        ON user_ratings (user_id, movie_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX idx_user_ratings_public_user_movie
        ON user_ratings (user_id, movie_id)
        WHERE is_public_candidate = 1
        """
    )

    connection.execute(
        """
        CREATE INDEX idx_user_ratings_public_movie_user
        ON user_ratings (movie_id, user_id)
        WHERE is_public_candidate = 1
        """
    )

    connection.execute("ANALYZE")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--chunksize", type=int, default=500_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_user_knn_pearson_shrinkage_model(
        UserKnnPearsonShrinkageBuildConfig(
            overwrite=args.overwrite,
            chunksize=args.chunksize,
        )
    )


if __name__ == "__main__":
    main()
