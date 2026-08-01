"""Code-defined deployment profiles for persisted recommender artifacts."""

from dataclasses import dataclass

from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import BiasedMatrixFactorizationBuildConfig
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import ItemKnnCosineBuildConfig


class UnsupportedBuildProfileError(ValueError):
    pass


@dataclass(frozen=True)
class ItemKnnVariantProfile:
    variant_id: str
    label: str
    top_k: int
    min_support: int
    chunk_size: int
    recommended: bool = False

    def build_config(self, *, overwrite: bool) -> ItemKnnCosineBuildConfig:
        config = ItemKnnCosineBuildConfig(self.top_k, self.min_support, self.chunk_size, overwrite)
        if config.variant_id != self.variant_id:
            raise RuntimeError(f"Item KNN profile ID does not match its configuration: {self.variant_id}")
        return config


@dataclass(frozen=True)
class BiasedMatrixFactorizationVariantProfile:
    variant_id: str
    label: str
    factor_count: int
    epochs: int
    learning_rate: float
    regularization: float
    validation_ratio: float = 0.1
    random_seed: int = 42
    chunksize: int = 500_000
    init_std: float = 0.05
    early_stopping_patience: int | None = None
    min_validation_improvement: float = 0.0

    def build_config(self, *, overwrite: bool) -> BiasedMatrixFactorizationBuildConfig:
        config = BiasedMatrixFactorizationBuildConfig(
            self.factor_count, self.epochs, self.learning_rate, self.regularization,
            self.validation_ratio, self.random_seed, overwrite, self.chunksize,
            self.init_std, early_stopping_patience=self.early_stopping_patience,
            min_validation_improvement=self.min_validation_improvement,
        )
        if config.variant_id != self.variant_id:
            raise RuntimeError(f"BMF profile ID does not match its configuration: {self.variant_id}")
        return config


ITEM_KNN_VARIANT_PROFILES = (
    ItemKnnVariantProfile("top_k_100_min_support_25", "Recommended Item KNN (100 neighbors)", 100, 25, 256, True),
    ItemKnnVariantProfile("top_k_50_min_support_25", "Compact Item KNN (50 neighbors)", 50, 25, 256),
)
BIASED_MATRIX_FACTORIZATION_VARIANT_PROFILES = (
    BiasedMatrixFactorizationVariantProfile("factors_128_epochs_100_lr_0_005_reg_0_02", "Production BMF (128 factors)", 128, 100, 0.005, 0.02),
)
DEFAULT_ITEM_KNN_VARIANT_ID = next(profile.variant_id for profile in ITEM_KNN_VARIANT_PROFILES if profile.recommended)
DEFAULT_BIASED_MATRIX_FACTORIZATION_VARIANT_ID = BIASED_MATRIX_FACTORIZATION_VARIANT_PROFILES[0].variant_id


def get_supported_item_knn_profiles() -> tuple[ItemKnnVariantProfile, ...]:
    return ITEM_KNN_VARIANT_PROFILES


def get_supported_biased_matrix_factorization_profiles() -> tuple[BiasedMatrixFactorizationVariantProfile, ...]:
    return BIASED_MATRIX_FACTORIZATION_VARIANT_PROFILES


def get_item_knn_variant_profile(variant_id: str) -> ItemKnnVariantProfile:
    for profile in ITEM_KNN_VARIANT_PROFILES:
        if profile.variant_id == variant_id:
            return profile
    raise UnsupportedBuildProfileError(f"Unsupported active Item KNN variant: {variant_id}. Supported variants: {', '.join(p.variant_id for p in ITEM_KNN_VARIANT_PROFILES)}")


def get_biased_matrix_factorization_variant_profile(variant_id: str) -> BiasedMatrixFactorizationVariantProfile:
    for profile in BIASED_MATRIX_FACTORIZATION_VARIANT_PROFILES:
        if profile.variant_id == variant_id:
            return profile
    raise UnsupportedBuildProfileError(f"Unsupported active BMF variant: {variant_id}. Supported variants: {', '.join(p.variant_id for p in BIASED_MATRIX_FACTORIZATION_VARIANT_PROFILES)}")
