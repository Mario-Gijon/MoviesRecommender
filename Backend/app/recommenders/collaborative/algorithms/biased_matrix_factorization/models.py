from dataclasses import dataclass
from pathlib import Path


ALGORITHM_ID = "biased_matrix_factorization"
ALGORITHM_LABEL = "Biased Matrix Factorization"
MODEL_VERSION = "1"


@dataclass(frozen=True)
class BiasedMatrixFactorizationBuildConfig:
    factor_count: int
    epochs: int
    learning_rate: float
    regularization: float
    validation_ratio: float
    random_seed: int
    overwrite: bool
    chunksize: int = 500_000
    init_std: float = 0.05
    min_rating: float = 0.5
    max_rating: float = 5.0
    early_stopping_patience: int | None = None
    min_validation_improvement: float = 0.0

    @property
    def variant_id(self) -> str:
        learning_rate = _format_float_token(self.learning_rate)
        regularization = _format_float_token(self.regularization)
        return (
            f"factors_{self.factor_count}"
            f"_epochs_{self.epochs}"
            f"_lr_{learning_rate}"
            f"_reg_{regularization}"
        )


@dataclass(frozen=True)
class BiasedMatrixFactorizationRuntimeConfig:
    variant_id: str
    session_inference_steps: int = 10
    session_learning_rate: float = 0.01
    session_regularization: float = 0.05
    min_prediction_score: float = 3.0


@dataclass(frozen=True)
class BiasedMatrixFactorizationArtifacts:
    variant_dir: Path
    movie_factors_path: Path
    movie_biases_path: Path
    movie_index_path: Path
    global_stats_path: Path
    training_metrics_path: Path
    manifest_path: Path
    user_factors_path: Path
    user_biases_path: Path
    user_index_path: Path


def _format_float_token(value: float) -> str:
    token = f"{value:.12g}"
    return token.replace("-", "neg_").replace(".", "_")
