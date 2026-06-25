import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.project_paths.dataset_paths import COLLABORATIVE_RECOMMENDER_MODELS_DIR
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    ALGORITHM_ID,
    ALGORITHM_LABEL,
    MODEL_VERSION,
    BiasedMatrixFactorizationArtifacts,
    BiasedMatrixFactorizationBuildConfig,
)


def get_biased_matrix_factorization_variant_artifacts(
    variant_id: str,
) -> BiasedMatrixFactorizationArtifacts:
    variant_dir = COLLABORATIVE_RECOMMENDER_MODELS_DIR / ALGORITHM_ID / variant_id
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
) -> BiasedMatrixFactorizationArtifacts:
    artifacts = get_biased_matrix_factorization_variant_artifacts(config.variant_id)

    if artifacts.variant_dir.exists():
        if not config.overwrite:
            raise RuntimeError(
                f"Biased Matrix Factorization variant already exists: {artifacts.variant_dir}. "
                "Use --overwrite to rebuild it."
            )

        shutil.rmtree(artifacts.variant_dir)

    artifacts.variant_dir.mkdir(parents=True, exist_ok=False)
    return artifacts


def load_biased_matrix_factorization_manifest(variant_id: str) -> dict[str, Any]:
    artifacts = get_biased_matrix_factorization_variant_artifacts(variant_id)

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
        "config": {
            "factorCount": config.factor_count,
            "epochs": config.epochs,
            "learningRate": config.learning_rate,
            "regularization": config.regularization,
            "validationRatio": config.validation_ratio,
            "randomSeed": config.random_seed,
            "chunksize": config.chunksize,
            "batchSize": config.batch_size,
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
