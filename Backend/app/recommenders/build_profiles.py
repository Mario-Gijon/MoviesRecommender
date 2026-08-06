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
        config = ItemKnnCosineBuildConfig(top_k=self.top_k, min_support=self.min_support, chunk_size=self.chunk_size, overwrite=overwrite)
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
            factor_count=self.factor_count, epochs=self.epochs, learning_rate=self.learning_rate, regularization=self.regularization,
            validation_ratio=self.validation_ratio, random_seed=self.random_seed, overwrite=overwrite, chunksize=self.chunksize,
            init_std=self.init_std, early_stopping_patience=self.early_stopping_patience,
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
def validate_profile_catalogues(
    item_profiles: tuple[ItemKnnVariantProfile, ...] = ITEM_KNN_VARIANT_PROFILES,
    bmf_profiles: tuple[BiasedMatrixFactorizationVariantProfile, ...] = BIASED_MATRIX_FACTORIZATION_VARIANT_PROFILES,
) -> tuple[str, str]:
    if len({profile.variant_id for profile in item_profiles}) != len(item_profiles):
        raise RuntimeError("Item KNN profile IDs must be unique.")
    if len({profile.variant_id for profile in bmf_profiles}) != len(bmf_profiles):
        raise RuntimeError("BMF profile IDs must be unique.")
    recommended = [profile for profile in item_profiles if profile.recommended]
    if len(recommended) != 1:
        raise RuntimeError("Exactly one Item KNN profile must be recommended.")
    if not bmf_profiles:
        raise RuntimeError("Exactly one default BMF profile must be registered.")
    for profile in item_profiles:
        if profile.build_config(overwrite=True).variant_id != profile.variant_id:
            raise RuntimeError("Item KNN profile ID does not match its configuration.")
    for profile in bmf_profiles:
        if profile.build_config(overwrite=True).variant_id != profile.variant_id:
            raise RuntimeError("BMF profile ID does not match its configuration.")
    return recommended[0].variant_id, bmf_profiles[0].variant_id


DEFAULT_ITEM_KNN_VARIANT_ID, DEFAULT_BIASED_MATRIX_FACTORIZATION_VARIANT_ID = validate_profile_catalogues()


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
