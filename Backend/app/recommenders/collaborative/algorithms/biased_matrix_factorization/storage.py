import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.project_paths.dataset_paths import COLLABORATIVE_RECOMMENDER_MODELS_DIR
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    MODEL_VERSION,
    BiasedMatrixFactorizationArtifacts,
    BiasedMatrixFactorizationBuildConfig,
)


RUNTIME_REQUIRED_GLOBAL_STATS_KEYS = (
    "globalMean",
    "ratingMin",
    "ratingMax",
)


def get_biased_matrix_factorization_variant_artifacts(
    variant_id: str,
    artifact_root: Path | None = None,
) -> BiasedMatrixFactorizationArtifacts:
    resolved_artifact_root = artifact_root or COLLABORATIVE_RECOMMENDER_MODELS_DIR
    variant_dir = resolved_artifact_root / ALGORITHM_ID / variant_id
    return BiasedMatrixFactorizationArtifacts(
        variant_dir=variant_dir,
        movie_factors_path=variant_dir / "movie_factors.npy",
        movie_biases_path=variant_dir / "movie_biases.csv",
        movie_index_path=variant_dir / "movie_index.csv",
        global_stats_path=variant_dir / "global_stats.json",
        training_metrics_path=variant_dir / "training_metrics.json",
        manifest_path=variant_dir / "model_manifest.json",
        user_factors_path=variant_dir / "user_factors.npy",
        user_biases_path=variant_dir / "user_biases.csv",
        user_index_path=variant_dir / "user_index.csv",
    )


def prepare_biased_matrix_factorization_artifacts(
    config: BiasedMatrixFactorizationBuildConfig,
    artifact_root: Path | None = None,
) -> BiasedMatrixFactorizationArtifacts:
    artifacts = get_biased_matrix_factorization_variant_artifacts(
        config.variant_id,
        artifact_root=artifact_root,
    )

    if artifacts.variant_dir.exists():
        if not config.overwrite:
            raise RuntimeError(
                f"Biased Matrix Factorization variant already exists: {artifacts.variant_dir}. "
                "Use --overwrite to rebuild it."
            )

        shutil.rmtree(artifacts.variant_dir)

    artifacts.variant_dir.mkdir(parents=True, exist_ok=False)
    return artifacts


def load_biased_matrix_factorization_manifest(
    variant_id: str,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    artifacts = get_biased_matrix_factorization_variant_artifacts(
        variant_id,
        artifact_root=artifact_root,
    )

    if not artifacts.manifest_path.exists():
        raise RuntimeError(
            "Biased Matrix Factorization manifest is missing for variant "
            f"{variant_id}: {artifacts.manifest_path}"
        )

    return json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))


def write_model_manifest(
    *,
    artifacts: BiasedMatrixFactorizationArtifacts,
    config: BiasedMatrixFactorizationBuildConfig,
    status: str,
    runtime_status: str,
    runtime_status_reason: str | None,
    counts: dict[str, Any],
    training_metrics: dict[str, Any],
) -> None:
    manifest = {
        "algorithmId": ALGORITHM_ID,
        "algorithmLabel": ALGORITHM_LABEL,
        "modelVersion": MODEL_VERSION,
        "variantId": config.variant_id,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "runtimeStatus": runtime_status,
        "runtimeStatusReason": runtime_status_reason,
        "config": {
            "factorCount": config.factor_count,
            "epochs": config.epochs,
            "learningRate": config.learning_rate,
            "regularization": config.regularization,
            "validationRatio": config.validation_ratio,
            "randomSeed": config.random_seed,
            "chunksize": config.chunksize,
            "initStd": config.init_std,
            "minRating": config.min_rating,
            "maxRating": config.max_rating,
            "earlyStoppingPatience": config.early_stopping_patience,
            "minValidationImprovement": config.min_validation_improvement,
        },
        "artifacts": {
            "movieFactors": artifacts.movie_factors_path.name,
            "movieBiases": artifacts.movie_biases_path.name,
            "movieIndex": artifacts.movie_index_path.name,
            "globalStats": artifacts.global_stats_path.name,
            "trainingMetrics": artifacts.training_metrics_path.name,
            "userFactors": artifacts.user_factors_path.name,
            "userBiases": artifacts.user_biases_path.name,
            "userIndex": artifacts.user_index_path.name,
        },
        "runtimeDesign": {
            "ratingMode": "raw_explicit_ratings",
            "predictionFormula": "global_mean_plus_user_bias_plus_movie_bias_plus_dot",
            "sessionAdaptation": "future_online_session_inference",
            "candidatePolicy": "public_movies_only_at_runtime",
        },
        "counts": counts,
        "trainingMetrics": training_metrics,
    }

    artifacts.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def file_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0

    return round(path.stat().st_size / 1024 / 1024, 3)


