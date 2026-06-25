from app.core.config import settings
from app.recommenders.collaborative.algorithms.item_knn_cosine.recommender import (
    ItemKnnCosineRecommender,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.recommender import (
    PopularityBaselineRecommender,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.recommender import (
    UserKnnPearsonShrinkageRecommender,
)
from app.recommenders.collaborative.common.base import CollaborativeRecommender
from app.recommenders.collaborative.common.errors import (
    CollaborativeAlgorithmNotAvailableError,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    BiasedMatrixFactorizationRuntimeConfig,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.recommender import (
    BiasedMatrixFactorizationRecommender,
)


COLLABORATIVE_RECOMMENDER_REGISTRY: dict[str, CollaborativeRecommender] = {
    PopularityBaselineRecommender.algorithm_id: PopularityBaselineRecommender(),
    ItemKnnCosineRecommender.algorithm_id: ItemKnnCosineRecommender(
        model_variant_id=settings.active_collaborative_model_variant,
    ),
    UserKnnPearsonShrinkageRecommender.algorithm_id: UserKnnPearsonShrinkageRecommender(),
    BiasedMatrixFactorizationRecommender.algorithm_id: BiasedMatrixFactorizationRecommender(
        runtime_config=BiasedMatrixFactorizationRuntimeConfig(
            variant_id=settings.biased_matrix_factorization_model_variant,
        ),
    ),
}


def get_collaborative_recommender(algorithm_id: str) -> CollaborativeRecommender:
    recommender = COLLABORATIVE_RECOMMENDER_REGISTRY.get(algorithm_id)
    if recommender is None:
        raise CollaborativeAlgorithmNotAvailableError(
            code="collaborative_algorithm_not_available",
            message=f"Collaborative recommender algorithm is not available: {algorithm_id}",
        )
    return recommender