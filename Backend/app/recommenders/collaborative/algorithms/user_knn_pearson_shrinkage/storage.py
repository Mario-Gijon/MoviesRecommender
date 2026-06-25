import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.project_paths.dataset_paths import COLLABORATIVE_RECOMMENDER_MODELS_DIR
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    MODEL_VERSION,
    VARIANT_ID,
    UserKnnPearsonShrinkageArtifacts,
    UserKnnPearsonShrinkageBuildConfig,
)


def get_user_knn_pearson_shrinkage_artifacts() -> UserKnnPearsonShrinkageArtifacts:
    variant_dir = COLLABORATIVE_RECOMMENDER_MODELS_DIR / ALGORITHM_ID / VARIANT_ID

    return UserKnnPearsonShrinkageArtifacts(
        variant_dir=variant_dir,
        ratings_sqlite_path=variant_dir / "ratings.sqlite",
        user_stats_csv_path=variant_dir / "user_stats.csv",
        manifest_path=variant_dir / "model_manifest.json",
    )


def prepare_user_knn_pearson_shrinkage_artifacts(
    config: UserKnnPearsonShrinkageBuildConfig,
) -> UserKnnPearsonShrinkageArtifacts:
    artifacts = get_user_knn_pearson_shrinkage_artifacts()

    if artifacts.variant_dir.exists():
        if not config.overwrite:
            raise RuntimeError(
                f"UserKNN Pearson Shrinkage artifact already exists: {artifacts.variant_dir}. "
                "Use --overwrite to rebuild it."
            )

        shutil.rmtree(artifacts.variant_dir)

    artifacts.variant_dir.mkdir(parents=True, exist_ok=False)
    return artifacts


def load_user_knn_pearson_shrinkage_manifest() -> dict[str, Any]:
    artifacts = get_user_knn_pearson_shrinkage_artifacts()

    if not artifacts.manifest_path.exists():
        raise RuntimeError(
            "UserKNN Pearson Shrinkage manifest is missing: "
            f"{artifacts.manifest_path}"
        )

    return json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))


def write_model_manifest(
    *,
    artifacts: UserKnnPearsonShrinkageArtifacts,
    counts: dict[str, Any],
) -> None:
    manifest = {
        "algorithmId": ALGORITHM_ID,
        "algorithmLabel": ALGORITHM_LABEL,
        "modelVersion": MODEL_VERSION,
        "variantId": VARIANT_ID,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "ratingsSqlite": "ratings.sqlite",
            "userStatsCsv": "user_stats.csv",
        },
        "runtimeDesign": {
            "neighborSearch": "on_demand_user_neighbors",
            "candidatePolicy": "public_movies_only",
            "similarity": "mean_centered_pearson_with_shrinkage",
            "ratingSource": "collaborative_ratings",
        },
        "counts": counts,
    }

    artifacts.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def file_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0

    return round(path.stat().st_size / 1024 / 1024, 3)