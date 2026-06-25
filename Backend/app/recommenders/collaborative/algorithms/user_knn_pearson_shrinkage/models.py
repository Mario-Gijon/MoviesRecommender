from dataclasses import dataclass
from pathlib import Path


ALGORITHM_ID = "user_knn_pearson_shrinkage"
ALGORITHM_LABEL = "UserKNN Pearson Shrinkage"
MODEL_VERSION = "1"
VARIANT_ID = "default"


@dataclass(frozen=True)
class UserKnnPearsonShrinkageBuildConfig:
    overwrite: bool
    chunksize: int = 500_000


@dataclass(frozen=True)
class UserKnnPearsonShrinkageRuntimeConfig:
    variant_id: str = "neighbors_100_min_overlap_2_shrinkage_25_candidate_min_2_candidate_shrinkage_5"
    top_neighbors: int = 100
    min_overlap: int = 2
    shrinkage: float = 25.0
    active_rating_center: float = 3.0
    min_candidate_neighbor_count: int = 2
    candidate_shrinkage: float = 5.0
    min_prediction_score: float = 3.0


@dataclass(frozen=True)
class UserKnnPearsonShrinkageArtifacts:
    variant_dir: Path
    ratings_sqlite_path: Path
    user_stats_csv_path: Path
    manifest_path: Path