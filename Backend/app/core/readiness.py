from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.project_paths.dataset_paths import (
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
    OFFLINE_DATASET_MANIFEST_PATH,
    OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH,
    OFFLINE_DATASET_POSTERS_DIR,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import (
    get_biased_matrix_factorization_variant_artifacts,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.storage import (
    get_item_knn_cosine_variant_artifacts,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.storage import (
    get_popularity_baseline_artifacts,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.storage import (
    get_user_knn_pearson_shrinkage_artifacts,
)
from app.recommenders.content_based.constants import CONTENT_INDEX_REQUIRED_PATHS


@dataclass(frozen=True)
class RuntimeReadiness:
    missing: tuple[str, ...]

    @property
    def is_ready(self) -> bool:
        return not self.missing


def check_runtime_readiness() -> RuntimeReadiness:
    required_paths = {
        "offline_dataset.manifest": OFFLINE_DATASET_MANIFEST_PATH,
        "offline_dataset.public_movies": OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        "offline_dataset.collaborative_support_movies": (
            OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH
        ),
        "offline_dataset.excluded_movies": OFFLINE_DATASET_EXCLUDED_MOVIES_CSV_PATH,
        "offline_dataset.movie_ratings_summary": (
            OFFLINE_DATASET_MOVIE_RATINGS_SUMMARY_CSV_PATH
        ),
        "offline_dataset.collaborative_ratings": (
            OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH
        ),
        "offline_dataset.posters": OFFLINE_DATASET_POSTERS_DIR,
    }
    required_paths.update(
        {
            f"content.tfidf.{name}": path
            for name, path in CONTENT_INDEX_REQUIRED_PATHS.items()
        }
    )
    required_paths.update(_collaborative_required_paths())
    return RuntimeReadiness(
        missing=tuple(
            name for name, path in required_paths.items() if not _path_is_available(path)
        )
    )


def _collaborative_required_paths() -> dict[str, Path]:
    popularity = get_popularity_baseline_artifacts()
    item_knn = get_item_knn_cosine_variant_artifacts(
        settings.active_collaborative_model_variant
    )
    user_knn = get_user_knn_pearson_shrinkage_artifacts()
    biased = get_biased_matrix_factorization_variant_artifacts(
        settings.biased_matrix_factorization_model_variant
    )
    return {
        "collaborative.popularity.manifest": popularity.manifest_path,
        "collaborative.popularity.ranking": popularity.ranking_sqlite_path,
        "collaborative.item_knn.manifest": item_knn.manifest_path,
        "collaborative.item_knn.neighbors": item_knn.neighbors_sqlite_path,
        "collaborative.user_knn.manifest": user_knn.manifest_path,
        "collaborative.user_knn.ratings": user_knn.ratings_sqlite_path,
        "collaborative.biased.manifest": biased.manifest_path,
        "collaborative.biased.movie_factors": biased.movie_factors_path,
        "collaborative.biased.movie_biases": biased.movie_biases_path,
        "collaborative.biased.movie_index": biased.movie_index_path,
        "collaborative.biased.global_stats": biased.global_stats_path,
        "collaborative.biased.training_metrics": biased.training_metrics_path,
    }


def _path_is_available(path: Path) -> bool:
    return path.is_dir() if path.suffix == "" else path.is_file()