def resolve_biased_matrix_factorization_runtime_status(
    artifacts: BiasedMatrixFactorizationArtifacts,
) -> tuple[str, str | None]:
    try:
        validate_biased_matrix_factorization_runtime_artifacts(artifacts)
    except RuntimeError as exc:
        return "artifact_validation_failed", str(exc)

    return "ready", None


def validate_biased_matrix_factorization_runtime_artifacts(
    artifacts: BiasedMatrixFactorizationArtifacts,
) -> None:
    required_paths = [
        artifacts.movie_factors_path,
        artifacts.movie_biases_path,
        artifacts.movie_index_path,
        artifacts.global_stats_path,
        artifacts.training_metrics_path,
    ]

    for path in required_paths:
        if not path.exists():
            raise RuntimeError(
                "Missing required Biased Matrix Factorization runtime artifact: "
                f"{path}"
            )

    movie_factors = np.load(artifacts.movie_factors_path)
    movie_index_df = pd.read_csv(
        artifacts.movie_index_path,
        usecols=["movieId", "movieIndex"],
    ).sort_values("movieIndex")
    movie_biases_df = pd.read_csv(
        artifacts.movie_biases_path,
        usecols=["movieIndex", "movieBias"],
    ).sort_values("movieIndex")
    global_stats = json.loads(artifacts.global_stats_path.read_text(encoding="utf-8"))
    json.loads(artifacts.training_metrics_path.read_text(encoding="utf-8"))

    _validate_runtime_shapes(
        movie_factors=movie_factors,
        movie_index_df=movie_index_df,
        movie_biases_df=movie_biases_df,
    )

    missing_keys = [
        key
        for key in RUNTIME_REQUIRED_GLOBAL_STATS_KEYS
        if key not in global_stats
    ]
    if missing_keys:
        raise RuntimeError(
            "Biased Matrix Factorization global stats are missing required keys: "
            + ", ".join(missing_keys)
        )


def _validate_runtime_shapes(
    *,
    movie_factors: np.ndarray,
    movie_index_df: pd.DataFrame,
    movie_biases_df: pd.DataFrame,
) -> None:
    movie_count = len(movie_index_df)

    if movie_factors.ndim != 2:
        raise RuntimeError("movie_factors.npy must be a 2D array.")

    if movie_factors.shape[0] != movie_count:
        raise RuntimeError(
            "movie_factors.npy row count does not match movie_index.csv rows."
        )

    if len(movie_biases_df) != movie_count:
        raise RuntimeError(
            "movie_biases.csv row count does not match movie_index.csv rows."
        )

    expected_indices = np.arange(movie_count, dtype=np.int32)
    movie_indices = movie_index_df["movieIndex"].to_numpy(dtype=np.int32, copy=True)
    bias_indices = movie_biases_df["movieIndex"].to_numpy(dtype=np.int32, copy=True)

    if not np.array_equal(movie_indices, expected_indices):
        raise RuntimeError(
            "movie_index.csv must be contiguous from 0 to movie_count - 1."
        )

    if not np.array_equal(bias_indices, expected_indices):
        raise RuntimeError(
            "movie_biases.csv must be aligned to contiguous movieIndex values."
        )
