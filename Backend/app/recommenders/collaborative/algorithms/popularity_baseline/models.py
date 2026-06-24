from dataclasses import dataclass
from pathlib import Path


ALGORITHM_ID = "popularity_baseline"
ALGORITHM_LABEL = "Popularity baseline"
MODEL_VERSION = "1"
VARIANT_ID = "default"


@dataclass(frozen=True)
class PopularityBaselineBuildConfig:
    overwrite: bool


@dataclass(frozen=True)
class PopularityRankingEntry:
    rank: int
    movie_id: int
    score: float
    average_rating: float
    rating_count: int
    stand_display_score: float


@dataclass(frozen=True)
class PopularityBaselineArtifacts:
    variant_dir: Path
    ranking_csv_path: Path
    ranking_sqlite_path: Path
    manifest_path: Path