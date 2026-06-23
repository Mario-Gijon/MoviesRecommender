import csv
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.project_paths.dataset_paths import COLLABORATIVE_RECOMMENDER_MODELS_DIR
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    MODEL_VERSION,
    ItemKnnCosineArtifacts,
    ItemKnnCosineBuildConfig,
    ItemNeighbor,
)


def get_item_knn_cosine_artifacts(
    config: ItemKnnCosineBuildConfig,
) -> ItemKnnCosineArtifacts:
    return get_item_knn_cosine_variant_artifacts(config.variant_id)


def get_item_knn_cosine_variant_artifacts(
    variant_id: str,
) -> ItemKnnCosineArtifacts:
    variant_dir = (
        COLLABORATIVE_RECOMMENDER_MODELS_DIR
        / ALGORITHM_ID
        / variant_id
    )

    return ItemKnnCosineArtifacts(
        variant_dir=variant_dir,
        neighbors_csv_path=variant_dir / "neighbors.csv",
        neighbors_sqlite_path=variant_dir / "neighbors.sqlite",
        manifest_path=variant_dir / "model_manifest.json",
    )


def load_item_knn_cosine_manifest(variant_id: str) -> dict[str, Any]:
    artifacts = get_item_knn_cosine_variant_artifacts(variant_id)

    if not artifacts.manifest_path.exists():
        raise RuntimeError(
            f"ItemKNN Cosine manifest does not exist for variant {variant_id}: "
            f"{artifacts.manifest_path}"
        )

    return json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))


def prepare_item_knn_cosine_artifacts(
    config: ItemKnnCosineBuildConfig,
) -> ItemKnnCosineArtifacts:
    artifacts = get_item_knn_cosine_artifacts(config)

    if artifacts.variant_dir.exists():
        if not config.overwrite:
            raise RuntimeError(
                f"ItemKNN Cosine variant already exists: {artifacts.variant_dir}. "
                "Use --overwrite to rebuild it."
            )

        shutil.rmtree(artifacts.variant_dir)

    artifacts.variant_dir.mkdir(parents=True, exist_ok=False)
    return artifacts


class ItemNeighborArtifactWriter:
    def __init__(self, artifacts: ItemKnnCosineArtifacts) -> None:
        self._artifacts = artifacts
        self._csv_file = None
        self._csv_writer = None
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> "ItemNeighborArtifactWriter":
        self._csv_file = self._artifacts.neighbors_csv_path.open(
            "w",
            encoding="utf-8",
            newline="",
        )
        self._csv_writer = csv.DictWriter(
            self._csv_file,
            fieldnames=[
                "sourceMovieId",
                "neighborMovieId",
                "similarity",
                "support",
                "rank",
            ],
        )
        self._csv_writer.writeheader()

        self._connection = sqlite3.connect(self._artifacts.neighbors_sqlite_path)
        self._connection.execute("PRAGMA journal_mode = OFF")
        self._connection.execute("PRAGMA synchronous = OFF")
        self._connection.execute("PRAGMA temp_store = MEMORY")
        self._connection.execute(
            """
            CREATE TABLE item_neighbors (
                source_movie_id INTEGER NOT NULL,
                neighbor_movie_id INTEGER NOT NULL,
                similarity REAL NOT NULL,
                support INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                PRIMARY KEY (source_movie_id, neighbor_movie_id)
            )
            """
        )

        return self

    def write_neighbors(self, neighbors: list[ItemNeighbor]) -> None:
        if not neighbors:
            return

        if self._csv_writer is None:
            raise RuntimeError("CSV neighbor writer is not open.")

        if self._connection is None:
            raise RuntimeError("SQLite neighbor writer is not open.")

        self._csv_writer.writerows(
            {
                "sourceMovieId": neighbor.source_movie_id,
                "neighborMovieId": neighbor.neighbor_movie_id,
                "similarity": f"{neighbor.similarity:.9f}",
                "support": neighbor.support,
                "rank": neighbor.rank,
            }
            for neighbor in neighbors
        )

        self._connection.executemany(
            """
            INSERT INTO item_neighbors (
                source_movie_id,
                neighbor_movie_id,
                similarity,
                support,
                rank
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    neighbor.source_movie_id,
                    neighbor.neighbor_movie_id,
                    neighbor.similarity,
                    neighbor.support,
                    neighbor.rank,
                )
                for neighbor in neighbors
            ],
        )

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._connection is not None:
            if exc_type is None:
                self._connection.execute(
                    """
                    CREATE INDEX idx_item_neighbors_source_rank
                    ON item_neighbors (source_movie_id, rank)
                    """
                )
                self._connection.execute(
                    """
                    CREATE INDEX idx_item_neighbors_neighbor
                    ON item_neighbors (neighbor_movie_id)
                    """
                )
                self._connection.commit()
            else:
                self._connection.rollback()

            self._connection.close()

        if self._csv_file is not None:
            self._csv_file.close()


def write_model_manifest(
    *,
    artifacts: ItemKnnCosineArtifacts,
    config: ItemKnnCosineBuildConfig,
    dataset_metadata: dict[str, Any],
    counts: dict[str, int],
) -> None:
    manifest = {
        "algorithmId": ALGORITHM_ID,
        "algorithmLabel": ALGORITHM_LABEL,
        "modelVersion": MODEL_VERSION,
        "variantId": config.variant_id,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "datasetName": dataset_metadata.get("datasetName"),
        "schemaVersion": dataset_metadata.get("schemaVersion"),
        "artifacts": {
            "neighborsCsv": "neighbors.csv",
            "neighborsSqlite": "neighbors.sqlite",
        },
        "parameters": {
            "topK": config.top_k,
            "minSupport": config.min_support,
            "similarity": "cosine",
            "ratingMode": "raw_explicit_ratings",
        },
        "counts": counts,
    }

    artifacts.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def file_size_mb(path: Path) -> float:
    return round(path.stat().st_size / 1024 / 1024, 3)