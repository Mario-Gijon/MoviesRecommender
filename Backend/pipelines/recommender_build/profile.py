from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import BiasedMatrixFactorizationBuildConfig
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import ItemKnnCosineBuildConfig
from app.recommenders.collaborative.algorithms.popularity_baseline.models import PopularityBaselineBuildConfig
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import UserKnnPearsonShrinkageBuildConfig


def popularity_config() -> PopularityBaselineBuildConfig:
    return PopularityBaselineBuildConfig(overwrite=True)


def item_knn_config() -> ItemKnnCosineBuildConfig:
    return ItemKnnCosineBuildConfig(top_k=50, min_support=25, chunk_size=256, overwrite=True)


def user_knn_config() -> UserKnnPearsonShrinkageBuildConfig:
    return UserKnnPearsonShrinkageBuildConfig(overwrite=True, chunksize=500_000)


def biased_config() -> BiasedMatrixFactorizationBuildConfig:
    return BiasedMatrixFactorizationBuildConfig(
        factor_count=128, epochs=100, learning_rate=0.005, regularization=0.02,
        validation_ratio=0.1, random_seed=42, overwrite=True, chunksize=500_000,
        init_std=0.05, early_stopping_patience=None, min_validation_improvement=0.0,
    )


ITEM_KNN_VARIANT_ID = item_knn_config().variant_id
BIASED_VARIANT_ID = biased_config().variant_id
