from dataclasses import dataclass
from pathlib import Path

from app.project_paths.dataset_paths import (
    COLLABORATIVE_RECOMMENDER_MODELS_DIR,
    OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
    OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH,
    OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
    RECOMMENDER_AUDIT_DIR,
)


@dataclass(frozen=True)
class CollaborativeDatasetPaths:
    ratings_csv_path: Path
    public_movies_csv_path: Path
    collaborative_support_movies_csv_path: Path


@dataclass(frozen=True)
class CollaborativeOfflineContext:
    dataset_paths: CollaborativeDatasetPaths
    collaborative_model_artifact_root: Path
    audit_output_root: Path
    candidate_universe_name: str = "production_public_catalog"

    @property
    def ratings_csv_path(self) -> Path:
        return self.dataset_paths.ratings_csv_path

    @property
    def public_movies_csv_path(self) -> Path:
        return self.dataset_paths.public_movies_csv_path

    @property
    def collaborative_support_movies_csv_path(self) -> Path:
        return self.dataset_paths.collaborative_support_movies_csv_path


def get_default_collaborative_dataset_paths() -> CollaborativeDatasetPaths:
    return CollaborativeDatasetPaths(
        ratings_csv_path=OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
        public_movies_csv_path=OFFLINE_DATASET_PUBLIC_MOVIES_CSV_PATH,
        collaborative_support_movies_csv_path=(
            OFFLINE_DATASET_COLLABORATIVE_SUPPORT_MOVIES_CSV_PATH
        ),
    )


def get_default_collaborative_offline_context() -> CollaborativeOfflineContext:
    return CollaborativeOfflineContext(
        dataset_paths=get_default_collaborative_dataset_paths(),
        collaborative_model_artifact_root=COLLABORATIVE_RECOMMENDER_MODELS_DIR,
        audit_output_root=RECOMMENDER_AUDIT_DIR,
    )
