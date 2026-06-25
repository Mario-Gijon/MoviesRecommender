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
class UserKnnPearsonShrinkageArtifacts:
    variant_dir: Path
    ratings_sqlite_path: Path
    user_stats_csv_path: Path
    manifest_path: Path