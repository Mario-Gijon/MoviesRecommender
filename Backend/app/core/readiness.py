from __future__ import annotations

from dataclasses import dataclass

from app.domain.recommendations.content_based.constants import (
    CONTENT_INDEX_REQUIRED_PATHS,
)
from app.infrastructure.datasets.movielens_paths import (
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
    OFFLINE_DATASET_POSTERS_DIR,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
    RECOMMENDER_MODELS_DIR,
)


@dataclass(frozen=True)
class RuntimeReadiness:
    missing: tuple[str, ...]

    @property
    def is_ready(self) -> bool:
        return not self.missing


def check_runtime_readiness() -> RuntimeReadiness:
    required_paths = {
        "offline dataset manifest": OFFLINE_DATASET_MANIFEST_PATH,
        "public movies CSV": OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        "collaborative support movies CSV": (
            OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH
        ),
        "excluded movies CSV": OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
        "movie ratings summary CSV": OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
        "collaborative ratings CSV": OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
        "offline poster directory": OFFLINE_DATASET_POSTERS_DIR,
        "recommender model directory": RECOMMENDER_MODELS_DIR,
    }
    required_paths.update(
        {
            f"content index {name}": path
            for name, path in CONTENT_INDEX_REQUIRED_PATHS.items()
        }
    )

    missing = [
        label
        for label, path in required_paths.items()
        if not path.exists()
    ]
    for algorithm in (
        "item_knn_cosine",
        "popularity_baseline",
        "user_knn_pearson_shrinkage",
        "biased_matrix_factorization",
    ):
        manifest_paths = list(
            (RECOMMENDER_MODELS_DIR / "collaborative" / algorithm).glob(
                "*/model_manifest.json"
            )
        )
        if not manifest_paths:
            missing.append(f"{algorithm} recommender artifact")

    return RuntimeReadiness(missing=tuple(missing))
