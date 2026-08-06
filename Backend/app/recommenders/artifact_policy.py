"""Runtime artifact requirements for persisted recommender models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecommenderArtifactPolicy:
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()


ARTIFACT_POLICIES: dict[str, RecommenderArtifactPolicy] = {
    "tfidf": RecommenderArtifactPolicy(
        required=(
            "movie_content_features.npz",
            "movie_content_index.json",
            "content_feature_names.json",
            "content_feature_metadata.json",
        ),
        optional=("content_index_summary.json",),
    ),
    "popularity": RecommenderArtifactPolicy(
        required=("model_manifest.json", "ranking.sqlite"),
        optional=("ranking.csv",),
    ),
    "item_knn": RecommenderArtifactPolicy(
        required=("model_manifest.json", "neighbors.sqlite"),
        optional=("neighbors.csv",),
    ),
    "user_knn": RecommenderArtifactPolicy(
        required=("model_manifest.json", "ratings.sqlite"),
        optional=("user_stats.csv",),
    ),
    "biased": RecommenderArtifactPolicy(
        required=(
            "model_manifest.json",
            "movie_factors.npy",
            "movie_biases.csv",
            "movie_index.csv",
            "global_stats.json",
            "training_metrics.json",
        ),
        optional=("user_factors.npy", "user_biases.csv", "user_index.csv"),
    ),
}


def get_artifact_policy(algorithm: str) -> RecommenderArtifactPolicy:
    try:
        return ARTIFACT_POLICIES[algorithm]
    except KeyError as exc:
        raise ValueError(f"Unsupported recommender algorithm: {algorithm}") from exc


def required_artifacts(algorithm: str) -> tuple[str, ...]:
    return get_artifact_policy(algorithm).required


def optional_artifacts(algorithm: str) -> tuple[str, ...]:
    return get_artifact_policy(algorithm).optional


def validate_runtime_artifacts(algorithm: str, target_dir: Path) -> None:
    """Ensure the target has every file required by its runtime loader."""
    missing = [
        name
        for name in required_artifacts(algorithm)
        if not (target_dir / name).is_file() or (target_dir / name).stat().st_size == 0
    ]
    if missing:
        raise RuntimeError(
            f"{algorithm} runtime artifacts are missing, empty, or not regular files: "
            + ", ".join(missing)
        )


def remove_optional_artifacts(algorithm: str, target_dir: Path) -> tuple[str, ...]:
    """Remove only explicitly optional build outputs from a staged target."""
    removed: list[str] = []
    for name in optional_artifacts(algorithm):
        path = target_dir / name
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                raise RuntimeError(f"Optional artifact is unexpectedly a directory: {path}")
            path.unlink()
            removed.append(name)
    return tuple(removed)
