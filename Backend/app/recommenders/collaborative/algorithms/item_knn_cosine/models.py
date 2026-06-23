from dataclasses import dataclass
from pathlib import Path


ALGORITHM_ID = "item_knn_cosine"
ALGORITHM_LABEL = "ItemKNN Cosine"
MODEL_VERSION = "1"


@dataclass(frozen=True)
class ItemKnnCosineBuildConfig:
    top_k: int
    min_support: int
    chunk_size: int
    overwrite: bool

    @property
    def variant_id(self) -> str:
        return f"top_k_{self.top_k}_min_support_{self.min_support}"


@dataclass(frozen=True)
class ItemNeighbor:
    source_movie_id: int
    neighbor_movie_id: int
    similarity: float
    support: int
    rank: int


@dataclass(frozen=True)
class ItemKnnCosineArtifacts:
    variant_dir: Path
    neighbors_csv_path: Path
    neighbors_sqlite_path: Path
    manifest_path: Path