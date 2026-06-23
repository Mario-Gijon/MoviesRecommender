import argparse
import json
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.preprocessing import normalize

from app.project_paths.dataset_paths import (
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import (
    ItemKnnCosineBuildConfig,
    ItemNeighbor,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.storage import (
    ItemNeighborArtifactWriter,
    file_size_mb,
    prepare_item_knn_cosine_artifacts,
    write_model_manifest,
)


def build_item_knn_cosine_model(config: ItemKnnCosineBuildConfig) -> None:
    _validate_config(config)
    _validate_input_file(OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH)
    _validate_input_file(OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH)
    _validate_input_file(OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH)

    started_at = time.perf_counter()
    artifacts = prepare_item_knn_cosine_artifacts(config)
    dataset_metadata = _load_dataset_metadata()

    print(f"Building ItemKNN Cosine variant: {config.variant_id}")
    print(f"Output directory: {artifacts.variant_dir}")

    public_movie_ids = _load_public_movie_ids()
    support_movie_ids = _load_support_movie_ids()
    model_movie_ids = _merge_movie_ids(public_movie_ids, support_movie_ids)

    ratings = _load_collaborative_ratings(model_movie_ids)

    rating_matrix, column_movie_ids, user_count = _build_user_item_matrix(
        ratings=ratings,
        model_movie_ids=model_movie_ids,
    )
    rating_count = int(rating_matrix.nnz)

    del ratings

    item_user_matrix = rating_matrix.T.tocsr()
    del rating_matrix

    normalized_item_user_matrix = normalize(
        item_user_matrix,
        norm="l2",
        axis=1,
        copy=True,
    ).tocsr()

    binary_item_user_matrix = item_user_matrix.astype(bool).astype(np.int32)
    generated_neighbor_rows = _write_neighbors(
        config=config,
        artifacts=artifacts,
        normalized_item_user_matrix=normalized_item_user_matrix,
        binary_item_user_matrix=binary_item_user_matrix,
        column_movie_ids=column_movie_ids,
    )

    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    write_model_manifest(
        artifacts=artifacts,
        config=config,
        dataset_metadata=dataset_metadata,
        counts={
            "ratings": rating_count,
            "users": user_count,
            "publicMovies": len(public_movie_ids),
            "supportMovies": len(support_movie_ids),
            "modelMovies": len(model_movie_ids),
            "generatedNeighborRows": generated_neighbor_rows,
            "buildTimeSeconds": int(elapsed_seconds),
            "neighborsCsvSizeMb": int(file_size_mb(artifacts.neighbors_csv_path)),
            "neighborsSqliteSizeMb": int(file_size_mb(artifacts.neighbors_sqlite_path)),
        },
    )

    print("ItemKNN Cosine build completed.")
    print(f"Public movies: {len(public_movie_ids)}")
    print(f"Support movies: {len(support_movie_ids)}")
    print(f"Model movies: {len(model_movie_ids)}")
    print(f"Generated neighbor rows: {generated_neighbor_rows}")
    print(f"CSV: {artifacts.neighbors_csv_path}")
    print(f"SQLite: {artifacts.neighbors_sqlite_path}")
    print(f"Manifest: {artifacts.manifest_path}")
    print(f"Elapsed seconds: {elapsed_seconds}")


def _validate_config(config: ItemKnnCosineBuildConfig) -> None:
    if config.top_k <= 0:
        raise RuntimeError("--top-k must be greater than 0.")

    if config.min_support <= 0:
        raise RuntimeError("--min-support must be greater than 0.")

    if config.chunk_size <= 0:
        raise RuntimeError("--chunk-size must be greater than 0.")


def _validate_input_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Required input file does not exist: {path}")


def _load_dataset_metadata() -> dict:
    if not OFFLINE_DATASET_MANIFEST_PATH.exists():
        return {}

    return json.loads(OFFLINE_DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_public_movie_ids() -> list[int]:
    public_movies = pd.read_csv(
        OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        usecols=["movieId"],
        dtype={"movieId": np.int32},
    )

    movie_ids = public_movies["movieId"].drop_duplicates().astype(int).tolist()

    if not movie_ids:
        raise RuntimeError("Public movies CSV contains no movieId values.")

    return movie_ids


def _load_support_movie_ids() -> list[int]:
    support_movies = pd.read_csv(
        OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
        usecols=["movieId"],
        dtype={"movieId": np.int32},
    )

    movie_ids = support_movies["movieId"].drop_duplicates().astype(int).tolist()

    if not movie_ids:
        raise RuntimeError("Collaborative support movies CSV contains no movieId values.")

    return movie_ids


def _merge_movie_ids(
    public_movie_ids: Sequence[int],
    support_movie_ids: Sequence[int],
) -> list[int]:
    seen_movie_ids: set[int] = set()
    model_movie_ids: list[int] = []

    for movie_id in [*public_movie_ids, *support_movie_ids]:
        movie_id = int(movie_id)

        if movie_id in seen_movie_ids:
            continue

        seen_movie_ids.add(movie_id)
        model_movie_ids.append(movie_id)

    if not model_movie_ids:
        raise RuntimeError("ItemKNN Cosine model movie universe is empty.")

    return model_movie_ids


def _load_collaborative_ratings(model_movie_ids: Sequence[int]) -> pd.DataFrame:
    model_movie_id_set = set(model_movie_ids)

    ratings = pd.read_csv(
        OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
        usecols=["userId", "movieId", "rating"],
        dtype={
            "userId": np.int32,
            "movieId": np.int32,
            "rating": np.float32,
        },
    )

    ratings = ratings[ratings["movieId"].isin(model_movie_id_set)]

    if ratings.empty:
        raise RuntimeError("Collaborative ratings CSV contains no ratings for model movies.")

    return ratings


def _build_user_item_matrix(
    *,
    ratings: pd.DataFrame,
    model_movie_ids: Sequence[int],
) -> tuple[sparse.csr_matrix, list[int], int]:
    movie_id_to_column = {
        int(movie_id): column
        for column, movie_id in enumerate(model_movie_ids)
    }

    movie_columns = ratings["movieId"].map(movie_id_to_column)

    if movie_columns.isna().any():
        raise RuntimeError("Some collaborative ratings reference unsupported movieId values.")

    user_rows, user_ids = pd.factorize(ratings["userId"], sort=True)

    rating_matrix = sparse.csr_matrix(
        (
            ratings["rating"].to_numpy(dtype=np.float32),
            (
                user_rows.astype(np.int32),
                movie_columns.to_numpy(dtype=np.int32),
            ),
        ),
        shape=(len(user_ids), len(model_movie_ids)),
        dtype=np.float32,
    )
    rating_matrix.sum_duplicates()

    return rating_matrix, [int(movie_id) for movie_id in model_movie_ids], len(user_ids)


def _write_neighbors(
    *,
    config: ItemKnnCosineBuildConfig,
    artifacts: object,
    normalized_item_user_matrix: sparse.csr_matrix,
    binary_item_user_matrix: sparse.csr_matrix,
    column_movie_ids: Sequence[int],
) -> int:
    item_count = normalized_item_user_matrix.shape[0]
    generated_neighbor_rows = 0

    with ItemNeighborArtifactWriter(artifacts) as writer:
        for start in range(0, item_count, config.chunk_size):
            end = min(start + config.chunk_size, item_count)
            print(f"Processing item chunk {start}:{end} / {item_count}")

            similarity_chunk = (
                normalized_item_user_matrix[start:end]
                @ normalized_item_user_matrix.T
            )
            support_chunk = (
                binary_item_user_matrix[start:end]
                @ binary_item_user_matrix.T
            )

            similarity_values = similarity_chunk.toarray().astype(np.float32, copy=False)
            support_values = support_chunk.toarray().astype(np.int32, copy=False)

            chunk_neighbors = _top_neighbors_from_chunk(
                config=config,
                start=start,
                similarity_values=similarity_values,
                support_values=support_values,
                column_movie_ids=column_movie_ids,
            )

            writer.write_neighbors(chunk_neighbors)
            generated_neighbor_rows += len(chunk_neighbors)

    return generated_neighbor_rows


def _top_neighbors_from_chunk(
    *,
    config: ItemKnnCosineBuildConfig,
    start: int,
    similarity_values: np.ndarray,
    support_values: np.ndarray,
    column_movie_ids: Sequence[int],
) -> list[ItemNeighbor]:
    neighbors: list[ItemNeighbor] = []

    for local_source_index in range(similarity_values.shape[0]):
        source_column = start + local_source_index
        source_movie_id = int(column_movie_ids[source_column])
        similarity_row = similarity_values[local_source_index]
        support_row = support_values[local_source_index]

        similarity_row[source_column] = 0.0
        support_row[source_column] = 0

        candidate_columns = np.flatnonzero(
            (similarity_row > 0)
            & (support_row >= config.min_support)
        )

        if candidate_columns.size == 0:
            continue

        if candidate_columns.size > config.top_k:
            candidate_scores = similarity_row[candidate_columns]
            selected_positions = np.argpartition(
                candidate_scores,
                -config.top_k,
            )[-config.top_k:]
            candidate_columns = candidate_columns[selected_positions]

        candidate_scores = similarity_row[candidate_columns]
        ordered_positions = np.argsort(-candidate_scores, kind="mergesort")
        ordered_candidate_columns = candidate_columns[ordered_positions][: config.top_k]

        neighbors.extend(
            ItemNeighbor(
                source_movie_id=source_movie_id,
                neighbor_movie_id=int(column_movie_ids[neighbor_column]),
                similarity=float(similarity_row[neighbor_column]),
                support=int(support_row[neighbor_column]),
                rank=rank,
            )
            for rank, neighbor_column in enumerate(ordered_candidate_columns, start=1)
        )

    return neighbors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=200)
    parser.add_argument("--min-support", type=int, default=25)
    parser.add_argument("--chunk-size", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_item_knn_cosine_model(
        ItemKnnCosineBuildConfig(
            top_k=args.top_k,
            min_support=args.min_support,
            chunk_size=args.chunk_size,
            overwrite=args.overwrite,
        )
    )


if __name__ == "__main__":
    main()