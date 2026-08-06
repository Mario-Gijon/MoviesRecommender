"""Maintenance adapters for the application deployment-profile catalogue."""

from app.recommenders.build_profiles import (
    get_biased_matrix_factorization_variant_profile,
    get_item_knn_variant_profile,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.models import PopularityBaselineBuildConfig
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import UserKnnPearsonShrinkageBuildConfig


def popularity_config() -> PopularityBaselineBuildConfig:
    return PopularityBaselineBuildConfig(overwrite=True)


def user_knn_config() -> UserKnnPearsonShrinkageBuildConfig:
    return UserKnnPearsonShrinkageBuildConfig(overwrite=True, chunksize=500_000)


def item_knn_config(variant_id: str):
    return get_item_knn_variant_profile(variant_id).build_config(overwrite=True)


def biased_config(variant_id: str):
    return get_biased_matrix_factorization_variant_profile(variant_id).build_config(overwrite=True)
